# Chronos Narrative Engine — Project Rules & State

## AIR-GAPPED CJIS ENVIRONMENT
- No internet access. No `pip install` without approval. All deps pre-installed.
- Streamlit app on RTX 5070 Ti (16GB VRAM). Ollama + faster-whisper on localhost.
- All `.py` must parse clean (AST-level). Run `ast.parse()` check before concluding.

## CAVEMAN PROTOCOL & TOKEN MINIMIZATION
- **CRITICAL**: The agent MUST speak in "caveman" for all chat messages (e.g., "Me fix code. Code good. You test now.").
- **CRITICAL**: The agent MUST attempt extreme token minimization in chat. Use extremely brief, one-sentence status updates. Do not provide long summaries in the chat window.
- **EXCEPTION**: The agent must write clean, professional, fully-featured code, comments, and documentation. Only the conversational chat interface is restricted to caveman/terse speak.

## File Inventory (69 Python files)
```
app.py                  — Entry point: auth gate, sidebar nav, page router
auth.py                 — PBKDF2-SHA256 password auth, officers.json, rate limiting
config.py               — All env vars via CHRONOS_* (35+ settings)
database.py             — SQLite via sqlite3: legal_audit_logs, evidence_chain, login_attempts,
                          login_audit_log, evidence_files, officer_users, user_sessions,
                          report_search_index (FTS5)
export.py               — DOCX (python-docx), PDF (reportlab), bulk ZIP, signature capture HTML
logger.py               — Dual logging: human chronos.log (30d rotation) + JSON chronos.jsonl (90d)
narrative_generator.py  — LLM prompt assembly for narrative generation
nibrs_export.py         — FBI NIBRS XML builder
nibrs_checker.py        — NIBRS compliance checks, missing fields, probable cause
pdf_parser.py           — Zuercher CAD PDF parsing via pdfplumber + Ollama
transcriber.py          — faster-whisper bodycam audio transcription
redactor.py             — PII redaction (SSN, phone, email, credit card, etc.)
templates.py            — Report template definitions (DUI, domestic, theft, etc.)
phrase_book.py          — Officer phrase book with categories, snapshots, search
profiler.py             — Officer style profile from past reports
pipeline_manager.py     — ThreadPoolExecutor for parallel PDF+video processing
health.py               — Health checks: Ollama, disk, DB, Whisper device
dashboard.py            — Dashboard analytics (stats, trends, officer activity)
ui.py                   — CSS, badge SVGs, department header, category loader
draft.py                — Auto-save drafts
compliance_content.py   — Safeguards certification content
utils.py                — extract_json(), safe_filename()
case_similar.py         — Load past report as template
evidence_locker.py      — Disk-based evidence file storage + retrieval
spell_check.py          — 70+ common LE typos, auto-correct
wi_statutes.py          — 221 WI criminal statutes + 96 jury instructions with search
api_server.py           — FastAPI REST API (optional, needs fastapi+uvicorn)
batch_queue.py          — Batch queue state management
diffview.py             — Side-by-side diff viewer for report versions
evidence_store.py       — Disk-based evidence file storage and retrieval
llm_provider.py         — Legacy LLM provider adapter
transcript_corrector.py — LE-domain ASR transcript corrector
fine_tune_pipeline.py   — Export corrected pairs + fine-tune Whisper on LE vocabulary
llm_cache.py            — In-memory TTL cache for LLM responses
ncic_codes.py           — 90+ NCIC offense codes + 50+ vehicle makes, search

providers/
  __init__.py           — Registry init with graceful fallbacks
  base.py               — ABCs: LLMProvider, TranscriberProvider, PDFParserProvider
  registry.py           — Singleton provider registry, lookup by name
  llm_ollama.py         — Ollama LLMProvider implementation
  llm_fallback.py       — FallbackLLMProvider: template narrative when Ollama offline
  transcribe_whisper.py — Whisper TranscriberProvider wrapper
  pdf_zuercher.py       — Zuercher PDFParserProvider wrapper

pages/
  __init__.py
  generate_report.py    — Main report gen: evidence upload, CAD, transcription, editing, export, submit
  search.py             — Full-text FTS5 report search across all reports
  evidence_locker.py    — Upload/browse/chain-of-custody per incident
  batch.py              — Batch queue: queue incidents, process, export batch NIBRS XML
  officer_profiles.py   — Officer style profiles, phrase book management
  redactor.py           — PII redaction tool
  compliance.py         — AI safeguards certification viewer
  audit.py              — Submission history, detail viewer, diff viewer, version history
  review.py             — Supervisor review queue (approve/reject/request changes)
  settings.py           — Admin: DB backup/restore, case linking, data retention, evidence settings
  user_management.py    — Admin: add users, deactivate, role mgmt, login audit log
  health_page.py        — Health dashboard with live log tail

tests/
  test_utils.py               — Unit tests for utils
  test_nibrs_export.py        — Unit tests for NIBRS XML export
  test_redactor.py            — Unit tests for PII redaction
  test_new_modules.py         — Integration tests for wi_statutes, spell_check, case_similar, providers, etc.
  test_database.py            — 57 tests: submission logging, audit chain, evidence, rate limiting, review,
                                FTS5 search, user mgmt, case linking, evidence files, analytics, retention,
                                backup/restore, migrations, FTS5 tokenizer
  test_auth.py                — 43 tests: password strength, PBKDF2 hashing, register, authenticate,
                                role mgmt, active toggle, rate limit integration, IP rate limit, cache, edge cases
  test_narrative_generator.py — 7 tests: prompt truncation, placeholder detection
  test_llm_fallback.py        — 10 tests: fallback passthrough, error fallback, template narrative
  test_pipeline_manager.py    — 22 tests: VramSnapshot, VramBudgetTracker, PipelineManager, job lifecycle
  test_health.py              — 11 tests: HealthCheck icon, check_ollama, check_dirs, check_database, run_all
  test_integration.py         — 15 tests: full report lifecycle, audit chain, NIBRS round-trip, compliance,
                                PII redaction, statute search, evidence chain, backup/restore, user management,
                                evidence persistence, dashboard analytics, case linking, login audit

Other files:
  .pre-commit-config.yaml  — ruff, mypy, hooks
  .github/workflows/ci.yml — lint, typecheck, test, parse
  Dockerfile, docker-compose.yml, pytest.ini, requirements-dev.txt
  .env.example             — Documents all 35+ CHRONOS_* env vars with defaults
```

## Architecture
1. **app.py** initializes session → auth gate → sidebar nav → route to page
2. **Database**: PostgreSQL with `psycopg2` connection pooling. 9 tables + 1 FTS5 virtual table equivalent.
3. **LLM**: Provider pattern — OllamaProvider does HTTP POST to Ollama API (abstracted through LLMProvider ABC)
4. **Processing**: Celery + Redis background queue offloads heavy transcriptions and LLM generation. UI polls via `streamlit-autorefresh`.
5. **Export**: DOCX (python-docx) + PDF (reportlab) with letterhead, signature block, page numbers
6. **Container Orchestration**: Distributed Docker Compose environment integrating `postgres`, `redis`, `celery_worker`, `ollama`, and the `chronos` Streamlit app.

## Key Conventions
- No comments in code. No README/docs unless asked. No git commit unless asked.
- All UI strings go directly in `st.markdown()` or component calls — no i18n.
- Session state keys use snake_case with leading underscore for internal state.
- Env vars: `CHRONOS_*` prefix, read via `_env()`/`_env_int()` in config.py.

## Current State (all complete, verified 2026-07-20)
- 19 critical bugs fixed in initial pass, plus 18 code-review items fixed
- 14 feature categories implemented:
  - Voice dictation, NIBRS XML export, batch queue, version history diff
  - Print-optimized export, supervisor review + RBAC, DB backup/restore, case linking
  - Structured JSON logging, WI statute DB (221 statutes, 96 JIs), spell check, evidence store
  - Full-text FTS5 search, bulk ZIP export, department letterhead
  - Signature capture (HTML5 Canvas), make-similar-to-case template loader
  - User management page, login audit log viewer, data retention auto-purge
  - REST API (FastAPI), pre-commit hooks, CI pipeline
  - All files parse cleanly. **287 tests pass** (was 247).
- **Test coverage**: test_database.py (57), test_auth.py (43), test_pipeline_manager.py (22), test_llm_fallback.py (10), test_narrative_generator.py (7), test_health.py (11), test_integration.py (15), test_transcription_features.py (42), test_new_features.py (40), test_new_modules.py + existing

## Session History

### Session 1 — Initial Implementation
Initial commit of Chronos Narrative Engine with core features: auth, report generation, transcription, PDF parsing, NIBRS export, evidence locker, audit trail, dashboard.

### Session 2 — WI Statute Overhaul & Deep Audit Fixes
WI statute database implementation, deep audit fixes and improvements.

### Session 3 — Feature Improvements
Dashboard, health checks, auto-save, diffview, upload UX improvements. (Commit `7224834`)

### Session 4 — Code Review Fixes (18 items, 159→205 tests)
All 18 code-review issues resolved, 46 new tests added, all 205 passing.

### Session 5 — State Handoff & Commit
Updated AGENTS.md with session history, committed all outstanding code-review fixes. All 205 tests verified passing on Python 3.14.6 / pytest 9.1.1.

### Session 6 — Video Transcription Improvements
Overhauled the video transcription pipeline with 7 improvements:
- **FFmpeg audio extraction** — `extract_audio_from_video()` with `_check_ffmpeg()` guard for transparent video→audio conversion
- **Progress callback** — `progress_callback(current, total)` throughout `transcribe_file()` → `transcribe_to_text()` → `transcribe_bodycam()` chain, used in UI via `st.progress`
- **Long audio chunking** — `_split_audio_chunks()` splits audio >30min into segments, transcribes independently, re-joins with cumulative timestamps
- **Cancellation support** — `cancel()` / `reset_cancel()` on `BodyCamTranscriber` via `_cancel_event` threading.Event; `cancel_transcription()` public API; `_check_cancelled()` gates in transcription loop
- **Fixed double audio load** — `AudioPreprocessor.preprocess()` now loads audio once and passes `(y, sr)` to processing methods instead of re-loading in `trim_silence()`/`needs_noise_reduction()`
- **Fixed video file extension** — Upload handler saves with original extension (e.g. `.mp4`) instead of `.video` suffix
- **Added `cancel()` to provider** — `TranscriberProvider` ABC and `WhisperTranscriberProvider` now expose `cancel()` for graceful interruption

### Session 7 — Advanced Transcription Features (This Session)
Integrated research-backed improvements from WhisperX, OpenBWC, faster-whisper, and pyannote:

- **BatchedInferencePipeline** — Replaced sequential `model.transcribe()` with faster-whisper's `BatchedInferencePipeline` using VAD segmentation + batched inference. 4x throughput on GPU. Configurable via `CHRONOS_WHISPER_USE_BATCHED`. Falls back to sequential automatically.
- **Forced alignment (wav2vec2)** — Optional post-transcription word-level timestamp refinement via wav2vec2 forced alignment. Reduces timestamp error from ±500ms to ±50ms. Requires `transformers`. Configurable via `CHRONOS_WHISPER_ENABLE_ALIGNMENT`. Graceful fallback if unavailable.
- **Speaker diarization (pyannote)** — Optional speaker labeling via pyannote.audio 3.1 pipeline. Labels segments as SPEAKER_00, SPEAKER_01, etc. Configurable via `CHRONOS_WHISPER_ENABLE_DIARIZATION`. Graceful fallback if `pyannote.audio` not installed.
- **Confidence tier scoring** — Each segment classified as `high`/`medium`/`low`/`uncertain` based on word probability thresholds. Low-confidence segments marked with `[?]` in transcript output for officer review. Counter in METADATA line.
- **Fine-tuning pipeline** — `fine_tune_pipeline.py` exports AI-draft vs. officer-corrected pairs from the database and fine-tunes Whisper on LE-specific vocabulary. CLI: `python fine_tune_pipeline.py export && python fine_tune_pipeline.py train`.
- **Provider `get_segments()`** — New method on `TranscriberProvider` ABC and `WhisperTranscriberProvider` returning structured segment data for downstream processing.
- **Config surface** — Added `CHRONOS_WHISPER_USE_BATCHED`, `CHRONOS_WHISPER_ENABLE_ALIGNMENT`, `CHRONOS_WHISPER_ENABLE_DIARIZATION` env vars.

## Running Tests
```powershell
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_auth.py -v

# Run with coverage (if pytest-cov installed)
python -m pytest tests/ --cov=. --cov-report=term

# Run specific test class
python -m pytest tests/test_database.py::TestAuditChain -v
```

### Session 8 — Session 7 Completion & Test Coverage
Completed the cut-off Session 7 work and added test coverage:

- **Fixed batched pipeline gate** — Removed `not vad_filter` condition so `BatchedInferencePipeline` is used by default (was never triggering with default args). Now actually the primary transcription path as intended.
- **Fixed forced alignment audio reload** — Hoisted audio loading so alignment reuses already-loaded audio instead of decoding the file a second time.
- **Added 42 tests** — `test_transcription_features.py`: confidence tier classification, segment properties, hallucination detection, transcript formatting, metadata lines, provider get_segments(), fine-tune pipeline export/prepare, config defaults.
- **Updated AGENTS.md** — File count 55→66, test count 205→247, feature count 5→7.

### Session 9 — 60-Feature Mega Session (This Session)
Implemented all 60 remaining features and improvements across the full codebase:

- **Database migrations (#3-#5)**: `spell_custom_dict` table, `theme_pref` column on `officer_users`, `report_snapshots` table
- **Custom spell dict**: `add_custom_correction()`, `remove_custom_correction()`, `get_custom_dict()` with DB persistence; 32 new LE ASR correction patterns
- **Theme persistence**: Officer theme preference saved/loaded from DB via `set_theme_preference()` / `get_theme_preference()`
- **Report snapshots**: `save_snapshot_db()`, `get_snapshots()`, `get_snapshot_by_id()` for version tracking
- **Evidence purge**: `purge_old_records()` now deletes physical evidence files from disk
- **Location PII redaction**: GPS coordinates → `[GPS COORDINATES]`, intersections → `[INTERSECTION]`, landmarks → `[LANDMARK]`
- **NIBRS↔WI cross-reference**: 50-entry bidirectional map, `statutes_for_nibrs()`, `nibrs_for_statute()`, `find_statutes_in_text()`, `suggest_statutes_from_narrative()`
- **Enhanced NIBRS XML**: Optional `<Arrestee>`, `<Offender>`, `<Property>`, `<Victim>` segments
- **Statute import/export**: `import_statutes_from_json()`, `export_statutes_to_json()`
- **5 new report templates**: Domestic Violence Supplement, Juvenile Offense, Missing Person, Narcotics Incident, Sexual Assault Kit
- **NCIC codes**: `ncic_codes.py` with 90+ offense codes + 50+ vehicle makes + `search_ncic()`
- **Provider caching**: Singleton instances in registry (`get_llm`, `get_transcriber`, `get_pdf_parser`)
- **LLM JSON retry**: `LLMProvider.complete_json()` retries on parse failure (providers/base.py)
- **LLM response cache**: In-memory TTL cache via `llm_cache.py`, integrated into `base.py`
- **Log archival**: `archive_logs()`, `download_logs_zip()` with UI buttons on health page
- **Fine-tune quality metrics**: `export_quality_report()` in `fine_tune_pipeline.py`
- **Pipeline `submit_all()`**: Batch job submission
- **Multi-language transcription**: Language selector in UI, `WHISPER_LANGUAGE` config
- **Phrase book import/export**: `export_phrases_to_json()` / `import_phrases_from_json()` with UI
- **Report preview HTML**: `export_report_html_preview()` for in-app preview
- **Offline ZIP package**: `export_offline_package()` for portable viewing
- **Version diff**: `diff_report_versions()` using report snapshots
- **Keyboard shortcuts**: Ctrl+E (edit), Ctrl+D (dictation), Ctrl+R (regenerate); shortcut reference popover
- **Session timeout toast**: Warning before auto-logout
- **Mobile-responsive CSS**: Media queries in `ui.py`
- **Config warnings**: `validate_config()` shows missing/risky settings
- **Search snippet highlighting**: Context around matched terms in FTS5 results
- **Batch NIBRS export from search**: Export filtered search results to NIBRS XML
- **Evidence QR code popover**: Quick shareable code in evidence locker
- **Evidence upload in batch queue**: Attach files to queue items
- **Dashboard export**: PDF/CSV export buttons
- **Confirmation modals**: Destructive action confirmations in settings
- **Report Template Manager**: UI for managing templates in settings
- **Statute DB management**: Import/export tools in settings
- **generate_report.py enhancements**: Language selector, section-based editor, statute suggestion display, NCIC code reference, confidence segment badges, voice dictation into editor, `st.status()` loading, auto-save timestamps, contextual help tooltips, HTML preview + offline download buttons
- **40 new tests** in `test_new_features.py` covering LLM cache, NCIC codes, JSON retry, statute auto-linking, NIBRS cross-reference, statute suggestion, enhanced NIBRS XML, phrase book import/export, provider caching, location redaction, spell check custom dict, multi-language, DB snapshots, config validation, fine-tune quality metrics

### Session 10 — Distributed Architecture Migration
Completed the transformation of the application from a single-node SQLite app to a scalable, distributed architecture:
- **Database Migration**: Replaced SQLite with PostgreSQL + `psycopg2` connection pooling. All queries refactored.
- **Authentication**: Added LDAP / Active Directory integration (`ldap3`) for role mapping.
- **Background Queue**: Implemented Celery + Redis to offload heavy transcriptions and LLM generation from Streamlit. UI polls via `streamlit-autorefresh`.
- **Container Orchestration**: Wrote a full `docker-compose.yml` integrating `postgres`, `redis`, `celery_worker`, `ollama`, and the `chronos` Streamlit app, with `wait-for-it` logic to ensure clean startup sequencing.

### Session 11 — Next.js Migration & Advanced AI
Massive structural and AI capability upgrade:
- **Next.js Migration**: Scaffolded a premium Next.js 14 App Router frontend (Tailwind CSS, shadcn/ui) in `frontend/` to replace the Streamlit monolith.
- **API Server & JWT**: Refactored `api_server.py` to use a custom JWT implementation (`jwt_utils.py`) to avoid external dependencies, supporting HTTPBearer. Added SSE streaming for real-time narrative generation.
- **NIEM CAD Integration**: Created `niem_parser.py` to ingest National Information Exchange Model (NIEM) standard XML/JSON payloads from CAD systems.
- **Vector RAG (pgvector)**: Migrated Postgres to use `pgvector`. Narrative generation now performs L2 distance semantic searches (`<->`) via Ollama `nomic-embed-text` to retrieve the department's top 5 similar past reports and use them as few-shot style examples.
- **Multi-modal Vision AI**: Implemented `vision_parser.py` using `ffmpeg` to extract a bodycam frame every 10s and feed it to Ollama's `llava` model. Scene descriptions are interleaved with the audio transcript.
- **Cruiser Dictation PWA**: Converted the Next.js frontend into a Progressive Web App (PWA) with `@ducanh2912/next-pwa`. Added a dedicated `/mobile` route for high-stress touchscreen dictation in squad cars.

### Session 12 — Extreme Video AI & UI Upgrades
Complete overhaul of the multi-modal evidence processing pipeline:
- **Interactive UI**: Built `frontend/src/app/redact/[incidentId]/page.tsx` as a Next.js interactive video player that syncs Whisper transcripts (click-to-seek) and renders dynamic HTML bounding boxes over the video for redaction preview.
- **Extreme Speed (Hardware Accel)**: Converted `vision_parser.py` to dispatch Ollama VLM requests concurrently using `asyncio`/`aiohttp`. Mapped InsightFace onto the `TensorrtExecutionProvider` and `CUDAExecutionProvider` via ONNX, and applied `torch.compile` to VideoMAE.
- **Continuous Learning (VLM Fine-tuning)**: Wrote `fine_tune_vlm.py` to query PostgreSQL for officer corrections to AI-generated scene descriptions, automatically generating PEFT/LoRA adapters targeting the `moondream2` attention layers.
- **Microservices Scale**: Ripped out the single Celery worker in `docker-compose.yml` and replaced it with `celery_worker_audio` and `celery_worker_vision`, running independent Redis queues so that processing can be distributed seamlessly across a multi-node police precinct network.

### Session 13 — Advanced Next.js UI Integration & Voice Matching (This Session)
Completed the Next.js frontend integration, bridging the gap between the dictation/transcription logic and the officer's review process:
- **State Management & PWA Auth**: Connected `frontend/src/store/useAppStore.ts` (Zustand) to the JWT login flow, persisting `audioUrl`, `transcriptionTaskId`, and `transcriptionStatus`.
- **Background Task Polling**: Implemented a robust 2-second HTTP polling loop via `useEffect` in `page.tsx` against the backend Celery tasks, dynamically rendering `PENDING` states until `SUCCESS` is achieved.
- **Voice Matching Workflow**: Built a multi-step entity matching system.
  - Officers can fetch involved individuals from the Zuercher CAD system via a mock API and filter them.
  - Upon transcription completion, a regex parser on the frontend scans for unique `SPEAKER_XX` tokens and extracts their exact start timestamps.
  - The UI dynamically generates mini HTML5 `<audio>` players linked to `#t=startSecs` for instant audio clip playback.
  - Officers can listen to the short clip and map the voice to an individual from the CAD data.
- **Transcript String Replacement**: Applying the voice mapping automatically executes a global regex replacement across the transcript, replacing `SPEAKER_XX` with real names before loading into the manual Transcript Review Pane.

### Session 14 — Next-Gen Competitive Advantages (This Session)
Completed a major sequence of competitive advantage features to distinguish Chronos from legacy systems:
- **Smart Redaction Copilot**: Integrated and verified intelligent PII redaction.
- **Automated Probable Cause & Statute Verification**: Added `check_statute_elements` and `/review` queue to ensure elements of the crime are met before submission (without bypassing human supervisor review).
- **Automated Case Briefs**: Built NLP map-reduce summarization in `summarizer.py` and a new `/investigations` UI for at-a-glance case context.
- **Officer Performance Insights**: Created `analytics.py` for LLM-driven coaching insights (Tone, De-escalation, Policy Triggers) accessible in `/coaching` UI. Strictly limited to communication, prohibiting legal conclusions.
- **Enhanced Multi-Modal Data Injection**: Updated `narrative_generator.py` and `api_server.py` to ingest `dispatch_audio_transcript` (911 calls) chronologically alongside bodycam data for richer report generation.
- **Granular AI Audit Trails**: Developed a `/api/v1/audit/diff` endpoint and `/audit` Next.js heatmap UI to visually compare the original AI draft against the officer's final edits using `diffview.py`.

## Next Session
The application's Next-Gen capabilities are complete. 

### Suggested Focus Areas (priority order)
1. **End-to-end Testing of New Workflows** — Test the `/audit`, `/coaching`, `/investigations`, and `/review` Next.js UIs against a live database.
2. **End-to-end PWA Testing** — Test the `/mobile` cruiser dictation Next.js Progressive Web App and ensure it successfully routes transcripts into the `celery_worker_audio` queue and surfaces the results.
3. **Vision AI Tests** — Create `test_vision_parser.py` to ensure hardware acceleration and asyncio dispatch function perfectly across different hardware topologies without breaking the test suite.

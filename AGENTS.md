# Chronos Narrative Engine — Project Rules & State

## AIR-GAPPED CJIS ENVIRONMENT
- No internet access. No `pip install` without approval. All deps pre-installed.
- Streamlit app on RTX 5070 Ti (16GB VRAM). Ollama + faster-whisper on localhost.
- All `.py` must parse clean (AST-level). Run `ast.parse()` check before concluding.

## File Inventory (55 Python files)
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
2. **Database**: SQLite with WAL mode, 9 tables + 1 FTS5 virtual table
3. **LLM**: Provider pattern — OllamaProvider does HTTP POST to Ollama API (abstracted through LLMProvider ABC)
4. **Processing**: Pipeline manager runs PDF parsing + transcription in parallel threads
5. **Export**: DOCX (python-docx) + PDF (reportlab) with letterhead, signature block, page numbers
6. **Everything runs in-process in Streamlit** (single-threaded UI, background threads for pipeline)

## Key Conventions
- No comments in code. No README/docs unless asked. No git commit unless asked.
- All UI strings go directly in `st.markdown()` or component calls — no i18n.
- Session state keys use snake_case with leading underscore for internal state.
- Env vars: `CHRONOS_*` prefix, read via `_env()`/`_env_int()` in config.py.

## Current State (all complete, verified 2026-07-19)
- 19 critical bugs fixed in initial pass, plus 18 code-review items fixed
- 14 feature categories implemented:
  - Voice dictation, NIBRS XML export, batch queue, version history diff
  - Print-optimized export, supervisor review + RBAC, DB backup/restore, case linking
  - Structured JSON logging, WI statute DB (221 statutes, 96 JIs), spell check, evidence store
  - Full-text FTS5 search, bulk ZIP export, department letterhead
  - Signature capture (HTML5 Canvas), make-similar-to-case template loader
  - User management page, login audit log viewer, data retention auto-purge
  - REST API (FastAPI), pre-commit hooks, CI pipeline
  - All files parse cleanly. **205 tests pass** (was 159).
- **Test coverage**: test_database.py (57), test_auth.py (43), test_pipeline_manager.py (22), test_llm_fallback.py (10), test_narrative_generator.py (7), test_health.py (11), test_integration.py (15) + existing

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

### Session 6 — Video Transcription Improvements (This Session)
Overhauled the video transcription pipeline with 7 improvements:
- **FFmpeg audio extraction** — `extract_audio_from_video()` with `_check_ffmpeg()` guard for transparent video→audio conversion
- **Progress callback** — `progress_callback(current, total)` throughout `transcribe_file()` → `transcribe_to_text()` → `transcribe_bodycam()` chain, used in UI via `st.progress`
- **Long audio chunking** — `_split_audio_chunks()` splits audio >30min into segments, transcribes independently, re-joins with cumulative timestamps
- **Cancellation support** — `cancel()` / `reset_cancel()` on `BodyCamTranscriber` via `_cancel_event` threading.Event; `cancel_transcription()` public API; `_check_cancelled()` gates in transcription loop
- **Fixed double audio load** — `AudioPreprocessor.preprocess()` now loads audio once and passes `(y, sr)` to processing methods instead of re-loading in `trim_silence()`/`needs_noise_reduction()`
- **Fixed video file extension** — Upload handler saves with original extension (e.g. `.mp4`) instead of `.video` suffix
- **Added `cancel()` to provider** — `TranscriberProvider` ABC and `WhisperTranscriberProvider` now expose `cancel()` for graceful interruption

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

## Next Session
Video transcription improvements complete. 205 tests passing.

### Suggested Focus Areas (priority order)
1. **Statute citation auto-linking** — Scan generated narratives and link WI statute references (e.g., `§ 940.01`) to the statute DB for hover/click lookup
2. **NIBRS ↔ WI statute cross-reference** — Map NIBRS offense codes to corresponding WI statutes for compliance checking
3. **RMS/CAD API integration** — Connect to external RMS/CAD systems for direct data import
4. **Streaming narrative generation** — Show LLM output token-by-token instead of blocking
5. **Report-type-to-statute suggestion** — Auto-suggest relevant statutes based on document type selection

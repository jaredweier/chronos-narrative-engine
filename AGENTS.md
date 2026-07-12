# 🚔 AGENTS.md: Core AI Development Blueprint & Project Instructions

You are an expert AI software engineer specializing in offline, hardware-accelerated law enforcement applications. Your mission is to build the complete, department-isolated "Chronos Narrative Engine" report suite from scratch within this directory.

---

## 💻 Target Host Workstation Environment
- [cite_start]**Device Name:** Investigative-Workstation (Department Host) [cite: 111]
- [cite_start]**OS Platform:** Windows 11 / Windows Server (x64 Architecture) [cite: 111, 115]
- [cite_start]**Processor Muscle:** AMD Ryzen 9 9950X (16-Core / 32-Threads) [cite: 111, 113]
- [cite_start]**Primary GPU Layer:** NVIDIA GeForce RTX 5070 Ti (16 GB dedicated VRAM) [cite: 111, 113]
- [cite_start]**System Memory:** 96.0 GB RAM [cite: 111, 113]
- [cite_start]**Network Setting:** 100% Air-Gapped / Isolated Network (Strict CJIS Security) [cite: 75, 132]

---

## 🗂️ Targeted Project Directory Layout
You must construct the repository precisely matching this file organization tree:
ReportGenerator/
├── AGENTS.md                          # This master specification index
├── automate_infra_setup.ps1          # Automated installer for dependencies
├── launch_report_system.bat          # Simple one-click application execution
├── department_reports.db             # Local SQLite immutable transaction log
├── temp_processing/                  # Temporary staging for uploaded video/PDF inputs
├── completed_reports/                # Export directory for human-finalized texts
├── officer_profiles/                 # Directory tree holding few-shot baselines
│   └── [officer_name]/
│       └── [report_category_type]/   # Isolated text examples (.txt files)
├── redactor.py                       # Automated rule-based PII masking layer
├── pdf_parser.py                     # Zuercher CAD JSON extraction script
├── transcriber.py                    # GPU-accelerated video text speech engine
├── nibrs_checker.py                  # Local LLM legal compliance auditor
├── profiler.py                       # Multi-category few-shot style manager
├── database.py                       # Immutable court audit log and feedback engine
├── pipeline_manager.py               # Asynchronous parallel job controller
└── app.py                            # Streamlit frontend user interface

---

## 🛠️ Step-by-Step Code Component Specifications

### 1. `automate_infra_setup.ps1` (Automated Environment Deployment)
- [cite_start]Create a PowerShell script running with Administrator elevation checks[cite: 189].
- [cite_start]Use `winget` to silently install `Nvidia.CUDA` (v12.x) and `Ollama.Ollama`[cite: 190, 191].
- [cite_start]Programmatically download the FFmpeg essentials build zip from gyan.dev, expand it to `C:\ffmpeg`, and append its nested `bin/` directory permanently to the Machine's System Environment Variable `Path`[cite: 121, 192].
- [cite_start]Establish an isolated Python 3.11+ virtual environment (`venv`)[cite: 79, 128]. [cite_start]Upgrades `pip` and installs: `streamlit`, `faster-whisper`, `pdfplumber`, `requests`, `torch`, `pydantic`[cite: 128, 193].
- [cite_start]Start the Ollama server pipeline and execute `ollama pull llama3.1:8b` completely backgrounded[cite: 122].

### 2. `launch_report_system.bat` (The App Launcher)
- [cite_start]A click-ready Windows batch shortcut that activates the virtual environment via `call venv\Scripts\activate` and triggers the host web dashboard layout: `streamlit run app.py`[cite: 138].

### 3. `redactor.py` (The Automated Privacy Scrubber)
- [cite_start]Define a function `sanitize_pii_content(raw_text)` that uses strict standard `re` regex mappings to detect and substitute sensitive elements before they enter any local LLM context window[cite: 214]:
  - [cite_start]Social Security Numbers (`XXX-XX-XXXX` or 9 digits) $\rightarrow$ `[REDACTED_SSN]` [cite: 215, 216]
  - [cite_start]Standard phone formats $\rightarrow$ `[REDACTED_PHONE]` [cite: 215, 216]
  - [cite_start]Email addresses $\rightarrow$ `[REDACTED_EMAIL]` [cite: 216, 246]
- [cite_start]Include dynamic keyword evaluation to locate patterns like "minor child [Name]" or "juvenile suspect [Name]" and mask the subsequent names as `[REDACTED_JUVENILE_NAME]`[cite: 215, 217].

### 4. `pdf_parser.py` (Semantic Zuercher CAD PDF Ingestor)
- [cite_start]Implement `parse_zuercher_pdf(pdf_path)` using `pdfplumber` to pull raw text[cite: 98]. Pass text through `redactor.py`.
- [cite_start]Query your local Ollama instance (`llama3.1:8b`) with a zero-temperature strict instruction payload forcing text organization into a Pydantic verified JSON schema returning[cite: 28, 29, 30]:
  - `call_id` (Incident tracking code)
  - `call_type` (Nature of offense)
  - `location` (Address of scene)
  - `dispatch_time`, `arrival_time`, `clear_time`
  - `involved_parties` (An array containing Name, DOB, Sex, Age variables)

### 5. `transcriber.py` (Hardware-Optimized Local Speech Engine)
- [cite_start]Use `faster-whisper` pointing to a local body camera file path[cite: 100].
- [cite_start]Force optimization specifically tailored for the RTX 5070 Ti and Ryzen 9 setup: `WhisperModel("small", device="cuda", compute_type="float16", cpu_threads=16)`[cite: 119, 137].
- Enable `vad_filter=True` to prune static or empty air gaps. [cite_start]Loop through segments and format outputs text string line-by-line using timestamp identifiers: `[MM:SS -> MM:SS] Text Transcript Sample`[cite: 100].

### 6. `nibrs_checker.py` (Local Compliance Legal Auditor)
- [cite_start]Define `check_nibrs_compliance(call_type, narrative_text)` query targeting local Llama 3.1[cite: 292].
- [cite_start]Instruct model to act as a federal NIBRS compliance officer, confirming if critical elements corresponding to the case's specific CAD call type are documented (e.g., weapon specifics for assault, forced entry methods for burglary)[cite: 260, 293]. [cite_start]Return findings strictly as a JSON string list of checklist warnings[cite: 294].

### 7. `profiler.py` (Category-Specific Few-Shot Style Router)
- [cite_start]Manage file profiles under directory layers mapped as: `officer_profiles/[officer_name]/[report_category_type]/`[cite: 313].
- [cite_start]`save_style_sample` updates profile folders with raw text selections[cite: 312].
- [cite_start]`get_style_examples` reads stored `.txt` templates matching the specific active document type selection to perform structured Few-Shot prompt injection, ensuring Llama clones the user's distinct operational phrasing without global model fine-tuning[cite: 15, 111, 151].

### 8. `database.py` (Court Audit Trail & Dynamic Feedback Learning Loop)
- [cite_start]Instantiate an offline SQLite database `department_reports.db` containing table tracking fields for `legal_audit_logs`: `id`, `incident_id`, `officer_name`, `document_type`, `submission_timestamp`, `unedited_ai_draft`, `final_approved_report`, `was_modified_by_human`, `verification_signature_flag`[cite: 85, 314].
- [cite_start]Implement `get_recent_corrections(officer_name, report_type, limit=3)` to retrieve the officer's three most recently submitted final reports within that matching category[cite: 93, 315]. [cite_start]These are injected into the context window as a dynamic reinforcement loop so the AI automatically learns from previous user edits[cite: 157, 161].

### 9. `pipeline_manager.py` (Asynchronous Job Controller)
- [cite_start]Use Python's `concurrent.futures.ThreadPoolExecutor(max_workers=2)` to process background jobs concurrently[cite: 204]. Run `parse_zuercher_pdf` and `transcribe_bodycam` at the exact same moment on the thread pool to maximize CPU/GPU execution[cite: 204, 209].
- [cite_start]Implement a VRAM Memory Guardrail function `clear_vram_guardrail()` that triggers `gc.collect()` and `torch.cuda.empty_cache()` to keep the RTX 5070 Ti fresh and prevent out-of-memory errors over long operational shifts[cite: 205].

### 10. `app.py` (Chronos Narrative Engine UI Framework)
- Enforce full-screen width dashboard configurations (`layout="wide"`). [cite_start]Build a top-tier static navigation profile capturing Officer ID and a global classification selector: `REPORT_CATEGORIES = ["Standard Incident Report", "Search Warrant Affidavit", "Internal Use-of-Force Review", "OWI / DUI Report"]`[cite: 317].
- [cite_start]Provide a sidebar mode controller with three system application functions[cite: 153, 247]:
  1. [cite_start]**Generate Report:** Ingests evidence, displays validation states, and outputs the finalized legal text[cite: 4, 143, 231].
  2. [cite_start]**Configure Officer Style:** Allows users to upload 5–10 redacted text report samples to train the category-specific profiles[cite: 14, 314].
  3. [cite_start]**Standalone Report Redactor:** Allows instant local upload and sanitization of generic plain text files via the privacy wrapper, displaying original and masked texts side-by-side with a localized download option[cite: 105, 247].
- [cite_start]**Generate Report - Left UI Column:** Dual file uploader segments[cite: 4]. [cite_start]Native streaming video player (`st.video`) with an active transcript container below it[cite: 26, 106]. [cite_start]Parse lines using text filters (`st.text_input`); append an interactive `⏱️ Jump` button next to each line that maps time calculations to `st.session_state['video_start_time']` to instantly fast-forward the video playback timeline[cite: 60, 271, 300].
- [cite_start]**Generate Report - Right UI Column:** Renders an editable data validation table grid via `st.data_editor` parsing extracted CAD entities[cite: 4, 219, 220]. [cite_start]If characters like "?" or "!" appear, throw low-confidence scan validation alerts[cite: 36, 221]. [cite_start]Display NIBRS check alerts prominently above the narrative workspace[cite: 267].
- [cite_start]**Enforced Verification Gate:** Render an explicit attestation checkbox acknowledging personal and professional legal responsibility for the report accuracy[cite: 21, 62]. [cite_start]Lock the submission and text compilation file output triggers until checked[cite: 21]. [cite_start]Clicking save commits all draft layers to the SQLite audit log table, cleans up temporary system directory files, and executes `clear_vram_guardrail()`[cite: 108, 180, 205].

---

## 🚦 AI Agent Execution Directives
1. Read the complete directory specification mapping rules.
2. [cite_start]Draft the supporting system utility modules (`redactor.py`, `pdf_parser.py`, `transcriber.py`, `nibrs_checker.py`, `profiler.py`, `database.py`, `pipeline_manager.py`) sequentially, confirming zero cloud-dependent external API configurations are hardcoded[cite: 76, 132].
3. [cite_start]Construct the comprehensive unified orchestrator dashboard wrapper script `app.py` incorporating the three workspace navigation modes[cite: 153, 247].
4. [cite_start]Generate the automation script `automate_infra_setup.ps1` and the execution bridge batch script `launch_report_system.bat` to ensure a completely automated configuration flow[cite: 173, 188].

- **Multi-User Network Configuration:** Configure the Streamlit server deployment flag inside the initialization scripts to explicitly allow headless network broadcasting by setting browser server parameters (`streamlit run app.py --server.address=0.0.0.0`). Ensure all SQLite connection streams utilize a `timeout=30.0` parameter to protect transaction queues from multi-user write collisions.

- **Shared-Computer Session Authentication Gate:** - Enforce an absolute UI lock using `st.session_state['authenticated_officer']`. On application load, if this state variable is empty, hide all navigation menus and report assets, and display a centralized "Chronos Profile Login" panel requiring an Officer Name/ID.
  - Upon clicking "Secure Login", commit the input string to the session state. 
  - Provide a highly visible "Exit & Clear Session" button at the top of the sidebar navigation. Clicking this button must explicitly execute `st.session_state.clear()`, wipe the active browser cache, and re-lock the login gate to prevent cross-user profile accidents on shared department computers.
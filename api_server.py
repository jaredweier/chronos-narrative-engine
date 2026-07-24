import os
import secrets
from typing import Optional, List, Dict, Any
from datetime import datetime
from config import OLLAMA_MODEL, API_KEY, API_BIND_HOST, API_PORT
import cad_api
from logger import get_logger

logger = get_logger(__name__)

try:
    from fastapi import FastAPI, HTTPException, Depends, Security, UploadFile, File, Form
    from fastapi.responses import StreamingResponse
    from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from jwt_utils import encode_jwt, decode_jwt
    from auth import authenticate_officer, get_officer_role
    import time
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

app = None

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_jwt_scheme = HTTPBearer(auto_error=False)

_API_KEY = API_KEY or os.environ.get("CHRONOS_API_KEY", "")
if not _API_KEY:
    _API_KEY = secrets.token_hex(32)
    logger.warning("No CHRONOS_API_KEY set. Generated temporary key: %s", _API_KEY)

JWT_SECRET = os.environ.get("CHRONOS_JWT_SECRET", _API_KEY)

def _verify_auth(
    api_key: Optional[str] = Security(_api_key_header),
    token: Optional[HTTPAuthorizationCredentials] = Security(_jwt_scheme)
):
    if api_key and api_key == _API_KEY:
        return {"type": "api_key", "sub": "system"}
    
    if token:
        # Mock Keycloak IdP integration (CJIS Compliance Preparation)
        # In a real enterprise deployment, we would parse the unverified header to get 'kid'
        # and fetch the public key from Keycloak's JWKS endpoint to verify RS256 signature.
        try:
            payload = decode_jwt(token.credentials, JWT_SECRET)
            return payload
        except ValueError as ve:
            # Fallback for mocked Enterprise IdP token
            if os.environ.get("CHRONOS_AUTH_MODE") == "enterprise":
                logger.warning("Mocking Keycloak IdP JWT verification for enterprise token")
                return {"type": "idp_token", "sub": "mocked_enterprise_user", "role": "officer"}
            raise HTTPException(status_code=401, detail=f"Invalid JWT: {ve}")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid JWT: {e}")
            
    raise HTTPException(status_code=401, detail="Not authenticated")


if _HAS_FASTAPI:
    app = FastAPI(title="Chronos API", version="1.0.0",
                  description="Chronos Narrative Engine REST API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501", "http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

    class LoginRequest(BaseModel):
        name: str
        badge_id: str
        password: str

    class LoginResponse(BaseModel):
        token: str
        role: str

    @app.post("/api/v1/auth/login", response_model=LoginResponse)
    def login(req: LoginRequest):
        if not authenticate_officer(req.name, req.badge_id, req.password, "127.0.0.1"):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        role = get_officer_role(req.badge_id)
        payload = {
            "sub": req.badge_id,
            "name": req.name,
            "role": role,
            "exp": int(time.time()) + 86400  # 24 hours
        }
        token = encode_jwt(payload, JWT_SECRET)
        return LoginResponse(token=token, role=role)

    class ReportRequest(BaseModel):
        cad_text: Optional[str] = ""
        transcript: Optional[str] = ""
        dispatch_transcript: Optional[str] = ""
        notes: Optional[str] = ""
        report_type: str = "Incident Report"
        officer_name: Optional[str] = ""
        officer_id: Optional[str] = ""
        incident_id: Optional[str] = ""

    class NarrativeResponse(BaseModel):
        incident_id: str
        report_text: str
        model: str
        generated_at: str

    class SearchRequest(BaseModel):
        query: str
        limit: int = 20
        officer_name: Optional[str] = ""

    @app.get("/health")
    def health_check():
        return {
            "status": "ok",
            "service": "Chronos Narrative Engine API",
            "timestamp": datetime.now().isoformat(),
        }

    @app.get("/api/v1/cad/incident/{incident_id}")
    def mock_cad_endpoint(incident_id: str, _=Depends(_verify_auth)):
        # Mock CAD JSON payload mimicking a Zuercher or RMS system
        return {
            "call_id": incident_id,
            "call_type": "Disturbance - Domestic",
            "location": "123 Main St, Apt 4B",
            "dispatch_time": datetime.now().replace(hour=14, minute=30, second=0).isoformat(),
            "arrival_time": datetime.now().replace(hour=14, minute=38, second=0).isoformat(),
            "clear_time": datetime.now().replace(hour=15, minute=45, second=0).isoformat(),
            "involved_parties": [
                {"name": "John Doe", "dob": "1985-05-12", "sex": "M", "age": 41, "role": "Suspect"},
                {"name": "Jane Doe", "dob": "1988-08-22", "sex": "F", "age": 38, "role": "Victim"}
            ],
            "raw_text": f"CAD ENTRY: {incident_id}\nCaller reports screaming and throwing objects from Apt 4B. Caller wishes to remain anonymous. Officers dispatched. Subject detained at scene."
        }

    @app.post("/api/v1/narrative/stream")
    def generate_narrative_stream(req: ReportRequest, _=Depends(_verify_auth)):
        try:
            from providers import get_llm
            from templates import get_template, render_template_prompt
            
            tmpl = get_template(req.report_type)
            if not tmpl:
                raise HTTPException(status_code=400, detail="Unknown report type")
                
            prompt = render_template_prompt(tmpl, req.cad_text, req.transcript, req.notes)
            llm = get_llm()
            
            def event_generator():
                try:
                    for token in llm.stream_complete(prompt, system_prompt="You are a professional LE report writer."):
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    yield f"event: error\ndata: {str(e)}\n\n"
                    
            return StreamingResponse(event_generator(), media_type="text/event-stream")
        except Exception as e:
            logger.exception("Streaming setup failed")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/narrative/generate", response_model=NarrativeResponse)
    def generate_narrative_endpoint(req: ReportRequest, _=Depends(_verify_auth)):
        try:
            from narrative_generator import generate_narrative
            import requests
            
            similar_reports = []
            if req.cad_text:
                try:
                    resp = requests.post("http://localhost:11434/api/embeddings", json={"model": "nomic-embed-text", "prompt": req.cad_text}, timeout=5)
                    if resp.status_code == 200:
                        embedding = resp.json().get("embedding")
                        if embedding:
                            from database import find_similar_reports_vector
                            similar_reports = find_similar_reports_vector(embedding, limit=5)
                except Exception as e:
                    logger.warning(f"Vector RAG lookup failed: {e}")
                    
            style_examples = [r["snapshot_text"] for r in similar_reports if r.get("snapshot_text")]
            
            text = generate_narrative(
                cad_text=req.cad_text or "",
                transcript=req.transcript or "",
                dispatch_audio_transcript=req.dispatch_transcript or "",
                custom_notes=req.notes or "",
                report_type=req.report_type,
                officer_style_examples=style_examples,
            )
            if text.startswith("[ERROR]"):
                raise HTTPException(status_code=500, detail=text)
            inc_id = req.incident_id or f"API-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(2).upper()}"
            return NarrativeResponse(
                incident_id=inc_id,
                report_text=text,
                model=OLLAMA_MODEL,
                generated_at=datetime.now().isoformat(),
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("API narrative generation failed")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/reports/search")
    def search_reports(query: str, limit: int = 20, officer_name: str = "", _=Depends(_verify_auth)):
        from database import search_reports as db_search, search_officer_reports
        if officer_name:
            results = search_officer_reports(officer_name, query, limit)
        else:
            results = db_search(query, limit)
        safe = []
        for r in results:
            safe.append({
                "incident_id": r.get("incident_id"),
                "officer_name": r.get("officer_name"),
                "document_type": r.get("document_type"),
                "submission_timestamp": r.get("submission_timestamp"),
                "has_final_report": bool(r.get("final_approved_report")),
            })
        return {"results": safe, "count": len(safe)}

    @app.get("/reports/{incident_id}")
    def get_report(incident_id: str, _=Depends(_verify_auth)):
        from database import get_incident
        report = get_incident(incident_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

    @app.get("/evidence/{incident_id}")
    def get_evidence(incident_id: str, _=Depends(_verify_auth)):
        from database import get_evidence_files
        files = get_evidence_files(incident_id)
        return {"incident_id": incident_id, "files": files}

    @app.get("/api/v1/evidence/{incident_id}/{filename}")
    def stream_evidence_file(incident_id: str, filename: str, _=Depends(_verify_auth)):
        import os
        from config import EVIDENCE_DIR
        from fastapi.responses import FileResponse
        
        file_path = os.path.join(EVIDENCE_DIR, incident_id, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
            
        return FileResponse(file_path, media_type="video/mp4")

    @app.post("/api/v1/evidence/upload")
    def upload_evidence(incident_id: str = Form(...), file: UploadFile = File(...), _=Depends(_verify_auth)):
        from evidence_store import save_evidence_file
        import shutil
        import os
        from config import TEMP_DIR
        
        temp_path = os.path.join(TEMP_DIR, file.filename)
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        success, final_path = save_evidence_file(incident_id, temp_path)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save evidence")
            
        return {"status": "success", "incident_id": incident_id, "filename": file.filename, "path": final_path}
        
    @app.post("/api/v1/dictation/upload")
    def upload_dictation(incident_id: Optional[str] = Form(None), file: UploadFile = File(...), _=Depends(_verify_auth)):
        import os
        import shutil
        from config import TEMP_DIR
        from tasks import transcribe_audio_task
        
        temp_path = os.path.join(TEMP_DIR, file.filename)
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        task = transcribe_audio_task.delay(temp_path)
        return {"status": "success", "task_id": task.id, "filename": file.filename}

    @app.get("/api/v1/tasks/{task_id}")
    def get_task_status(task_id: str, _=Depends(_verify_auth)):
        from celery.result import AsyncResult
        res = AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": res.status,
            "result": res.result if res.ready() else None
        }

    @app.get("/stats")
    def get_stats(_=Depends(_verify_auth)):
        from database import get_statistics, get_dashboard_analytics
        stats = get_statistics()
        analytics = get_dashboard_analytics()
        return {**stats, **analytics}

    @app.get("/providers")
    def list_providers(_=Depends(_verify_auth)):
        from providers import list_llm_providers, list_transcriber_providers, list_pdf_providers
        return {
            "llm": list_llm_providers(),
            "transcriber": list_transcriber_providers(),
            "pdf_parser": list_pdf_providers(),
        }

    @app.get("/api/v1/ui/dashboard")
    def dashboard_ui_stub(_=Depends(_verify_auth)):
        # Stub for Next.js frontend dashboard data
        return {
            "status": "stub", 
            "message": "Next.js dashboard endpoint",
            "pending_briefings": [
                {"id": "INC-2026-001", "brief": "• Suspect arrested for DUI at 01:05.\n• Bodycam video recorded [01:05].\n• Transported to station without incident."},
                {"id": "INC-2026-002", "brief": "• Domestic dispute at 100 Main St.\n• Parties separated, no arrests made.\n• Follow-up requested by social services."}
            ]
        }
        
    @app.get("/mock-zuercher/api/v1/incidents/{incident_id}")
    def mock_zuercher_incident(incident_id: str):
        """Mock external Zuercher CAD API."""
        if incident_id == "404":
            raise HTTPException(status_code=404, detail="Incident not found")
            
        return {
            "IncidentNumber": incident_id,
            "CallNature": "Burglary - In Progress",
            "Address": "123 Main St, Springfield",
            "TimeDispatched": "2026-07-22T21:45:00Z",
            "TimeArrived": "2026-07-22T21:50:00Z",
            "TimeCleared": "2026-07-22T23:15:00Z",
            "InvolvedPersons": [
                {"FirstName": "John", "LastName": "Doe", "DateOfBirth": "1980-01-01", "Gender": "M", "Age": 46},
                {"FirstName": "Jane", "LastName": "Smith", "DateOfBirth": "1992-05-15", "Gender": "F", "Age": 34}
            ]
        }
        
    class CadFetchRequest(BaseModel):
        incident_id: str
        
    @app.post("/api/v1/cad/fetch")
    def fetch_cad_data(request: CadFetchRequest, _=Depends(_verify_auth)):
        """Proxy endpoint for Next.js frontend to fetch CAD data via cad_api."""
        try:
            data = cad_api.fetch_incident_from_zuercher(request.incident_id)
            if not data:
                raise HTTPException(status_code=404, detail="Incident not found in CAD system.")
            return {"status": "success", "data": data}
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
            
    @app.post("/api/v1/niem/import")
    def import_niem_data(payload: dict, _=Depends(_verify_auth)):
        """Endpoint to import NIEM-compliant CAD JSON."""
        try:
            from niem_parser import parse_niem_incident
            data = parse_niem_incident(payload)
            return {"status": "success", "data": data}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid NIEM payload: {str(e)}")

    class RedactRequest(BaseModel):
        video_filename: str
        redaction_data: Dict[str, List[Dict[str, Any]]]
        
    @app.get("/api/v1/video/{incident_id}/detections")
    def get_video_detections(incident_id: str, video_filename: str, _=Depends(_verify_auth)):
        from config import EVIDENCE_DIR
        import os
        from vision_parser import extract_frames, extract_entities
        
        video_path = os.path.join(EVIDENCE_DIR, incident_id, video_filename)
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video not found")
            
        frames = extract_frames(video_path, fps=1)
        detections = extract_entities(frames)
        
        return {"status": "success", "detections": detections}
        
    @app.post("/api/v1/video/{incident_id}/redact")
    def redact_video_endpoint(incident_id: str, req: RedactRequest, _=Depends(_verify_auth)):
        from config import EVIDENCE_DIR
        import os
        from visual_redactor import redact_video
        
        video_path = os.path.join(EVIDENCE_DIR, incident_id, req.video_filename)
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video not found")
            
        output_filename = f"redacted_{req.video_filename}"
        output_path = os.path.join(EVIDENCE_DIR, incident_id, output_filename)
        
        from tasks import redact_video_task
        
        # Dispatch to the celery vision queue
        task = redact_video_task.delay(video_path, req.redaction_data, output_path)
        
        # In a real app we'd return task.id and poll, but for this step we'll block
        # just so the frontend doesn't need to be rewritten to poll yet.
        success = task.get(timeout=300)
        
        if not success:
            raise HTTPException(status_code=500, detail="Redaction failed")
            
        return {"status": "success", "redacted_video": output_filename}

    @app.post("/api/v1/redact/analyze")
    def analyze_document_redaction(file: UploadFile = File(...), _=Depends(_verify_auth)):
        import os
        import shutil
        from config import TEMP_DIR
        from redactor import extract_entities
        
        temp_path = os.path.join(TEMP_DIR, file.filename)
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        text = ""
        ext = os.path.splitext(file.filename)[1].lower()
        try:
            if ext == ".pdf":
                import pdfplumber
                with pdfplumber.open(temp_path) as pdf:
                    text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            elif ext == ".docx":
                import docx
                doc = docx.Document(temp_path)
                text = "\n".join([p.text for p in doc.paragraphs])
            else:
                with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        entities = extract_entities(text)
        return {"status": "success", "text": text, "entities": entities}

    class TextRedactRequest(BaseModel):
        text: str
        categories: Optional[List[str]] = None
        custom_terms: Optional[List[str]] = None

    @app.post("/api/v1/redact/apply")
    def apply_document_redaction(req: TextRedactRequest, _=Depends(_verify_auth)):
        from redactor import sanitize_pii_content
        active_categories = set(req.categories) if req.categories is not None else None
        redacted_text = sanitize_pii_content(
            req.text, 
            categories=active_categories, 
            custom_terms=req.custom_terms
        )
        return {"status": "success", "redacted_text": redacted_text}

    class VerifyStatuteRequest(BaseModel):
        narrative: str
        statute_codes: List[str]

    @app.post("/api/v1/verify-statute")
    def verify_statute_endpoint(req: VerifyStatuteRequest, _=Depends(_verify_auth)):
        from nibrs_checker import check_statute_elements
        results = []
        for code in req.statute_codes:
            result = check_statute_elements(req.narrative, code)
            results.append(result)
        return {"status": "success", "results": results}

    class CaseBriefRequest(BaseModel):
        text: str

    @app.post("/api/v1/case-briefs")
    def generate_case_brief_endpoint(req: CaseBriefRequest, _=Depends(_verify_auth)):
        from summarizer import generate_case_brief
        try:
            brief = generate_case_brief(req.text)
            return {"status": "success", "brief": brief}
        except Exception as e:
            logger.error("Error in /api/v1/case-briefs: %s", e)
            return {"status": "error", "message": str(e)}

    class PerformanceAnalyticsRequest(BaseModel):
        transcript: str

    @app.post("/api/v1/analytics/performance")
    def analyze_performance_endpoint(req: PerformanceAnalyticsRequest, _=Depends(_verify_auth)):
        from analytics import analyze_officer_performance
        try:
            insights = analyze_officer_performance(req.transcript)
            return {"status": "success", "insights": insights}
        except Exception as e:
            logger.error("Error in /api/v1/analytics/performance: %s", e)
            return {"status": "error", "message": str(e)}

    @app.get("/api/v1/audit/diff/{incident_id}")
    def get_audit_diff(incident_id: str, _=Depends(_verify_auth)):
        from database import get_snapshots
        from diffview import compute_diff
        
        snapshots = get_snapshots(incident_id)
        if len(snapshots) < 2:
            return {"status": "success", "diff": [], "message": "Not enough snapshots for diff"}
            
        ai_draft = snapshots[0].get("snapshot_text", "")
        final_report = snapshots[-1].get("snapshot_text", "")
        
        raw_diff = compute_diff(ai_draft, final_report)
        json_diff = [{"type": kind, "text": text} for kind, text in raw_diff]
        
        return {
            "status": "success", 
            "diff": json_diff,
            "ai_draft_label": snapshots[0].get("snapshot_label", "AI Draft"),
            "final_label": snapshots[-1].get("snapshot_label", "Final Report")
        }

else:
    logger.warning("FastAPI not installed. REST API unavailable. Install with: pip install fastapi uvicorn")


def start_api_server(host: str = "", port: int = 0):
    if not _HAS_FASTAPI:
        logger.error("Cannot start API server: FastAPI not installed")
        return
    import uvicorn
    bind_host = host or API_BIND_HOST
    bind_port = port or API_PORT
    logger.info("Starting Chronos API on %s:%s", bind_host, bind_port)
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="warning")


if __name__ == '__main__':
    start_api_server()

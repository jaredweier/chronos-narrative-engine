import os
import secrets
from typing import Optional
from datetime import datetime
from config import OLLAMA_MODEL, API_KEY, API_BIND_HOST, API_PORT
from logger import get_logger

logger = get_logger(__name__)

try:
    from fastapi import FastAPI, HTTPException, Depends, Security
    from fastapi.security import APIKeyHeader
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

app = None

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_API_KEY = API_KEY or os.environ.get("CHRONOS_API_KEY", "")
if not _API_KEY:
    _API_KEY = secrets.token_hex(32)
    logger.warning("No CHRONOS_API_KEY set. Generated temporary key: %s", _API_KEY)


def _verify_api_key(api_key: str = Security(_api_key_header)):
    if not api_key or api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


if _HAS_FASTAPI:
    app = FastAPI(title="Chronos API", version="1.0.0",
                  description="Chronos Narrative Engine REST API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

    class ReportRequest(BaseModel):
        cad_text: Optional[str] = ""
        transcript: Optional[str] = ""
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

    @app.post("/narrative/generate", response_model=NarrativeResponse)
    def generate_narrative_endpoint(req: ReportRequest, _=Depends(_verify_api_key)):
        try:
            from narrative_generator import generate_narrative
            text = generate_narrative(
                cad_text=req.cad_text or "",
                transcript=req.transcript or "",
                custom_notes=req.notes or "",
                report_type=req.report_type,
                officer_style_examples=[],
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
    def search_reports(query: str, limit: int = 20, officer_name: str = "", _=Depends(_verify_api_key)):
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
    def get_report(incident_id: str, _=Depends(_verify_api_key)):
        from database import get_incident
        report = get_incident(incident_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

    @app.get("/evidence/{incident_id}")
    def get_evidence(incident_id: str, _=Depends(_verify_api_key)):
        from database import get_evidence_files
        files = get_evidence_files(incident_id)
        return {"incident_id": incident_id, "files": files}

    @app.get("/stats")
    def get_stats(_=Depends(_verify_api_key)):
        from database import get_statistics, get_dashboard_analytics
        stats = get_statistics()
        analytics = get_dashboard_analytics()
        return {**stats, **analytics}

    @app.get("/providers")
    def list_providers(_=Depends(_verify_api_key)):
        from providers import list_llm_providers, list_transcriber_providers, list_pdf_providers
        return {
            "llm": list_llm_providers(),
            "transcriber": list_transcriber_providers(),
            "pdf_parser": list_pdf_providers(),
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

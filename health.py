import os
import shutil
from dataclasses import dataclass
from typing import List

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    TEMP_DIR,
    COMPLETED_DIR,
    PROFILES_DIR,
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
)
from logger import get_logger

logger = get_logger(__name__)


@dataclass
class HealthCheck:
    name: str
    status: bool
    message: str
    severity: str = "warning"

    def icon(self) -> str:
        if self.severity == "error":
            return "\u26A0" if not self.status else "\u2705"
        return "\u2705" if self.status else "\u26A0"


def check_ollama() -> HealthCheck:
    try:
        try:
            import requests as _req
        except ModuleNotFoundError:
            return HealthCheck("Ollama", False, "requests module not installed", "error")
        r = _req.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            model_found = OLLAMA_MODEL in models or any(
                m.startswith(OLLAMA_MODEL) for m in models
            )
            if model_found:
                return HealthCheck(
                    "Ollama", True, f"{OLLAMA_MODEL} available", "ok"
                )
            return HealthCheck(
                "Ollama Model", False,
                f"{OLLAMA_MODEL} not pulled. Run: ollama pull {OLLAMA_MODEL}",
                "error",
            )
        return HealthCheck(
            "Ollama", False, f"Ollama API returned {r.status_code}", "error"
        )
    except Exception as e:
        if any(x in type(e).__name__ for x in ("ConnectionError", "ConnectError")):
            return HealthCheck(
                "Ollama", False,
                f"Cannot reach {OLLAMA_BASE_URL}. Is Ollama running? (ollama serve)",
                "error",
            )
        return HealthCheck("Ollama", False, str(e), "error")


def check_dirs() -> List[HealthCheck]:
    checks = []
    for name, path in [
        ("Temp Processing", TEMP_DIR),
        ("Completed Reports", COMPLETED_DIR),
        ("Officer Profiles", PROFILES_DIR),
    ]:
        try:
            os.makedirs(path, exist_ok=True)
            writable = os.access(path, os.W_OK)
            free = shutil.disk_usage(path).free
            free_gb = free / (1024 ** 3)
            if not writable:
                checks.append(HealthCheck(name, False, f"{path} not writable", "error"))
            elif free_gb < 1:
                checks.append(HealthCheck(name, True, f"{path} OK (only {free_gb:.1f}GB free)", "warning"))
            else:
                checks.append(HealthCheck(name, True, f"{path} OK ({free_gb:.1f}GB free)", "ok"))
        except Exception as e:
            checks.append(HealthCheck(name, False, str(e), "error"))
    return checks


def check_database() -> HealthCheck:
    try:
        from database import get_db_connection
        with get_db_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM legal_audit_logs").fetchone()[0]
        return HealthCheck("Database", True, f"{count} records in legal_audit_logs", "ok")
    except Exception as e:
        msg = str(e)
        if "no such table" in msg:
            return HealthCheck("Database", True, "Empty database (tables not yet created)", "ok")
        return HealthCheck("Database", False, f"Database error: {msg}", "error")


def check_whisper() -> HealthCheck:
    try:
        import torch
        if WHISPER_DEVICE == "cuda" and not torch.cuda.is_available():
            return HealthCheck(
                "Whisper Device", False,
                f"WHISPER_DEVICE=cuda but CUDA not available. Falling back to CPU.",
                "warning",
            )
        if WHISPER_DEVICE == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_mem / (1024 ** 3)
            return HealthCheck(
                "Whisper GPU", True,
                f"{gpu_name} ({vram:.1f}GB VRAM), model: {WHISPER_MODEL_SIZE}",
                "ok",
            )
        return HealthCheck(
            "Whisper Device", True,
            f"Using {WHISPER_DEVICE}, model: {WHISPER_MODEL_SIZE}",
            "ok",
        )
    except Exception as e:
        return HealthCheck("Whisper", False, f"Device check failed: {e}", "warning")


def run_all_checks() -> List[HealthCheck]:
    results = []
    results.append(check_ollama())
    results.extend(check_dirs())
    results.append(check_database())
    results.append(check_whisper())
    return results


def render_health_banner(checks: List[HealthCheck]):
    import streamlit as st

    errors = [c for c in checks if c.severity == "error"]
    warnings = [c for c in checks if c.severity == "warning"]

    if not errors and not warnings:
        return

    if errors:
        with st.expander("\u26A0 System Issues Detected", expanded=True):
            for c in errors:
                st.warning(f"**{c.name}**: {c.message}")
            for c in warnings:
                if c.severity == "warning":
                    st.info(f"**{c.name}**: {c.message}")
    elif warnings:
        with st.expander("\u2139 System Notes", expanded=False):
            for c in warnings:
                st.info(f"**{c.name}**: {c.message}")


def render_health_dashboard(checks: List[HealthCheck]):
    import streamlit as st
    cols = st.columns(len(checks))
    for i, c in enumerate(checks):
        with cols[i]:
            severity_colors = {
                "error": "#ef4444",
                "warning": "#f59e0b",
                "ok": "#22c55e",
                "info": "#64748b",
            }
            color = severity_colors.get(c.severity, "#64748b")
            st.markdown(
                f"""<div style="text-align:center;padding:12px;border:1px solid {color}33;
                border-radius:8px;background:{color}0a;">
                <div style="font-size:1.5rem;margin-bottom:4px;">{c.icon()}</div>
                <div style="font-size:0.72rem;font-weight:600;color:{color};">{c.name}</div>
                <div style="font-size:0.58rem;opacity:0.5;margin-top:4px;">{c.message[:50]}</div>
                </div>""",
                unsafe_allow_html=True,
            )

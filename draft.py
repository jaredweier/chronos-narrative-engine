import streamlit as st
import os
import json
from datetime import datetime
from typing import Optional

AUTO_SAVE_KEY = "autosave_draft"
DRAFT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_processing", "drafts")


def _draft_path(officer_name: str) -> str:
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in officer_name)
    os.makedirs(DRAFT_DIR, exist_ok=True)
    return os.path.join(DRAFT_DIR, f"{safe}.json")


def _load_disk_draft(officer_name: str) -> Optional[dict]:
    path = _draft_path(officer_name)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _save_disk_draft(officer_name: str, text: str) -> None:
    path = _draft_path(officer_name)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"officer": officer_name, "text": text, "timestamp": datetime.now().isoformat()}, f)
    except OSError:
        pass


def _remove_disk_draft(officer_name: str) -> None:
    path = _draft_path(officer_name)
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def save_draft(officer_name: str, report_text: str) -> None:
    if not report_text or not officer_name:
        return
    st.session_state[AUTO_SAVE_KEY] = {
        "officer": officer_name,
        "text": report_text,
        "timestamp": datetime.now().isoformat(),
    }
    _save_disk_draft(officer_name, report_text)


def restore_draft(officer_name: str) -> Optional[str]:
    draft = st.session_state.get(AUTO_SAVE_KEY)
    if draft and draft.get("officer") == officer_name:
        return draft.get("text")
    disk_draft = _load_disk_draft(officer_name)
    if disk_draft and disk_draft.get("officer") == officer_name:
        st.session_state[AUTO_SAVE_KEY] = disk_draft
        return disk_draft.get("text")
    return None


def clear_draft(officer_name: Optional[str] = None):
    st.session_state.pop(AUTO_SAVE_KEY, None)
    if officer_name:
        _remove_disk_draft(officer_name)


if __name__ == '__main__':
    print("Draft module")
    print(f"Draft directory: {DRAFT_DIR}")


def render_draft_banner(officer_name: str) -> None:
    draft = st.session_state.get(AUTO_SAVE_KEY)
    if not draft or draft.get("officer") != officer_name:
        disk_draft = _load_disk_draft(officer_name)
        if disk_draft and disk_draft.get("officer") == officer_name:
            st.session_state[AUTO_SAVE_KEY] = disk_draft
            draft = disk_draft
        else:
            return

    ts = draft.get("timestamp", "")
    if ts:
        try:
            formatted_ts = ts[:16].replace("T", " ")
        except Exception:
            formatted_ts = ts
    else:
        formatted_ts = "unknown"

    st.markdown(
        f"""<div style="background:rgba(251,191,36,0.06);border:1px solid rgba(251,191,36,0.2);
        border-left:3px solid #f59e0b;border-radius:0 6px 6px 0;padding:10px 16px;margin-bottom:16px;
        display:flex;justify-content:space-between;align-items:center;">
        <div><span style="font-size:0.7rem;color:#f59e0b;font-weight:600;">UNSAVED DRAFT</span>
        <span style="font-size:0.62rem;color:#64748b;margin-left:8px;">from {formatted_ts}</span></div>
        <div style="font-size:0.62rem;color:#64748b;">Use buttons below</div></div>""",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Restore Draft", use_container_width=True, key="restore_draft_btn"):
            st.session_state["report_editor"] = draft["text"]
            clear_draft(officer_name)
            st.rerun()
    with col2:
        if st.button("Dismiss", use_container_width=True, key="dismiss_draft_btn"):
            clear_draft(officer_name)
            st.rerun()

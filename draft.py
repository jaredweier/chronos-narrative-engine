import streamlit as st
from datetime import datetime
from typing import Optional

AUTO_SAVE_KEY = "autosave_draft"


def save_draft(officer_name: str, report_text: str) -> None:
    if not report_text or not officer_name:
        return
    st.session_state[AUTO_SAVE_KEY] = {
        "officer": officer_name,
        "text": report_text,
        "timestamp": datetime.now().isoformat(),
    }


def restore_draft(officer_name: str) -> Optional[str]:
    draft = st.session_state.get(AUTO_SAVE_KEY)
    if draft is None:
        return None
    if draft.get("officer") != officer_name:
        return None
    return draft.get("text")


def clear_draft():
    st.session_state.pop(AUTO_SAVE_KEY, None)


def render_draft_banner(officer_name: str) -> None:
    from app import _case_bar_html

    draft = restore_draft(officer_name)
    if not draft:
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
        <div style="display:flex; gap:8px;">
        <span id="restore_draft" style="font-size:0.65rem;color:#60a5fa;font-weight:600;cursor:pointer;">Restore</span>
        <span id="dismiss_draft" style="font-size:0.65rem;color:#ef4444;font-weight:600;cursor:pointer;">Dismiss</span>
        </div></div>""",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Restore Draft", use_container_width=True, key="restore_draft_btn"):
            st.session_state["report_editor"] = draft["text"]
            clear_draft()
            st.rerun()
    with col2:
        if st.button("Dismiss", use_container_width=True, key="dismiss_draft_btn"):
            clear_draft()
            st.rerun()

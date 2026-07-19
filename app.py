import streamlit as st
import os
import secrets
from datetime import datetime
from html import escape as h
import time as _time
import requests as _req

from dotenv import load_dotenv
load_dotenv()

from database import get_officer_history, get_review_counts
from config import TEMP_DIR, COMPLETED_DIR, EVIDENCE_DIR, OLLAMA_BASE_URL, SESSION_TIMEOUT_SECONDS
from pipeline_manager import cleanup_pipeline
from auth import authenticate_officer, register_officer, officer_exists, get_officer_role
from logger import get_logger
from ui import (
    inject_css, badge_html, badge_sm_html,
)
from dashboard import mode_dashboard
from health import run_all_checks, render_health_banner
from database import purge_old_records
from pages import (
    generate_report, officer_profiles as officer_profiles_page,
    redactor as redactor_page,
    compliance as compliance_page,
    audit as audit_page,
    batch as batch_page,
    review as review_page,
    settings as settings_page,
    health_page,
    search as search_page,
    evidence_locker as evidence_locker_page,
    user_management as user_management_page,
)

logger = get_logger("app")


def _get_client_ip() -> str:
    try:
        headers = st.context.headers
        ip = headers.get("X-Forwarded-For", headers.get("X-Real-IP", ""))
        if ip:
            return ip.split(",")[0].strip()
    except Exception:
        pass
    return ""


@st.cache_data(ttl=120, show_spinner=False)
def _ollama_health():
    try:
        _r = _req.get(f"{OLLAMA_BASE_URL}/api/version", timeout=3)
        return _r.status_code == 200
    except Exception:
        return False


st.set_page_config(
    page_title="Chronos - LE Report Assistance",
    page_icon="\U0001F6A8",
    layout="wide",
    initial_sidebar_state="expanded",
)

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(COMPLETED_DIR, exist_ok=True)
os.makedirs(EVIDENCE_DIR, exist_ok=True)


def _cleanup_temp_files():
    now = _time.time()
    for f in os.listdir(TEMP_DIR):
        fp = os.path.join(TEMP_DIR, f)
        if os.path.isfile(fp) and (now - os.path.getmtime(fp)) > 600:
            try:
                os.remove(fp)
            except Exception:
                pass


def init_session_state() -> None:
    now = _time.time()
    if st.session_state.get('authenticated_officer'):
        last = st.session_state.get('_last_activity', 0)
        if now - last > SESSION_TIMEOUT_SECONDS:
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
    st.session_state['_last_activity'] = now

    defaults = {
        'authenticated_officer': None,
        'officer_id': None,
        'video_path': None,
        'pdf_path': None,
        'cad_data': None,
        'transcript': None,
        'generated_report': None,
        'original_ai_draft': None,
        'compliance_warnings': None,
        'missing_fields': None,
        'probable_cause': None,
        'case_number': f"INC-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}-{secrets.token_hex(2).upper()}",
        'redact_input_text': '',
        'report_snapshots': [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if '_health_checked' not in st.session_state:
        st.session_state['_health_checks'] = run_all_checks()
        st.session_state['_health_checked'] = True
    now = _time.time()
    last = st.session_state.get('_last_cleanup', 0)
    if now - last > 300:
        _cleanup_temp_files()
        st.session_state['_last_cleanup'] = now


# --- LOGIN ---
def login_gate() -> bool:
    st.session_state['_purge_checked'] = st.session_state.get('_purge_checked', False)
    if not st.session_state['_purge_checked']:
        st.session_state['_purge_checked'] = True
        purged = purge_old_records()
        if purged:
            logger.info("Data retention: purged %d old records", purged)

    if st.session_state['authenticated_officer']:
        return True
    inject_css()
    render_health_banner(st.session_state.get('_health_checks', []))
    badge = badge_html(80)
    st.markdown(f"""<div class="login-wrapper"><div class="login-card">
    <div style="display:flex;justify-content:center;margin-bottom:20px;">{badge}</div>
    <div class="login-heading">Chronos Narrative Engine</div>
    <div class="login-sub">Law Enforcement Report Assistance Program</div>
    </div></div>""", unsafe_allow_html=True)
    _, center, _ = st.columns([1, 2, 1])
    with center:
        login_tab, register_tab = st.tabs(["Sign In", "Register"])
        with login_tab:
            officer_name = st.text_input("Officer Name", key="login_name", placeholder="Full name")
            officer_id = st.text_input("Badge Number", key="login_id", placeholder="Badge ID")
            password = st.text_input("Password", key="login_pw", type="password", placeholder="Password")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("Authenticate", type="primary", use_container_width=True, key="login_btn"):
                if officer_name and officer_id and password:
                    client_ip = _get_client_ip()
                    if authenticate_officer(officer_name, officer_id, password, client_ip):
                        st.session_state['authenticated_officer'] = officer_name
                        st.session_state['officer_id'] = officer_id
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
                else:
                    st.error("All fields required")
        with register_tab:
            reg_name = st.text_input("Full Name", key="reg_name", placeholder="Officer name")
            reg_id = st.text_input("Badge Number", key="reg_id", placeholder="Badge ID")
            reg_pw = st.text_input("Password", key="reg_pw", type="password", placeholder="Choose a password")
            if reg_pw:
                score = sum([
                    len(reg_pw) >= 8,
                    any(c.isupper() for c in reg_pw),
                    any(c.islower() for c in reg_pw),
                    any(c.isdigit() for c in reg_pw),
                    any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in reg_pw),
                ])
                colors = ["#ef4444","#f97316","#eab308","#22c55e","#22c55e"]
                labels = ["Very Weak","Weak","Fair","Strong","Very Strong"]
                pct = (score / 5) * 100
                st.markdown(f"""<div style="margin:-8px 0 4px 0;height:4px;background:#1e293b;border-radius:2px;"><div style="width:{pct}%;height:100%;background:{colors[score-1 if score>0 else 0]};border-radius:2px;transition:width 0.3s;"></div></div><div style="font-size:0.6rem;color:{colors[score-1 if score>0 else 0]};margin-bottom:4px;">{labels[score-1 if score>0 else 0]}</div>""", unsafe_allow_html=True)
            reg_pw2 = st.text_input("Confirm Password", key="reg_pw2", type="password", placeholder="Confirm password")
            if st.button("Register", use_container_width=True, key="reg_btn"):
                if reg_name and reg_id and reg_pw:
                    if reg_pw != reg_pw2:
                        st.error("Passwords do not match")
                    elif officer_exists(reg_id):
                        st.error("Badge ID already registered")
                    else:
                        success, msg = register_officer(reg_name, reg_id, reg_pw)
                        if success:
                            st.success("Registered! Sign in with your credentials.")
                        elif msg:
                            st.error(msg)
                else:
                    st.error("All fields required")
    return False


# --- SIDEBAR ---
def render_sidebar() -> str:
    with st.sidebar:
        badge = badge_sm_html(30)
        st.markdown(f"""<div class="sidebar-dept">{badge}<h3>Chronos</h3><p>Dispatch &bull; Records &bull; Reports</p></div>""", unsafe_allow_html=True)
        officer_name_h = h(st.session_state['authenticated_officer'])
        officer_id_h = h(st.session_state['officer_id'])
        initials = ''.join(w[0] for w in st.session_state['authenticated_officer'].split()[:2]).upper()
        st.markdown(f"""<div class="sidebar-user"><div class="avatar">{h(initials)}</div><div>
        <div class="name">{officer_name_h}</div>
        <div class="badge-id">Badge #{officer_id_h}</div></div></div>""", unsafe_allow_html=True)
        role = get_officer_role(st.session_state.get('officer_id', ''))
        st.session_state['_user_role'] = role
        nav_items = ["Dashboard", "Report Generation", "Search Reports", "Evidence Locker", "Batch Queue", "Officer Profiles", "PII Redactor", "AI Compliance", "Audit Trail"]
        if role in ('supervisor', 'admin'):
            nav_items.insert(1, "Supervisor Review")
        if role == 'admin':
            nav_items.append("Settings")
            nav_items.append("User Management")
            nav_items.append("Health")
        nav = st.radio("Navigation", nav_items, key="nav_mode", label_visibility="collapsed")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        theme = st.session_state.get("_theme", "dark")
        new_theme = "light" if theme == "dark" else "dark"
        label = "Light Mode" if theme == "dark" else "Dark Mode"
        if st.button(label, use_container_width=True, key="theme_toggle_btn"):
            st.session_state["_theme"] = new_theme
            st.rerun()

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        if role in ('supervisor', 'admin'):
            counts = get_review_counts()
            pending = counts.get('pending', 0)
            if pending > 0:
                st.markdown(
                    f"""<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;margin-bottom:8px;
                    border:1px solid #f59e0b33;border-radius:6px;background:#f59e0b0a;">
                    <span style="font-size:0.7rem;">&#128276;</span>
                    <span style="font-size:0.68rem;font-weight:600;color:#fbbf24;">{pending} pending review(s)</span>
                    </div>""",
                    unsafe_allow_html=True,
                )

        st.markdown("<div class='card-header'>Recent Reports</div>", unsafe_allow_html=True)
        recent = get_officer_history(st.session_state['authenticated_officer'], limit=8)
        if recent:
            for r in recent:
                ts = r['submission_timestamp'][:16].replace('T', ' ')
                mod = '<span class="ar-mod ar-mod-yes">edited</span>' if r.get('was_modified_by_human') else '<span class="ar-mod ar-mod-no">as drafted</span>'
                st.markdown(f"""<div class="recent-item"><div><span class="ri-id">{h(r['incident_id'])}</span> <span class="ri-type">{h(r['document_type'])}</span></div><div><span class="ri-time">{ts}</span> {mod}</div></div>""", unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size:0.62rem;opacity:0.3;padding:6px;'>No reports yet</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        ollama_ok = _ollama_health()
        status_color = "#22c55e" if ollama_ok else "#ef4444"
        status_text = "Online" if ollama_ok else "Ollama Offline"
        st.markdown("<div class='status-label'>System</div>", unsafe_allow_html=True)
        st.markdown(f"""<div class="status-indicator" style="border-color:{status_color}33;background:{status_color}0a;"><div class="status-dot" style="background:{status_color};box-shadow:0 0 8px {status_color}99,0 0 16px {status_color}44;"></div><div class="status-text" style="color:{status_color};">{status_text}</div></div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button("Sign Out", use_container_width=True, key="logout_btn"):
            st.session_state.clear()
            st.rerun()
    return nav


def _inject_keyboard_shortcuts() -> None:
    st.components.v1.html(
        """
<script>
(function() {
    function findButton(text) {
        var btns = window.parent.document.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {
            if (btns[i].textContent.indexOf(text) !== -1) {
                return btns[i];
            }
        }
        return null;
    }
    window.parent.document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            var btn = findButton('Generate Narrative');
            if (btn) btn.click();
        }
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            var btn = findButton('Submit to Audit');
            if (btn && !btn.disabled) btn.click();
        }
    });
})();
</script>
        """,
        height=0,
    )


def main() -> None:
    inject_css()
    _inject_keyboard_shortcuts()
    init_session_state()
    if not login_gate():
        return
    nav = render_sidebar()
    if nav == "Dashboard":
        mode_dashboard()
    elif nav == "Report Generation":
        generate_report.render()
    elif nav == "Supervisor Review":
        review_page.render()
    elif nav == "Search Reports":
        search_page.render()
    elif nav == "Evidence Locker":
        evidence_locker_page.render()
    elif nav == "Batch Queue":
        batch_page.render()
    elif nav == "Officer Profiles":
        officer_profiles_page.render()
    elif nav == "PII Redactor":
        redactor_page.render()
    elif nav == "AI Compliance":
        compliance_page.render()
    elif nav == "Audit Trail":
        audit_page.render()
    elif nav == "Settings":
        settings_page.render()
    elif nav == "User Management":
        user_management_page.render()
    elif nav == "Health":
        health_page.render()


if __name__ == '__main__':
    try:
        main()
    finally:
        cleanup_pipeline()


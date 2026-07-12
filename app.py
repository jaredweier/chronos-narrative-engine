import streamlit as st
import os
import tempfile
from datetime import datetime
from pathlib import Path
from html import escape as h
import re as _re
import time as _time
import requests as _req

from redactor import sanitize_pii_content, get_redaction_report, REDACTION_CATEGORIES
from pdf_parser import parse_zuercher_pdf
from transcriber import transcribe_bodycam, cleanup_transcriber
from nibrs_checker import (
    check_nibrs_compliance, format_compliance_report, get_compliance_summary,
    suggest_missing_fields, check_probable_cause,
)
from profiler import (
    save_style_sample, get_style_examples, get_all_officers,
    get_officer_categories, REPORT_CATEGORIES,
    extract_text_from_file, SUPPORTED_SAMPLE_EXTENSIONS,
)
from database import initialize_database, log_submission, get_officer_history, get_incident, get_statistics, get_recent_corrections
from export import (
    export_report_docx, export_report_pdf,
    export_compliance_docx, export_compliance_pdf,
)
from narrative_generator import generate_narrative
from phrase_book import (
    add_phrase, get_phrases, get_phrase_categories,
    use_phrase, delete_phrase, search_phrases,
    save_snapshot, get_snapshots, initialize_phrase_book,
)
from templates import get_template, get_template_sections, render_template_prompt
from config import TEMP_DIR, COMPLETED_DIR, CUSTOM_CATEGORIES_FILE, MAX_UPLOAD_SIZE_BYTES
from pipeline_manager import submit_pdf_and_transcribe, cleanup_pipeline
from auth import authenticate_officer, register_officer, officer_exists
from compliance_content import (
    get_compliance_html as _compliance_html,
    get_compliance_text as _compliance_text,
    get_compliance_docx_sections,
    get_compliance_pdf_elements,
)

st.set_page_config(
    page_title="Chronos - LE Report Assistance",
    page_icon="\U0001F6A8",
    layout="wide",
    initial_sidebar_state="expanded",
)

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(COMPLETED_DIR, exist_ok=True)


def _safe_filename(name: str) -> str:
    return _re.sub(r'[^\w\-.]', '_', os.path.basename(name))


def _cleanup_temp_files():
    now = _time.time()
    for f in os.listdir(TEMP_DIR):
        fp = os.path.join(TEMP_DIR, f)
        if os.path.isfile(fp) and (now - os.path.getmtime(fp)) > 3600:
            try:
                os.remove(fp)
            except Exception:
                pass


def _load_custom_categories():
    cats = list(REPORT_CATEGORIES)
    if os.path.exists(CUSTOM_CATEGORIES_FILE):
        with open(CUSTOM_CATEGORIES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and line not in cats:
                    cats.append(line)
    return cats


def _save_custom_category(category: str):
    cats = _load_custom_categories()
    if category not in cats:
        with open(CUSTOM_CATEGORIES_FILE, 'a', encoding='utf-8') as f:
            f.write(category + '\n')

BADGE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" width="Wpx" height="Hpx">
<defs>
<linearGradient id="shA" x1="0%" y1="0%" x2="0%" y2="100%">
<stop offset="0%" stop-color="#94a3b8"/>
<stop offset="50%" stop-color="#64748b"/>
<stop offset="100%" stop-color="#475569"/>
</linearGradient>
<linearGradient id="acA" x1="0%" y1="0%" x2="0%" y2="100%">
<stop offset="0%" stop-color="#3b82f6"/>
<stop offset="100%" stop-color="#1d4ed8"/>
</linearGradient>
</defs>
<polygon points="100,4 190,40 190,130 100,236 10,130 10,40" fill="url(#shA)" stroke="#94a3b8" stroke-width="2"/>
<polygon points="100,18 178,48 178,126 100,224 22,126 22,48" fill="none" stroke="#e2e8f0" stroke-width="1" opacity="0.35"/>
<circle cx="100" cy="96" r="30" fill="none" stroke="#e2e8f0" stroke-width="1.5"/>
<circle cx="100" cy="96" r="22" fill="url(#acA)" opacity="0.85"/>
<text x="100" y="107" text-anchor="middle" font-family="serif" font-size="34" font-weight="bold" fill="white">&#9878;</text>
<text x="100" y="160" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="700" fill="#94a3b8" letter-spacing="0.15em">CHRONOS</text>
<rect x="50" y="170" width="100" height="1.5" fill="#3b82f6" opacity="0.5"/>
<text x="100" y="190" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#64748b" letter-spacing="0.12em">NARRATIVE ENGINE</text>
</svg>"""

BADGE_SVG_SM = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" width="Wpx" height="Hpx">
<defs>
<linearGradient id="shB" x1="0%" y1="0%" x2="0%" y2="100%">
<stop offset="0%" stop-color="#94a3b8"/>
<stop offset="100%" stop-color="#475569"/>
</linearGradient>
</defs>
<polygon points="100,4 190,40 190,130 100,236 10,130 10,40" fill="url(#shB)" stroke="#94a3b8" stroke-width="2"/>
<circle cx="100" cy="88" r="26" fill="none" stroke="#e2e8f0" stroke-width="1.2"/>
<text x="100" y="98" text-anchor="middle" font-family="serif" font-size="30" font-weight="bold" fill="white">&#9878;</text>
<text x="100" y="148" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="700" fill="#94a3b8" letter-spacing="0.15em">CHRONOS</text>
</svg>"""


CUSTOM_CSS = r"""
<style>
.block-container { padding-top: 0.5rem !important; padding-bottom: 1rem !important; }
section[data-testid="stSidebar"] > div { padding-top: 0.75rem !important; }

/* -- Header -- */
.dept-header {
    background: linear-gradient(180deg, #0c1220 0%, #111b2e 100%);
    border-bottom: 1px solid #1e293b;
    padding: 12px 24px;
    margin: 0 -1rem 16px -1rem;
    display: flex; align-items: center; gap: 14px;
    position: relative;
}
.dept-header::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0;
    height: 2px; background: linear-gradient(90deg, transparent, #3b82f6, transparent);
}
.dept-info h1 { margin: 0 !important; font-size: 1rem !important; letter-spacing: 0.07em; text-transform: uppercase; color: #e2e8f0; }
.dept-info p  { margin: 2px 0 0 !important; font-size: 0.58rem !important; text-transform: uppercase; letter-spacing: 0.16em; opacity: 0.4; }

/* -- Case bar -- */
.case-bar {
    background: linear-gradient(90deg, rgba(59,130,246,0.05), rgba(59,130,246,0.02));
    border: 1px solid rgba(59,130,246,0.15); border-left: 3px solid #3b82f6;
    border-radius: 0 6px 6px 0; padding: 9px 16px; margin-bottom: 16px;
    display: flex; justify-content: space-between; align-items: center;
    font-size: 0.7rem; color: #94a3b8; font-family: 'Courier New', monospace;
}
.case-bar .cl { opacity: 0.45; text-transform: uppercase; letter-spacing: 0.1em; font-family: sans-serif; }
.case-bar .cv { color: #60a5fa; font-weight: 700; }

/* -- Login -- */
.login-wrapper { display: flex; justify-content: center; align-items: center; min-height: 80vh; }
.login-card {
    width: 420px; padding: 48px 40px 40px;
    border: 1px solid #1e293b; border-radius: 12px;
    box-shadow: 0 24px 64px rgba(0,0,0,0.55); text-align: center;
    background: linear-gradient(180deg, #0f172a, #0b1120); position: relative;
}
.login-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, #3b82f6, transparent); border-radius: 12px 12px 0 0; }
.login-heading { font-size: 1.12rem; font-weight: 700; margin-bottom: 4px !important; letter-spacing: 0.05em; color: #e2e8f0; }
.login-sub { font-size: 0.56rem; text-transform: uppercase; letter-spacing: 0.22em; opacity: 0.35; margin-bottom: 32px !important; }

/* -- Sidebar -- */
.sidebar-dept { padding: 14px; margin-bottom: 14px; background: linear-gradient(135deg, rgba(59,130,246,0.06), rgba(59,130,246,0.01)); border: 1px solid rgba(59,130,246,0.12); border-radius: 8px; text-align: center; }
.sidebar-dept h3 { margin: 0 !important; font-size: 0.78rem !important; text-transform: uppercase; letter-spacing: 0.12em; color: #60a5fa !important; }
.sidebar-dept p  { margin: 3px 0 0 !important; font-size: 0.55rem !important; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.35; }
.sidebar-user { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid #1e293b; border-radius: 8px; margin-bottom: 14px; background: rgba(15,23,42,0.5); }
.sidebar-user .avatar { width: 32px; height: 32px; border-radius: 6px; background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.7rem; flex-shrink: 0; }
.sidebar-user .name { font-size: 0.78rem; font-weight: 600; }
.sidebar-user .badge-id { font-size: 0.58rem; opacity: 0.4; font-family: monospace; }

.status-indicator { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border: 1px solid rgba(34,197,94,0.2); border-radius: 8px; background: rgba(34,197,94,0.04); margin-bottom: 14px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,0.6), 0 0 16px rgba(34,197,94,0.3); animation: pulse-glow 2s ease-in-out infinite; flex-shrink: 0; }
@keyframes pulse-glow { 0%,100%{box-shadow:0 0 6px rgba(34,197,94,0.5),0 0 12px rgba(34,197,94,0.2)} 50%{box-shadow:0 0 10px rgba(34,197,94,0.8),0 0 20px rgba(34,197,94,0.4)} }
.status-text { font-size: 0.72rem; font-weight: 600; color: #22c55e; text-transform: uppercase; letter-spacing: 0.1em; }
.status-label { font-size: 0.58rem; opacity: 0.4; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }

/* -- Card headers -- */
.card-header { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.45; margin-bottom: 10px; padding-bottom: 7px; border-bottom: 1px solid #1e293b; display: flex; align-items: center; gap: 8px; }
.card-header::before { content: ''; display: inline-block; width: 3px; height: 12px; background: #3b82f6; border-radius: 2px; flex-shrink: 0; }
.card-highlight { border: 1px solid #1e293b; border-left: 3px solid #3b82f6; border-radius: 0 6px 6px 0; padding: 10px 14px; margin-bottom: 6px; background: rgba(59,130,246,0.03); }

/* -- Metrics -- */
.metric { border: 1px solid #1e293b; border-radius: 8px; padding: 18px; text-align: center; background: rgba(15,23,42,0.4); }
.metric-val { font-size: 1.8rem; font-weight: 700; color: #60a5fa !important; line-height: 1; }
.metric-label { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.12em; opacity: 0.4; margin-top: 6px; }

/* -- Badges -- */
.badge-pass { display: inline-flex; align-items: center; gap: 8px; background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.25); border-radius: 6px; padding: 10px 16px; font-size: 0.78rem; font-weight: 600; color: #22c55e; }
.badge-fail { display: inline-flex; align-items: center; gap: 8px; background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.25); border-radius: 6px; padding: 10px 16px; font-size: 0.78rem; font-weight: 600; color: #ef4444; }

/* -- Empty states -- */
.empty-state { text-align: center; padding: 48px 24px; border: 1px dashed #1e293b; border-radius: 8px; }
.empty-state .icon { font-size: 36px; margin-bottom: 14px; opacity: 0.2; }
.empty-state .title { font-size: 0.82rem; font-weight: 600; opacity: 0.6; margin-bottom: 4px !important; }
.empty-state .desc  { font-size: 0.7rem; opacity: 0.3; }

/* -- Redaction -- */
.redact-item { padding: 7px 12px; border: 1px solid #1e293b; border-radius: 4px; margin-bottom: 4px; font-size: 0.72rem; font-family: monospace; background: rgba(15,23,42,0.3); }
.redact-orig { color: #f87171; text-decoration: line-through; opacity: 0.8; }
.redact-new  { color: #4ade80; font-weight: 600; }

/* -- Export -- */
.export-panel { background: rgba(59,130,246,0.04); border: 1px solid rgba(59,130,246,0.12); border-radius: 8px; padding: 14px 16px; margin-bottom: 14px; }
.export-panel .export-label { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.45; margin-bottom: 10px; }

/* -- Compliance document (white paper look) -- */
.compliance-wrap { max-width: 820px; margin: 0 auto; }
.compliance-paper { background: #ffffff; color: #1a1a1a; border-radius: 2px; padding: 48px 56px; box-shadow: 0 4px 24px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,255,255,0.05); font-family: 'Times New Roman', Times, serif; font-size: 13px; line-height: 1.7; }
.compliance-paper .cp-header { text-align: center; border-bottom: 2px solid #1e3a8a; padding-bottom: 20px; margin-bottom: 28px; }
.compliance-paper .cp-header h2 { font-size: 16px; text-transform: uppercase; letter-spacing: 0.06em; margin: 12px 0 4px 0; color: #1e3a8a; }
.compliance-paper .cp-header .cp-sub { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.15em; }
.compliance-paper .cp-header .cp-meta { font-size: 11px; color: #64748b; margin-top: 6px; }
.compliance-paper p { margin: 0 0 10px 0; }
.compliance-paper h4 { font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: #1e3a8a; margin: 18px 0 6px 0; padding-bottom: 4px; border-bottom: 1px solid #e2e8f0; }
.compliance-paper ul { margin: 0 0 8px 0; padding-left: 22px; }
.compliance-paper li { font-size: 12px; line-height: 1.7; margin-bottom: 3px; }
.compliance-paper .cp-footer { border-top: 1px solid #cbd5e1; margin-top: 28px; padding-top: 12px; font-size: 10px; color: #94a3b8; text-align: center; }
.compliance-paper .cp-badge { display: flex; justify-content: center; margin-bottom: 8px; }

/* -- Phrase book -- */
.phrase-card { border: 1px solid #1e293b; border-radius: 6px; padding: 10px 14px; margin-bottom: 6px; background: rgba(15,23,42,0.3); cursor: pointer; transition: border-color 0.15s; }
.phrase-card:hover { border-color: #3b82f6; }
.phrase-card .ph-label { font-size: 0.74rem; font-weight: 600; color: #94a3b8; margin-bottom: 3px; }
.phrase-card .ph-text { font-size: 0.68rem; color: #64748b; line-height: 1.5; max-height: 3.6em; overflow: hidden; }
.phrase-card .ph-meta { font-size: 0.56rem; opacity: 0.3; margin-top: 4px; }

/* -- Suggestions / PC -- */
.suggest-item { border: 1px solid rgba(251,191,36,0.2); border-left: 3px solid #f59e0b; border-radius: 0 6px 6px 0; padding: 10px 14px; margin-bottom: 6px; background: rgba(251,191,36,0.03); }
.suggest-item .si-elem { font-size: 0.72rem; font-weight: 600; color: #f59e0b; text-transform: uppercase; letter-spacing: 0.04em; }
.suggest-item .si-text { font-size: 0.7rem; color: #94a3b8; margin-top: 3px; }
.pc-strong { border: 1px solid rgba(34,197,94,0.25); border-left: 3px solid #22c55e; border-radius: 0 6px 6px 0; padding: 10px 14px; margin-bottom: 6px; background: rgba(34,197,94,0.03); }
.pc-weak { border: 1px solid rgba(239,68,68,0.25); border-left: 3px solid #ef4444; border-radius: 0 6px 6px 0; padding: 10px 14px; margin-bottom: 6px; background: rgba(239,68,68,0.03); }

/* -- Audit trail -- */
.audit-row { border: 1px solid #1e293b; border-radius: 6px; padding: 12px 16px; margin-bottom: 8px; background: rgba(15,23,42,0.3); display: flex; justify-content: space-between; align-items: center; }
.audit-row .ar-id { font-family: monospace; font-size: 0.74rem; color: #60a5fa; font-weight: 600; }
.audit-row .ar-type { font-size: 0.68rem; color: #94a3b8; }
.audit-row .ar-time { font-size: 0.62rem; opacity: 0.35; font-family: monospace; }
.audit-row .ar-mod { display: inline-block; font-size: 0.56rem; padding: 2px 6px; border-radius: 3px; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }
.ar-mod-yes { background: rgba(251,191,36,0.12); color: #f59e0b; }
.ar-mod-no  { background: rgba(34,197,94,0.08); color: #22c55e; }

/* -- Recent reports -- */
.recent-item { display: flex; justify-content: space-between; align-items: center; padding: 7px 10px; border: 1px solid #1e293b; border-radius: 4px; margin-bottom: 4px; font-size: 0.66rem; cursor: pointer; transition: border-color 0.15s; }
.recent-item:hover { border-color: #3b82f6; }
.recent-item .ri-id { font-family: monospace; color: #60a5fa; font-weight: 600; }
.recent-item .ri-type { color: #64748b; }
.recent-item .ri-time { color: #475569; font-family: monospace; font-size: 0.58rem; }
</style>
"""


def inject_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def badge_html(size=60):
    return BADGE_SVG.replace("Wpx", str(size)).replace("Hpx", str(int(size * 1.2)))


def badge_sm_html(size=36):
    return BADGE_SVG_SM.replace("Wpx", str(size)).replace("Hpx", str(int(size * 1.2)))


def _case_bar_html(case_no: str):
    now = datetime.now().strftime("%Y-%m-%d &nbsp; %H:%M:%S")
    return f"""<div class="case-bar"><span><span class="cl">Case No.</span> <span class="cv">{h(case_no)}</span></span><span><span class="cl">Timestamp</span> <span class="cv">{now}</span></span></div>"""


def init_session_state():
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
        'case_number': f"INC-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}",
        'redact_input_text': '',
        'report_snapshots': [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if '_db_initialized' not in st.session_state:
        initialize_database()
        initialize_phrase_book()
        st.session_state['_db_initialized'] = True
    _cleanup_temp_files()


# --- LOGIN ---
def login_gate():
    if st.session_state['authenticated_officer']:
        return True
    inject_css()
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
                    if authenticate_officer(officer_name, officer_id, password):
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
            reg_pw2 = st.text_input("Confirm Password", key="reg_pw2", type="password", placeholder="Confirm password")
            if st.button("Register", use_container_width=True, key="reg_btn"):
                if reg_name and reg_id and reg_pw:
                    if reg_pw != reg_pw2:
                        st.error("Passwords do not match")
                    elif officer_exists(reg_id):
                        st.error("Badge ID already registered")
                    else:
                        if register_officer(reg_name, reg_id, reg_pw):
                            st.success("Registered! Sign in with your credentials.")
                        else:
                            st.error("Registration failed")
                else:
                    st.error("All fields required")
    return False


# --- HEADER ---
def render_department_header():
    badge = badge_sm_html(38)
    st.markdown(f"""<div class="dept-header"><div>{badge}</div><div class="dept-info">
    <h1>Chronos Narrative Engine</h1>
    <p>Law Enforcement Report Assistance Program &bull; CJIS Compliant</p>
    </div></div>""", unsafe_allow_html=True)


# --- SIDEBAR ---
def render_sidebar():
    with st.sidebar:
        badge = badge_sm_html(30)
        st.markdown(f"""<div class="sidebar-dept">{badge}<h3>Chronos</h3><p>Dispatch &bull; Records &bull; Reports</p></div>""", unsafe_allow_html=True)
        officer_name_h = h(st.session_state['authenticated_officer'])
        officer_id_h = h(st.session_state['officer_id'])
        initials = ''.join(w[0] for w in st.session_state['authenticated_officer'].split()[:2]).upper()
        st.markdown(f"""<div class="sidebar-user"><div class="avatar">{h(initials)}</div><div>
        <div class="name">{officer_name_h}</div>
        <div class="badge-id">Badge #{officer_id_h}</div></div></div>""", unsafe_allow_html=True)
        nav = st.radio("Navigation", ["Report Generation", "Officer Profiles", "PII Redactor", "AI Compliance", "Audit Trail"], key="nav_mode", label_visibility="collapsed")
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

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

        # Ollama health check
        try:
            _r = _req.get("http://localhost:11434/api/tags", timeout=3)
            ollama_ok = _r.status_code == 200
        except Exception:
            ollama_ok = False
        status_color = "#22c55e" if ollama_ok else "#ef4444"
        status_text = "Online" if ollama_ok else "Ollama Offline"
        st.markdown("<div class='status-label'>System</div>", unsafe_allow_html=True)
        st.markdown(f"""<div class="status-indicator" style="border-color:{status_color}33;background:{status_color}0a;"><div class="status-dot" style="background:{status_color};box-shadow:0 0 8px {status_color}99,0 0 16px {status_color}44;"></div><div class="status-text" style="color:{status_color};">{status_text}</div></div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button("Sign Out", use_container_width=True, key="logout_btn"):
            st.session_state.clear()
            st.rerun()
    return nav


# --- EXPORT BUTTONS ---
def _render_export_buttons(report_text, label="report", key_prefix="rpt"):
    st.markdown("<div class='export-panel'><div class='export-label'>Export Options</div></div>", unsafe_allow_html=True)
    officer = st.session_state['authenticated_officer']
    badge_num = st.session_state['officer_id']
    case_no = st.session_state.get('case_number', 'INC-UNKNOWN')

    cache_key = f"{key_prefix}_exports"
    if cache_key not in st.session_state or st.session_state.get(f"{key_prefix}_text") != report_text:
        st.session_state[f"{key_prefix}_docx"] = export_report_docx(report_text, officer, badge_num, case_no)
        st.session_state[f"{key_prefix}_pdf"] = export_report_pdf(report_text, officer, badge_num, case_no)
        st.session_state[f"{key_prefix}_text"] = report_text

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("\U0001F4C4  Word (.docx)", data=st.session_state[f"{key_prefix}_docx"], file_name=f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key=f"{key_prefix}_docx")
    with c2:
        st.download_button("\U0001F4D1  PDF", data=st.session_state[f"{key_prefix}_pdf"], file_name=f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf", mime="application/pdf", use_container_width=True, key=f"{key_prefix}_pdf")
    with c3:
        st.download_button("\U0001F4DD  Text (.txt)", data=report_text, file_name=f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", mime="text/plain", use_container_width=True, key=f"{key_prefix}_txt")


# --- REPORT GENERATION ---
def mode_generate_report():
    try:
        render_department_header()

        case_col, ts_col = st.columns([3, 1])
        with case_col:
            case_val = st.text_input("Case Number", value=st.session_state.get('case_number', ''), key="case_number_input", placeholder="e.g. INC-20260711-143022", label_visibility="collapsed")
            if case_val:
                st.session_state['case_number'] = case_val
        with ts_col:
            st.markdown(f"<div style='font-size:0.7rem;color:#64748b;font-family:monospace;padding-top:6px;text-align:right;'>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)

        st.markdown(_case_bar_html(st.session_state.get('case_number', '\u2014')), unsafe_allow_html=True)

        col_left, col_right = st.columns([5, 7], gap="large")

        with col_left:
            st.markdown("<div class='card-header'>Evidence Upload</div>", unsafe_allow_html=True)

            pdf_file = st.file_uploader("Zuercher CAD Report", type=['pdf'], key="pdf_uploader")
            video_file = st.file_uploader("Body Camera Footage", type=['mp4', 'mov', 'avi', 'mkv'], key="video_uploader", help="Supports files up to 10 GB")

            if pdf_file:
                save_name = _safe_filename(pdf_file.name)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', dir=TEMP_DIR) as tmp:
                    tmp.write(pdf_file.read())
                    st.session_state['pdf_path'] = tmp.name
                st.success(f"CAD loaded: {pdf_file.name}")

            if video_file:
                CHUNK_SIZE = 8 * 1024 * 1024
                save_name = _safe_filename(video_file.name)
                save_path = os.path.join(TEMP_DIR, save_name + '.video')
                with open(save_path, 'wb') as f:
                    while True:
                        chunk = video_file.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                st.session_state['video_path'] = save_path
                st.success(f"Body cam loaded: {video_file.name}")
                st.video(st.session_state['video_path'])

            has_evidence = st.session_state.get('pdf_path') or st.session_state.get('video_path')

            if has_evidence:
                if st.button("Process Evidence", type="primary", use_container_width=True, key="process_btn"):
                    with st.spinner("Processing evidence..."):
                        cad_result, transcript_result = None, None
                        if st.session_state.get('pdf_path') and st.session_state.get('video_path'):
                            cad_result, transcript_result = submit_pdf_and_transcribe(
                                st.session_state['pdf_path'], st.session_state['video_path']
                            )
                        elif st.session_state.get('pdf_path'):
                            cad_result = parse_zuercher_pdf(st.session_state['pdf_path'])
                        elif st.session_state.get('video_path'):
                            transcript_result = transcribe_bodycam(st.session_state['video_path'])
                            cleanup_transcriber()
                        if cad_result is not None:
                            st.session_state['cad_data'] = cad_result
                        if transcript_result is not None:
                            st.session_state['transcript'] = transcript_result
                    st.success("Evidence processed")
                    st.rerun()

            st.markdown("<div class='card-header' style='margin-top:16px;'>Or Enter Notes Directly</div>", unsafe_allow_html=True)
            custom_notes = st.text_area("Additional Notes", height=120, key="custom_notes_input", placeholder="Type any additional notes, observations, or incident details here...", label_visibility="collapsed")

            st.markdown("<div class='card-header' style='margin-top:12px;'>Report Category</div>", unsafe_allow_html=True)
            all_categories = _load_custom_categories()
            report_type = st.selectbox("Category", all_categories, key="report_type_select", label_visibility="collapsed")

            template = get_template(report_type)
            if template:
                with st.expander(f"Template: {report_type}", expanded=False):
                    st.markdown(f"<div style='font-size:0.68rem;opacity:0.5;margin-bottom:8px;'>{h(template['description'])}</div>", unsafe_allow_html=True)
                    for title, hint in template["sections"]:
                        st.markdown(f"**{h(title)}** — <span style='font-size:0.66rem;opacity:0.4;'>{h(hint)}</span>", unsafe_allow_html=True)
                    use_tpl = st.checkbox("Include template structure in prompt", value=False, key="use_template_chk")
                if use_tpl:
                    st.session_state['_template_prompt'] = render_template_prompt(report_type)
                else:
                    st.session_state.pop('_template_prompt', None)

            st.markdown("<div class='card-header' style='margin-top:16px;'>Phrase Book</div>", unsafe_allow_html=True)
            officer = st.session_state['authenticated_officer']
            pb_cats = get_phrase_categories(officer)
            if pb_cats:
                pb_filter = st.selectbox("Filter", ["All"] + pb_cats, key="pb_filter", label_visibility="collapsed")
                phrases = get_phrases(officer, category=None if pb_filter == "All" else pb_filter)
                for ph in phrases[:6]:
                    st.markdown(f"""<div class="phrase-card" title="{h(ph['phrase_text'][:200])}"><div class="ph-label">{h(ph['label'])}</div><div class="ph-text">{h(ph['phrase_text'][:120])}{'...' if len(ph['phrase_text']) > 120 else ''}</div><div class="ph-meta">Used {ph['use_count']}x</div></div>""", unsafe_allow_html=True)
                pb_query = st.text_input("Search phrases", key="pb_search", placeholder="Search...", label_visibility="collapsed")
                if pb_query:
                    results = search_phrases(officer, pb_query)
                    for ph in results[:4]:
                        if st.button(f"Insert: {ph['label']}", key=f"pb_ins_{ph['id']}"):
                            use_phrase(ph['id'])
                            current = st.session_state.get('custom_notes_input', '')
                            st.session_state['custom_notes_input'] = current + "\n\n" + ph['phrase_text'] if current else ph['phrase_text']
                            st.rerun()
            else:
                st.markdown("<div style='font-size:0.62rem;opacity:0.3;padding:4px;'>No phrases saved yet. Add them in Officer Profiles.</div>", unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            with st.expander("Save New Phrase", expanded=False):
                ph_label = st.text_input("Label", key="new_ph_label", placeholder="e.g. 'Opening statement'")
                ph_text = st.text_area("Phrase text", key="new_ph_text", height=80, placeholder="Type the phrase or boilerplate text...")
                ph_cat = st.text_input("Category", key="new_ph_cat", value="General", placeholder="e.g. 'DUI', 'Domestic'")
                if st.button("Save Phrase", key="save_ph_btn"):
                    if ph_label and ph_text:
                        add_phrase(officer, ph_label, ph_text, ph_cat)
                        st.success(f"Saved: {ph_label}")
                        st.rerun()

            if st.button("Generate Narrative", type="primary", use_container_width=True, key="gen_narrative_btn"):
                cad_text = ""
                if st.session_state.get('cad_data'):
                    cad = st.session_state['cad_data']
                    cad_text = f"Call ID: {cad.call_id}\nType: {cad.call_type}\nLocation: {cad.location}\nDispatch: {cad.dispatch_time}\nArrival: {cad.arrival_time}\nCleared: {cad.clear_time}"
                    if cad.involved_parties:
                        cad_text += "\nInvolved parties: " + "; ".join(f"{p.name} (DOB:{p.dob}, {p.sex}, Age {p.age})" for p in cad.involved_parties)
                    if cad.raw_text:
                        cad_text += f"\n\nFull CAD text:\n{cad.raw_text}"

                transcript_text = sanitize_pii_content(st.session_state.get('transcript', ''))
                notes = sanitize_pii_content(custom_notes) if custom_notes else ""

                if not cad_text and not transcript_text and not notes:
                    st.warning("Provide CAD data, body cam footage, or notes to generate a narrative.")
                else:
                    with st.spinner("Generating narrative with LLM..."):
                        examples = get_style_examples(st.session_state['authenticated_officer'], report_type)
                        tpl_prompt = st.session_state.pop('_template_prompt', None)

                        corrections = get_recent_corrections(
                            st.session_state['authenticated_officer'], report_type, limit=3
                        )
                        correction_text = ""
                        if corrections:
                            correction_text = "\n\n--- PREVIOUS CORRECTIONS (learn from these edits) ---\n"
                            for c in corrections[:2]:
                                if c.get('final_approved_report') and c.get('unedited_ai_draft'):
                                    correction_text += f"Original AI draft:\n{c['unedited_ai_draft'][:1000]}\n"
                                    correction_text += f"Officer corrected to:\n{c['final_approved_report'][:1000]}\n---\n"

                        combined_notes = ""
                        if tpl_prompt:
                            combined_notes += tpl_prompt + "\n\n"
                        combined_notes += notes
                        if correction_text:
                            combined_notes += correction_text

                        narrative = generate_narrative(
                            cad_text=cad_text,
                            transcript=transcript_text,
                            officer_style_examples=examples,
                            custom_notes=combined_notes,
                            report_type=report_type,
                        )
                        if narrative.startswith("[ERROR]"):
                            st.error(f"LLM Error: {narrative}")
                        else:
                            st.session_state['generated_report'] = narrative
                            st.session_state['original_ai_draft'] = narrative
                            save_snapshot(st.session_state['case_number'], st.session_state['authenticated_officer'], narrative, "AI Draft")
                    with st.spinner("Running compliance checks..."):
                        warnings = check_nibrs_compliance(report_type, narrative if not narrative.startswith("[ERROR]") else "")
                        st.session_state['compliance_warnings'] = warnings
                        st.session_state['missing_fields'] = suggest_missing_fields(report_type, narrative if not narrative.startswith("[ERROR]") else "")
                        st.session_state['probable_cause'] = check_probable_cause(narrative if not narrative.startswith("[ERROR]") else "")
                    st.rerun()

            if st.session_state.get('transcript'):
                with st.expander("Transcript", expanded=False):
                    st.code(st.session_state['transcript'], language=None)


        with col_right:
            if st.session_state.get('cad_data'):
                st.markdown("<div class='card-header'>Extracted CAD Data</div>", unsafe_allow_html=True)
                cad = st.session_state['cad_data']
                cad_df = {'Field': ['Call ID', 'Type', 'Location', 'Dispatch', 'Arrival', 'Cleared'], 'Value': [cad.call_id, cad.call_type, cad.location, cad.dispatch_time, cad.arrival_time, cad.clear_time]}
                st.data_editor(cad_df, use_container_width=True, hide_index=True, disabled=True)
                if cad.involved_parties:
                    for party in cad.involved_parties:
                        st.markdown(f"<div class='card-highlight'><strong>{h(party.name)}</strong> &mdash; DOB {h(party.dob)} &bull; {h(party.sex)} &bull; Age {h(str(party.age))}</div>", unsafe_allow_html=True)
                if any('?' in str(v) or '!' in str(v) for v in [cad.call_id, cad.call_type, cad.location]):
                    st.warning("Low-confidence OCR detected \u2014 verify fields before submission")

            if st.session_state.get('compliance_warnings'):
                warnings = st.session_state['compliance_warnings']
                summary = get_compliance_summary(warnings)
                if summary['is_compliant']:
                    st.markdown("<div class='badge-pass'>&#10003; NIBRS Compliant</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='badge-fail'>&#10007; NIBRS Issues &mdash; {summary['critical_count']} critical, {summary['warning_count']} warnings</div>", unsafe_allow_html=True)
                with st.expander("Compliance Details"):
                    st.code(format_compliance_report(warnings))

            if st.session_state.get('missing_fields'):
                mf = st.session_state['missing_fields']
                if mf:
                    st.markdown("<div class='card-header' style='margin-top:8px;'>Suggested Additions</div>", unsafe_allow_html=True)
                    for item in mf:
                        st.markdown(f"""<div class="suggest-item"><div class="si-elem">{h(item.get('element', '').replace('_', ' '))}</div><div class="si-text">{h(item.get('suggestion', ''))}</div></div>""", unsafe_allow_html=True)

            if st.session_state.get('probable_cause'):
                pc = st.session_state['probable_cause']
                strength = pc.get('strength', 'unknown')
                strength_colors = {'strong': '#22c55e', 'adequate': '#f59e0b', 'weak': '#ef4444', 'insufficient': '#ef4444', 'unknown': '#64748b'}
                sc = strength_colors.get(strength, '#64748b')
                st.markdown(f"<div class='card-header' style='margin-top:8px;'>Probable Cause Analysis</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border:1px solid {sc}33;border-radius:6px;background:{sc}0a;margin-bottom:8px;'><span style='font-size:0.72rem;font-weight:600;color:{sc};text-transform:uppercase;'>{h(strength)}</span></div>", unsafe_allow_html=True)
                if pc.get('factors_present'):
                    for f in pc['factors_present']:
                        st.markdown(f"""<div class="pc-strong"><span style="font-size:0.7rem;color:#22c55e;">&#10003;</span> <span style="font-size:0.68rem;color:#94a3b8;">{h(f)}</span></div>""", unsafe_allow_html=True)
                if pc.get('factors_missing'):
                    for f in pc['factors_missing']:
                        st.markdown(f"""<div class="pc-weak"><span style="font-size:0.7rem;color:#ef4444;">&#10007;</span> <span style="font-size:0.68rem;color:#94a3b8;">{h(f)}</span></div>""", unsafe_allow_html=True)
                if pc.get('recommendations'):
                    with st.expander("Recommendations"):
                        for r in pc['recommendations']:
                            st.markdown(f"- {r}")
                if pc.get('legal_notes'):
                    st.info(pc['legal_notes'])

            if st.session_state.get('generated_report'):
                st.markdown("<div class='card-header'>Generated Narrative</div>", unsafe_allow_html=True)
                st.session_state['generated_report'] = st.text_area(
                    "Report", value=st.session_state['generated_report'],
                    height=400, key="report_editor", label_visibility="collapsed",
                )
                _render_export_buttons(st.session_state['generated_report'], label="incident_report", key_prefix="rpt")
                verified = st.checkbox(
                    "I have reviewed this report and attest that the information is accurate to the best of my knowledge. I accept full professional and legal responsibility for this submission.",
                    key="verification_checkbox"
                )
                if st.button("Submit to Audit Trail", type="primary", use_container_width=True, key="submit_audit", disabled=not verified):
                    log_submission(
                        incident_id=st.session_state.get('case_number', 'UNKNOWN'),
                        officer_name=st.session_state['authenticated_officer'],
                        document_type=report_type,
                        ai_draft=st.session_state.get('original_ai_draft', ''),
                        final_report=st.session_state['generated_report'],
                        was_modified=(st.session_state['generated_report'] != st.session_state.get('original_ai_draft', '')),
                        verified=verified,
                    )
                    save_snapshot(st.session_state['case_number'], st.session_state['authenticated_officer'], st.session_state['generated_report'], "Final Submitted")
                    st.success("Report submitted to audit trail")
            elif not st.session_state.get('cad_data'):
                st.markdown("""<div class="empty-state"><div class="icon">&#128203;</div>
                <div class="title">No Report Generated Yet</div>
                <div class="desc">Upload evidence and click Generate Narrative, or enter notes directly on the left</div>
                </div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.exception(e)


# --- OFFICER PROFILES ---
def mode_configure_officer_style():
    try:
        render_department_header()
        col1, col2 = st.columns([5, 7], gap="large")

        with col1:
            st.markdown("<div class='card-header'>Upload Style Samples</div>", unsafe_allow_html=True)
            officer_name = st.text_input("Officer Name", key="style_officer_name", placeholder="e.g. Det. Johnson")
            all_categories = _load_custom_categories()
            category = st.selectbox("Report Category", all_categories, key="style_category")

            st.markdown("<div style='margin-top:4px;margin-bottom:8px;font-size:0.65rem;opacity:0.4;text-transform:uppercase;letter-spacing:0.08em;'>Add Custom Category</div>", unsafe_allow_html=True)
            new_cat_col, add_col = st.columns([3, 1])
            with new_cat_col:
                new_cat = st.text_input("New category", key="new_cat_input", placeholder="e.g. Theft Report", label_visibility="collapsed")
            with add_col:
                if st.button("Add", key="add_cat_btn", use_container_width=True):
                    if new_cat and new_cat.strip():
                        _save_custom_category(new_cat.strip())
                        st.success(f"Added: {new_cat.strip()}")
                        st.rerun()

            uploaded_files = st.file_uploader("Report Samples", type=['txt', 'pdf', 'docx'], accept_multiple_files=True, key="style_files", help="5-10 redacted reports per officer per category")

            if uploaded_files and officer_name:
                st.info(f"{len(uploaded_files)} file(s) ready")
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                if st.button("Save Samples", type="primary", use_container_width=True, key="save_samples_btn"):
                    saved_count = 0
                    errors = []
                    for file in uploaded_files:
                        try:
                            ext = Path(file.name).suffix.lower()
                            if ext in SUPPORTED_SAMPLE_EXTENSIONS:
                                safe_fn = _safe_filename(file.name)
                                save_path = os.path.join(TEMP_DIR, safe_fn)
                                file_bytes = file.read()
                                with open(save_path, 'wb') as f:
                                    f.write(file_bytes)
                                content = extract_text_from_file(save_path)
                                if content and content.strip():
                                    safe_name = "".join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in file.name)
                                    save_style_sample(officer_name, category, content, safe_name)
                                    saved_count += 1
                                else:
                                    errors.append(f"{file.name}: no text extracted")
                                if os.path.exists(save_path):
                                    os.remove(save_path)
                            else:
                                errors.append(f"{file.name}: unsupported type")
                        except Exception as e:
                            errors.append(f"{file.name}: {e}")
                    if saved_count:
                        st.success(f"Saved {saved_count} sample(s) for {officer_name}")
                    for err in errors:
                        st.warning(err)
                    st.rerun()

        with col2:
            st.markdown("<div class='card-header'>Existing Profiles</div>", unsafe_allow_html=True)
            officers = get_all_officers()
            if officers:
                selected_officer = st.selectbox("Officer", officers, key="view_officer", label_visibility="collapsed")
                categories = get_officer_categories(selected_officer)
                if categories:
                    selected_cat = st.selectbox("Category", categories, key="view_cat")
                    examples = get_style_examples(selected_officer, selected_cat)
                    st.markdown(f"""<div class="metric"><div class="metric-val">{len(examples)}</div><div class="metric-label">Style Samples</div></div>""", unsafe_allow_html=True)
                    for i, example in enumerate(examples):
                        with st.expander(f"Sample {i+1}", expanded=False):
                            st.text(example[:800] + ("..." if len(example) > 800 else ""))
                else:
                    st.info("No categories configured")
            else:
                st.markdown("""<div class="empty-state"><div class="icon">&#128100;</div>
                <div class="title">No Profiles Yet</div><div class="desc">Upload samples to build officer writing profiles</div></div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.exception(e)


# --- PII REDACTOR ---
def mode_standalone_redactor():
    try:
        render_department_header()

        st.markdown("<div class='card-header'>Select What to Redact</div>", unsafe_allow_html=True)
        cat_cols = st.columns(4)
        selected_cats = set()
        for idx, (cat_id, cat_info) in enumerate(REDACTION_CATEGORIES.items()):
            col = cat_cols[idx % 4]
            with col:
                if st.checkbox(cat_info["label"], value=True, key=f"cat_{cat_id}", help=cat_info["description"]):
                    selected_cats.add(cat_id)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.markdown("<div class='card-header'>Original Text</div>", unsafe_allow_html=True)

            uploaded_doc = st.file_uploader(
                "Upload a document to redact",
                type=['txt', 'pdf', 'docx'],
                key="redact_file_upload",
                label_visibility="collapsed",
            )

            if uploaded_doc:
                try:
                    safe_fn = _safe_filename(uploaded_doc.name)
                    save_path = os.path.join(TEMP_DIR, safe_fn)
                    file_data = uploaded_doc.read()
                    with open(save_path, 'wb') as f:
                        f.write(file_data)
                    content = extract_text_from_file(save_path)
                    if os.path.exists(save_path):
                        os.remove(save_path)
                    if content and content.strip():
                        st.session_state['redact_input_text'] = content
                        st.rerun()
                    else:
                        st.warning("Could not extract text from file")
                except Exception as e:
                    st.error(f"Error reading file: {e}")

            input_val = st.session_state.get('redact_input_text', '')
            original_text = st.text_area(
                "Input",
                value=input_val,
                height=380,
                key="redact_original",
                label_visibility="collapsed",
                placeholder="Paste report text here, or upload a document above...",
            )

            if st.button("Redact PII", type="primary", use_container_width=True, key="redact_btn"):
                text_to_redact = original_text if original_text.strip() else st.session_state.get('redact_input_text', '')
                if text_to_redact.strip():
                    redacted = sanitize_pii_content(text_to_redact, selected_cats)
                    st.session_state['redacted_text'] = redacted
                    st.session_state['redaction_changes'] = get_redaction_report(text_to_redact, redacted)
                    st.rerun()
                else:
                    st.warning("Paste some text or upload a file first")

        with col2:
            st.markdown("<div class='card-header'>Redacted Output</div>", unsafe_allow_html=True)
            if st.session_state.get('redacted_text'):
                redacted_content = st.session_state['redacted_text']
                st.text_area("Output", value=redacted_content, height=340, disabled=True, key="redact_output", label_visibility="collapsed")

                if st.session_state.get('redaction_changes'):
                    with st.expander(f"{len(st.session_state['redaction_changes'])} PII items redacted", expanded=True):
                        for orig, red in st.session_state['redaction_changes']:
                            st.markdown(f"""<div class="redact-item"><span class="redact-orig">{h(orig[:80])}</span> &rarr; <span class="redact-new">{h(red[:80])}</span></div>""", unsafe_allow_html=True)

                st.markdown("<div class='export-panel'><div class='export-label'>Download Redacted File</div></div>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.download_button(
                        "\U0001F4C4  Word (.docx)",
                        data=export_report_docx(redacted_content, st.session_state['authenticated_officer'], st.session_state['officer_id'], f"REDACTED-{datetime.now().strftime('%Y%m%d')}", report_type="Redacted Report"),
                        file_name=f"redacted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key="redact_dl_docx",
                    )
                with c2:
                    st.download_button(
                        "\U0001F4D1  PDF",
                        data=export_report_pdf(redacted_content, st.session_state['authenticated_officer'], st.session_state['officer_id'], f"REDACTED-{datetime.now().strftime('%Y%m%d')}", report_type="Redacted Report"),
                        file_name=f"redacted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="redact_dl_pdf",
                    )
                with c3:
                    st.download_button(
                        "\U0001F4DD  Text (.txt)",
                        data=redacted_content,
                        file_name=f"redacted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key="redact_dl_txt",
                    )
            else:
                st.markdown("""<div class="empty-state"><div class="icon">&#128274;</div>
                <div class="title">No Text to Redact</div><div class="desc">Upload a document or paste text on the left</div></div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.exception(e)


# --- AI COMPLIANCE ---


def mode_ai_compliance():
    try:
        render_department_header()
        officer = st.session_state['authenticated_officer']
        badge_num = st.session_state['officer_id']
        doc_html = _compliance_html(officer, badge_num)
        compliance_text = _compliance_text(officer, badge_num)
        st.markdown(doc_html, unsafe_allow_html=True)
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button("\U0001F4C4  Word (.docx)", data=export_compliance_docx(officer, badge_num), file_name=f"ai_compliance_{datetime.now().strftime('%Y%m%d')}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, type="primary", key="cx_docx")
        with col2:
            st.download_button("\U0001F4D1  PDF", data=export_compliance_pdf(officer, badge_num), file_name=f"ai_compliance_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", use_container_width=True, key="cx_pdf")
        with col3:
            st.download_button("\U0001F4DD  Text (.txt)", data=compliance_text, file_name=f"ai_compliance_{datetime.now().strftime('%Y%m%d')}.txt", mime="text/plain", use_container_width=True, key="cx_txt")
    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.exception(e)


# --- AUDIT TRAIL ---
def mode_audit_trail():
    try:
        render_department_header()

        stats = get_statistics()
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="metric"><div class="metric-val">{stats['total_submissions']}</div><div class="metric-label">Total Submissions</div></div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="metric"><div class="metric-val">{stats['human_modified']}</div><div class="metric-label">Human Modified</div></div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="metric"><div class="metric-val">{stats['verified']}</div><div class="metric-label">Verified</div></div>""", unsafe_allow_html=True)
        with m4:
            types = len(stats.get('by_document_type', {}))
            st.markdown(f"""<div class="metric"><div class="metric-val">{types}</div><div class="metric-label">Report Types</div></div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        col_list, col_detail = st.columns([5, 7], gap="large")

        with col_list:
            st.markdown("<div class='card-header'>Submission History</div>", unsafe_allow_html=True)
            search_id = st.text_input("Search by Case ID", key="audit_search", placeholder="INC-20260711...")
            from database import get_db_connection
            with get_db_connection() as conn:
                if search_id:
                    rows = conn.execute(
                        "SELECT * FROM legal_audit_logs WHERE incident_id LIKE ? ORDER BY submission_timestamp DESC LIMIT 50",
                        (f"%{search_id}%",)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM legal_audit_logs ORDER BY submission_timestamp DESC LIMIT 50"
                    ).fetchall()
            if rows:
                for row in rows:
                    r = dict(row)
                    ts = r['submission_timestamp'][:16].replace('T', ' ')
                    ver = ' &#10003;' if r.get('verification_signature_flag') else ''
                    st.markdown(f"""<div class="audit-row"><div><div class="ar-id">{h(r['incident_id'])}{ver}</div><div class="ar-type">{h(r['document_type'])} &bull; {h(r['officer_name'])}</div></div><div><span class="ar-mod {'ar-mod-yes' if r.get('was_modified_by_human') else 'ar-mod-no'}">{'modified' if r.get('was_modified_by_human') else 'as drafted'}</span><div class="ar-time">{ts}</div></div></div>""", unsafe_allow_html=True)
            else:
                st.markdown("""<div class="empty-state"><div class="icon">&#128196;</div>
                <div class="title">No Records Found</div><div class="desc">Submissions will appear here</div></div>""", unsafe_allow_html=True)

        with col_detail:
            st.markdown("<div class='card-header'>Record Detail</div>", unsafe_allow_html=True)
            detail_id = st.text_input("Enter Case ID to View", key="audit_detail_id", placeholder="INC-20260711-143022")
            if detail_id:
                record = get_incident(detail_id)
                if record:
                    ts = record['submission_timestamp'][:19].replace('T', ' ')
                    mod_str = "Yes" if record.get('was_modified_by_human') else "No"
                    ver_str = "Yes" if record.get('verification_signature_flag') else "No"
                    st.markdown(f"""<div class="card-highlight">
                    <strong>{h(record['incident_id'])}</strong><br>
                    <span style="font-size:0.68rem;color:#64748b;">Officer: {h(record['officer_name'])} &bull; Badge: {h(record.get('officer_id', 'N/A'))}<br>
                    Type: {h(record['document_type'])} &bull; Submitted: {ts}<br>
                    Modified: {mod_str} &bull; Verified: {ver_str}</span>
                    </div>""", unsafe_allow_html=True)
                    if record.get('unedited_ai_draft') and record.get('final_approved_report'):
                        with st.expander("AI Draft vs Final Report", expanded=False):
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("<div style='font-size:0.68rem;font-weight:600;color:#94a3b8;margin-bottom:4px;'>AI DRAFT</div>", unsafe_allow_html=True)
                                st.text_area("AI Draft", value=record['unedited_ai_draft'], height=300, disabled=True, key="audit_ai_draft", label_visibility="collapsed")
                            with c2:
                                st.markdown("<div style='font-size:0.68rem;font-weight:600;color:#94a3b8;margin-bottom:4px;'>FINAL REPORT</div>", unsafe_allow_html=True)
                                st.text_area("Final Report", value=record['final_approved_report'], height=300, disabled=True, key="audit_final", label_visibility="collapsed")
                    elif record.get('final_approved_report'):
                        st.text_area("Report", value=record['final_approved_report'], height=300, disabled=True, key="audit_report_only", label_visibility="collapsed")

                    snapshots = get_snapshots(detail_id)
                    if snapshots:
                        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                        with st.expander(f"Version History ({len(snapshots)} snapshots)"):
                            for snap in snapshots:
                                snap_ts = snap['created_at'][:16].replace('T', ' ')
                                st.markdown(f"<div style='font-size:0.66rem;color:#64748b;margin-bottom:4px;'><strong>{h(snap['snapshot_label'])}</strong> &mdash; {snap_ts}</div>", unsafe_allow_html=True)
                                st.text_area(f"snap_{snap['id']}", value=snap['snapshot_text'], height=120, disabled=True, key=f"audit_snap_{snap['id']}", label_visibility="collapsed")
                else:
                    st.info("No record found for that Case ID")
    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.exception(e)


# --- MAIN ---
def main():
    inject_css()
    init_session_state()
    if not login_gate():
        return
    nav = render_sidebar()
    if nav == "Report Generation":
        mode_generate_report()
    elif nav == "Officer Profiles":
        mode_configure_officer_style()
    elif nav == "PII Redactor":
        mode_standalone_redactor()
    elif nav == "AI Compliance":
        mode_ai_compliance()
    elif nav == "Audit Trail":
        mode_audit_trail()


if __name__ == '__main__':
    main()


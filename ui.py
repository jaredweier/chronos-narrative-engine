import streamlit as st
import os
from datetime import datetime
from html import escape as h
from config import TEMP_DIR, COMPLETED_DIR, CUSTOM_CATEGORIES_FILE
from profiler import REPORT_CATEGORIES
from logger import get_logger

logger = get_logger(__name__)

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


THEME_CSS = r"""
<style>
:root {
    --bg-body: #0b1120;
    --bg-card: #0f172a;
    --bg-card-alt: rgba(15,23,42,0.4);
    --bg-hover: rgba(59,130,246,0.03);
    --bg-sidebar: #0f172a;
    --bg-login: #0f172a;
    --bg-login-gradient: linear-gradient(180deg, #0f172a, #0b1120);
    --bg-header: linear-gradient(180deg, #0c1220 0%, #111b2e 100%);
    --bg-export: rgba(59,130,246,0.04);
    --bg-phrase: rgba(15,23,42,0.3);
    --bg-audit: rgba(15,23,42,0.3);
    --bg-recent: transparent;
    --bg-metric: rgba(15,23,42,0.4);
    --bg-empty: transparent;
    --bg-suggest: rgba(251,191,36,0.03);
    --bg-pc-strong: rgba(34,197,94,0.03);
    --bg-pc-weak: rgba(239,68,68,0.03);
    --bg-badge-pass: rgba(34,197,94,0.08);
    --bg-badge-fail: rgba(239,68,68,0.08);
    --bg-mod-yes: rgba(251,191,36,0.12);
    --bg-mod-no: rgba(34,197,94,0.08);
    --border-color: #1e293b;
    --border-subtle: rgba(59,130,246,0.15);
    --border-light: rgba(59,130,246,0.12);
    --border-accent: rgba(59,130,246,0.15);
    --border-amber: rgba(251,191,36,0.2);
    --border-green: rgba(34,197,94,0.25);
    --border-red: rgba(239,68,68,0.25);
    --border-dash: #1e293b;
    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --text-dim: #475569;
    --text-accent: #60a5fa;
    --text-amber: #f59e0b;
    --text-green: #22c55e;
    --text-red: #ef4444;
    --text-blue: #3b82f6;
    --text-redact-orig: #f87171;
    --text-redact-new: #4ade80;
    --shadow: 0 24px 64px rgba(0,0,0,0.55);
    --heading-border: #1e293b;
    --accent-glow: rgba(34,197,94,0.6);
    --accent-glow-50: rgba(34,197,94,0.5);
    --accent-glow-80: rgba(34,197,94,0.8);
    --scrollbar-bg: #1e293b;
    --scrollbar-thumb: #334155;
    --status-green: #22c55e;
    --status-red: #ef4444;
}

[data-theme="light"] {
    --bg-body: #f1f5f9;
    --bg-card: #ffffff;
    --bg-card-alt: rgba(255,255,255,0.6);
    --bg-hover: rgba(59,130,246,0.04);
    --bg-sidebar: #ffffff;
    --bg-login: #ffffff;
    --bg-login-gradient: linear-gradient(180deg, #ffffff, #f8fafc);
    --bg-header: linear-gradient(180deg, #ffffff, #f8fafc);
    --bg-export: rgba(59,130,246,0.05);
    --bg-phrase: #f8fafc;
    --bg-audit: #f8fafc;
    --bg-recent: #f8fafc;
    --bg-metric: #f8fafc;
    --bg-empty: transparent;
    --bg-suggest: rgba(251,191,36,0.05);
    --bg-pc-strong: rgba(34,197,94,0.05);
    --bg-pc-weak: rgba(239,68,68,0.05);
    --bg-badge-pass: rgba(34,197,94,0.1);
    --bg-badge-fail: rgba(239,68,68,0.1);
    --bg-mod-yes: rgba(251,191,36,0.15);
    --bg-mod-no: rgba(34,197,94,0.1);
    --border-color: #e2e8f0;
    --border-subtle: rgba(59,130,246,0.2);
    --border-light: rgba(59,130,246,0.18);
    --border-accent: rgba(59,130,246,0.2);
    --border-amber: rgba(251,191,36,0.3);
    --border-green: rgba(34,197,94,0.3);
    --border-red: rgba(239,68,68,0.3);
    --border-dash: #cbd5e1;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #64748b;
    --text-dim: #94a3b8;
    --text-accent: #2563eb;
    --text-amber: #d97706;
    --text-green: #16a34a;
    --text-red: #dc2626;
    --text-blue: #2563eb;
    --text-redact-orig: #dc2626;
    --text-redact-new: #16a34a;
    --shadow: 0 4px 24px rgba(0,0,0,0.08);
    --heading-border: #e2e8f0;
    --accent-glow: rgba(22,163,74,0.4);
    --accent-glow-50: rgba(22,163,74,0.3);
    --accent-glow-80: rgba(22,163,74,0.5);
    --scrollbar-bg: #e2e8f0;
    --scrollbar-thumb: #cbd5e1;
    --status-green: #16a34a;
    --status-red: #dc2626;
}

.block-container { padding-top: 0.5rem !important; padding-bottom: 1rem !important; }
section[data-testid="stSidebar"] > div { padding-top: 0.75rem !important; }
.stApp { background: var(--bg-body); color: var(--text-primary); }
section[data-testid="stSidebar"] { background: var(--bg-sidebar); }
section[data-testid="stSidebar"] .st-emotion-cache,
section[data-testid="stSidebar"] [data-testid="baseButton-secondary"] { color: var(--text-primary); }
.stTextInput input, .stTextArea textarea, .stSelectbox, .stMultiSelect, .stNumberInput {
    background: var(--bg-card) !important; color: var(--text-primary) !important; border-color: var(--border-color) !important;
}

/* -- Header -- */
.dept-header {
    background: var(--bg-header);
    border-bottom: 1px solid var(--border-color);
    padding: 12px 24px;
    margin: 0 -1rem 16px -1rem;
    display: flex; align-items: center; gap: 14px;
    position: relative;
}
.dept-header::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0;
    height: 2px; background: linear-gradient(90deg, transparent, var(--text-blue), transparent);
}
.dept-info h1 { margin: 0 !important; font-size: 1rem !important; letter-spacing: 0.07em; text-transform: uppercase; color: var(--text-primary); }
.dept-info p  { margin: 2px 0 0 !important; font-size: 0.58rem !important; text-transform: uppercase; letter-spacing: 0.16em; opacity: 0.4; }

/* -- Case bar -- */
.case-bar {
    background: linear-gradient(90deg, rgba(59,130,246,0.05), rgba(59,130,246,0.02));
    border: 1px solid var(--border-accent); border-left: 3px solid var(--text-blue);
    border-radius: 0 6px 6px 0; padding: 9px 16px; margin-bottom: 16px;
    display: flex; justify-content: space-between; align-items: center;
    font-size: 0.7rem; color: var(--text-secondary); font-family: 'Courier New', monospace;
}
.case-bar .cl { opacity: 0.45; text-transform: uppercase; letter-spacing: 0.1em; font-family: sans-serif; }
.case-bar .cv { color: var(--text-accent); font-weight: 700; }

/* -- Login -- */
.login-wrapper { display: flex; justify-content: center; align-items: center; min-height: 80vh; }
.login-card {
    width: 420px; padding: 48px 40px 40px;
    border: 1px solid var(--border-color); border-radius: 12px;
    box-shadow: var(--shadow); text-align: center;
    background: var(--bg-login-gradient); position: relative;
}
.login-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, var(--text-blue), transparent); border-radius: 12px 12px 0 0; }
.login-heading { font-size: 1.12rem; font-weight: 700; margin-bottom: 4px !important; letter-spacing: 0.05em; color: var(--text-primary); }
.login-sub { font-size: 0.56rem; text-transform: uppercase; letter-spacing: 0.22em; opacity: 0.35; margin-bottom: 32px !important; }

/* -- Sidebar -- */
.sidebar-dept { padding: 14px; margin-bottom: 14px; background: linear-gradient(135deg, rgba(59,130,246,0.06), rgba(59,130,246,0.01)); border: 1px solid var(--border-light); border-radius: 8px; text-align: center; }
.sidebar-dept h3 { margin: 0 !important; font-size: 0.78rem !important; text-transform: uppercase; letter-spacing: 0.12em; color: var(--text-accent) !important; }
.sidebar-dept p  { margin: 3px 0 0 !important; font-size: 0.55rem !important; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.35; }
.sidebar-user { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 14px; background: var(--bg-card-alt); }
.sidebar-user .avatar { width: 32px; height: 32px; border-radius: 6px; background: linear-gradient(135deg, var(--text-blue), #1d4ed8); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.7rem; flex-shrink: 0; }
.sidebar-user .name { font-size: 0.78rem; font-weight: 600; color: var(--text-primary); }
.sidebar-user .badge-id { font-size: 0.58rem; opacity: 0.4; font-family: monospace; }

.status-indicator { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border: 1px solid rgba(34,197,94,0.2); border-radius: 8px; background: rgba(34,197,94,0.04); margin-bottom: 14px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--status-green); box-shadow: 0 0 8px var(--accent-glow), 0 0 16px rgba(34,197,94,0.3); animation: pulse-glow 2s ease-in-out infinite; flex-shrink: 0; }
@keyframes pulse-glow { 0%,100%{box-shadow:0 0 6px var(--accent-glow-50),0 0 12px rgba(34,197,94,0.2)} 50%{box-shadow:0 0 10px var(--accent-glow-80),0 0 20px rgba(34,197,94,0.4)} }
.status-text { font-size: 0.72rem; font-weight: 600; color: var(--status-green); text-transform: uppercase; letter-spacing: 0.1em; }
.status-label { font-size: 0.58rem; opacity: 0.4; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; color: var(--text-primary); }

/* -- Card headers -- */
.card-header { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.45; margin-bottom: 10px; padding-bottom: 7px; border-bottom: 1px solid var(--heading-border); display: flex; align-items: center; gap: 8px; color: var(--text-primary); }
.card-header::before { content: ''; display: inline-block; width: 3px; height: 12px; background: var(--text-blue); border-radius: 2px; flex-shrink: 0; }
.card-highlight { border: 1px solid var(--border-color); border-left: 3px solid var(--text-blue); border-radius: 0 6px 6px 0; padding: 10px 14px; margin-bottom: 6px; background: var(--bg-hover); }

/* -- Metrics -- */
.metric { border: 1px solid var(--border-color); border-radius: 8px; padding: 18px; text-align: center; background: var(--bg-metric); }
.metric-val { font-size: 1.8rem; font-weight: 700; color: var(--text-accent) !important; line-height: 1; }
.metric-label { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.12em; opacity: 0.4; margin-top: 6px; color: var(--text-primary); }

/* -- Badges -- */
.badge-pass { display: inline-flex; align-items: center; gap: 8px; background: var(--bg-badge-pass); border: 1px solid var(--border-green); border-radius: 6px; padding: 10px 16px; font-size: 0.78rem; font-weight: 600; color: var(--text-green); }
.badge-fail { display: inline-flex; align-items: center; gap: 8px; background: var(--bg-badge-fail); border: 1px solid var(--border-red); border-radius: 6px; padding: 10px 16px; font-size: 0.78rem; font-weight: 600; color: var(--text-red); }

/* -- Empty states -- */
.empty-state { text-align: center; padding: 48px 24px; border: 1px dashed var(--border-dash); border-radius: 8px; }
.empty-state .icon { font-size: 36px; margin-bottom: 14px; opacity: 0.2; }
.empty-state .title { font-size: 0.82rem; font-weight: 600; opacity: 0.6; margin-bottom: 4px !important; color: var(--text-primary); }
.empty-state .desc  { font-size: 0.7rem; opacity: 0.3; }

/* -- Redaction -- */
.redact-item { padding: 7px 12px; border: 1px solid var(--border-color); border-radius: 4px; margin-bottom: 4px; font-size: 0.72rem; font-family: monospace; background: var(--bg-card-alt); }
.redact-orig { color: var(--text-redact-orig); text-decoration: line-through; opacity: 0.8; }
.redact-new  { color: var(--text-redact-new); font-weight: 600; }

/* -- Export -- */
.export-panel { background: var(--bg-export); border: 1px solid var(--border-light); border-radius: 8px; padding: 14px 16px; margin-bottom: 14px; }
.export-panel .export-label { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.45; margin-bottom: 10px; color: var(--text-primary); }

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
.phrase-card { border: 1px solid var(--border-color); border-radius: 6px; padding: 10px 14px; margin-bottom: 6px; background: var(--bg-phrase); cursor: pointer; transition: border-color 0.15s; }
.phrase-card:hover { border-color: var(--text-blue); }
.phrase-card .ph-label { font-size: 0.74rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 3px; }
.phrase-card .ph-text { font-size: 0.68rem; color: var(--text-muted); line-height: 1.5; max-height: 3.6em; overflow: hidden; }
.phrase-card .ph-meta { font-size: 0.56rem; opacity: 0.3; margin-top: 4px; }

/* -- Suggestions / PC -- */
.suggest-item { border: 1px solid var(--border-amber); border-left: 3px solid var(--text-amber); border-radius: 0 6px 6px 0; padding: 10px 14px; margin-bottom: 6px; background: var(--bg-suggest); }
.suggest-item .si-elem { font-size: 0.72rem; font-weight: 600; color: var(--text-amber); text-transform: uppercase; letter-spacing: 0.04em; }
.suggest-item .si-text { font-size: 0.7rem; color: var(--text-secondary); margin-top: 3px; }
.pc-strong { border: 1px solid var(--border-green); border-left: 3px solid var(--text-green); border-radius: 0 6px 6px 0; padding: 10px 14px; margin-bottom: 6px; background: var(--bg-pc-strong); }
.pc-weak { border: 1px solid var(--border-red); border-left: 3px solid var(--text-red); border-radius: 0 6px 6px 0; padding: 10px 14px; margin-bottom: 6px; background: var(--bg-pc-weak); }

/* -- Audit trail -- */
.audit-row { border: 1px solid var(--border-color); border-radius: 6px; padding: 12px 16px; margin-bottom: 8px; background: var(--bg-audit); display: flex; justify-content: space-between; align-items: center; }
.audit-row .ar-id { font-family: monospace; font-size: 0.74rem; color: var(--text-accent); font-weight: 600; }
.audit-row .ar-type { font-size: 0.68rem; color: var(--text-secondary); }
.audit-row .ar-time { font-size: 0.62rem; opacity: 0.35; font-family: monospace; }
.audit-row .ar-mod { display: inline-block; font-size: 0.56rem; padding: 2px 6px; border-radius: 3px; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }
.ar-mod-yes { background: var(--bg-mod-yes); color: var(--text-amber); }
.ar-mod-no  { background: var(--bg-mod-no); color: var(--text-green); }

/* -- Recent reports -- */
.recent-item { display: flex; justify-content: space-between; align-items: center; padding: 7px 10px; border: 1px solid var(--border-color); border-radius: 4px; margin-bottom: 4px; font-size: 0.66rem; cursor: pointer; transition: border-color 0.15s; background: var(--bg-recent); }
.recent-item:hover { border-color: var(--text-blue); }
.recent-item .ri-id { font-family: monospace; color: var(--text-accent); font-weight: 600; }
.recent-item .ri-type { color: var(--text-muted); }
.recent-item .ri-time { color: var(--text-dim); font-family: monospace; font-size: 0.58rem; }

/* -- Scrollbar -- */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--scrollbar-bg); }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* -- Mobile responsive -- */
@media (max-width: 768px) {
    .block-container { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
    .dept-header { flex-direction: column; text-align: center; gap: 8px; padding: 10px 12px; margin: 0 -0.5rem 12px -0.5rem; }
    .dept-info h1 { font-size: 0.85rem !important; }
    .login-card { width: 90%; padding: 32px 20px 28px; margin: 0 auto; }
    .metric { padding: 12px 8px; }
    .metric-val { font-size: 1.3rem; }
    section[data-testid="stSidebar"] > div { padding-top: 0.5rem !important; }
    .compliance-paper { padding: 24px 16px; }
    .compliance-paper .cp-header h2 { font-size: 13px; }
    .audit-row { flex-direction: column; align-items: flex-start; gap: 6px; }
    .recent-item { flex-direction: column; align-items: flex-start; gap: 3px; }
}
@media (max-width: 480px) {
    .dept-header { margin: 0 -0.5rem 8px -0.5rem; }
    .login-card { width: 95%; padding: 24px 14px 20px; }
    .login-heading { font-size: 0.95rem; }
    .card-header { font-size: 0.62rem; }
}
</style>
"""


def inject_css():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    current = st.session_state.get("_theme", "dark")
    st.markdown(
        f"""<script>
var t = window.parent.document.documentElement.getAttribute('data-theme');
if (t !== '{current}') {{
    window.parent.document.documentElement.setAttribute('data-theme', '{current}');
}}
</script>""",
        unsafe_allow_html=True,
    )


def badge_html(size=60):
    return BADGE_SVG.replace("Wpx", str(size)).replace("Hpx", str(int(size * 1.2)))


def badge_sm_html(size=36):
    return BADGE_SVG_SM.replace("Wpx", str(size)).replace("Hpx", str(int(size * 1.2)))


def _case_bar_html(case_no: str):
    now = datetime.now().strftime("%Y-%m-%d &nbsp; %H:%M:%S")
    return f"""<div class="case-bar"><span><span class="cl">Case No.</span> <span class="cv">{h(case_no)}</span></span><span><span class="cl">Timestamp</span> <span class="cv">{now}</span></span></div>"""


def render_department_header():
    badge = badge_sm_html(38)
    st.markdown(f"""<div class="dept-header"><div>{badge}</div><div class="dept-info">
    <h1>Chronos Narrative Engine</h1>
    <p>Law Enforcement Report Assistance Program &bull; CJIS Compliant</p>
    </div></div>""", unsafe_allow_html=True)


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


if __name__ == '__main__':
    print("UI module")
    print(f"Categories file: {CUSTOM_CATEGORIES_FILE}")
    cats = _load_custom_categories()
    print(f"Loaded {len(cats)} categories")
    print(f"Badge SVG size: {len(BADGE_SVG)} chars")
    print(f"Theme CSS size: {len(THEME_CSS)} chars")

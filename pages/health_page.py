import streamlit as st
import os
import time
from ui import render_department_header
from health import run_all_checks
from logger import get_logger

logger = get_logger(__name__)


def render():
    try:
        render_department_header()
        st.markdown("<div class='card-header'>System Health</div>", unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("Refresh Checks", type="primary", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        checks = run_all_checks()
        for c in checks:
            color_map = {"ok": "#22c55e", "warning": "#f59e0b", "error": "#ef4444", "info": "#64748b"}
            color = color_map.get(c.severity, "#64748b")
            icon = c.icon()
            st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;padding:12px 16px;border:1px solid {color}33;border-radius:8px;background:{color}0a;margin-bottom:8px;">
            <div style="font-size:1.2rem;">{icon}</div>
            <div style="flex:1;"><div style="font-size:0.78rem;font-weight:600;color:{color};">{c.name}</div>
            <div style="font-size:0.65rem;color:#94a3b8;">{c.message}</div></div>
            <div><span style="font-size:0.58rem;text-transform:uppercase;letter-spacing:0.06em;padding:2px 8px;border-radius:3px;background:{color}22;color:{color};font-weight:600;">{c.severity}</span></div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='card-header'>Logs</div>", unsafe_allow_html=True)
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        if os.path.exists(log_dir):
            log_files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')], reverse=True)[:5]
            for lf in log_files:
                log_path = os.path.join(log_dir, lf)
                size_kb = os.path.getsize(log_path) / 1024
                with st.expander(f"{lf} ({size_kb:.0f} KB)"):
                    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                        tail = f.readlines()[-100:]
                        st.code("".join(tail), language=None)
    except Exception as e:
        logger.exception("Health page error: %s", e)
        st.error(f"Error: {e}")

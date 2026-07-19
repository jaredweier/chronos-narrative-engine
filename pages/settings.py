import streamlit as st
from html import escape as h
from database import backup_database, restore_database, purge_old_records
from ui import render_department_header
from config import DB_PATH, DATA_RETENTION_DAYS, EVIDENCE_DIR, SESSION_TIMEOUT_SECONDS
from auth import get_officer_role
from logger import get_logger
from datetime import datetime
import os

logger = get_logger(__name__)


def render():
    try:
        render_department_header()
        role = get_officer_role(st.session_state.get('officer_id', ''))
        if role != 'admin':
            st.warning("Admin access required.")
            return

        tab_db, tab_retention, tab_linking, tab_evidence = st.tabs(
            ["Database", "Data Retention", "Case Linking", "Evidence Settings"]
        )

        with tab_db:
            st.markdown("<div class='card-header'>Database Administration</div>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div style='font-size:0.72rem;font-weight:600;margin-bottom:8px;'>Backup</div>", unsafe_allow_html=True)
                db_size = os.path.getsize(DB_PATH) / 1024 if os.path.exists(DB_PATH) else 0
                st.markdown(f"<div style='font-size:0.62rem;color:#64748b;margin-bottom:8px;'>Size: {db_size:.0f} KB</div>", unsafe_allow_html=True)
                backup_data = backup_database()
                st.download_button(
                    "Download Backup", data=backup_data,
                    file_name=f"chronos_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                    mime="application/octet-stream", use_container_width=True,
                )
            with col2:
                st.markdown("<div style='font-size:0.72rem;font-weight:600;margin-bottom:8px;'>Restore</div>", unsafe_allow_html=True)
                st.warning("Replaces current database. Auto-backup created.")
                uploaded = st.file_uploader("Upload .db file", type=['db'], key="restore_upload", label_visibility="collapsed")
                if uploaded and st.button("Restore", type="primary", use_container_width=True):
                    if restore_database(uploaded.read()):
                        st.success("Restored. Re-run to apply.")
                    else:
                        st.error("Restore failed")

        with tab_retention:
            st.markdown("<div class='card-header'>Data Retention & Auto-Purge</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:0.65rem;opacity:0.5;margin-bottom:8px;'>Current setting: {DATA_RETENTION_DAYS} days (0 = disabled)</div>", unsafe_allow_html=True)
            if DATA_RETENTION_DAYS > 0:
                st.info(f"Records older than {DATA_RETENTION_DAYS} days will be auto-purged on app startup.")
            if st.button("Purge Old Records Now", type="primary", use_container_width=True):
                purged = purge_old_records(DATA_RETENTION_DAYS)
                if purged > 0:
                    st.success(f"Purged {purged} old record(s)")
                else:
                    st.info("No records to purge")
            st.markdown("<div style='margin-top:12px;font-size:0.65rem;opacity:0.4;'>Set CHRONOS_DATA_RETENTION_DAYS in environment to change the retention period.</div>", unsafe_allow_html=True)

        with tab_linking:
            st.markdown("<div class='card-header'>Case Linking</div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:0.65rem;opacity:0.5;margin-bottom:8px;'>Link related incidents (e.g. one suspect, multiple cases).</div>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                primary = st.text_input("Primary Case ID", key="link_primary", placeholder="INC-20260711-...")
            with c2:
                related = st.text_input("Related Case ID", key="link_related", placeholder="INC-20260711-...")
            with c3:
                relation = st.selectbox("Relation", ["related", "same_suspect", "same_location", "same_incident", "follow_up"], key="link_rel")
            if st.button("Link Cases", use_container_width=True):
                if primary and related:
                    from database import link_cases
                    link_cases(primary, related, relation)
                    st.success(f"Linked {primary} <-> {related}")
                else:
                    st.warning("Both case IDs required")

        with tab_evidence:
            st.markdown("<div class='card-header'>Evidence Storage</div>", unsafe_allow_html=True)
            ev_size = 0
            if os.path.isdir(EVIDENCE_DIR):
                for dirpath, _, filenames in os.walk(EVIDENCE_DIR):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        ev_size += os.path.getsize(fp)
            st.markdown(f"<div style='font-size:0.62rem;color:#64748b;'>Evidence directory: {EVIDENCE_DIR}<br>Total storage: {ev_size / 1024 / 1024:.1f} MB</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='margin-top:8px;font-size:0.65rem;opacity:0.4;'>Session timeout: {SESSION_TIMEOUT_SECONDS}s ({SESSION_TIMEOUT_SECONDS // 60} min)</div>", unsafe_allow_html=True)
    except Exception as e:
        logger.exception("Settings error: %s", e)
        st.error(f"Error: {e}")

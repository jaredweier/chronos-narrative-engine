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

        tab_db, tab_retention, tab_linking, tab_evidence, tab_templates, tab_presets = st.tabs(
            ["Database", "Data Retention", "Case Linking", "Evidence Settings", "Templates & Statutes", "Export Presets"]
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
                if uploaded and st.button("Restore", type="primary", use_container_width=True, key="restore_btn"):
                    st.session_state['_confirm_action'] = 'restore_db'
                if st.session_state.get('_confirm_action') == 'restore_db' and uploaded:
                    confirm = st.text_input("Type CONFIRM to proceed with restore", key="confirm_restore")
                    if st.button("Execute Restore", key="exec_restore"):
                        if confirm == "CONFIRM":
                            if restore_database(uploaded.read()):
                                st.session_state.pop('_confirm_action', None)
                                st.success("Restored. Re-run to apply.")
                                st.rerun()
                            else:
                                st.error("Restore failed")
                        else:
                            st.warning("Type CONFIRM exactly")

        with tab_retention:
            st.markdown("<div class='card-header'>Data Retention & Auto-Purge</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:0.65rem;opacity:0.5;margin-bottom:8px;'>Current setting: {DATA_RETENTION_DAYS} days (0 = disabled)</div>", unsafe_allow_html=True)
            if DATA_RETENTION_DAYS > 0:
                st.info(f"Records older than {DATA_RETENTION_DAYS} days will be auto-purged on app startup.")
            if st.button("Purge Old Records Now", type="primary", use_container_width=True, key="purge_btn"):
                st.session_state['_confirm_action'] = 'purge'
            if st.session_state.get('_confirm_action') == 'purge':
                confirm = st.text_input("Type DELETE to confirm purge", key="confirm_purge")
                if st.button("Execute Purge", key="exec_purge"):
                    if confirm == "DELETE":
                        purged = purge_old_records(DATA_RETENTION_DAYS)
                        st.session_state.pop('_confirm_action', None)
                        if purged > 0:
                            st.success(f"Purged {purged} old record(s)")
                        else:
                            st.info("No records to purge")
                        st.rerun()
                    else:
                        st.warning("Type DELETE exactly")
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

        with tab_templates:
            st.markdown("<div class='card-header'>Report Template Manager</div>", unsafe_allow_html=True)
            with st.expander("Report Template Manager", expanded=True):
                from templates import get_all_templates, save_template, get_all_template_types
                all_tpl = get_all_templates()
                tpl_keys = list(all_tpl.keys())
                selected_tpl = st.selectbox("Current Templates", tpl_keys, key="tpl_selector")
                if selected_tpl and selected_tpl in all_tpl:
                    tpl_data = all_tpl[selected_tpl]
                    st.markdown(f"**Description:** {tpl_data.get('description', '')}")
                    st.markdown("**Sections:**")
                    for title, hint in tpl_data.get("sections", []):
                        st.markdown(f"- **{title}** — {hint}")
                st.markdown("<hr style='margin:12px 0;border-color:#1e293b;'>", unsafe_allow_html=True)
                st.markdown("**New Template**")
                new_key = st.text_input("Key Name", key="new_tpl_key", placeholder="e.g. Traffic Crash Report")
                new_desc = st.text_input("Description", key="new_tpl_desc", placeholder="Description of the template")
                new_sections = st.text_area("Sections (one per line, `Title|Hint` format)", key="new_tpl_sections", height=120, placeholder="Incident Overview|Date/time, location, reporting officer\nResponse|Dispatch and arrival times")
                if st.button("Save Template", key="save_tpl_btn", use_container_width=True):
                    if save_template(new_key, new_desc, new_sections):
                        st.success(f"Template '{new_key}' saved")
                        st.rerun()
                    else:
                        st.warning("Key, description, and sections required")

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            st.markdown("<div class='card-header'>Statute Database Management</div>", unsafe_allow_html=True)
            with st.expander("Statute Database Management", expanded=True):
                from wi_statutes import WI_CRIMINAL_STATUTES, export_statutes_to_json, import_statutes_from_json
                import tempfile, json, os
                st.markdown(f"Current statute count: **{len(WI_CRIMINAL_STATUTES)}**")
                if st.button("Export Statutes to JSON", use_container_width=True, key="export_statutes_btn"):
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w', encoding='utf-8')
                    export_statutes_to_json(tmp.name)
                    with open(tmp.name, 'rb') as f:
                        st.download_button("Download Statutes JSON", data=f, file_name="wi_statutes_export.json", mime="application/json", use_container_width=True, key="dl_statutes")
                    os.unlink(tmp.name)
                uploaded_statutes = st.file_uploader("Import Statutes from JSON", type=['json'], key="statutes_import", label_visibility="collapsed")
                if uploaded_statutes is not None:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='wb')
                    tmp.write(uploaded_statutes.read())
                    tmp.close()
                    imported, total = import_statutes_from_json(tmp.name)
                    os.unlink(tmp.name)
                    st.success(f"Imported {imported} statutes. Total: {total}")
                    st.rerun()

        with tab_presets:
            st.markdown("<div class='card-header'>Export Presets</div>", unsafe_allow_html=True)
            import json
            PRESETS_FILE = os.path.join(os.path.dirname(__file__), "..", "export_presets.json")
            if os.path.exists(PRESETS_FILE):
                with open(PRESETS_FILE, 'r') as f:
                    presets = json.load(f)
            else:
                presets = {}
                
            st.markdown("Current Presets:")
            for k, v in presets.items():
                st.markdown(f"- **{h(k)}**: {v.get('format', 'DOCX')} - Auto-NIBRS: {v.get('auto_nibrs', False)}")
                
            st.markdown("---")
            st.markdown("**New Preset**")
            new_preset_name = st.text_input("Preset Name", placeholder="e.g. Supervisor Review Mode")
            new_preset_format = st.selectbox("Export Format", ["DOCX", "PDF", "TXT", "HTML", "OFFLINE"])
            new_preset_nibrs = st.checkbox("Auto-generate NIBRS XML?")
            
            if st.button("Save Preset", use_container_width=True):
                if new_preset_name:
                    presets[new_preset_name] = {
                        "format": new_preset_format,
                        "auto_nibrs": new_preset_nibrs
                    }
                    with open(PRESETS_FILE, 'w') as f:
                        json.dump(presets, f, indent=2)
                    st.success(f"Preset {new_preset_name} saved.")
                    st.rerun()
                else:
                    st.error("Name is required.")

    except Exception as e:
        logger.exception("Settings error: %s", e)
        st.error(f"Error: {e}")

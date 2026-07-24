import streamlit as st
import os
import tempfile
from html import escape as h
from database import save_evidence_file, get_evidence_files, delete_evidence_file, get_evidence_chain, add_evidence_event
from evidence_store import store_evidence_file, get_evidence_storage_size, list_evidence_files_on_disk
from config import EVIDENCE_DIR, TEMP_DIR
from ui import render_department_header


def render():
    try:
        render_department_header()
        st.markdown("<div class='card-header'>Evidence Locker</div>", unsafe_allow_html=True)

        incident_id = st.text_input(
            "Incident / Case Number",
            value=st.session_state.get('case_number', ''),
            placeholder="e.g. INC-20260711-143022",
            key="ev_incident_id",
        )

        if not incident_id:
            st.markdown(
                """<div class="empty-state"><div class="icon">&#128193;</div>
                <div class="title">Enter a Case Number</div>
                <div class="desc">Type an incident ID above to manage its evidence</div></div>""",
                unsafe_allow_html=True,
            )
            return

        tab_upload, tab_browse, tab_chain = st.tabs(["Upload", "Browse Files", "Chain of Custody"])

        with tab_upload:
            st.markdown("<div class='card-header'>Upload Evidence</div>", unsafe_allow_html=True)
            uploaded_file = st.file_uploader(
                "Select File", label_visibility="collapsed",
                type=['pdf', 'mp4', 'mov', 'avi', 'mkv', 'jpg', 'jpeg', 'png', 'wav', 'mp3', 'docx', 'xlsx', 'txt'],
            )
            if uploaded_file:
                st.markdown(f"**{uploaded_file.name}** ({uploaded_file.size / 1024:.0f} KB)")
                desc = st.text_input("Description", placeholder="e.g. Bodycam #2, Officer's notes scan")
                cat = st.selectbox("Category", ["bodycam", "photo", "audio", "document", "cad_report", "other"], index=5)
                if st.button("Upload to Evidence Locker", type="primary", use_container_width=True):
                    bytes_data = uploaded_file.read()
                    stored_path = store_evidence_file(incident_id, uploaded_file.name, bytes_data)
                    if stored_path:
                        save_evidence_file(
                            incident_id=incident_id,
                            file_name=uploaded_file.name,
                            file_path=stored_path,
                            file_size=uploaded_file.size,
                            mime_type=uploaded_file.type or "application/octet-stream",
                            uploaded_by=st.session_state.get('authenticated_officer', ''),
                            description=desc,
                            category=cat,
                        )
                        add_evidence_event(incident_id, f"EV-{uploaded_file.name[:20]}", f"Uploaded: {desc or uploaded_file.name}",
                                           "Physical Evidence", "Collected",
                                           st.session_state.get('authenticated_officer', ''),
                                           f"Stored at: {stored_path}")
                        st.success(f"Uploaded to {stored_path}")
                        st.rerun()
                    else:
                        st.error("Upload failed")

            storage_size = get_evidence_storage_size(incident_id)
            st.markdown(f"<div style='font-size:0.65rem;opacity:0.4;'>Storage used: {storage_size / 1024:.0f} KB</div>", unsafe_allow_html=True)

        with tab_browse:
            db_files = get_evidence_files(incident_id)
            disk_files = list_evidence_files_on_disk(incident_id)
            total_files = len(db_files) + len(disk_files)
            if total_files == 0:
                st.markdown(
                    """<div class="empty-state"><div class="icon">&#128452;</div>
                    <div class="title">No Evidence Files</div>
                    <div class="desc">Upload files to build a digital evidence locker for this case</div></div>""",
                    unsafe_allow_html=True,
                )
            else:
                for ef in db_files:
                    cols = st.columns([3, 1, 1, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{h(ef['file_name'])}**<br><span style='font-size:0.6rem;opacity:0.4;'>{ef.get('description','')[:60]}</span>", unsafe_allow_html=True)
                    with cols[1]:
                        st.markdown(f"<div style='font-size:0.6rem;opacity:0.4;'>{h(ef['category'])}</div>", unsafe_allow_html=True)
                    with cols[2]:
                        st.markdown(f"<div style='font-size:0.6rem;opacity:0.4;'>{ef['uploaded_at'][:16].replace('T',' ')}</div>", unsafe_allow_html=True)
                    with cols[3]:
                        with st.popover("QR", key=f"qr_pop_{ef['id']}"):
                            st.markdown(f"**Evidence ID:** {h(ef.get('evidence_id', '')) or h(ef['file_name'])}")
                            st.markdown(f"**Incident ID:** {h(incident_id)}")
                            st.markdown(f"**Timestamp:** {ef['uploaded_at'][:16].replace('T',' ')}")
                            st.markdown("---")
                            st.info("Print this label and affix to physical evidence item")
                    with cols[4]:
                        if os.path.exists(ef['file_path']):
                            with open(ef['file_path'], 'rb') as f:
                                st.download_button("DL", data=f, file_name=ef['file_name'],
                                                   key=f"dl_{ef['id']}", use_container_width=True)
                        if st.button("Del", key=f"del_{ef['id']}"):
                            delete_evidence_file(ef['id'])
                            st.rerun()

        with tab_chain:
            chain = get_evidence_chain(incident_id)
            if chain:
                for ev in chain:
                    st.markdown(f"""<div style="border-left:3px solid #334155;padding:6px 12px;margin-bottom:6px;font-size:0.68rem;">
                    <div style="display:flex;gap:8px;align-items:center;">
                    <span style="font-weight:600;">{h(ev['evidence_id'])}</span>
                    <span style="color:#94a3b8;">{h(ev['action'])}</span>
                    <span style="color:#64748b;">by {h(ev['actor'])}</span>
                    <span style="color:#475569;margin-left:auto;">{ev['timestamp'][:16].replace('T',' ')}</span>
                    </div>
                    <div style="color:#94a3b8;">{h(ev['description'])}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.markdown("<div style='font-size:0.65rem;opacity:0.4;padding:8px;'>No chain-of-custody events logged</div>", unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            with st.expander("Log Chain-of-Custody Event"):
                ev_id = st.text_input("Evidence ID", key="ecl_ev_id", placeholder="e.g. EVI-001")
                ev_action = st.selectbox("Action", ["Collected", "Transferred", "Analyzed", "Stored", "Viewed", "Reviewed", "Exported", "Destroyed"], key="ecl_action")
                ev_desc = st.text_input("Description", key="ecl_desc")
                ev_actor = st.text_input("Handled By", key="ecl_actor", value=st.session_state.get('authenticated_officer', ''))
                if st.button("Log Event", key="ecl_log", use_container_width=True):
                    if ev_id and ev_desc and ev_action:
                        add_evidence_event(incident_id, ev_id, ev_desc, "Physical Evidence", ev_action, ev_actor)
                        st.success("Event logged")
                        st.rerun()
    except Exception as e:
        st.error(f"Evidence Locker error: {e}")

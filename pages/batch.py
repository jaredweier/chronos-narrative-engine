import os
import tempfile
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from celery.result import AsyncResult
from html import escape as h
from batch_queue import get_queue, add_to_queue, remove_from_queue, clear_queue, update_item, queue_stats
from narrative_generator import generate_narrative
from nibrs_checker import check_nibrs_compliance, format_compliance_report
from nibrs_export import export_nibrs_xml
from pdf_parser import parse_zuercher_pdf
from transcriber import transcribe_bodycam
from ui import render_department_header
from logger import get_logger

logger = get_logger(__name__)


def render():
    try:
        render_department_header()
        stats = queue_stats()

        st.markdown("<div class='card-header'>Batch Queue</div>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="metric"><div class="metric-val">{stats['total']}</div><div class="metric-label">Total</div></div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="metric"><div class="metric-val">{stats['queued']}</div><div class="metric-label">Queued</div></div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="metric"><div class="metric-val">{stats['done']}</div><div class="metric-label">Completed</div></div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""<div class="metric"><div class="metric-val">{stats['error']}</div><div class="metric-label">Errors</div></div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        col_input, col_queue = st.columns([4, 6], gap="large")

        with col_input:
            st.markdown("<div class='card-header'>Add to Queue</div>", unsafe_allow_html=True)
            case_no = st.text_input("Case Number", placeholder="INC-20260711-143022", key="bq_case")
            call_id = st.text_input("Call ID", placeholder="CAD call ID", key="bq_call")
            call_type = st.text_input("Call Type", placeholder="e.g. Domestic, Theft, Assault", key="bq_type")
            location = st.text_input("Location", placeholder="Incident address", key="bq_loc")
            report_type = st.selectbox("Report Type", ["Standard Incident Report", "Search Warrant Affidavit", "Internal Use-of-Force Review", "OWI / DUI Report"], key="bq_rpt_type")
            notes = st.text_area("Notes", height=100, key="bq_notes", placeholder="Incident notes or description...", label_visibility="collapsed")
            evidence_file = st.file_uploader(
                "Evidence File (optional)", type=['pdf', 'mp4', 'mov', 'avi', 'mkv', 'wav', 'mp3'],
                key="bq_evidence", label_visibility="collapsed",
            )

            if st.button("Add to Queue", type="primary", use_container_width=True, key="bq_add"):
                ev_path = ""
                if evidence_file:
                    os.makedirs("temp_evidence", exist_ok=True)
                    ev_path = os.path.join("temp_evidence", evidence_file.name)
                    with open(ev_path, 'wb') as f:
                        f.write(evidence_file.read())
                add_to_queue({
                    "case_number": case_no,
                    "call_id": call_id,
                    "call_type": call_type,
                    "location": location,
                    "report_type": report_type,
                    "notes": notes,
                    "evidence_file_path": ev_path,
                    "evidence_file_name": evidence_file.name if evidence_file else "",
                    "officer_name": st.session_state.get('authenticated_officer', ''),
                    "officer_id": st.session_state.get('officer_id', ''),
                })
                st.success("Added to queue")
                st.rerun()

        with col_queue:
            queue = get_queue()
            if not queue:
                st.markdown("""<div class="empty-state"><div class="icon">&#128196;</div><div class="title">Queue Empty</div><div class="desc">Add incidents to the queue for batch processing</div></div>""", unsafe_allow_html=True)
            else:
                for idx, item in enumerate(queue):
                    status_color = {"queued": "#64748b", "processing": "#f59e0b", "done": "#22c55e", "error": "#ef4444"}.get(item.get('status', 'queued'), "#64748b")
                    with st.container():
                        cols = st.columns([6, 2, 2])
                        with cols[0]:
                            st.markdown(f"""<div style="font-size:0.72rem;"><span style="font-weight:600;color:#60a5fa;">{h(item.get('case_number', 'N/A'))}</span><br><span style="font-size:0.62rem;color:#64748b;">{h(item.get('call_type', ''))} &bull; {h(item.get('location', ''))}</span></div>""", unsafe_allow_html=True)
                        with cols[1]:
                            st.markdown(f"""<div style="font-size:0.62rem;font-weight:600;color:{status_color};text-transform:uppercase;">{h(item.get('status', 'queued'))}</div>""", unsafe_allow_html=True)
                        with cols[2]:
                            if st.button("Remove", key=f"bq_rem_{idx}"):
                                remove_from_queue(idx)
                                st.rerun()
                        if item.get('error'):
                            st.warning(item['error'][:120])


                c1, c2, c3 = st.columns(3)
                with c1:
                    if queue and st.button("Process All", type="primary", use_container_width=True, key="bq_process"):
                        from tasks import process_batch_item_task
                        for i, item in enumerate(queue):
                            if item.get('status') == 'queued':
                                task = process_batch_item_task.delay(item)
                                update_item(i, {"status": "processing", "celery_task_id": task.id})
                        st.rerun()

                with c2:
                    done_items = [i for i in queue if i.get('status') == 'done' and i.get('narrative')]
                    if done_items:
                        batch_xml = export_nibrs_xml(
                            incidents=[{
                                "incident_id": i.get('case_number', ''),
                                "officer_name": i.get('officer_name', ''),
                                "officer_id": i.get('officer_id', ''),
                                "document_type": i.get('report_type', ''),
                                "final_approved_report": i.get('narrative', ''),
                                "call_id": i.get('call_id', ''),
                                "call_type": i.get('call_type', ''),
                                "location": i.get('location', ''),
                            } for i in done_items]
                        )
                        st.download_button("Export All XML", data=batch_xml, file_name=f"nibrs_batch_{len(done_items)}.xml", mime="application/xml", use_container_width=True, key="bq_xml")
                with c3:
                    if queue and st.button("Clear All", use_container_width=True, key="bq_clear"):
                        clear_queue()
                        st.rerun()
                        
            any_processing = any(item.get('status') == 'processing' for item in get_queue())
            if any_processing:
                st_autorefresh(interval=2000, limit=100, key="batch_poller")
                changed = False
                for i, item in enumerate(get_queue()):
                    if item.get('status') == 'processing' and item.get('celery_task_id'):
                        res = AsyncResult(item['celery_task_id'])
                        if res.ready():
                            if res.successful():
                                narrative = res.result
                                update_item(i, {"status": "done" if not narrative.startswith("[ERROR]") else "error", "narrative": narrative, "error": narrative if narrative.startswith("[ERROR]") else ""})
                            else:
                                update_item(i, {"status": "error", "error": str(res.result)})
                            changed = True
                if changed:
                    st.rerun()

                with c2:
                    done_items = [i for i in queue if i.get('status') == 'done' and i.get('narrative')]
                    if done_items:
                        batch_xml = export_nibrs_xml(
                            incidents=[{
                                "incident_id": i.get('case_number', ''),
                                "officer_name": i.get('officer_name', ''),
                                "officer_id": i.get('officer_id', ''),
                                "document_type": i.get('report_type', ''),
                                "final_approved_report": i.get('narrative', ''),
                                "call_id": i.get('call_id', ''),
                                "call_type": i.get('call_type', ''),
                                "location": i.get('location', ''),
                            } for i in done_items]
                        )
                        st.download_button("Export All XML", data=batch_xml, file_name=f"nibrs_batch_{len(done_items)}.xml", mime="application/xml", use_container_width=True, key="bq_xml")
                with c3:
                    if queue and st.button("Clear All", use_container_width=True, key="bq_clear"):
                        clear_queue()
                        st.rerun()
    except Exception as e:
        logger.exception("Batch page error: %s", e)
        st.error(f"Error: {e}")

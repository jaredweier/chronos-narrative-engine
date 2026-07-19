import streamlit as st
from html import escape as h

from database import get_statistics, get_incident, get_db_connection, get_evidence_chain
from phrase_book import get_snapshots
from diffview import render_diff_viewer
from ui import render_department_header
from logger import get_logger

logger = get_logger(__name__)


def render():
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
            search_id = st.text_input("Search Case ID or Officer", key="audit_search", placeholder="INC-20260711... or officer name...")
            search_text = st.text_input("Search within report text", key="audit_search_text", placeholder="Search report content...", label_visibility="collapsed")
            with get_db_connection() as conn:
                if search_text and len(search_text) >= 2:
                    like_phrase = f"%{search_text}%"
                    rows = conn.execute(
                        """SELECT * FROM legal_audit_logs
                           WHERE incident_id LIKE ? OR officer_name LIKE ?
                              OR unedited_ai_draft LIKE ? OR final_approved_report LIKE ?
                           ORDER BY submission_timestamp DESC LIMIT 50""",
                        (like_phrase, like_phrase, like_phrase, like_phrase)
                    ).fetchall()
                elif search_id:
                    rows = conn.execute(
                        "SELECT * FROM legal_audit_logs WHERE incident_id LIKE ? OR officer_name LIKE ? ORDER BY submission_timestamp DESC LIMIT 50",
                        (f"%{search_id}%", f"%{search_id}%")
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
                st.markdown("""<div class=\"empty-state\"><div class=\"icon\">&#128196;</div>
                <div class=\"title\">No Records Found</div><div class=\"desc\">Submissions will appear here</div></div>""", unsafe_allow_html=True)

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
                        with st.expander("AI Draft vs Final Report", expanded=True):
                            render_diff_viewer(record['unedited_ai_draft'], record['final_approved_report'])
                    elif record.get('final_approved_report'):
                        st.text_area("Report", value=record['final_approved_report'], height=300, disabled=True, key="audit_report_only", label_visibility="collapsed")

                    evidence = get_evidence_chain(detail_id)
                    if evidence:
                        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                        with st.expander(f"Evidence Chain-of-Custody ({len(evidence)} events)", expanded=False):
                            for ev in evidence:
                                st.markdown(f"""<div style="border-left:3px solid #334155;padding:6px 12px;margin-bottom:6px;font-size:0.68rem;">
                                <div style="display:flex;gap:8px;align-items:center;">
                                <span style="font-weight:600;">{h(ev['evidence_id'])}</span>
                                <span style="color:#94a3b8;">{h(ev['action'])}</span>
                                <span style="color:#64748b;">by {h(ev['actor'])}</span>
                                <span style="color:#475569;margin-left:auto;">{ev['timestamp'][:16].replace('T',' ')}</span>
                                </div>
                                <div style="color:#94a3b8;">{h(ev['description'])} <span style="color:#64748b;">({h(ev['evidence_type'])}</span>)</div>
                                {f"<div style='color:#64748b;font-style:italic;'>{h(ev['notes'])}</div>" if ev.get('notes') else ""}
                                </div>""", unsafe_allow_html=True)

                    snapshots = get_snapshots(detail_id)
                    if snapshots:
                        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                        with st.expander(f"Version History ({len(snapshots)} snapshots)"):
                            prev_text = None
                            for snap in snapshots:
                                snap_ts = snap['created_at'][:16].replace('T', ' ')
                                st.markdown(f"<div style='font-size:0.66rem;color:#64748b;margin-bottom:4px;'><strong>{h(snap['snapshot_label'])}</strong> &mdash; {snap_ts}</div>", unsafe_allow_html=True)
                                if prev_text is not None and snap['snapshot_text'] != prev_text:
                                    with st.expander(f"Diff vs previous", expanded=False):
                                        render_diff_viewer(prev_text, snap['snapshot_text'])
                                st.text_area(f"snap_{snap['id']}", value=snap['snapshot_text'], height=120, disabled=True, key=f"audit_snap_{snap['id']}", label_visibility="collapsed")
                                prev_text = snap['snapshot_text']
                else:
                    st.info("No record found for that Case ID")
    except Exception as e:
        logger.exception("Error in audit trail: %s", e)
        st.error(f"An error occurred: {e}")
        st.exception(e)

import streamlit as st
from html import escape as h
from database import get_pending_reviews, get_review_counts, update_review_status, get_incident
from diffview import render_diff_viewer
from ui import render_department_header
from auth import get_officer_role
from logger import get_logger

logger = get_logger(__name__)


def render():
    try:
        render_department_header()
        role = get_officer_role(st.session_state.get('officer_id', ''))
        if role not in ('supervisor', 'admin'):
            st.warning("Supervisor access required. Contact your administrator.")
            return

        counts = get_review_counts()
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="metric"><div class="metric-val">{counts.get('pending', 0)}</div><div class="metric-label">Pending Review</div></div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="metric"><div class="metric-val">{counts.get('submitted', 0)}</div><div class="metric-label">Awaiting Review</div></div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="metric"><div class="metric-val">{counts.get('approved', 0)}</div><div class="metric-label">Approved</div></div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""<div class="metric"><div class="metric-val">{counts.get('rejected', 0)}</div><div class="metric-label">Rejected</div></div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='card-header'>Pending Reports</div>", unsafe_allow_html=True)

        pending = get_pending_reviews()
        if not pending:
            st.markdown("""<div class="empty-state"><div class="icon">&#9989;</div><div class="title">All Caught Up</div><div class="desc">No reports pending review</div></div>""", unsafe_allow_html=True)
            return

        for rec in pending:
            ts = rec['submission_timestamp'][:16].replace('T', ' ')
            status_badge = {"submitted": "Awaiting Review", "reviewed": "Re-reviewed"}.get(rec.get('review_status', ''), rec.get('review_status', ''))
            with st.container():
                st.markdown(f"""<div style="border:1px solid #1e293b;border-radius:8px;padding:14px;margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                <div><strong style="color:#60a5fa;font-family:monospace;">{h(rec['incident_id'])}</strong>
                <span style="font-size:0.68rem;color:#64748b;margin-left:8px;">{h(rec['officer_name'])} &bull; {h(rec['document_type'])}</span></div>
                <div><span style="font-size:0.62rem;padding:2px 8px;border-radius:3px;background:rgba(251,191,36,0.12);color:#f59e0b;font-weight:600;">{status_badge}</span>
                <span style="font-size:0.6rem;color:#475569;margin-left:8px;">{ts}</span></div></div>""", unsafe_allow_html=True)

                detail_key = f"review_detail_{rec['incident_id']}"
                if st.button(f"Review {rec['incident_id']}", key=detail_key):
                    st.session_state['_review_incident'] = rec['incident_id']

                if st.session_state.get('_review_incident') == rec['incident_id']:
                    report = rec.get('final_approved_report') or rec.get('unedited_ai_draft') or ""
                    st.text_area("Report", value=report, height=250, disabled=True, key=f"review_rpt_{rec['incident_id']}", label_visibility="collapsed")

                    if rec.get('unedited_ai_draft') and rec.get('final_approved_report'):
                        with st.expander("AI Draft vs Final"):
                            render_diff_viewer(rec['unedited_ai_draft'], rec['final_approved_report'])

                    notes = st.text_area("Review Notes", key=f"review_notes_{rec['incident_id']}", placeholder="Enter feedback or notes for the officer...", value=rec.get('reviewer_notes', ''))

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("Approve", type="primary", key=f"app_{rec['incident_id']}"):
                            update_review_status(rec['incident_id'], 'approved', st.session_state.get('authenticated_officer', ''), notes)
                            st.success("Approved")
                            st.rerun()
                    with c2:
                        if st.button("Request Changes", key=f"rev_{rec['incident_id']}"):
                            update_review_status(rec['incident_id'], 'reviewed', st.session_state.get('authenticated_officer', ''), notes)
                            st.success("Changes requested")
                            st.rerun()
                    with c3:
                        if st.button("Reject", key=f"rej_{rec['incident_id']}"):
                            update_review_status(rec['incident_id'], 'rejected', st.session_state.get('authenticated_officer', ''), notes)
                            st.success("Rejected")
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    except Exception as e:
        logger.exception("Review page error: %s", e)
        st.error(f"Error: {e}")

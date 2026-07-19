import streamlit as st
from html import escape as h
from database import search_reports, search_officer_reports, rebuild_search_index, delete_reports
from ui import render_department_header


def render():
    try:
        render_department_header()
        st.markdown("<div class='card-header'>Report Search</div>", unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])
        with col1:
            query = st.text_input("Search", placeholder="Search by incident ID, officer, report type, or keywords...", label_visibility="collapsed")
        with col2:
            scope = st.selectbox("Scope", ["All Reports", "My Reports Only"], label_visibility="collapsed")

        if "selected_ids" not in st.session_state:
            st.session_state["selected_ids"] = set()

        if query:
            with st.spinner("Searching..."):
                if scope == "My Reports Only":
                    results = search_officer_reports(
                        st.session_state.get('authenticated_officer', ''), query
                    )
                else:
                    results = search_reports(query)

            if results:
                st.markdown(f"<div style='font-size:0.65rem;opacity:0.4;margin-bottom:8px;'>{len(results)} result(s)</div>", unsafe_allow_html=True)

                select_all = st.checkbox("Select All", key="bulk_select_all")
                if select_all:
                    st.session_state["selected_ids"] = {r["id"] for r in results}
                elif st.session_state["selected_ids"]:
                    st.session_state["selected_ids"] = set()

                for r in results:
                    rid = r["id"]
                    ts = r.get('submission_timestamp', '')[:16].replace('T', ' ')
                    text_preview = (r.get('final_approved_report') or r.get('unedited_ai_draft', ''))[:200]
                    col_a, col_b = st.columns([0.05, 0.95])
                    with col_a:
                        checked = rid in st.session_state["selected_ids"]
                        if st.checkbox("", value=checked, key=f"sel_{rid}", label_visibility="collapsed"):
                            st.session_state["selected_ids"].add(rid)
                        else:
                            st.session_state["selected_ids"].discard(rid)
                    with col_b:
                        with st.expander(f"{h(r.get('incident_id', ''))} — {h(r.get('document_type', ''))} — {ts}"):
                            st.markdown(f"**Officer:** {h(r.get('officer_name', ''))}")
                            st.markdown(f"**Incident:** {h(r.get('incident_id', ''))}")
                            st.markdown(f"**Type:** {h(r.get('document_type', ''))}")
                            st.markdown(f"**Timestamp:** {ts}")
                            st.markdown(f"**Modified:** {'Yes' if r.get('was_modified_by_human') else 'No'}")
                            st.markdown(f"**Reviewed:** {r.get('review_status', 'N/A')}")
                            if text_preview:
                                st.markdown("**Preview:**")
                                st.text(text_preview)
                            st.download_button(
                                "Download Text", data=text_preview,
                                file_name=f"{r.get('incident_id', 'report')}.txt",
                                mime="text/plain", key=f"dl_{rid}",
                            )

                bulk_count = len(st.session_state["selected_ids"])
                if bulk_count > 0:
                    st.markdown(f"<div style='margin-top:12px;font-size:0.7rem;opacity:0.5;'>{bulk_count} report(s) selected</div>", unsafe_allow_html=True)
                    bc1, bc2, bc3 = st.columns([1, 1, 3])
                    with bc1:
                        selected_data = []
                        for r in results:
                            if r["id"] in st.session_state["selected_ids"]:
                                text = r.get('final_approved_report') or r.get('unedited_ai_draft', '')
                                selected_data.append(f"=== {r['incident_id']} ({r['document_type']}) ===\n{text}")
                        bulk_text = "\n\n".join(selected_data)
                        st.download_button(
                            "Bulk Download",
                            data=bulk_text,
                            file_name="bulk_reports.txt",
                            mime="text/plain",
                            use_container_width=True,
                            key="bulk_download",
                        )
                    with bc2:
                        role = st.session_state.get('_user_role', '')
                        if role in ('supervisor', 'admin'):
                            if st.button("Bulk Delete", type="secondary", use_container_width=True, key="bulk_delete"):
                                st.session_state["_confirm_bulk_delete"] = True
                        if st.session_state.get("_confirm_bulk_delete"):
                            st.warning(f"Delete {bulk_count} report(s)? This cannot be undone.")
                            if st.button("Confirm Delete", type="primary", key="confirm_bulk_del"):
                                ids_to_delete = list(st.session_state["selected_ids"])
                                deleted = delete_reports(ids_to_delete)
                                st.session_state["selected_ids"] = set()
                                st.session_state["_confirm_bulk_delete"] = False
                                st.success(f"{deleted} report(s) deleted")
                                st.rerun()
                            if st.button("Cancel", key="cancel_bulk_del"):
                                st.session_state["_confirm_bulk_delete"] = False
                                st.rerun()
            else:
                st.markdown(
                    """<div class="empty-state"><div class="icon">&#128269;</div>
                    <div class="title">No Results</div>
                    <div class="desc">Try a different search term</div></div>""",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                """<div class="empty-state"><div class="icon">&#128269;</div>
                <div class="title">Search Reports</div>
                <div class="desc">Search across all submitted reports by incident ID, officer name, document type, or narrative content</div></div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button("Rebuild Search Index", use_container_width=True):
            with st.spinner("Rebuilding..."):
                rebuild_search_index()
            st.success("Search index rebuilt")
    except Exception as e:
        st.error(f"Search error: {e}")

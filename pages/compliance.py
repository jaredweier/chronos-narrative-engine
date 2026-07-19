import streamlit as st
from datetime import datetime
from html import escape as h

from compliance_content import get_compliance_html, get_compliance_text
from export import export_compliance_docx, export_compliance_pdf
from ui import render_department_header
from logger import get_logger

logger = get_logger(__name__)


def render():
    try:
        render_department_header()
        officer = st.session_state['authenticated_officer']
        badge_num = st.session_state['officer_id']
        doc_html = get_compliance_html(officer, badge_num)
        compliance_text = get_compliance_text(officer, badge_num)
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
        logger.exception("Error in AI compliance: %s", e)
        st.error(f"An error occurred: {e}")
        st.exception(e)

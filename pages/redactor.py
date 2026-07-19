import streamlit as st
import os
from datetime import datetime
from html import escape as h
from utils import safe_filename

from redactor import sanitize_pii_content, get_redaction_report, REDACTION_CATEGORIES
from profiler import extract_text_from_file
from config import TEMP_DIR
from export import export_report_docx, export_report_pdf
from ui import render_department_header
from logger import get_logger

logger = get_logger(__name__)


def render():
    try:
        render_department_header()

        st.markdown("<div class='card-header'>Select What to Redact</div>", unsafe_allow_html=True)
        cat_cols = st.columns(4)
        selected_cats = set()
        for idx, (cat_id, cat_info) in enumerate(REDACTION_CATEGORIES.items()):
            col = cat_cols[idx % 4]
            with col:
                if st.checkbox(cat_info["label"], value=True, key=f"cat_{cat_id}", help=cat_info["description"]):
                    selected_cats.add(cat_id)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.markdown("<div class='card-header'>Original Text</div>", unsafe_allow_html=True)

            uploaded_doc = st.file_uploader(
                "Upload a document to redact",
                type=['txt', 'pdf', 'docx'],
                key="redact_file_upload",
                label_visibility="collapsed",
            )

            if uploaded_doc:
                try:
                    safe_fn = safe_filename(uploaded_doc.name)
                    save_path = os.path.join(TEMP_DIR, safe_fn)
                    file_data = uploaded_doc.read()
                    with open(save_path, 'wb') as f:
                        f.write(file_data)
                    content = extract_text_from_file(save_path)
                    if os.path.exists(save_path):
                        os.remove(save_path)
                    if content and content.strip():
                        st.session_state['redact_input_text'] = content
                        st.rerun()
                    else:
                        st.warning("Could not extract text from file")
                except Exception as e:
                    st.error(f"Error reading file: {e}")

            input_val = st.session_state.get('redact_input_text', '')
            original_text = st.text_area(
                "Input",
                value=input_val,
                height=380,
                key="redact_original",
                label_visibility="collapsed",
                placeholder="Paste report text here, or upload a document above...",
            )

            if st.button("Redact PII", type="primary", use_container_width=True, key="redact_btn"):
                text_to_redact = original_text if original_text.strip() else st.session_state.get('redact_input_text', '')
                if text_to_redact.strip():
                    redacted = sanitize_pii_content(text_to_redact, selected_cats)
                    st.session_state['redacted_text'] = redacted
                    st.session_state['redaction_changes'] = get_redaction_report(text_to_redact, redacted)
                    st.rerun()
                else:
                    st.warning("Paste some text or upload a file first")

        with col2:
            st.markdown("<div class='card-header'>Redacted Output</div>", unsafe_allow_html=True)
            if st.session_state.get('redacted_text'):
                redacted_content = st.session_state['redacted_text']
                st.text_area("Output", value=redacted_content, height=340, disabled=True, key="redact_output", label_visibility="collapsed")

                if st.session_state.get('redaction_changes'):
                    with st.expander(f"{len(st.session_state['redaction_changes'])} PII items redacted", expanded=True):
                        for orig, red in st.session_state['redaction_changes']:
                            st.markdown(f"""<div class="redact-item"><span class="redact-orig">{h(orig[:80])}</span> &rarr; <span class="redact-new">{h(red[:80])}</span></div>""", unsafe_allow_html=True)

                st.markdown("<div class='export-panel'><div class='export-label'>Download Redacted File</div></div>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.download_button(
                        "\U0001F4C4  Word (.docx)",
                        data=export_report_docx(redacted_content, st.session_state['authenticated_officer'], st.session_state['officer_id'], f"REDACTED-{datetime.now().strftime('%Y%m%d')}", report_type="Redacted Report"),
                        file_name=f"redacted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key="redact_dl_docx",
                    )
                with c2:
                    st.download_button(
                        "\U0001F4D1  PDF",
                        data=export_report_pdf(redacted_content, st.session_state['authenticated_officer'], st.session_state['officer_id'], f"REDACTED-{datetime.now().strftime('%Y%m%d')}", report_type="Redacted Report"),
                        file_name=f"redacted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="redact_dl_pdf",
                    )
                with c3:
                    st.download_button(
                        "\U0001F4DD  Text (.txt)",
                        data=redacted_content,
                        file_name=f"redacted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key="redact_dl_txt",
                    )
            else:
                st.markdown("""<div class="empty-state"><div class="icon">&#128274;</div>
                <div class="title">No Text to Redact</div><div class="desc">Upload a document or paste text on the left</div></div>""", unsafe_allow_html=True)
    except Exception as e:
        logger.exception("Error in PII redactor: %s", e)
        st.error(f"An error occurred: {e}")
        st.exception(e)

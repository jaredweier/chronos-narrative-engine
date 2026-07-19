import streamlit as st
import os
from pathlib import Path

from profiler import (
    save_style_sample, get_style_examples, get_all_officers,
    get_officer_categories, extract_text_from_file, SUPPORTED_SAMPLE_EXTENSIONS,
)
from config import TEMP_DIR
from ui import render_department_header, _load_custom_categories, _save_custom_category
from logger import get_logger

logger = get_logger(__name__)


def render():
    try:
        render_department_header()
        col1, col2 = st.columns([5, 7], gap="large")

        with col1:
            st.markdown("<div class='card-header'>Upload Style Samples</div>", unsafe_allow_html=True)
            officer_name = st.text_input("Officer Name", key="style_officer_name", placeholder="e.g. Det. Johnson")
            all_categories = _load_custom_categories()
            category = st.selectbox("Report Category", all_categories, key="style_category")

            st.markdown("<div style='margin-top:4px;margin-bottom:8px;font-size:0.65rem;opacity:0.4;text-transform:uppercase;letter-spacing:0.08em;'>Add Custom Category</div>", unsafe_allow_html=True)
            new_cat_col, add_col = st.columns([3, 1])
            with new_cat_col:
                new_cat = st.text_input("New category", key="new_cat_input", placeholder="e.g. Theft Report", label_visibility="collapsed")
            with add_col:
                if st.button("Add", key="add_cat_btn", use_container_width=True):
                    if new_cat and new_cat.strip():
                        _save_custom_category(new_cat.strip())
                        st.success(f"Added: {new_cat.strip()}")
                        st.rerun()

            uploaded_files = st.file_uploader("Report Samples", type=['txt', 'pdf', 'docx'], accept_multiple_files=True, key="style_files", help="5-10 redacted reports per officer per category")

            if uploaded_files and officer_name:
                st.info(f"{len(uploaded_files)} file(s) ready")
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                if st.button("Save Samples", type="primary", use_container_width=True, key="save_samples_btn"):
                    saved_count = 0
                    errors = []
                    for file in uploaded_files:
                        try:
                            ext = Path(file.name).suffix.lower()
                            if ext in SUPPORTED_SAMPLE_EXTENSIONS:
                                safe_fn = "".join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in file.name)
                                save_path = os.path.join(TEMP_DIR, safe_fn)
                                file_bytes = file.read()
                                with open(save_path, 'wb') as f:
                                    f.write(file_bytes)
                                content = extract_text_from_file(save_path)
                                if content and content.strip():
                                    save_style_sample(officer_name, category, content, safe_fn)
                                    saved_count += 1
                                else:
                                    errors.append(f"{file.name}: no text extracted")
                                if os.path.exists(save_path):
                                    os.remove(save_path)
                            else:
                                errors.append(f"{file.name}: unsupported type")
                        except Exception as e:
                            errors.append(f"{file.name}: {e}")
                    if saved_count:
                        st.success(f"Saved {saved_count} sample(s) for {officer_name}")
                    for err in errors:
                        st.warning(err)
                    st.rerun()

        with col2:
            st.markdown("<div class='card-header'>Existing Profiles</div>", unsafe_allow_html=True)
            officers = get_all_officers()
            if officers:
                selected_officer = st.selectbox("Officer", officers, key="view_officer", label_visibility="collapsed")
                categories = get_officer_categories(selected_officer)
                if categories:
                    selected_cat = st.selectbox("Category", categories, key="view_cat")
                    examples = get_style_examples(selected_officer, selected_cat)
                    st.markdown(f"""<div class="metric"><div class="metric-val">{len(examples)}</div><div class="metric-label">Style Samples</div></div>""", unsafe_allow_html=True)
                    for i, example in enumerate(examples):
                        with st.expander(f"Sample {i+1}", expanded=False):
                            st.text(example[:800] + ("..." if len(example) > 800 else ""))
                else:
                    st.info("No categories configured")
            else:
                st.markdown("""<div class="empty-state"><div class="icon">&#128100;</div>
                <div class="title">No Profiles Yet</div><div class="desc">Upload samples to build officer writing profiles</div></div>""", unsafe_allow_html=True)
    except Exception as e:
        logger.exception("Error in officer profiles: %s", e)
        st.error(f"An error occurred: {e}")
        st.exception(e)

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from celery.result import AsyncResult
from state_manager import StateManager
import os
import tempfile
from datetime import datetime
from html import escape as h
from utils import safe_filename

from redactor import sanitize_pii_content
from pdf_parser import parse_zuercher_pdf
from transcriber import transcribe_bodycam, cleanup_transcriber
from nibrs_checker import (
    check_nibrs_compliance, format_compliance_report, get_compliance_summary,
    suggest_missing_fields, check_probable_cause,
)
from nibrs_export import build_nibrs_xml, validate_nibrs_xml, lookup_nibrs_code, NIBRS_2025_OFFENSES
from profiler import get_style_examples
from database import get_recent_corrections
from narrative_generator import generate_narrative
from phrase_book import (
    add_phrase, get_phrases, get_phrase_categories,
    use_phrase, search_phrases, save_snapshot,
)
from templates import get_template, render_template_prompt
from config import TEMP_DIR, MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_GB
from pipeline_manager import submit_pdf_and_transcribe
from database import log_submission, add_evidence_event, get_evidence_chain
from export import export_report_docx, export_report_pdf
from ui import (
    inject_button_animations,
    render_animated_evidence_card,
    _case_bar_html, render_department_header,
    _load_custom_categories,
)
from draft import save_draft, render_draft_banner
from logger import get_logger
from spell_check import check_text_spelling, auto_correct, auto_correct_transcript, highlight_issues
from wi_statutes import search_statutes, search_jury_instructions, statutes_for_report_type, all_categories, WI_CRIMINAL_STATUTES
from case_similar import get_similar_case_data, apply_similar_case_template

logger = get_logger(__name__)


def _render_evidence_upload():
    st.markdown("<div class='card-header'>Evidence Upload</div>", unsafe_allow_html=True)
    pdf_file = st.file_uploader("Zuercher CAD Report", type=['pdf'], key="pdf_uploader")
    video_file = st.file_uploader("Body Camera Footage", type=['mp4', 'mov', 'avi', 'mkv'], key="video_uploader", help="Supports files up to 10 GB")

    if pdf_file and pdf_file.size <= MAX_UPLOAD_SIZE_BYTES:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', dir=TEMP_DIR) as tmp:
            tmp.write(pdf_file.read())
            st.session_state['pdf_path'] = tmp.name
        st.success(f"CAD loaded: {pdf_file.name} ({pdf_file.size / 1024:.0f}KB)")
    elif pdf_file:
        st.error(f"PDF too large ({pdf_file.size / 1024 / 1024:.1f}MB). Max {MAX_UPLOAD_SIZE_BYTES / 1024 / 1024:.0f}MB.")

    if video_file:
        max_video = MAX_UPLOAD_SIZE_BYTES
        if video_file.size > max_video:
            st.error(f"Video too large ({video_file.size / 1024 / 1024 / 1024:.1f}GB). Max 10GB.")
        else:
            _, ext = os.path.splitext(video_file.name)
            if not ext:
                ext = '.mp4'
            save_path = os.path.join(TEMP_DIR, safe_filename(video_file.name))
            progress = st.progress(0, text=f"Uploading {video_file.name}...")
            with open(save_path, 'wb') as f:
                total = 0
                while True:
                    chunk = video_file.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    total += len(chunk)
                    if video_file.size > 0:
                        progress.progress(min(total / video_file.size, 1.0))
            progress.empty()
            st.session_state['video_path'] = save_path
            st.success(f"Body cam loaded: {video_file.name} ({video_file.size / 1024 / 1024:.0f}MB)")
            st.video(save_path)

    render_draft_banner(StateManager.get_authenticated_officer())

    if st.session_state.get('pdf_path') or st.session_state.get('video_path'):
        active_tasks = st.session_state.get('active_tasks', {})
        if active_tasks:
            # Poll every 2 seconds
            st_autorefresh(interval=2000, limit=100, key="task_poller")
            st.info("Processing evidence in background...")
            
            all_done = True
            cad_result = st.session_state.get('cad_data')
            transcript_result = st.session_state.get('transcript')
            
            if 'pdf' in active_tasks:
                res = AsyncResult(active_tasks['pdf'])
                if res.ready():
                    if res.successful():
                        cad_result = res.result
                        st.session_state['cad_data'] = cad_result
                    else:
                        st.error(f"PDF parsing failed: {res.result}")
                    del active_tasks['pdf']
                else:
                    st.write("CAD PDF Status:", res.status)
                    all_done = False
                    
            if 'video' in active_tasks:
                res = AsyncResult(active_tasks['video'])
                if res.ready():
                    from spell_check import auto_correct_transcript
                    if res.successful():
                        transcript_result = res.result
                        if transcript_result:
                            transcript_result = auto_correct_transcript(transcript_result)
                        st.session_state['transcript'] = transcript_result
                    else:
                        st.error(f"Transcription failed: {res.result}")
                    del active_tasks['video']
                else:
                    st.write("Transcription Status:", res.status)
                    all_done = False
                    
            st.session_state['active_tasks'] = active_tasks
            if all_done:
                st.success("Evidence processed")
                st.session_state['active_tasks'] = {}
                st.rerun()
                
        elif st.button("Process Evidence", type="primary", use_container_width=True, key="process_btn"):
            pdf = st.session_state.get('pdf_path')
            video = st.session_state.get('video_path')
            tasks = submit_pdf_and_transcribe(pdf, video)
            st.session_state['active_tasks'] = tasks
            st.rerun()


def _render_notes_and_category():
    st.markdown("<div class='card-header' style='margin-top:16px;'>Or Enter Notes Directly</div>", unsafe_allow_html=True)
    notes = st.text_area("Additional Notes", height=120, key="custom_notes_input", placeholder="Type any additional notes, observations, or incident details here...", label_visibility="collapsed")

    with st.expander("Voice Dictation", expanded=False):
        st.markdown("<div style='font-size:0.65rem;opacity:0.5;margin-bottom:8px;'>Upload an audio recording of your notes. The system will transcribe it and append the text above.</div>", unsafe_allow_html=True)
        audio_file = st.file_uploader("Audio File", type=['wav', 'mp3', 'm4a', 'ogg', 'flac', 'webm'], key="dictation_upload", label_visibility="collapsed")
        if audio_file and st.button("Transcribe Audio", key="transcribe_btn", use_container_width=True):
            with st.spinner("Transcribing audio with Whisper..."):
                audio_path = os.path.join(TEMP_DIR, safe_filename(audio_file.name))
                with open(audio_path, 'wb') as f:
                    f.write(audio_file.read())
                try:
                    from config import WHISPER_INITIAL_PROMPT
                    transcript = transcribe_bodycam(audio_path, initial_prompt="Police officer dictating incident notes for report generation. " + WHISPER_INITIAL_PROMPT)
                    from spell_check import auto_correct_transcript
                    transcript = auto_correct_transcript(transcript)
                    current = st.session_state.get('custom_notes_input', '')
                    st.session_state['custom_notes_input'] = (current + "\n\n[DICTATED]\n" + transcript) if current else "[DICTATED]\n" + transcript
                    st.success(f"Transcribed {len(transcript)} characters")
                except Exception as e:
                    st.error(f"Transcription failed: {e}")
                finally:
                    cleanup_transcriber()
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                st.rerun()

    st.markdown("<div class='card-header' style='margin-top:12px;'>Report Category</div>", unsafe_allow_html=True)
    all_categories = _load_custom_categories()
    report_type = st.selectbox("Category", all_categories, key="report_type_select", label_visibility="collapsed")

    template = get_template(report_type)
    if template:
        with st.expander(f"Template: {report_type}", expanded=False):
            st.markdown(f"<div style='font-size:0.68rem;opacity:0.5;margin-bottom:8px;'>{h(template['description'])}</div>", unsafe_allow_html=True)
            for title, hint in template["sections"]:
                st.markdown(f"**{h(title)}** — <span style='font-size:0.66rem;opacity:0.4;'>{h(hint)}</span>", unsafe_allow_html=True)
            use_tpl = st.checkbox("Include template structure in prompt", value=False, key="use_template_chk")
        if use_tpl:
            st.session_state['_template_prompt'] = render_template_prompt(report_type)
        else:
            st.session_state.pop('_template_prompt', None)
    return notes, report_type


def _render_phrase_book():
    officer = StateManager.get_authenticated_officer()
    st.markdown("<div class='card-header' style='margin-top:16px;'>Phrase Book</div>", unsafe_allow_html=True)
    pb_cats = get_phrase_categories(officer)
    if pb_cats:
        pb_filter = st.selectbox("Filter", ["All"] + pb_cats, key="pb_filter", label_visibility="collapsed")
        for ph in get_phrases(officer, category=None if pb_filter == "All" else pb_filter)[:6]:
            st.markdown(f"""<div class="phrase-card" title="{h(ph['phrase_text'][:200])}"><div class="ph-label">{h(ph['label'])}</div><div class="ph-text">{h(ph['phrase_text'][:120])}{'...' if len(ph['phrase_text']) > 120 else ''}</div><div class="ph-meta">Used {ph['use_count']}x</div></div>""", unsafe_allow_html=True)
        pb_query = st.text_input("Search phrases", key="pb_search", placeholder="Search...", label_visibility="collapsed")
        if pb_query:
            for ph in search_phrases(officer, pb_query)[:4]:
                if st.button(f"Insert: {ph['label']}", key=f"pb_ins_{ph['id']}"):
                    use_phrase(ph['id'])
                    current = st.session_state.get('custom_notes_input', '')
                    st.session_state['custom_notes_input'] = (current + "\n\n" + ph['phrase_text']) if current else ph['phrase_text']
                    st.rerun()
    else:
        st.markdown("<div style='font-size:0.62rem;opacity:0.3;padding:4px;'>No phrases saved yet. Add them in Officer Profiles.</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    st.markdown("<div class='card-header'>Make Similar To Case</div>", unsafe_allow_html=True)
    similar_id = st.text_input("Case #", key="similar_case_input", placeholder="INC-20260711-143022", label_visibility="collapsed")
    if similar_id:
        similar_data = get_similar_case_data(similar_id)
        if similar_data:
            st.markdown(f"<div style='font-size:0.65rem;opacity:0.4;'>Loaded: {similar_data['document_type']} by {similar_data['officer_name']}</div>", unsafe_allow_html=True)
            if st.button("Apply Template from Case", key="apply_similar_btn", use_container_width=True):
                template = apply_similar_case_template(similar_data['report_text'], StateManager.get_authenticated_officer())
                if template:
                    current = st.session_state.get('custom_notes_input', '')
                    st.session_state['custom_notes_input'] = (current + "\n\n[FROM CASE " + similar_id + "]\n" + template) if current else "[FROM CASE " + similar_id + "]\n" + template
                    st.success(f"Template from {similar_id} applied")
                    st.rerun()
        else:
            st.markdown("<div style='font-size:0.62rem;opacity:0.3;padding:4px;'>Case not found</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("Save New Phrase", expanded=False):
        ph_label = st.text_input("Label", key="new_ph_label", placeholder="e.g. 'Opening statement'")
        ph_text = st.text_area("Phrase text", key="new_ph_text", height=80, placeholder="Type the phrase or boilerplate text...")
        ph_cat = st.text_input("Category", key="new_ph_cat", value="General", placeholder="e.g. 'DUI', 'Domestic'")
        if st.button("Save Phrase", key="save_ph_btn") and ph_label and ph_text:
            add_phrase(officer, ph_label, ph_text, ph_cat)
            st.success(f"Saved: {ph_label}")
            st.rerun()


def _render_evidence_chain():
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander(f"{chr(0x1F4E6)} Evidence Chain-of-Custody", expanded=False):
        case_id = StateManager.get_case_number()
        if case_id:
            chain = get_evidence_chain(case_id)
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
                st.markdown("<div style='font-size:0.65rem;opacity:0.4;padding:4px;'>No evidence logged yet</div>", unsafe_allow_html=True)

            st.markdown("<div style='margin-top:8px;font-size:0.65rem;opacity:0.5;'>Log Evidence Event</div>", unsafe_allow_html=True)
            ec1, ec2 = st.columns(2)
            with ec1:
                ev_id = st.text_input("Evidence ID", key="ev_id", placeholder="e.g. EVI-001")
                ev_type = st.selectbox("Type", ["Bodycam Footage", "CAD Report", "Photo", "Document", "Physical Evidence", "Recording", "Other"], key="ev_type")
                ev_action = st.selectbox("Action", ["Collected", "Transferred", "Analyzed", "Stored", "Viewed", "Reviewed", "Exported", "Destroyed"], key="ev_action")
            with ec2:
                ev_desc = st.text_input("Description", key="ev_desc", placeholder="e.g. Bodycam #2 - Officer Wilson")
                ev_actor = st.text_input("Handled By", key="ev_actor", value=StateManager.get_authenticated_officer())
                ev_notes = st.text_input("Notes", key="ev_notes", placeholder="Optional notes")
            if st.button("Log Event", key="log_ev_btn", use_container_width=True):
                if ev_id and ev_desc and ev_action:
                    add_evidence_event(case_id, ev_id, ev_desc, ev_type, ev_action, ev_actor, ev_notes)
                    st.success("Evidence event logged")
                    st.rerun()
                else:
                    st.warning("Evidence ID, Description, and Action required")


def _render_cad_data():
    cad_list = StateManager.get_cad_data_list()
    if not cad_list:
        return
    st.markdown("<div class='card-header'>Extracted CAD Data</div>", unsafe_allow_html=True)
    for cad in cad_list:
        details = f"{h(cad.call_type)} at {h(cad.location)}"
        render_animated_evidence_card(f"CAD {h(cad.call_id)}", details, icon="🚓", color_theme="blue")
        if cad.involved_parties:
            for party in cad.involved_parties:
                st.markdown(f"<div class='card-highlight' style='margin-left: 20px;'><strong>{h(sanitize_pii_content(party.name))}</strong> &mdash; DOB {h(sanitize_pii_content(party.dob))} &bull; {h(party.sex)} &bull; Age {h(str(party.age))}</div>", unsafe_allow_html=True)
        if any('?' in str(v) or '!' in str(v) for v in [cad.call_id, cad.call_type, cad.location]):
            st.warning("Low-confidence OCR detected \u2014 verify fields before submission")


def _render_compliance_results():
    warnings = st.session_state.get('compliance_warnings')
    if warnings:
        summary = get_compliance_summary(warnings)
        if summary['is_compliant']:
            st.markdown("<div class='badge-pass'>&#10003; NIBRS Compliant</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='badge-fail'>&#10007; NIBRS Issues &mdash; {summary['critical_count']} critical, {summary['warning_count']} warnings</div>", unsafe_allow_html=True)
        with st.expander("Compliance Details"):
            st.code(format_compliance_report(warnings))

    cad = st.session_state.get('cad_data')
    if warnings:
        parties = []
        if cad and cad.involved_parties:
            parties = [{"name": p.name, "dob": p.dob, "sex": p.sex, "age": p.age} for p in cad.involved_parties]
        nibrs_xml = build_nibrs_xml(
            incident_id=StateManager.get_case_number(),
            officer_name=StateManager.get_authenticated_officer(),
            officer_id=StateManager.get_officer_id(),
            report_type=st.session_state.get('report_type_select', ''),
            narrative=StateManager.get_generated_report(),
            call_id=cad.call_id if cad else '',
            call_type=cad.call_type if cad else '',
            location=cad.location if cad else '',
            dispatch_time=cad.dispatch_time if cad else '',
            arrival_time=cad.arrival_time if cad else '',
            clear_time=cad.clear_time if cad else '',
            involved_parties=parties,
        )
        st.download_button(
            "NIBRS XML", data=nibrs_xml,
            file_name=f"nibrs_{st.session_state.get('case_number', 'incident')}.xml",
            mime="application/xml", use_container_width=True, key="nibrs_xml_export",
        )

        xml_errors = validate_nibrs_xml(nibrs_xml)
        if xml_errors:
            crit = sum(1 for e in xml_errors if e.get("severity") == "critical")
            warn = sum(1 for e in xml_errors if e.get("severity") == "warning")
            st.markdown(f"""<div style="font-size:0.62rem;margin-top:4px;color:{"#ef4444" if crit else "#f59e0b"};">
            XML validation: {crit} critical, {warn} warnings</div>""", unsafe_allow_html=True)
            with st.expander("XML Validation Details", expanded=False):
                for err in xml_errors:
                    icon = "✗" if err["severity"] == "critical" else "⚠"
                    st.markdown(f"""<div style="font-size:0.65rem;border-left:2px solid {"#ef4444" if err["severity"] == "critical" else "#f59e0b"};padding:2px 8px;margin:2px 0;">
                    {icon} <strong>{err.get("field", "?")}</strong>: {err.get("message", "")}</div>""", unsafe_allow_html=True)

    mf = st.session_state.get('missing_fields')
    if mf:
        st.markdown("<div class='card-header' style='margin-top:8px;'>Suggested Additions</div>", unsafe_allow_html=True)
        for item in mf:
            st.markdown(f"""<div class="suggest-item"><div class="si-elem">{h(item.get('element', '').replace('_', ' '))}</div><div class="si-text">{h(item.get('suggestion', ''))}</div></div>""", unsafe_allow_html=True)

    pc = st.session_state.get('probable_cause')
    if pc:
        strength = pc.get('strength', 'unknown')
        colors = {'strong': '#22c55e', 'adequate': '#f59e0b', 'weak': '#ef4444', 'insufficient': '#ef4444', 'unknown': '#64748b'}
        sc = colors.get(strength, '#64748b')
        st.markdown(f"<div class='card-header' style='margin-top:8px;'>Probable Cause Analysis</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border:1px solid {sc}33;border-radius:6px;background:{sc}0a;margin-bottom:8px;'><span style='font-size:0.72rem;font-weight:600;color:{sc};text-transform:uppercase;'>{h(strength)}</span></div>", unsafe_allow_html=True)
        for f in pc.get('factors_present', []):
            st.markdown(f"""<div class="pc-strong"><span style="font-size:0.7rem;color:#22c55e;">&#10003;</span> <span style="font-size:0.68rem;color:#94a3b8;">{h(f)}</span></div>""", unsafe_allow_html=True)
        for f in pc.get('factors_missing', []):
            st.markdown(f"""<div class="pc-weak"><span style="font-size:0.7rem;color:#ef4444;">&#10007;</span> <span style="font-size:0.68rem;color:#94a3b8;">{h(f)}</span></div>""", unsafe_allow_html=True)
        if pc.get('recommendations'):
            with st.expander("Recommendations"):
                for r in pc['recommendations']:
                    st.markdown(f"- {r}")
        if pc.get('legal_notes'):
            st.info(pc['legal_notes'])


def _render_statute_selector(report_type):
    st.markdown("<div class='card-header' style='margin-top:16px;'>Wisconsin Statutes</div>", unsafe_allow_html=True)
    auto_codes = statutes_for_report_type(report_type)
    auto_codes_set = {s["code"] for s in auto_codes}

    current = st.session_state.get('_selected_statute_codes', [])
    if not current and auto_codes:
        current = list(auto_codes_set)

    all_opts = {f"{s['code']} — {s['title']}": s["code"] for s in WI_CRIMINAL_STATUTES}
    label_map = {v: k for k, v in all_opts.items()}
    current_labels = [label_map.get(c, c) for c in current if c in label_map]

    selected_labels = st.multiselect(
        "Statutes", options=list(all_opts.keys()), default=current_labels,
        key="_statute_sel", label_visibility="collapsed",
        placeholder="Select statutes for LLM context...",
    )
    selected_codes = [all_opts[lb] for lb in selected_labels if lb in all_opts]
    st.session_state['_selected_statute_codes'] = selected_codes

    if selected_codes:
        extra_search = st.text_input("Search statutes...", key="_statute_extra", placeholder="e.g. theft, 940.19, battery...", label_visibility="collapsed")
        if extra_search:
            for s in search_statutes(extra_search, limit=5):
                if s["code"] not in selected_codes:
                    if st.button(f"Add {s['code']} — {s['title']}", key=f"sta_add_{s['code']}", use_container_width=True):
                        st.session_state['_selected_statute_codes'] = selected_codes + [s["code"]]
                        st.rerun()
        st.caption(f"{len(selected_codes)} statute(s) selected — descriptions will be sent to the LLM as context")


def _generate_narrative_flow(report_type, custom_notes, statutes=None):
    cad_text = ""
    cad_list = StateManager.get_cad_data_list()
    if cad_list:
        cad = cad_list[0]
        cad_text = f"Call ID: {cad.call_id}\nType: {cad.call_type}\nLocation: {cad.location}\nDispatch: {cad.dispatch_time}\nArrival: {cad.arrival_time}\nCleared: {cad.clear_time}"
        if cad.involved_parties:
            cad_text += "\nInvolved parties: " + "; ".join(f"{p.name} (DOB:{p.dob}, {p.sex}, Age {p.age})" for p in cad.involved_parties)
        if cad.raw_text:
            cad_text += f"\n\nFull CAD text:\n{cad.raw_text}"

    raw_transcript = ""
    transcripts = StateManager.get_transcripts()
    if transcripts:
        raw_transcript = "\n".join(transcripts)
    transcript_text = sanitize_pii_content(auto_correct_transcript(raw_transcript))
    notes = sanitize_pii_content(custom_notes) if custom_notes else ""

    if not cad_text and not transcript_text and not notes:
        st.warning("Provide CAD data, body cam footage, or notes to generate a narrative.")
        return

    examples = get_style_examples(StateManager.get_authenticated_officer(), report_type)
    tpl_prompt = st.session_state.get('_template_prompt')

    correction_text = ""
    corrections = get_recent_corrections(StateManager.get_authenticated_officer(), report_type, limit=3)
    if corrections:
        correction_text = "\n\n--- PREVIOUS CORRECTIONS (learn from these edits) ---\n"
        for c in corrections[:2]:
            if c.get('final_approved_report') and c.get('unedited_ai_draft'):
                correction_text += f"Original AI draft:\n{c['unedited_ai_draft'][:1000]}\n"
                correction_text += f"Officer corrected to:\n{c['final_approved_report'][:1000]}\n---\n"

    combined_notes = ""
    if tpl_prompt:
        combined_notes += tpl_prompt + "\n\n"
    combined_notes += notes
    if correction_text:
        combined_notes += correction_text

    statute_objects = None
    selected_codes = statutes or st.session_state.get('_selected_statute_codes', [])
    if selected_codes:
        from wi_statutes import WI_CRIMINAL_STATUTES
        statute_objects = [s for s in WI_CRIMINAL_STATUTES if s["code"] in selected_codes]

    st.markdown("### Generating Narrative...")
    
    from narrative_generator import generate_narrative_stream
    stream = generate_narrative_stream(
        cad_text=cad_text, transcript=transcript_text,
        officer_style_examples=examples,
        custom_notes=combined_notes, report_type=report_type,
        statutes=statute_objects,
    )
    
    narrative = st.write_stream(stream)
    
    if narrative.startswith("[ERROR]"):
        st.error(f"LLM Error: {narrative}")
    else:
        StateManager.set_generated_report(narrative)
        StateManager.set_original_ai_draft(narrative)
        save_snapshot(StateManager.get_case_number(), StateManager.get_authenticated_officer(), narrative, "AI Draft")

    if not narrative.startswith("[ERROR]"):
        with st.spinner("Running compliance checks..."):
            st.session_state['compliance_warnings'] = check_nibrs_compliance(report_type, narrative)
            st.session_state['missing_fields'] = suggest_missing_fields(report_type, narrative)
            st.session_state['probable_cause'] = check_probable_cause(narrative)


def _render_report_editor_and_export(report_type):
    if not StateManager.get_generated_report():
        return
    st.markdown("<div class='card-header'>Generated Narrative</div>", unsafe_allow_html=True)

    report_text = StateManager.get_generated_report()

    spell_col, statute_col = st.columns(2)
    with spell_col:
        if st.button("Check Spelling", use_container_width=True):
            issues = check_text_spelling(report_text)
            if issues:
                st.warning(f"{len(issues)} issue(s) found")
                for orig, corr, pos in issues[:10]:
                    st.markdown(f"<div style='font-size:0.68rem;'><span style='color:#f87171;text-decoration:line-through;'>{orig}</span> &rarr; <span style='color:#4ade80;'>{corr}</span></div>", unsafe_allow_html=True)
                if st.button("Auto-Correct All", key="auto_correct_btn"):
                    corrected = auto_correct(report_text)
                    StateManager.set_generated_report(corrected)
                    st.rerun()
            else:
                st.success("No spelling issues found")
    with statute_col:
        statute_query = st.text_input("Statute Lookup", placeholder="e.g. 940.19, theft, homicide...", label_visibility="collapsed")
        if statute_query:
            statutes = search_statutes(statute_query, limit=5)
            if statutes:
                for s in statutes:
                    if st.button(f"Add {s['code']} - {s['title']}", key=f"sta_{s['code']}", use_container_width=True):
                        current = StateManager.get_generated_report()
                        StateManager.set_generated_report(current + f"\n\nWI Stat. {s['code']} — {s['title']}")
                        st.rerun()
            jis = search_jury_instructions(statute_query, limit=3)
            if jis:
                for ji in jis:
                    if st.button(f"Add {ji['code']} - {ji['title']}", key=f"ji_{ji['code']}", use_container_width=True):
                        current = StateManager.get_generated_report()
                        StateManager.set_generated_report(current + f"\n\n{ji['code']} — {ji['title']}")
                        st.rerun()

    nibrs_code = st.session_state.get('_selected_nibrs_code', "")
    nibrs_col1, nibrs_col2 = st.columns([3, 4])
    with nibrs_col1:
        nibrs_code = st.selectbox(
            "NIBRS Offense Code", options=[""] + sorted(NIBRS_2025_OFFENSES.keys()),
            index=0 if not nibrs_code else sorted(NIBRS_2025_OFFENSES.keys()).index(nibrs_code) + 1,
            key="_nibrs_code_sel", label_visibility="collapsed",
            placeholder="NIBRS offense code...",
        )
        if nibrs_code:
            st.caption(lookup_nibrs_code(nibrs_code))
            st.session_state['_selected_nibrs_code'] = nibrs_code
    with nibrs_col2:
        if nibrs_code:
            desc = lookup_nibrs_code(nibrs_code)
            if st.button(f"Add to report: [{nibrs_code}] {desc}", key="add_nibrs_btn", use_container_width=True):
                current = StateManager.get_generated_report()
                StateManager.set_generated_report(current + f"\n\nNIBRS Code: {nibrs_code} — {desc}")

    StateManager.set_generated_report(st.text_area(
        "Report", value=StateManager.get_generated_report(),
        height=400, key="report_editor", label_visibility="collapsed",
    ))
    report_text = StateManager.get_generated_report()
    if report_text and StateManager.get_original_ai_draft() and report_text != StateManager.get_original_ai_draft():
        save_draft(StateManager.get_authenticated_officer(), report_text)

    st.markdown("<div class='export-panel'><div class='export-label'>Export Options</div></div>", unsafe_allow_html=True)
    officer_name = StateManager.get_authenticated_officer()
    badge_num = StateManager.get_officer_id()
    case_no = StateManager.get_case_number() or 'INC-UNKNOWN'
    rpt_text = StateManager.get_generated_report()
    docx_data = export_report_docx(rpt_text, officer_name, badge_num, case_no)
    pdf_data = export_report_pdf(rpt_text, officer_name, badge_num, case_no)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("\U0001F4C4  Word (.docx)", data=docx_data, file_name=f"incident_report_{ts}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="rpt_docx")
    with c2:
        st.download_button("\U0001F4D1  PDF", data=pdf_data, file_name=f"incident_report_{ts}.pdf", mime="application/pdf", use_container_width=True, key="rpt_pdf")
    with c3:
        st.download_button("\U0001F4DD  Text (.txt)", data=rpt_text, file_name=f"incident_report_{ts}.txt", mime="text/plain", use_container_width=True, key="rpt_txt")

    sig_data = ""
    from config import SIGNATURE_ENABLED
    if SIGNATURE_ENABLED:
        st.markdown("<div class='card-header'>Signature</div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.65rem;opacity:0.5;margin-bottom:6px;'>Sign below to attest to this report:</div>", unsafe_allow_html=True)
        from export import SIGNATURE_CAPTURE_HTML
        st.components.v1.html(SIGNATURE_CAPTURE_HTML, height=260)
        sig_data = st.text_input("Signature Data (auto-filled)", key="sig_data_input", label_visibility="collapsed", placeholder="Sign above using mouse or touch")

    verified = st.checkbox(
        "I have reviewed this report and attest that the information is accurate to the best of my knowledge. I accept full professional and legal responsibility for this submission.",
        key="verification_checkbox"
    )
    if st.button("Submit to Audit Trail", type="primary", use_container_width=True, key="submit_audit", disabled=not verified):
        log_submission(
            incident_id=st.session_state.get('case_number', 'UNKNOWN'),
            officer_name=StateManager.get_authenticated_officer(),
            officer_id=StateManager.get_officer_id(),
            document_type=report_type,
            ai_draft=StateManager.get_original_ai_draft(),
            final_report=StateManager.get_generated_report(),
            was_modified=(StateManager.get_generated_report() != StateManager.get_original_ai_draft()),
            verified=verified,
        )
        save_snapshot(StateManager.get_case_number(), StateManager.get_authenticated_officer(), StateManager.get_generated_report(), "Final Submitted")
        st.success("Report submitted to audit trail")


def render():
    try:
        render_department_header()

        case_col, ts_col = st.columns([3, 1])
        with case_col:
            case_val = st.text_input("Case Number", value=StateManager.get_case_number(), key="case_number_input", placeholder="e.g. INC-20260711-143022", label_visibility="collapsed")
            if case_val:
                StateManager.set_case_number(case_val)
        with ts_col:
            st.markdown(f"<div style='font-size:0.7rem;color:#64748b;font-family:monospace;padding-top:6px;text-align:right;'>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)

        st.markdown(_case_bar_html(st.session_state.get('case_number', '\u2014')), unsafe_allow_html=True)

        col_left, col_right = st.columns([5, 7], gap="large")

        with col_left:
            _render_evidence_upload()
            custom_notes, report_type = _render_notes_and_category()
            _render_phrase_book()
            _render_statute_selector(report_type)
            _render_evidence_chain()

            if st.button("Generate Narrative", type="primary", use_container_width=True, key="gen_narrative_btn"):
                _generate_narrative_flow(report_type, custom_notes)
                st.rerun()

            if st.session_state.get('transcript'):
                with st.expander("Transcript", expanded=False):
                    st.code(st.session_state['transcript'], language=None)

        with col_right:
            _render_cad_data()
            _render_compliance_results()
            _render_report_editor_and_export(report_type)

            if not StateManager.get_generated_report() and not st.session_state.get('cad_data'):
                st.markdown("""<div class="empty-state"><div class="icon">&#128203;</div>
                <div class="title">No Report Generated Yet</div>
                <div class="desc">Upload evidence and click Generate Narrative, or enter notes directly on the left</div>
                </div>""", unsafe_allow_html=True)
    except Exception as e:
        logger.exception("Error in report generation: %s", e)
        st.error(f"An error occurred: {e}")
        st.exception(e)




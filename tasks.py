from celery_app import celery_app
import gc

@celery_app.task(bind=True)
def parse_pdf_task(self, pdf_path: str):
    from pdf_parser import parse_zuercher_pdf
    return parse_zuercher_pdf(pdf_path)

@celery_app.task(bind=True)
def transcribe_video_task(self, video_path: str, initial_prompt: str = None):
    from transcriber import transcribe_bodycam
    from vision_parser import extract_frames, describe_frames
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    gc.collect()
    
    result = transcribe_bodycam(video_path, initial_prompt=initial_prompt)
    
    try:
        frames = extract_frames(video_path, interval_sec=10)
        if frames:
            descriptions = describe_frames(frames)
            if descriptions.strip():
                result += f"\n\n--- Vision AI Scene Descriptions (sampled every 10s) ---\n{descriptions}"
    except Exception as e:
        import logging
        logging.warning(f"Vision parser failed: {e}")
    
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    gc.collect()
    
    return result
def check_nibrs_task(self, text: str):
    from nibrs_checker import check_nibrs_compliance
    return check_nibrs_compliance(text)

@celery_app.task(bind=True)
def process_batch_item_task(self, item: dict):
    import os
    from pdf_parser import parse_zuercher_pdf
    from transcriber import transcribe_bodycam
    from narrative_generator import generate_narrative
    
    extra_notes = item.get('notes', '')
    ev_path = item.get('evidence_file_path', '')
    if ev_path and os.path.exists(ev_path):
        if ev_path.lower().endswith('.pdf'):
            pdf_text = parse_zuercher_pdf(ev_path)
            extra_notes = f"{extra_notes}\n--- CAD PDF ---\n{pdf_text}"
        elif any(ev_path.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.wav', '.mp3']):
            transcript = transcribe_bodycam(ev_path)
            extra_notes = f"{extra_notes}\n--- Transcript ---\n{transcript}"
            
    narrative = generate_narrative(
        cad_text=f"Call ID: {item.get('call_id', '')}\nType: {item.get('call_type', '')}\nLocation: {item.get('location', '')}",
        custom_notes=extra_notes,
        report_type=item.get('report_type', 'Standard Incident Report'),
    )
    return narrative

@celery_app.task(bind=True)
def transcribe_audio_task(self, audio_path: str):
    from transcriber import transcribe_bodycam
    return transcribe_bodycam(audio_path)

@celery_app.task(bind=True)
def generate_narrative_task(self, cad_text: str, custom_notes: str, report_type: str):
    from narrative_generator import generate_narrative
    return generate_narrative(cad_text=cad_text, custom_notes=custom_notes, report_type=report_type)

@celery_app.task(bind=True)
def redact_video_task(self, video_path: str, redaction_data: dict, output_path: str):
    from visual_redactor import redact_video
    return redact_video(video_path, redaction_data, output_path)

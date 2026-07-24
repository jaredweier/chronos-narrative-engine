import cv2
import os
import subprocess
import tempfile
from typing import List, Dict, Any

from logger import get_logger

logger = get_logger(__name__)

def apply_blur(img, box, ksize=(51, 51)):
    """Apply Gaussian blur to a bounding box region."""
    x1, y1, x2, y2 = box
    # Ensure coordinates are within image bounds
    h, w = img.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    
    if x2 <= x1 or y2 <= y1:
        return img
        
    roi = img[y1:y2, x1:x2]
    blurred_roi = cv2.GaussianBlur(roi, ksize, 0)
    img[y1:y2, x1:x2] = blurred_roi
    return img

def redact_video(video_path: str, redaction_data: Dict[str, List[Dict[str, Any]]], output_path: str) -> bool:
    """
    Redact a video based on frame-level bounding boxes.
    redaction_data maps frame filenames or index to a list of detections:
    { "frame_0001.jpg": [{"box": [x1,y1,x2,y2]}, ...] }
    """
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video: {video_path}")
            return False
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # We write to a temporary AVI file first, then use ffmpeg to combine with original audio
        temp_avi = tempfile.mktemp(suffix=".avi")
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(temp_avi, fourcc, fps, (width, height))
        
        frame_idx = 1
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_name = f"frame_{frame_idx:04d}.jpg"
            detections = redaction_data.get(frame_name, [])
            
            for det in detections:
                box = det.get("box")
                if box:
                    frame = apply_blur(frame, box)
                    
            out.write(frame)
            frame_idx += 1
            
        cap.release()
        out.release()
        
        # Merge audio from original video with the redacted video using ffmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", temp_avi,
            "-i", video_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0?", # Map audio if exists
            "-shortest",
            output_path
        ]
        
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        # Cleanup
        if os.path.exists(temp_avi):
            os.remove(temp_avi)
            
        logger.info(f"Redacted video saved to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Redaction failed: {e}")
        return False

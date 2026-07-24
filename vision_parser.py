import base64
import json
import os
import subprocess
import tempfile
import asyncio
import aiohttp
import urllib.request
import numpy as np
from typing import List, Dict, Any, Optional

from config import (
    OLLAMA_API_ENDPOINT,
    VISION_VLM_MODEL,
    VISION_ENABLE_ALPR,
    VISION_ENABLE_FACIAL_REC,
    VISION_ENABLE_ACTION_REC
)
from logger import get_logger

logger = get_logger(__name__)

def extract_frames(video_path: str, fps: int = 1) -> List[str]:
    """Extract frames at a given FPS using ffmpeg."""
    temp_dir = tempfile.mkdtemp()
    output_pattern = os.path.join(temp_dir, "frame_%04d.jpg")
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps={fps}",
        output_pattern
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        frames = sorted([os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith(".jpg")])
        logger.info(f"Extracted {len(frames)} frames from {video_path} at {fps} FPS")
        return frames
    except Exception as e:
        logger.error(f"Failed to extract frames: {e}")
        return []

async def _fetch_description(session, path):
    try:
        with open(path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")
        data = {
            "model": VISION_VLM_MODEL,
            "prompt": "Describe any people, weapons, vehicles, or notable actions in this scene.",
            "images": [encoded_image],
            "stream": False
        }
        async with session.post(OLLAMA_API_ENDPOINT, json=data) as response:
            result = await response.json()
            return result.get("response", "").strip()
    except Exception as e:
        logger.warning(f"VLM inference failed for frame {path}: {e}")
        return ""

async def _describe_frames_async(frame_paths: List[str]) -> List[str]:
    async with aiohttp.ClientSession() as session:
        tasks = [_fetch_description(session, path) for path in frame_paths]
        return await asyncio.gather(*tasks)

def describe_frames(frame_paths: List[str]) -> str:
    """Describe frames using the configured VLM (e.g. moondream2) concurrently."""
    try:
        descriptions = asyncio.run(_describe_frames_async(frame_paths))
        return "\n".join(descriptions)
    except Exception as e:
        logger.error(f"Async description failed: {e}")
        return ""

def detect_faces(frame_path: str) -> List[Dict[str, Any]]:
    """Detect faces using InsightFace."""
    if not VISION_ENABLE_FACIAL_REC:
        return []
    try:
        import cv2
        from insightface.app import FaceAnalysis
        
        # Initialize lazily to save VRAM when not used
        # Use ONNXRuntime CUDA/TensorRT provider if available
        providers = ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
        app = FaceAnalysis(name='buffalo_l', providers=providers)
        app.prepare(ctx_id=0, det_size=(640, 640))
        
        img = cv2.imread(frame_path)
        faces = app.get(img)
        
        detections = []
        for face in faces:
            box = face.bbox.astype(int).tolist()
            detections.append({
                "type": "face",
                "box": box, # [x1, y1, x2, y2]
                "score": float(face.det_score)
            })
        return detections
    except ImportError:
        logger.warning("InsightFace not installed. Skipping facial detection.")
        return []
    except Exception as e:
        logger.warning(f"Face detection failed: {e}")
        return []

def detect_license_plates(frame_path: str) -> List[Dict[str, Any]]:
    """Detect license plates (Mocked ALPR/LPRNet integration)."""
    if not VISION_ENABLE_ALPR:
        return []
    try:
        import cv2
        import easyocr
        
        reader = easyocr.Reader(['en'], gpu=True)
        img = cv2.imread(frame_path)
        results = reader.readtext(img)
        
        detections = []
        for (bbox, text, prob) in results:
            # Very basic heuristic for license plate (alphanumeric, 5-8 chars)
            clean_text = ''.join(e for e in text if e.isalnum())
            if 5 <= len(clean_text) <= 8 and prob > 0.5:
                # bbox is a list of 4 points: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                box = [int(min(x_coords)), int(min(y_coords)), int(max(x_coords)), int(max(y_coords))]
                detections.append({
                    "type": "license_plate",
                    "box": box,
                    "text": clean_text,
                    "score": float(prob)
                })
        return detections
    except ImportError:
        logger.warning("EasyOCR not installed. Skipping ALPR.")
        return []
    except Exception as e:
        logger.warning(f"ALPR failed: {e}")
        return []

def extract_entities(frame_paths: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Run entity extraction (faces, plates) across all frames."""
    results = {}
    for path in frame_paths:
        frame_name = os.path.basename(path)
        faces = detect_faces(path)
        plates = detect_license_plates(path)
        if faces or plates:
            results[frame_name] = faces + plates
    return results

def recognize_actions(video_path: str) -> List[Dict[str, Any]]:
    """Recognize actions using VideoMAE."""
    if not VISION_ENABLE_ACTION_REC:
        return []
    try:
        from transformers import VideoMAEImageProcessor, VideoMAEForVideoClassification
        import decord
        import torch
        
        decord.bridge.set_bridge("torch")
        
        processor = VideoMAEImageProcessor.from_pretrained("MCG-NJU/videomae-base-finetuned-kinetics")
        model = VideoMAEForVideoClassification.from_pretrained("MCG-NJU/videomae-base-finetuned-kinetics")
        
        vr = decord.VideoReader(video_path)
        
        # Sample 16 frames uniformly
        frame_indices = np.linspace(0, len(vr) - 1, 16, dtype=int)
        video_frames = vr.get_batch(frame_indices).permute(0, 3, 1, 2) # T, C, H, W
        
        # Convert to list of numpy arrays for processor
        video_frames = list(video_frames.numpy().transpose(0, 2, 3, 1))
        
        inputs = processor(video_frames, return_tensors="pt")
        
        # Optimize model execution
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Optional: Use torch.compile for speedup if PyTorch 2.0+ is used
        if hasattr(torch, "compile"):
            model = torch.compile(model)
            
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            
        predicted_class_idx = logits.argmax(-1).item()
        action = model.config.id2label[predicted_class_idx]
        
        logger.info(f"Detected action: {action}")
        return [{"action": action, "score": float(logits.softmax(-1).max())}]
        
    except ImportError:
        logger.warning("Transformers/Decord not installed. Skipping Action Recognition.")
        return []
    except Exception as e:
        logger.warning(f"Action recognition failed: {e}")
        return []

import os
import shutil
import tempfile
from typing import List, Optional
from config import EVIDENCE_DIR
from logger import get_logger

logger = get_logger(__name__)

os.makedirs(EVIDENCE_DIR, exist_ok=True)


def store_evidence_file(incident_id: str, file_name: str, file_bytes: bytes) -> Optional[str]:
    incident_dir = os.path.join(EVIDENCE_DIR, incident_id)
    os.makedirs(incident_dir, exist_ok=True)
    dest_path = os.path.join(incident_dir, file_name)
    n = 1
    while os.path.exists(dest_path):
        name, ext = os.path.splitext(file_name)
        dest_path = os.path.join(incident_dir, f"{name}_{n}{ext}")
        n += 1
    try:
        with open(dest_path, "wb") as f:
            f.write(file_bytes)
        logger.info("Stored evidence: %s", dest_path)
        return dest_path
    except Exception as e:
        logger.error("Failed to store evidence: %s", e)
        return None


def delete_evidence_file_on_disk(file_path: str) -> bool:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info("Deleted evidence: %s", file_path)
        return True
    except Exception as e:
        logger.error("Failed to delete evidence: %s", e)
        return False


def get_evidence_storage_size(incident_id: str) -> int:
    incident_dir = os.path.join(EVIDENCE_DIR, incident_id)
    if not os.path.isdir(incident_dir):
        return 0
    total = 0
    for dirpath, _, filenames in os.walk(incident_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total += os.path.getsize(fp)
    return total


def delete_incident_evidence(incident_id: str) -> bool:
    incident_dir = os.path.join(EVIDENCE_DIR, incident_id)
    if os.path.isdir(incident_dir):
        try:
            shutil.rmtree(incident_dir)
            logger.info("Deleted all evidence for incident: %s", incident_id)
            return True
        except Exception as e:
            logger.error("Failed to delete incident evidence: %s", e)
            return False
    return True


def list_evidence_files_on_disk(incident_id: str) -> List[dict]:
    incident_dir = os.path.join(EVIDENCE_DIR, incident_id)
    if not os.path.isdir(incident_dir):
        return []
    results = []
    for fname in os.listdir(incident_dir):
        fpath = os.path.join(incident_dir, fname)
        if os.path.isfile(fpath):
            results.append({
                "file_name": fname,
                "file_path": fpath,
                "file_size": os.path.getsize(fpath),
                "modified": os.path.getmtime(fpath),
            })
    return sorted(results, key=lambda x: x["modified"], reverse=True)


if __name__ == '__main__':
    print("Evidence Store module")
    print(f"Evidence directory: {EVIDENCE_DIR}")
    print(f"Directory exists: {os.path.isdir(EVIDENCE_DIR)}")

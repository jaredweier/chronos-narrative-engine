import os
import re
import glob
from typing import List, Optional
from pathlib import Path
from config import PROFILES_DIR, MAX_STYLE_EXAMPLES, MAX_STYLE_SAMPLES_PER_OFFICER
from logger import get_logger
from utils import extract_text_from_pdf

logger = get_logger(__name__)

SUPPORTED_SAMPLE_EXTENSIONS = ('.txt', '.pdf', '.docx')


def extract_text_from_docx(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    return '\n\n'.join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text_from_file(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == '.txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    elif ext == '.pdf':
        return extract_text_from_pdf(file_path, separator="\n\n")
    elif ext == '.docx':
        return extract_text_from_docx(file_path)
    return ''

REPORT_CATEGORIES = [
    "Standard Incident Report",
    "Search Warrant Affidavit",
    "Internal Use-of-Force Review",
    "OWI / DUI Report",
    "Domestic Violence Supplement",
    "Juvenile Offense Report",
    "Missing Person Report",
    "Narcotics Incident Report",
    "Sexual Assault Kit (SAK) Documentation",
]


def get_officer_dir(officer_name: str) -> str:
    safe_name = re.sub(r'[^a-zA-Z0-9_+\-]', '_', officer_name.replace(' ', '+'))
    return os.path.join(PROFILES_DIR, safe_name)


def get_category_dir(officer_name: str, category: str) -> str:
    safe_category = re.sub(r'[^a-zA-Z0-9_-]', '_', category)
    return os.path.join(get_officer_dir(officer_name), safe_category)


def save_style_sample(officer_name: str, category: str, sample_text: str, filename: Optional[str] = None) -> str:
    category_dir = get_category_dir(officer_name, category)
    os.makedirs(category_dir, exist_ok=True)
    
    existing = _get_all_sample_files(category_dir)
    if len(existing) >= MAX_STYLE_SAMPLES_PER_OFFICER:
        existing.sort(key=os.path.getmtime)
        excess = len(existing) - MAX_STYLE_SAMPLES_PER_OFFICER + 1
        for fpath in existing[:excess]:
            try:
                os.remove(fpath)
            except OSError:
                pass
        existing = _get_all_sample_files(category_dir)
    
    if filename is None:
        filename = f'sample_{len(existing) + 1}.txt'
    
    filepath = os.path.join(category_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(sample_text)
    
    return filepath


def _get_all_sample_files(category_dir: str) -> List[str]:
    files = []
    for ext in SUPPORTED_SAMPLE_EXTENSIONS:
        files.extend(glob.glob(os.path.join(category_dir, f'*{ext}')))
    return sorted(files)


def get_style_examples(officer_name: str, category: str, max_examples: Optional[int] = None) -> List[str]:
    category_dir = get_category_dir(officer_name, category)
    
    if not os.path.exists(category_dir):
        return []
    
    sample_files = _get_all_sample_files(category_dir)
    sample_files.sort(key=os.path.getmtime, reverse=True)
    
    limit = max_examples if max_examples is not None else MAX_STYLE_EXAMPLES
    
    examples = []
    for filepath in sample_files[:limit]:
        try:
            content = extract_text_from_file(filepath).strip()
            if content:
                examples.append(content)
        except Exception as e:
            logger.warning("Could not read style sample %s: %s", filepath, e)
            continue
    
    return examples


def get_all_officers() -> List[str]:
    if not os.path.exists(PROFILES_DIR):
        return []
    
    officers = []
    for item in os.listdir(PROFILES_DIR):
        if os.path.isdir(os.path.join(PROFILES_DIR, item)):
            officers.append(item.replace('+', ' '))
    
    return sorted(officers)


def get_officer_categories(officer_name: str) -> List[str]:
    officer_dir = get_officer_dir(officer_name)
    
    if not os.path.exists(officer_dir):
        return []
    
    categories = []
    for item in os.listdir(officer_dir):
        if os.path.isdir(os.path.join(officer_dir, item)):
            categories.append(item.replace('+', ' '))
    
    return sorted(categories)


if __name__ == '__main__':
    print("Profiler module")
    print(f"Profiles directory: {PROFILES_DIR}")
    print(f"Report categories: {REPORT_CATEGORIES}")
    for officer in get_all_officers():
        cats = get_officer_categories(officer)
        print(f"  {officer}: {cats}")




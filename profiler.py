import os
import re
import glob
from typing import List, Optional
from pathlib import Path
from config import PROFILES_DIR

SUPPORTED_SAMPLE_EXTENSIONS = ('.txt', '.pdf', '.docx')


def extract_text_from_pdf(file_path: str) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return '\n\n'.join(text_parts)


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
        return extract_text_from_pdf(file_path)
    elif ext == '.docx':
        return extract_text_from_docx(file_path)
    return ''

REPORT_CATEGORIES = [
    "Standard Incident Report",
    "Search Warrant Affidavit",
    "Internal Use-of-Force Review",
    "OWI / DUI Report"
]


def get_officer_dir(officer_name: str) -> str:
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', officer_name)
    return os.path.join(PROFILES_DIR, safe_name)


def get_category_dir(officer_name: str, category: str) -> str:
    safe_category = re.sub(r'[^a-zA-Z0-9_-]', '_', category)
    return os.path.join(get_officer_dir(officer_name), safe_category)


def save_style_sample(officer_name: str, category: str, sample_text: str, filename: Optional[str] = None) -> str:
    category_dir = get_category_dir(officer_name, category)
    os.makedirs(category_dir, exist_ok=True)
    
    if filename is None:
        existing = _get_all_sample_files(category_dir)
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


def get_style_examples(officer_name: str, category: str, max_examples: int = 5) -> List[str]:
    category_dir = get_category_dir(officer_name, category)
    
    if not os.path.exists(category_dir):
        return []
    
    sample_files = _get_all_sample_files(category_dir)
    
    examples = []
    for filepath in sample_files[:max_examples]:
        try:
            content = extract_text_from_file(filepath).strip()
            if content:
                examples.append(content)
        except Exception:
            continue
    
    return examples


def get_all_officers() -> List[str]:
    if not os.path.exists(PROFILES_DIR):
        return []
    
    officers = []
    for item in os.listdir(PROFILES_DIR):
        if os.path.isdir(os.path.join(PROFILES_DIR, item)):
            officers.append(item.replace('_', ' '))
    
    return sorted(officers)


def get_officer_categories(officer_name: str) -> List[str]:
    officer_dir = get_officer_dir(officer_name)
    
    if not os.path.exists(officer_dir):
        return []
    
    categories = []
    for item in os.listdir(officer_dir):
        if os.path.isdir(os.path.join(officer_dir, item)):
            categories.append(item.replace('_', ' '))
    
    return sorted(categories)


def delete_style_sample(officer_name: str, category: str, filename: str) -> bool:
    category_dir = get_category_dir(officer_name, category)
    filepath = os.path.join(category_dir, filename)
    
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False


def get_sample_count(officer_name: str, category: str) -> int:
    category_dir = get_category_dir(officer_name, category)
    
    if not os.path.exists(category_dir):
        return 0
    
    return len(_get_all_sample_files(category_dir))


def build_few_shot_prompt(officer_name: str, category: str, task_description: str) -> str:
    examples = get_style_examples(officer_name, category)
    
    if not examples:
        return task_description
    
    prompt_parts = [
        "You are generating a report in the style of the following examples.",
        "Match the tone, structure, and phrasing patterns demonstrated below.",
        "",
        "EXAMPLES:"
    ]
    
    for i, example in enumerate(examples, 1):
        prompt_parts.append(f"\n--- Example {i} ---")
        prompt_parts.append(example)
        prompt_parts.append("--- End Example ---")
    
    prompt_parts.extend([
        "",
        "TASK:",
        task_description,
        "",
        "Generate the report matching the style demonstrated in the examples above."
    ])
    
    return "\n".join(prompt_parts)


if __name__ == '__main__':
    print("Available categories:", REPORT_CATEGORIES)
    print("Officers with profiles:", get_all_officers())

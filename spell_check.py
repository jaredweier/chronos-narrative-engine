import re
from typing import List, Tuple, Optional
from config import SPELL_CHECK_ENABLED
from logger import get_logger

logger = get_logger(__name__)

COMMON_LE_TYPOS = {
    "recieved": "received",
    "occured": "occurred",
    "ocurred": "occurred",
    "alot": "a lot",
    "alright": "all right",
    "could of": "could have",
    "should of": "should have",
    "would of": "would have",
    "its": "it's",
    "dont": "don't",
    "didnt": "didn't",
    "wont": "won't",
    "wouldnt": "wouldn't",
    "couldnt": "couldn't",
    "shouldnt": "shouldn't",
    "wasnt": "wasn't",
    "werent": "weren't",
    "havent": "haven't",
    "hasnt": "hasn't",
    "hadnt": "hadn't",
    "isnt": "isn't",
    "arent": "aren't",
    "coudln't": "couldn't",
    "seperate": "separate",
    "definately": "definitely",
    "definitley": "definitely",
    "truely": "truly",
    "beleive": "believe",
    "belive": "believe",
    "wich": "which",
    "thier": "their",
    "recieve": "receive",
    "acheive": "achieve",
    "acheived": "achieved",
    "accomodate": "accommodate",
    "accomodated": "accommodated",
    "apparant": "apparent",
    "apparantly": "apparently",
    "appearance": "appearance",
    "comit": "commit",
    "comitted": "committed",
    "comitting": "committing",
    "commitee": "committee",
    "consistant": "consistent",
    "embarras": "embarrass",
    "enviroment": "environment",
    "goverment": "government",
    "guage": "gauge",
    "harasment": "harassment",
    "harrassment": "harassment",
    "independant": "independent",
    "interogate": "interrogate",
    "interogation": "interrogation",
    "judgment": "judgment",
    "liason": "liaison",
    "maintainance": "maintenance",
    "maintence": "maintenance",
    "miniscule": "minuscule",
    "misdameanor": "misdemeanor",
    "misdemeaner": "misdemeanor",
    "neccessary": "necessary",
    "neccessarily": "necessarily",
    "offical": "official",
    "offically": "officially",
    "occassion": "occasion",
    "occassionally": "occasionally",
    "paralel": "parallel",
    "paralell": "parallel",
    "particuarly": "particularly",
    "perpetrator": "perpetrator",
    "perpretrator": "perpetrator",
    "posession": "possession",
    "possesion": "possession",
    "priviledge": "privilege",
    "priveledge": "privilege",
    "proceedure": "procedure",
    "recieving": "receiving",
    "reccomend": "recommend",
    "reccommend": "recommend",
    "refered": "referred",
    "refering": "referring",
    "resturaunt": "restaurant",
    "sargeant": "sergeant",
    "seargent": "sergeant",
    "sargent": "sergeant",
    "suset": "suspect",
    "suspects": "suspects",
    "tommorow": "tomorrow",
    "tommorrow": "tomorrow",
    "treshold": "threshold",
    "unecessary": "unnecessary",
    "unneccessary": "unnecessary",
    "vehicule": "vehicle",
    "victem": "victim",
    "warrent": "warrant",
    "warrented": "warranted",
    "whitness": "witness",
    "wierd": "weird",
    "withold": "withhold",
    "witholding": "withholding",
    "caliber": "calibre",
    "centre": "center",
    "meter": "metre",
    "license": "licence",
    "licence": "license",
    "practise": "practice",
    "defence": "defense",
    "offence": "offense",
    "pretense": "pretense",
}


def check_text_spelling(text: str) -> List[Tuple[str, str, int]]:
    if not SPELL_CHECK_ENABLED:
        return []
    results = []
    seen_positions: set[int] = set()
    words = re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)
    for match in words:
        word = match.group()
        lower = word.lower()
        if lower in COMMON_LE_TYPOS:
            pos = match.start()
            if pos not in seen_positions:
                correction = COMMON_LE_TYPOS[lower]
                results.append((word, correction, pos))
                seen_positions.add(pos)
    if results:
        logger.info("Spell check found %d issue(s)", len(results))
    return results


def highlight_issues(text: str, issues: List[Tuple[str, str, int]]) -> str:
    if not issues:
        return text
    result = text
    for original, correction, pos in sorted(issues, key=lambda x: x[2], reverse=True):
        result = result[:pos] + f"~~{original}~~" + result[pos + len(original):]
    return result


def auto_correct(text: str) -> str:
    if not SPELL_CHECK_ENABLED:
        return text
    result = text
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)
    for word in sorted(words, key=len, reverse=True):
        lower = word.lower()
        if lower in COMMON_LE_TYPOS:
            correction = COMMON_LE_TYPOS[lower]
            if lower == word:
                result = result.replace(word, correction)
            elif lower.capitalize() == word:
                result = result.replace(word, correction.capitalize())
    return result


_WHISPER_TRANSCRIPTION_FIXES = [
    (re.compile(r'\b(\d+)\s*(\d{3})\s*(\d{4})\b'), r'\1-\2-\3'),
    (re.compile(r'\bzees\b', re.IGNORECASE), "Z's"),
    (re.compile(r'\bp i\b', re.IGNORECASE), 'PI'),
    (re.compile(r'\bdUI\b'), 'OWI'),
    (re.compile(r'\bMIRANDA\b'), 'Miranda'),
    (re.compile(r'\bNCIC\b'), 'NCIC'),
]


def auto_correct_transcript(transcript: str) -> str:
    if not SPELL_CHECK_ENABLED:
        return transcript
    result = auto_correct(transcript)
    for pattern, replacement in _WHISPER_TRANSCRIPTION_FIXES:
        result = pattern.sub(replacement, result)
    return result


if __name__ == '__main__':
    sample = "The suspect recieved a citation for distubing the peace. He was ocured at 123 Main St."
    print("Original:", sample)
    print("Corrected:", auto_correct(sample))
    issues = check_text_spelling(sample)
    print(f"\n{len(issues)} issue(s) found:")
    for orig, corr, pos in issues:
        print(f"  {orig} -> {corr} (at pos {pos})")

import re
import functools
from typing import List, Tuple, Optional
from config import SPELL_CHECK_ENABLED
from database import get_custom_dict
from logger import get_logger

logger = get_logger(__name__)


def _get_combined_dict() -> dict:
    base = dict(COMMON_LE_TYPOS)
    try:
        custom = get_custom_dict()
        base.update(custom)
    except Exception:
        pass
    return base


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
    combined = _get_combined_dict()
    words = re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)
    for match in words:
        word = match.group()
        lower = word.lower()
        if lower in combined:
            pos = match.start()
            if pos not in seen_positions:
                correction = combined[lower]
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
    combined = _get_combined_dict()
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)
    for word in sorted(words, key=len, reverse=True):
        lower = word.lower()
        if lower in combined:
            correction = combined[lower]
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
    (re.compile(r'\bforty\b', re.IGNORECASE), 'forty'),
    (re.compile(r'\bminits\b', re.IGNORECASE), 'minutes'),
    (re.compile(r'\bsecinds\b', re.IGNORECASE), 'seconds'),
    (re.compile(r'\bprobly\b', re.IGNORECASE), 'probably'),
    (re.compile(r'\bgonna\b', re.IGNORECASE), 'going to'),
    (re.compile(r'\bwanna\b', re.IGNORECASE), 'want to'),
    (re.compile(r'\bgimme\b', re.IGNORECASE), 'give me'),
    (re.compile(r'\boutta\b', re.IGNORECASE), 'out of'),
    (re.compile(r'\bkinda\b', re.IGNORECASE), 'kind of'),
    (re.compile(r'\bsorta\b', re.IGNORECASE), 'sort of'),
    (re.compile(r'\blotta\b', re.IGNORECASE), 'lot of'),
    (re.compile(r'\bcmon\b', re.IGNORECASE), 'come on'),
    (re.compile(r'\bdunno\b', re.IGNORECASE), "don't know"),
    (re.compile(r'\blemmi\b', re.IGNORECASE), 'let me'),
    (re.compile(r'\bgotta\b', re.IGNORECASE), 'got to'),
    (re.compile(r'\bhafta\b', re.IGNORECASE), 'have to'),
    (re.compile(r'\bcoulda\b', re.IGNORECASE), 'could have'),
    (re.compile(r'\bshouda\b', re.IGNORECASE), 'should have'),
    (re.compile(r'\bwouda\b', re.IGNORECASE), 'would have'),
    (re.compile(r'\bmusta\b', re.IGNORECASE), 'must have'),
    (re.compile(r'\btenn\b', re.IGNORECASE), '10'),
    (re.compile(r'\btwunny\b', re.IGNORECASE), '20'),
    (re.compile(r'\bthirtee\b', re.IGNORECASE), '30'),
    (re.compile(r'\bfortee\b', re.IGNORECASE), '40'),
    (re.compile(r'\bfiftee\b', re.IGNORECASE), '50'),
    (re.compile(r'\bsixt\b', re.IGNORECASE), 'sixth'),
    (re.compile(r'\btwenny\b', re.IGNORECASE), '20'),
    (re.compile(r'\baffidavid\b', re.IGNORECASE), 'affidavit'),
    (re.compile(r'\bprolly\b', re.IGNORECASE), 'probably'),
    (re.compile(r'\bcode \d{1,2}\b', re.IGNORECASE), lambda m: m.group(0).upper()),
    (re.compile(r'\btenn code\b', re.IGNORECASE), '10-code'),
    (re.compile(r'\bsignal \d+\b', re.IGNORECASE), lambda m: m.group(0).upper()),
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

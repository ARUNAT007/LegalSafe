import re
import unicodedata
from rapidfuzz import process, fuzz


def normalize_text(s: str) -> str:
    if not s:
        return s
    s = unicodedata.normalize("NFKD", s)
    s = s.strip()
    s = re.sub(r"[\n\r\t]", " ", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r'^[\"\']+|[\"\']+$', "", s)
    s = s.strip(" .,:;")
    return s


def canonical_party_name(name: str) -> str:
    s = normalize_text(name)
    s = re.sub(r"\s+", " ", s)
    return s


def fuzzy_find_equivalent(candidate: str, existing: list, threshold: int = 85):
    if not existing:
        return None
    candidate = normalize_text(candidate)
    choices = [normalize_text(e) for e in existing]
    match = process.extractOne(candidate, choices, scorer=fuzz.token_set_ratio)
    if not match:
        return None

    matched_text, score, _ = match
    if score >= threshold:
        for orig in existing:
            if normalize_text(orig) == matched_text:
                return orig
    return None

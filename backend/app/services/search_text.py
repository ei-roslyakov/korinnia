"""Search normalisation for names and places.

Stored `search_text` = lower-cased, accent-free tokens of the original *plus* their
Ukrainian→Latin transliteration (official KMU 2010 system). A Latin query therefore finds
Cyrillic names ("kovalenko" → "Коваленко") and vice versa (the query is transliterated too).
Trigram indexes on `search_text` make substring and fuzzy matching fast.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# KMU 2010 (Cabinet of Ministers of Ukraine resolution No. 55). Word-initial forms differ.
_UK_INITIAL = {"є": "ye", "ї": "yi", "й": "y", "ю": "yu", "я": "ya"}
_UK = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie",
    "ж": "zh", "з": "z", "и": "y", "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ь": "", "ю": "iu",
    "я": "ia",
    # Russian / Belarusian letters that appear in old records.
    "ё": "io", "ъ": "", "ы": "y", "э": "e", "ў": "u",
}  # fmt: skip
_APOSTROPHES = "'’ʼ`´"
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def transliterate_uk(text: str) -> str:
    """Ukrainian Cyrillic → Latin (KMU 2010), lower-case. Non-Cyrillic text passes through."""
    out: list[str] = []
    # Apostrophes are part of the word (Знам'янка), so drop them before splitting.
    lowered = "".join(ch for ch in text.lower() if ch not in _APOSTROPHES)
    for word in re.split(r"(\W+)", lowered):
        res = []
        for i, ch in enumerate(word):
            if i == 0 and ch in _UK_INITIAL:
                res.append(_UK_INITIAL[ch])
            elif ch == "г" and i > 0 and word[i - 1] == "з":
                res.append("gh")  # "зг" → "zgh" (Згурський → Zghurskyi)
            else:
                res.append(_UK.get(ch, ch))
        out.append("".join(res))
    return "".join(out)


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str) -> str:
    """Lower-case, remove apostrophes and diacritics (й→и, ł stays ł)."""
    text = "".join(ch for ch in text.lower() if ch not in _APOSTROPHES)
    return strip_accents(text)


def tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def build_search_text(parts: Iterable[str | None]) -> str:
    """Deduplicated tokens of all parts, normalised and transliterated."""
    seen: dict[str, None] = {}
    for part in parts:
        if not part:
            continue
        for tok in tokens(normalize(part)) + tokens(transliterate_uk(part)):
            seen.setdefault(tok, None)
    return " ".join(seen)


def query_alternatives(query: str) -> list[list[str]]:
    """For each query token, the alternative spellings to match (original + transliterated)."""
    result = []
    for raw in tokens(query.lower()):
        alts = {t for t in tokens(normalize(raw)) + tokens(transliterate_uk(raw)) if t}
        if alts:
            result.append(sorted(alts))
    return result

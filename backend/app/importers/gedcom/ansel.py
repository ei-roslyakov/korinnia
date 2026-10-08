"""ANSEL (ANSI Z39.47), the default character set of GEDCOM 5.5 and still exported by
older programs. ASCII is unchanged; special letters live in 0xA1–0xC8; diacritics are
combining marks in 0xE0–0xFE written *before* the letter they modify (Unicode puts them
after), so they are moved behind the next character and the result is NFC-normalised.
"""

from __future__ import annotations

import unicodedata

_SPECIAL = {
    0xA1: "Ł", 0xA2: "Ø", 0xA3: "Đ", 0xA4: "Þ", 0xA5: "Æ", 0xA6: "Œ", 0xA7: "ʹ",
    0xA8: "·", 0xA9: "♭", 0xAA: "®", 0xAB: "±", 0xAC: "Ơ", 0xAD: "Ư", 0xAE: "ʼ",
    0xB0: "ʻ", 0xB1: "ł", 0xB2: "ø", 0xB3: "đ", 0xB4: "þ", 0xB5: "æ", 0xB6: "œ",
    0xB7: "ʺ", 0xB8: "ı", 0xB9: "£", 0xBA: "ð", 0xBC: "ơ", 0xBD: "ư", 0xBE: "□",
    0xBF: "■", 0xC0: "°", 0xC1: "ℓ", 0xC2: "℗", 0xC3: "©", 0xC4: "♯", 0xC5: "¿",
    0xC6: "¡", 0xC7: "ß", 0xC8: "€", 0xCD: "e", 0xCE: "o", 0xCF: "ß",
}  # fmt: skip

_COMBINING = {
    0xE0: "̉", 0xE1: "̀", 0xE2: "́", 0xE3: "̂", 0xE4: "̃",
    0xE5: "̄", 0xE6: "̆", 0xE7: "̇", 0xE8: "̈", 0xE9: "̌",
    0xEA: "̊", 0xEB: "︠", 0xEC: "︡", 0xED: "̕", 0xEE: "̋",
    0xEF: "̐", 0xF0: "̧", 0xF1: "̨", 0xF2: "̣", 0xF3: "̤",
    0xF4: "̥", 0xF5: "̳", 0xF6: "̲", 0xF7: "̦", 0xF8: "̜",
    0xF9: "̮", 0xFA: "︢", 0xFB: "︣", 0xFE: "̓",
}  # fmt: skip


def decode_ansel(raw: bytes) -> str:
    out: list[str] = []
    pending: list[str] = []  # combining marks waiting for their base letter
    for b in raw:
        if b in _COMBINING:
            pending.append(_COMBINING[b])
            continue
        ch = chr(b) if b < 0x80 else _SPECIAL.get(b, "�")
        out.append(ch)
        if pending:
            out.extend(pending)
            pending.clear()
    out.extend(pending)
    return unicodedata.normalize("NFC", "".join(out))

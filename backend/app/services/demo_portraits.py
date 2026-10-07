"""Illustrated portraits for the fictional demo family.

The demo people are invented, so there are no real photographs of them, and photo-realistic
fakes could be mistaken for genuine records in a family archive. Instead each person gets a
detailed *drawn* portrait made to look like a photograph of their time:

- born before 1915: a sepia cabinet card (oval photo on a cream mount);
- 1915–1959: a faded black-and-white print with a white border;
- from 1960: a slightly yellowed colour print.

Faces, hair, clothing (embroidered shirts, coral beads, headscarves, jackets and ties) and
age vary per person and era. Everything is drawn with Pillow at double size and scaled down
for smooth edges; a seeded generator makes the result deterministic. A small "ілюстрація"
mark stays on every image.
"""

from __future__ import annotations

import io
import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

WIDTH, HEIGHT = 600, 750
S = 2  # supersampling factor
# Square crop around the face (fractions of the image), used for the card portrait.
HEAD_CROP = {"x": 0.2, "y": 0.12, "w": 0.6, "h": 0.48}

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
RGB = tuple[int, int, int]
Pt = tuple[float, float]
ERAS = ("sepia", "faded", "colour")


def era_of(birth_year: int | None) -> str:
    if birth_year is None or birth_year < 1915:
        return "sepia"
    return "faded" if birth_year < 1960 else "colour"


@cache
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    name = "DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf"
    try:
        return ImageFont.truetype(f"{FONT_DIR}/{name}", size)
    except OSError:  # pragma: no cover - fonts are installed in the image
        return ImageFont.load_default(size)


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def _shade(c: RGB, f: float) -> RGB:
    """f < 1 darkens, f > 1 lightens."""
    return _mix(c, (0, 0, 0), 1 - f) if f < 1 else _mix(c, (255, 255, 255), f - 1)


@dataclass
class Look:
    """Everything that varies from person to person."""

    gender: str
    era: str
    age: int
    skin: RGB
    hair: RGB
    eyes: RGB
    lips: RGB
    face_w: float
    face_h: float
    eye_gap: float
    nose_len: float
    mouth_w: float
    tilt: float
    hairstyle: str
    moustache: bool
    beard: bool
    clothing: str
    backdrop: RGB


HAIR_COLOURS: list[RGB] = [(38, 28, 22), (62, 44, 30), (92, 64, 40), (128, 96, 62), (20, 18, 18)]
EYE_COLOURS: list[RGB] = [(84, 60, 40), (60, 90, 110), (90, 110, 80), (70, 52, 36), (100, 120, 140)]
BACKDROPS: dict[str, RGB] = {
    "sepia": (176, 168, 150),
    "faded": (150, 152, 150),
    "colour": (150, 170, 182),
}


def _look(gender: str, birth_year: int | None, age: int, rnd: random.Random) -> Look:
    era = era_of(birth_year)
    hair = rnd.choice(HAIR_COLOURS)
    if age >= 58:  # greying
        hair = _mix(hair, (190, 186, 180), min(0.85, (age - 50) / 30))
    female = gender == "female"
    if female:
        hairstyle = {
            "sepia": rnd.choice(["scarf", "bun", "braids"]),
            "faded": rnd.choice(["waves", "bun", "waves"]),
            "colour": rnd.choice(["long", "bob", "long"]),
        }[era]
        clothing = {
            "sepia": "vyshyvanka_f",
            "faded": rnd.choice(["dress", "vyshyvanka_f"]),
            "colour": rnd.choice(["blouse", "sweater"]),
        }[era]
    else:
        hairstyle = rnd.choice(["side", "back"])
        clothing = {
            "sepia": rnd.choice(["vyshyvanka_m", "jacket"]),
            "faded": rnd.choice(["suit", "suit", "vyshyvanka_m"]),
            "colour": rnd.choice(["suit_open", "sweater"]),
        }[era]
    return Look(
        gender=gender,
        era=era,
        age=age,
        skin=_mix((236, 196, 168), (196, 150, 118), rnd.random() * 0.6),
        hair=hair,
        eyes=rnd.choice(EYE_COLOURS),
        lips=_mix((184, 108, 100), (160, 92, 86), rnd.random()),
        face_w=rnd.uniform(64, 72) * (0.94 if female else 1.0),
        face_h=rnd.uniform(88, 96),
        eye_gap=rnd.uniform(0.38, 0.44),
        nose_len=rnd.uniform(0.28, 0.36),
        mouth_w=rnd.uniform(20, 25) * (0.92 if female else 1.0),
        tilt=rnd.uniform(-5, 5),
        hairstyle=hairstyle,
        moustache=not female and rnd.random() < {"sepia": 0.85, "faded": 0.3, "colour": 0.12}[era],
        beard=not female and era == "sepia" and age > 40 and rnd.random() < 0.35,
        clothing=clothing,
        backdrop=BACKDROPS[era],
    )


# --- Drawing helpers (base coordinates; scaled by S) -----------------------------------------


class Pen:
    def __init__(self, img: Image.Image) -> None:
        self.d = ImageDraw.Draw(img, "RGBA")

    def ellipse(self, box: tuple[float, float, float, float], fill: tuple[int, ...]) -> None:
        self.d.ellipse([v * S for v in box], fill=fill)

    def poly(self, pts: list[Pt], fill: tuple[int, ...]) -> None:
        self.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)

    def line(self, pts: list[Pt], fill: tuple[int, ...], width: float) -> None:
        self.d.line(
            [(x * S, y * S) for x, y in pts],
            fill=fill,
            width=max(1, round(width * S)),
            joint="curve",
        )


def _bezier(p0: Pt, p1: Pt, p2: Pt, n: int = 16) -> list[Pt]:
    return [
        (
            (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1],
        )
        for t in (i / n for i in range(n + 1))
    ]


def _face_outline(cx: float, cy: float, w: float, h: float) -> list[Pt]:
    """Egg shape: full cheeks, narrower jaw and chin."""
    pts = []
    for i in range(72):
        t = 2 * math.pi * i / 72
        narrow = 1 - 0.22 * max(0.0, math.sin(t)) ** 1.6
        pts.append((cx + w * math.cos(t) * narrow, cy + h * math.sin(t)))
    return pts


def _soft(
    size: tuple[int, int], draw: Callable[[ImageDraw.ImageDraw], None], blur: float
) -> Image.Image:
    """An L-mode mask drawn by `draw` and blurred (for shading)."""
    m = Image.new("L", size, 0)
    draw(ImageDraw.Draw(m))
    return m.filter(ImageFilter.GaussianBlur(blur * S))


def _embroidery(pen: Pen, x0: float, x1: float, y: float, rows: int = 2) -> None:
    """A band of cross-stitch: red and black diamonds, as on a vyshyvanka."""
    red, black = (170, 30, 36, 255), (30, 24, 24, 255)
    step = 9.0
    for r in range(rows):
        yy, x, k = y + r * step, x0, 0
        while x < x1:
            diamond = [
                (x, yy),
                (x + step / 2, yy - step / 2),
                (x + step, yy),
                (x + step / 2, yy + step / 2),
            ]
            pen.poly(diamond, red if (k + r) % 3 else black)
            x += step
            k += 1


# --- The portrait ------------------------------------------------------------------------------


def _clothes(pen: Pen, look: Look, cx: float, top: float, rnd: random.Random) -> None:
    female = look.gender == "female"
    sh_w = 180 if female else 205
    body = [
        (cx - sh_w, HEIGHT + 20),
        *_bezier((cx - sh_w, HEIGHT - 60), (cx - sh_w + 20, top + 6), (cx - 46, top - 4)),
        *_bezier((cx + 46, top - 4), (cx + sh_w - 20, top + 6), (cx + sh_w, HEIGHT - 60)),
        (cx + sh_w, HEIGHT + 20),
    ]
    base: RGB = {
        "vyshyvanka_f": (238, 234, 222),
        "vyshyvanka_m": (236, 232, 220),
        "jacket": (52, 46, 42),
        "suit": (48, 50, 56),
        "suit_open": (60, 72, 92),
        "dress": (70, 64, 70),
        "blouse": (196, 176, 150),
        "sweater": rnd.choice([(120, 60, 50), (60, 90, 70), (90, 90, 110)]),
    }[look.clothing]
    pen.poly(body, (*base, 255))
    clothing = look.clothing
    if clothing in ("jacket", "suit", "suit_open"):
        shirt = (232, 230, 224, 255)
        pen.poly([(cx - 40, top - 2), (cx + 40, top - 2), (cx, top + 120)], shirt)
        if clothing != "suit_open":  # tie
            tie = rnd.choice([(90, 30, 34), (40, 44, 70), (30, 30, 34)])
            pen.poly(
                [
                    (cx - 9, top + 12),
                    (cx + 9, top + 12),
                    (cx + 14, top + 110),
                    (cx, top + 125),
                    (cx - 14, top + 110),
                ],
                (*tie, 255),
            )
            pen.poly(
                [(cx - 11, top + 2), (cx + 11, top + 2), (cx + 8, top + 14), (cx - 8, top + 14)],
                (*_shade(tie, 0.8), 255),
            )
        lapel = (*_shade(base, 0.8), 255)
        for side in (-1, 1):
            pen.poly(
                [
                    (cx + side * 46, top - 4),
                    (cx + side * 8, top + 120),
                    (cx + side * 70, top + 60),
                    (cx + side * 96, top + 8),
                ],
                lapel,
            )
            pen.poly(
                [(cx + side * 40, top - 4), (cx + side * 4, top + 26), (cx + side * 30, top + 30)],
                shirt,
            )
    elif clothing.startswith("vyshyvanka"):
        pen.line(
            _bezier((cx - 44, top - 2), (cx, top + 26), (cx + 44, top - 2)),
            (*_shade(base, 0.8), 255),
            2,
        )
        _embroidery(pen, cx - 44, cx + 44, top + 8)
        if clothing == "vyshyvanka_m":
            for k in range(6):
                _embroidery(pen, cx - 12, cx + 12, top + 32 + k * 20, rows=1)
        else:
            for side in (-1, 1):
                _embroidery(pen, cx + side * 150 - 30, cx + side * 150 + 30, top + 70, rows=3)
    elif clothing == "dress":
        pen.poly(
            [
                (cx - 52, top - 6),
                (cx, top + 40),
                (cx + 52, top - 6),
                (cx + 60, top + 8),
                (cx, top + 52),
                (cx - 60, top + 8),
            ],
            (236, 232, 222, 255),
        )
        for k in range(3):
            pen.ellipse(
                (cx - 4, top + 60 + k * 26, cx + 4, top + 68 + k * 26), (220, 214, 200, 255)
            )
    elif clothing == "blouse":
        pen.line(
            _bezier((cx - 50, top - 2), (cx, top + 46), (cx + 50, top - 2)),
            (*_shade(base, 0.75), 255),
            3,
        )
    else:  # sweater
        pen.poly(
            [(cx - 46, top - 6), (cx + 46, top - 6), (cx + 50, top + 16), (cx - 50, top + 16)],
            (*_shade(base, 0.85), 255),
        )

    if female and look.era == "sepia":  # coral beads (namysto)
        coral = (176, 44, 40)
        for row in range(3):
            for x, y in _bezier(
                (cx - 58 - row * 4, top - 2),
                (cx, top + 40 + row * 14),
                (cx + 58 + row * 4, top - 2),
                n=14,
            ):
                pen.ellipse(
                    (x - 5, y - 5, x + 5, y + 5), (*_shade(coral, 0.85 + 0.1 * (row % 2)), 255)
                )
                pen.ellipse((x - 2.5, y - 3.5, x - 0.5, y - 1.5), (255, 220, 210, 160))


def _features(pen: Pen, look: Look, cx: float, cy: float) -> None:
    fw, fh, skin = look.face_w, look.face_h, look.skin
    female = look.gender == "female"
    for side in (-1, 1):  # cheeks
        pen.ellipse(
            (
                cx + side * fw * 0.5 - 18,
                cy + fh * 0.18 - 10,
                cx + side * fw * 0.5 + 18,
                cy + fh * 0.18 + 12,
            ),
            (200, 110, 100, 34),
        )

    ey = cy - fh * 0.06
    for side in (-1, 1):
        ex = cx + side * fw * look.eye_gap
        ew, eh = 15.0, 6.5
        pen.ellipse(
            (ex - ew - 4, ey - eh - 7, ex + ew + 4, ey + eh + 3), (*_shade(skin, 0.86), 110)
        )
        almond = _bezier((ex - ew, ey), (ex, ey - eh * 2), (ex + ew, ey)) + _bezier(
            (ex + ew, ey), (ex, ey + eh * 1.4), (ex - ew, ey)
        )
        pen.poly(almond, (236, 232, 226, 255))
        pen.ellipse((ex - 6.5, ey - 6.5, ex + 6.5, ey + 6.5), (*look.eyes, 255))
        pen.ellipse((ex - 3, ey - 3, ex + 3, ey + 3), (14, 12, 12, 255))
        pen.ellipse((ex + 1, ey - 4, ex + 3.5, ey - 1.5), (255, 255, 255, 220))
        pen.line(
            _bezier((ex - ew - 1, ey + 1), (ex, ey - eh * 2.1), (ex + ew + 1, ey)),
            (30, 24, 22, 255),
            2.4,
        )
        pen.line(
            _bezier((ex - ew + 3, ey + 2), (ex, ey + eh * 1.5), (ex + ew - 3, ey + 1)),
            (*_shade(skin, 0.7), 140),
            1,
        )
        by = ey - 19
        pen.line(
            _bezier((ex - 18, by + 4), (ex + side * 2, by - 6), (ex + 18, by + 3)),
            (*_shade(look.hair, 0.8), 230),
            3.0 if female else 4.2,
        )
        if look.age > 45:  # crow's feet
            for k in range(2):
                pen.line(
                    [
                        (ex + side * (ew + 6), ey - 2 + k * 5),
                        (ex + side * (ew + 13), ey - 4 + k * 7),
                    ],
                    (*_shade(skin, 0.75), 90),
                    1,
                )

    ny = cy + fh * look.nose_len
    pen.line(
        _bezier((cx - 6, ey + 4), (cx - 11, ny - 18), (cx - 9, ny - 2)),
        (*_shade(skin, 0.78), 110),
        3,
    )
    pen.ellipse((cx - 11, ny - 9, cx + 11, ny + 7), (*_shade(skin, 1.04), 160))
    for side in (-1, 1):
        pen.ellipse(
            (cx + side * 7 - 4, ny - 1, cx + side * 7 + 4, ny + 4), (*_shade(skin, 0.55), 200)
        )
        pen.line(
            _bezier((cx + side * 12, ny - 8), (cx + side * 16, ny), (cx + side * 9, ny + 4)),
            (*_shade(skin, 0.7), 150),
            1.6,
        )

    my, mw = cy + fh * 0.56, look.mouth_w
    upper = _bezier((cx - mw, my), (cx - mw * 0.4, my - 7), (cx, my - 3)) + _bezier(
        (cx, my - 3), (cx + mw * 0.4, my - 7), (cx + mw, my)
    )
    pen.poly(upper, (*_shade(look.lips, 0.88), 255))
    pen.poly(
        _bezier((cx + mw, my), (cx, my + (12 if female else 9)), (cx - mw, my)), (*look.lips, 255)
    )
    pen.line(
        _bezier((cx - mw, my), (cx, my + 2), (cx + mw, my)), (*_shade(look.lips, 0.5), 255), 1.6
    )
    pen.ellipse((cx - 8, my + 3, cx + 8, my + 7), (255, 230, 220, 60))
    if look.age > 40:  # nasolabial folds
        for side in (-1, 1):
            pen.line(
                _bezier(
                    (cx + side * 14, ny + 2),
                    (cx + side * 26, my - 6),
                    (cx + side * (mw + 6), my + 6),
                ),
                (*_shade(skin, 0.74), 90),
                1.6,
            )
    if look.age > 50:  # forehead lines
        for k in range(2):
            fy = cy - fh * 0.55 + k * 9
            pen.line(
                _bezier((cx - 30, fy), (cx, fy - 4), (cx + 30, fy)), (*_shade(skin, 0.78), 70), 1.2
            )

    hair_dark = _shade(look.hair, 0.7)
    if look.beard:
        jaw = _face_outline(cx, cy, fw + 2, fh + 6)[4:33]
        pen.poly([*jaw, (cx + mw + 8, my + 4), (cx - mw - 8, my + 4)], (*hair_dark, 235))
    if look.moustache:
        pen.poly(
            _bezier((cx - mw - 12, my + 6), (cx - mw * 0.6, my - 16), (cx, my - 12))
            + _bezier((cx, my - 12), (cx + mw * 0.6, my - 16), (cx + mw + 12, my + 6))
            + _bezier((cx + mw + 12, my + 6), (cx + mw * 0.5, my - 4), (cx, my - 3))
            + _bezier((cx, my - 3), (cx - mw * 0.5, my - 4), (cx - mw - 12, my + 6)),
            (*hair_dark, 250),
        )


def _hair(pen: Pen, look: Look, cx: float, cy: float, rnd: random.Random) -> None:
    fw, fh, hair = look.face_w, look.face_h, look.hair
    female = look.gender == "female"
    hl = cy - fh * 0.52  # hairline
    if look.hairstyle == "scarf":
        scarf = rnd.choice([(150, 40, 40), (60, 50, 90), (120, 90, 40)])
        outer = _bezier(
            (cx - fw - 18, cy + 30), (cx - fw - 30, cy - fh - 40), (cx, cy - fh - 30)
        ) + _bezier((cx, cy - fh - 30), (cx + fw + 30, cy - fh - 40), (cx + fw + 18, cy + 30))
        # Only the part around the head: the face opening stays visible.
        opening = _bezier((cx - fw + 2, cy + 10), (cx, hl - 30), (cx + fw - 2, cy + 10))
        pen.poly(outer + opening[::-1], (*scarf, 255))
        for k in range(16):  # printed flowers
            a = math.pi + math.pi * k / 15
            px, py = cx + (fw + 12) * math.cos(a), cy - 6 + (fh + 18) * math.sin(a)
            pen.ellipse((px - 4, py - 4, px + 4, py + 4), (235, 205, 120, 220))
        pen.poly(
            _bezier((cx - fw * 0.75, hl + 14), (cx, hl - 10), (cx + fw * 0.75, hl + 14)),
            (*hair, 255),
        )
        for side in (-1, 1):  # ends tied under the chin
            pen.poly(
                [
                    (cx + side * (fw + 16), cy + 26),
                    (cx + side * 10, cy + fh + 28),
                    (cx + side * (fw - 6), cy + 30),
                ],
                (*scarf, 255),
            )
        pen.ellipse((cx - 14, cy + fh + 16, cx + 14, cy + fh + 38), (*_shade(scarf, 0.8), 255))
        return
    if female and look.hairstyle in ("bun", "braids"):
        pen.ellipse((cx - 36, cy - fh - 52, cx + 36, cy - fh + 8), (*_shade(hair, 0.7), 255))
    if female:
        cap = _bezier(
            (cx - fw - 6, cy + 4), (cx - fw - 12, cy - fh - 30), (cx, cy - fh - 22)
        ) + _bezier((cx, cy - fh - 22), (cx + fw + 12, cy - fh - 30), (cx + fw + 6, cy + 4))
        # Centre part, swept to both sides.
        cap += _bezier((cx + fw - 2, cy - 6), (cx + fw * 0.4, hl - 6), (cx, hl - 10))
        cap += _bezier((cx, hl - 10), (cx - fw * 0.4, hl - 6), (cx - fw + 2, cy - 6))
        pen.poly(cap, (*hair, 255))
        for _ in range(7):  # a few loose strands, irregular so it never looks knitted
            sx = cx + rnd.uniform(-0.8, 0.8) * fw
            bend = rnd.uniform(-14, 14)
            pen.line(
                _bezier(
                    (cx, cy - fh - 16), (sx + bend, cy - fh * 0.8), (sx, hl + rnd.uniform(-6, 6))
                ),
                (*_shade(hair, rnd.uniform(1.15, 1.4)), rnd.randint(30, 70)),
                rnd.uniform(0.8, 1.6),
            )
    else:
        # Short hair close to the head: from temple to temple, a side part.
        recede = 10 if look.age > 50 else 0
        temple = cy - fh * 0.28
        part_x = cx - fw * 0.35 if look.hairstyle == "side" else cx
        cap = _bezier(
            (cx - fw - 2, temple), (cx - fw - 6, cy - fh - 16), (cx, cy - fh - 12)
        ) + _bezier((cx, cy - fh - 12), (cx + fw + 6, cy - fh - 16), (cx + fw + 2, temple))
        cap += _bezier(
            (cx + fw - 2, temple), (cx + fw * 0.55, hl - recede - 4), (part_x, hl - recede + 2)
        )
        cap += _bezier(
            (part_x, hl - recede + 2), (cx - fw * 0.6, hl - recede - 4), (cx - fw + 2, temple)
        )
        pen.poly(cap, (*hair, 255))
        # A few combed strands, sweeping away from the part.
        for _ in range(6):
            y0 = rnd.uniform(cy - fh - 8, hl - recede - 6)
            pen.line(
                _bezier(
                    (part_x, y0),
                    (part_x + fw * rnd.uniform(0.4, 0.8), y0 - 8),
                    (cx + fw - 4, y0 + rnd.uniform(6, 16)),
                ),
                (*_shade(hair, rnd.uniform(1.15, 1.35)), rnd.randint(30, 60)),
                rnd.uniform(0.8, 1.4),
            )
        # Sideburns.
        for side in (-1, 1):
            pen.poly(
                [
                    (cx + side * (fw - 1), temple),
                    (cx + side * (fw - 6), temple),
                    (cx + side * (fw - 5), cy + 2),
                    (cx + side * (fw - 1), cy + 2),
                ],
                (*hair, 255),
            )
    # Soft sheen where the studio light catches the hair.
    pen.ellipse((cx - fw * 0.55, cy - fh - 14, cx + fw * 0.05, cy - fh + 8), (255, 255, 255, 30))
    pen.ellipse((cx - fw * 0.4, cy - fh - 10, cx - fw * 0.05, cy - fh + 2), (255, 255, 255, 25))
    if female and look.hairstyle == "waves":
        for side in (-1, 1):
            for k in range(3):
                wy = cy - 10 + k * 26
                pen.ellipse(
                    (cx + side * (fw + 8) - 16, wy - 14, cx + side * (fw + 8) + 16, wy + 14),
                    (*hair, 255),
                )


def _draw_person(look: Look, rnd: random.Random) -> Image.Image:
    size = (WIDTH * S, HEIGHT * S)
    img = Image.new("RGB", size, look.backdrop)
    glow = _soft(size, lambda d: d.ellipse((150 * S, 80 * S, 450 * S, 480 * S), fill=255), 110)
    img = Image.composite(Image.new("RGB", size, _shade(look.backdrop, 1.22)), img, glow)
    pen = Pen(img)
    cx, cy = 300 + look.tilt, 262.0
    fw, fh = look.face_w, look.face_h
    skin_dark = _shade(look.skin, 0.78)
    female = look.gender == "female"

    if female and look.hairstyle in ("long", "braids", "waves", "bob"):  # hair behind the head
        drop = {"long": 175, "braids": 60, "waves": 95, "bob": 70}[look.hairstyle]
        pen.ellipse(
            (cx - fw - 24, cy - fh - 18, cx + fw + 24, cy + fh * 0.4 + drop),
            (*_shade(look.hair, 0.7), 255),
        )
        if look.hairstyle == "braids":
            for side in (-1, 1):
                bx = cx + side * (fw + 6)
                for k in range(7):
                    pen.ellipse(
                        (bx - 11, cy + 10 + k * 22, bx + 11, cy + 36 + k * 22), (*look.hair, 255)
                    )

    top = cy + fh + 46
    pen.poly(
        [
            (cx - fw * 0.42, cy + fh * 0.55),
            (cx + fw * 0.42, cy + fh * 0.55),
            (cx + fw * 0.5, top + 20),
            (cx - fw * 0.5, top + 20),
        ],
        (*skin_dark, 255),
    )
    # Shadow the chin casts on the neck (the face is drawn over its top half).
    pen.ellipse(
        (cx - fw * 0.5, cy + fh * 0.7, cx + fw * 0.5, cy + fh * 1.12),
        (*_shade(look.skin, 0.62), 150),
    )
    _clothes(pen, look, cx, top, rnd)
    for side in (-1, 1):  # ears
        ex = cx + side * (fw - 3)
        pen.ellipse((ex - 10, cy - 14, ex + 10, cy + 22), (*skin_dark, 255))
        pen.ellipse((ex - 6, cy - 8, ex + 6, cy + 16), (*_shade(skin_dark, 0.9), 255))

    # The face, lighter in the middle and shaded towards the edges.
    face_mask = Image.new("L", size, 0)
    ImageDraw.Draw(face_mask).polygon(
        [(x * S, y * S) for x, y in _face_outline(cx, cy, fw, fh)], fill=255
    )
    inner = _soft(
        size,
        lambda d: d.ellipse(
            ((cx - fw * 0.75) * S, (cy - fh * 0.85) * S, (cx + fw * 0.7) * S, (cy + fh * 0.75) * S),
            fill=255,
        ),
        26,
    )
    face = Image.composite(
        Image.new("RGB", size, _shade(look.skin, 1.06)), Image.new("RGB", size, skin_dark), inner
    )
    img.paste(face, (0, 0), face_mask)
    pen = Pen(img)
    _features(pen, look, cx, cy)
    _hair(pen, look, cx, cy, rnd)
    return img


def _finish(img: Image.Image, era: str, rnd: random.Random) -> Image.Image:
    """Photographic look of the era: tone, softness, grain, vignette."""
    img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).filter(
        ImageFilter.GaussianBlur(0.6)
    )
    if era == "sepia":
        img = ImageOps.colorize(ImageOps.grayscale(img), black=(40, 26, 16), white=(246, 232, 204))
    elif era == "faded":
        gray = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
        img = ImageOps.colorize(gray, black=(38, 38, 40), white=(236, 234, 226))
        img = Image.blend(img, Image.new("RGB", img.size, (200, 198, 190)), 0.12)
    else:
        img = Image.blend(img, Image.new("RGB", img.size, (230, 200, 150)), 0.1)
    grain = Image.frombytes("L", img.size, rnd.randbytes(WIDTH * HEIGHT)).convert("RGB")
    img = Image.blend(img, grain, 0.05 if era != "colour" else 0.03)
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).ellipse((40, 20, 560, 700), fill=255)
    vignette = m.filter(ImageFilter.GaussianBlur(60))
    dark = ImageChops.multiply(img, Image.new("RGB", img.size, (150, 140, 128)))
    return Image.composite(img, dark, vignette)


def render_portrait(
    *,
    name: str,
    years: str,
    gender: str,
    birth_year: int | None,
    seed: int,
    age: int = 40,
) -> bytes:
    """A JPEG illustration (600×750) styled as a photo of the person's era. Deterministic."""
    rnd = random.Random(seed)  # noqa: S311 - drawing variation, not security
    look = _look(gender, birth_year, age, rnd)
    photo = _finish(_draw_person(look, rnd), look.era, rnd)

    if look.era == "sepia":  # cabinet card: oval photo on a cream mount
        card = Image.new("RGB", (WIDTH, HEIGHT), (226, 212, 182))
        window = Image.new("L", (WIDTH, HEIGHT), 0)
        ImageDraw.Draw(window).ellipse((80, 40, 520, 610), fill=255)
        card.paste(photo, (0, 0), window.filter(ImageFilter.GaussianBlur(2)))
        d = ImageDraw.Draw(card)
        d.ellipse((72, 32, 528, 618), outline=(150, 118, 64), width=3)
        d.rectangle((14, 14, WIDTH - 15, HEIGHT - 15), outline=(170, 140, 90), width=2)
        ink: RGB = (88, 62, 34)
    else:  # print with a white border
        card = Image.new(
            "RGB", (WIDTH, HEIGHT), (240, 238, 230) if look.era == "faded" else (246, 244, 236)
        )
        card.paste(photo.crop((40, 30, WIDTH - 40, 620)), (40, 30))
        d = ImageDraw.Draw(card)
        ink = (70, 72, 86) if look.era == "faded" else (60, 66, 80)
    d.text((WIDTH // 2, 660), name, font=_font(28, bold=True), fill=ink, anchor="mm")
    if years:
        d.text((WIDTH // 2, 700), years, font=_font(22), fill=ink, anchor="mm")
    d.text(
        (WIDTH - 22, HEIGHT - 20),
        "ілюстрація",
        font=_font(12),
        fill=_mix(ink, (255, 255, 255), 0.45),
        anchor="rd",
    )

    out = io.BytesIO()
    card.save(out, "JPEG", quality=90, optimize=True)
    return out.getvalue()

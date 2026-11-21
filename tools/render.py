#!/usr/bin/env python3
"""Render the passport spread for the fictional Republic of Talveria.

Draws an open passport spread (data page + visa/stamp page) as a single
1024x1024 PNG. Everything is drawn programmatically with Pillow: no
photographs, no downloads, fully deterministic — the same bytes on every
run. The entry program (main.py) only copies the rendered PNG to
/output/entry.png.

Fictional country: the Republic of Talveria, a small alpine republic.
Holder: Mara Ilven Kessler, born 14 JUN 1988 in Aldermark. Passport
issued 12 MAR 2024, expires 11 MAR 2034. Every stamp is dated after
the issue date and before expiry, in chronological order, from
fictional neighbouring states (Meridia, Kastelvar, Isla Mirra).
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "assets", "passport.png")

# ---------------------------------------------------------------- fonts

SERIF = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]
SERIF_B = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
]
SERIF_I = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
]
SANS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
SANS_B = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
MONO = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


def font(candidates, size):
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


# ---------------------------------------------------------------- palette

PAPER = (247, 242, 230)
PAPER_EDGE = (233, 226, 207)
INK = (28, 32, 38)
NAVY = (31, 58, 95)
NAVY_DK = (22, 42, 70)
GREY = (110, 108, 100)
RULE = (150, 142, 122)
BURGUNDY = (122, 31, 43)
GREEN = (46, 94, 60)
DESK_TOP = (40, 48, 53)
DESK_BOT = (26, 31, 35)
PHOTO_BG_TOP = (186, 196, 201)
PHOTO_BG_BOT = (164, 178, 184)
SKIN = (210, 165, 138)
SKIN_DK = (196, 148, 120)
HAIR = (74, 50, 38)
JACKET = (43, 58, 74)


# ---------------------------------------------------------------- helpers


def text(draw, xy, s, candidates, size, fill, anchor="la"):
    draw.text(xy, s, font=font(candidates, size), fill=fill, anchor=anchor)


def spaced(draw, xy, s, candidates, size, fill, tracking, anchor="la"):
    """Draw text with extra tracking between characters."""
    fnt = font(candidates, size)
    x, y = xy
    if anchor in ("ma", "mm", "md"):
        total = sum(draw.textlength(ch, font=fnt) for ch in s)
        total += tracking * max(len(s) - 1, 0)
        x -= total // 2
    elif anchor in ("ra", "rm", "rd"):
        total = sum(draw.textlength(ch, font=fnt) for ch in s)
        total += tracking * max(len(s) - 1, 0)
        x -= total
    for ch in s:
        draw.text((x, y), ch, font=fnt, fill=fill, anchor="la")
        x += draw.textlength(ch, font=fnt) + tracking


def wrap(draw, s, candidates, size, width):
    fnt = font(candidates, size)
    words = s.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def check_digit(s):
    """ICAO 9303 check digit: weights 7,3,1; A=10..Z=35, '<'=0."""
    total = 0
    for i, ch in enumerate(s):
        if ch == "<":
            v = 0
        elif ch.isdigit():
            v = int(ch)
        else:
            v = ord(ch) - ord("A") + 10
        total += v * (7, 3, 1)[i % 3]
    return str(total % 10)


def mrz_lines():
    line1 = "P<TVKESSLER<<MARA<ILVEN" + "<" * 21
    doc = "TV4829137"
    nat = "TAL"
    dob = "880614"
    sex = "F"
    exp = "340311"
    personal = "MARA19880614<<"
    l2 = (
        doc + check_digit(doc)
        + nat
        + dob + check_digit(dob)
        + sex
        + exp + check_digit(exp)
        + personal + check_digit(personal)
    )
    l2 += check_digit(l2)
    assert len(line1) == 44, len(line1)
    assert len(l2) == 44, len(l2)
    return line1, l2


def stamp_rect(w, h, ink, lines, angle, border=3):
    """Rectangular rubber stamp on its own RGBA layer, rotated."""
    layer = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = (w + 40) // 2, (h + 40) // 2
    col = ink + (205,)
    d.rectangle([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
                outline=col, width=border)
    d.rectangle([cx - w // 2 + 5, cy - h // 2 + 5,
                 cx + w // 2 - 5, cy + h // 2 - 5],
                outline=col, width=1)
    y = cy - h // 2 + 12
    for s, f, size in lines:
        d.text((cx, y), s, font=font(f, size), fill=col, anchor="ma")
        y += size + 5
    return layer.rotate(angle, expand=False, resample=Image.BICUBIC)


def ring_text(layer, center, radius, s, start_deg, end_deg, f, fill):
    """Place characters along an arc of a circle."""
    cx, cy = center
    n = len(s)
    if n <= 1:
        return
    step = (end_deg - start_deg) / (n - 1)
    for i, ch in enumerate(s):
        ang = math.radians(start_deg + i * step)
        px = cx + radius * math.cos(ang)
        py = cy + radius * math.sin(ang)
        glyph = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glyph)
        gd.text((20, 20), ch, font=f, fill=fill, anchor="mm")
        glyph = glyph.rotate(-(start_deg + i * step) - 90,
                             resample=Image.BICUBIC, center=(20, 20))
        layer.alpha_composite(glyph, (int(px - 20), int(py - 20)))


def stamp_circle(r, ink, ring, center_lines, angle):
    """Circular rubber stamp on its own RGBA layer, rotated.

    The ring text runs along the TOP arc only (upright, readable);
    the centre carries the remaining lines.
    """
    size = 2 * r + 48
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = size // 2
    col = ink + (205,)
    d.ellipse([c - r, c - r, c + r, c + r], outline=col, width=3)
    d.ellipse([c - r + 6, c - r + 6, c + r - 6, c + r - 6],
              outline=col, width=1)
    ring_r = r - 16
    ring_size = 12
    span = len(ring) * ring_size * 0.62 / ring_r * 180 / math.pi
    ring_text(layer, (c, c), ring_r, ring, -90 - span / 2, -90 + span / 2,
              font(SANS_B, ring_size), col)
    y = c - 26
    for s, f, size_ in center_lines:
        d.text((c, y), s, font=font(f, size_), fill=col, anchor="ma")
        y += size_ + 4
    return layer.rotate(angle, expand=False, resample=Image.BICUBIC)


# ---------------------------------------------------------------- portrait


def draw_portrait(draw, x, y, w, h):
    """Flat vector passport portrait: head and shoulders, front-facing."""
    # background: pale blue-grey gradient
    for i in range(h):
        t = i / max(h - 1, 1)
        c = tuple(int(PHOTO_BG_TOP[k] + (PHOTO_BG_BOT[k] - PHOTO_BG_TOP[k]) * t)
                  for k in range(3))
        draw.line([(x, y + i), (x + w, y + i)], fill=c)
    draw.rectangle([x, y, x + w, y + h], outline=(120, 130, 135), width=2)
    cx = x + w // 2
    # shoulders / jacket
    draw.polygon([(x + 8, y + h), (x + w - 8, y + h),
                  (x + w - 14, y + h - 42), (cx + 26, y + h - 62),
                  (cx - 26, y + h - 62), (x + 14, y + h - 42)],
                 fill=JACKET)
    # shirt V
    draw.polygon([(cx - 16, y + h - 60), (cx + 16, y + h - 60),
                  (cx, y + h - 34)], fill=(238, 236, 230))
    # neck
    draw.rectangle([cx - 11, y + h - 78, cx + 11, y + h - 58], fill=SKIN_DK)
    # ears
    draw.ellipse([cx - 34, y + 52, cx - 24, y + 72], fill=SKIN)
    draw.ellipse([cx + 24, y + 52, cx + 34, y + 72], fill=SKIN)
    # head
    draw.ellipse([cx - 30, y + 18, cx + 30, y + 86], fill=SKIN)
    # hair: bob cut framing the face
    draw.polygon([(cx - 32, y + 78), (cx - 34, y + 40), (cx - 26, y + 16),
                  (cx, y + 8), (cx + 26, y + 16), (cx + 34, y + 40),
                  (cx + 32, y + 78), (cx + 22, y + 74), (cx + 24, y + 44),
                  (cx + 14, y + 26), (cx, y + 22), (cx - 14, y + 26),
                  (cx - 24, y + 44), (cx - 22, y + 74)], fill=HAIR)
    # face: brows, eyes, nose, mouth — minimal and symmetric
    draw.arc([cx - 20, y + 46, cx - 8, y + 54], 200, 340, fill=(90, 62, 48), width=2)
    draw.arc([cx + 8, y + 46, cx + 20, y + 54], 200, 340, fill=(90, 62, 48), width=2)
    draw.ellipse([cx - 17, y + 56, cx - 11, y + 61], fill=(38, 30, 26))
    draw.ellipse([cx + 11, y + 56, cx + 17, y + 61], fill=(38, 30, 26))
    draw.line([(cx, y + 60), (cx - 2, y + 72)], fill=SKIN_DK, width=2)
    draw.arc([cx - 7, y + 76, cx + 7, y + 84], 15, 165, fill=(150, 90, 80), width=2)


# ---------------------------------------------------------------- emblem


def draw_emblem(draw, cx, cy, r, color):
    """Coat of arms: double circle, three peaks, one star."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)
    draw.ellipse([cx - r + 5, cy - r + 5, cx + r - 5, cy + r - 5],
                 outline=color, width=1)
    draw.polygon([(cx - r + 8, cy + r - 9), (cx - 8, cy - 2),
                  (cx - 2, cy + 6), (cx + 6, cy - 10), (cx + 12, cy + 2),
                  (cx + r - 8, cy + r - 9)], fill=color)
    # eight-point star above the peaks
    sx, sy, sr = cx, cy - r + 12, 5
    pts = []
    for i in range(16):
        a = math.pi * i / 8 - math.pi / 2
        rr = sr if i % 2 == 0 else sr * 0.45
        pts.append((sx + rr * math.cos(a), sy + rr * math.sin(a)))
    draw.polygon(pts, fill=color)


# ---------------------------------------------------------------- pages


def draw_left_page(img, x0, y0, w, h):
    d = ImageDraw.Draw(img, "RGBA")
    # faint watermark emblem
    wm = Image.new("RGBA", img.size, (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)
    draw_emblem(wd, x0 + w // 2, y0 + h // 2, 120, (31, 58, 95, 16))
    img.alpha_composite(wm)
    d = ImageDraw.Draw(img, "RGBA")
    cx = x0 + w // 2
    draw_emblem(d, cx, y0 + 42, 26, NAVY)
    text(d, (cx, y0 + 78), "REPUBLIC OF TALVERIA",
         SERIF_B, 29, NAVY, anchor="ma")
    spaced(d, (cx, y0 + 110), "TALVERIAN PASSPORT",
           SANS_B, 12, NAVY, 3, anchor="ma")
    d.line([(x0 + 30, y0 + 134), (x0 + w - 30, y0 + 134)], fill=RULE, width=1)
    d.line([(x0 + 30, y0 + 138), (x0 + w - 30, y0 + 138)], fill=RULE, width=2)

    px, py, pw, ph = x0 + 30, y0 + 158, 132, 168
    draw_portrait(d, px, py, pw, ph)

    # fields: (label, value) rows, two columns where paired
    fx = x0 + 182
    rows = [
        ("SURNAME", "KESSLER", None, None),
        ("GIVEN NAMES", "MARA ILVEN", None, None),
        ("NATIONALITY", "TALVERIAN", "SEX", "F"),
        ("DATE OF BIRTH", "14 JUN 1988", "PLACE OF BIRTH", "ALDERMARK"),
        ("DATE OF ISSUE", "12 MAR 2024", "DATE OF EXPIRY", "11 MAR 2034"),
        ("AUTHORITY", "MINISTRY OF THE INTERIOR", None, None),
        ("PASSPORT No.", "TV 4 829 137", None, None),
    ]
    y = y0 + 158
    for lab, val, lab2, val2 in rows:
        text(d, (fx, y), lab, SANS, 10, GREY)
        text(d, (fx, y + 13), val, SERIF_B, 17, INK)
        if lab2:
            text(d, (fx + 200, y), lab2, SANS, 10, GREY)
            text(d, (fx + 200, y + 13), val2, SERIF_B, 17, INK)
        y += 42

    # signature
    sy = y0 + 478
    d.line([(fx, sy), (fx + 150, sy)], fill=INK, width=1)
    sig = Image.new("RGBA", (170, 30), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sig)
    sd.arc([6, 2, 60, 26], 180, 20, fill=INK + (230,), width=2)
    sd.arc([40, 6, 110, 28], 200, 340, fill=INK + (230,), width=2)
    sd.arc([95, 4, 160, 26], 180, 60, fill=INK + (230,), width=2)
    img.alpha_composite(sig, (fx - 4, sy - 26))
    text(d, (fx, sy + 5), "SIGNATURE OF BEARER", SANS, 9, GREY)
    text(d, (x0 + 30, y0 + 560),
         "This passport remains the property of the Republic of Talveria.",
         SERIF_I, 11, GREY)

    # MRZ
    line1, line2 = mrz_lines()
    text(d, (x0 + 30, y0 + 606), line1, MONO, 15, INK)
    text(d, (x0 + 30, y0 + 628), line2, MONO, 15, INK)
    text(d, (x0 + 30, y0 + h - 22), "12", SANS, 10, GREY)


def draw_right_page(img, x0, y0, w, h):
    d = ImageDraw.Draw(img, "RGBA")
    wm = Image.new("RGBA", img.size, (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)
    draw_emblem(wd, x0 + w // 2, y0 + h // 2, 120, (31, 58, 95, 16))
    img.alpha_composite(wm)
    d = ImageDraw.Draw(img, "RGBA")
    cx = x0 + w // 2
    text(d, (cx, y0 + 30), "VISAS", SERIF_B, 26, NAVY, anchor="ma")
    spaced(d, (cx, y0 + 62), "VISA  •  VISA", SANS, 11, GREY, 2, anchor="ma")
    d.line([(x0 + 30, y0 + 86), (x0 + w - 30, y0 + 86)], fill=RULE, width=1)

    # stamp 1 — Meridia arrival (rectangular, burgundy)
    s1 = stamp_rect(228, 92, BURGUNDY, [
        ("REPUBLIC OF MERIDIA", SANS_B, 14),
        ("PORT OF MERIDIAN", SANS_B, 12),
        ("ARRIVAL  •  02 APR 2024", SANS, 13),
    ], -5)
    img.alpha_composite(s1, (x0 + 38, y0 + 118))
    # stamp 2 — Kastelvar departure (circular, navy)
    s2 = stamp_circle(64, NAVY, "KASTELVAR",
                      [("BORDER CONTROL", SANS, 11),
                       ("DEPARTURE", SANS_B, 13),
                       ("18 APR 2024", SANS_B, 13)],
                      7)
    img.alpha_composite(s2, (x0 + 296, y0 + 112))
    # stamp 3 — Isla Mirra entry (rectangular, green)
    s3 = stamp_rect(228, 92, GREEN, [
        ("ISLA MIRRA", SANS_B, 15),
        ("IMMIGRATION", SANS_B, 12),
        ("ENTRY  •  07 JUN 2024", SANS, 13),
    ], 3)
    img.alpha_composite(s3, (x0 + 38, y0 + 252))
    # stamp 4 — Talveria re-entry (circular, burgundy)
    s4 = stamp_circle(58, BURGUNDY, "TALVERIA",
                      [("ALDERMARK", SANS, 11),
                       ("RE-ENTRY", SANS_B, 13),
                       ("23 JUN 2024", SANS_B, 13)],
                      -8)
    img.alpha_composite(s4, (x0 + 300, y0 + 250))

    # visa-condition box — the telling paperwork detail
    bx0, by0, bx1, by1 = x0 + 30, y0 + 400, x0 + w - 30, y0 + 560
    d.rectangle([bx0, by0, bx1, by1], outline=NAVY, width=2)
    d.rectangle([bx0 + 4, by0 + 4, bx1 - 4, by1 - 4], outline=NAVY, width=1)
    text(d, (bx0 + 16, by0 + 12), "CONDITION OF ENTRY",
         SANS_B, 13, NAVY)
    body = ("The bearer must hold mountain-rescue insurance for "
            "travel above 3,000 m. Border posts close at dusk in "
            "winter. This passport is valid for all countries "
            "except where a separate permit is required.")
    lines = wrap(d, body, SANS, 12, bx1 - bx0 - 32)
    yy = by0 + 38
    for ln in lines:
        text(d, (bx0 + 16, yy), ln, SANS, 12, INK)
        yy += 18
    text(d, (bx0 + 16, by1 - 30), "TALVERIAN BORDER SERVICE",
         SANS_B, 11, NAVY)
    # fee stamp overlapping the box corner
    fee = stamp_rect(150, 46, BURGUNDY, [
        ("ALTITUDE LEVY", SANS_B, 11),
        ("PAID  •  40 TAL", SANS_B, 11),
    ], -7, border=2)
    img.alpha_composite(fee, (bx1 - 178, by1 - 60))
    text(d, (x0 + w - 30, y0 + h - 22), "13", SANS, 10, GREY, anchor="ra")


# ---------------------------------------------------------------- compose


def render():
    img = Image.new("RGB", (1024, 1024), DESK_BOT)
    d = ImageDraw.Draw(img)
    for i in range(1024):
        t = i / 1023
        c = tuple(int(DESK_TOP[k] + (DESK_BOT[k] - DESK_TOP[k]) * t)
                  for k in range(3))
        d.line([(0, i), (1024, i)], fill=c)

    # soft shadow under the spread
    shadow = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([26, 182, 1014, 880], radius=6, fill=(0, 0, 0, 110))
    img.paste(Image.alpha_composite(
        img.convert("RGBA"),
        shadow.filter(ImageFilter.GaussianBlur(10))).convert("RGB"), (0, 0))

    # spread: two cream pages with a gutter
    d = ImageDraw.Draw(img)
    x0, y0, w, h = 14, 158, 996, 707
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=4, fill=PAPER)
    # page edge tint + inner border
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=4,
                        outline=(190, 180, 155), width=1)
    # gutter shadow
    img = img.convert("RGBA")
    gutter = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gutter)
    gd.rectangle([x0 + w // 2 - 3, y0, x0 + w // 2 + 3, y0 + h],
                 fill=(0, 0, 0, 55))
    gd.line([x0 + w // 2, y0, x0 + w // 2, y0 + h], fill=(120, 110, 88), width=1)
    img.alpha_composite(gutter.filter(ImageFilter.GaussianBlur(2)))

    draw_left_page(img, x0, y0, w // 2, h)
    draw_right_page(img, x0 + w // 2, y0, w // 2, h)

    img = img.convert("RGB")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    render()

"""The routine animation, written out as a GIF.

WHY A FILE AND NOT JUST THE PAGE

The animation in render.py is CSS and JavaScript: it only moves while a
browser is running the result page. That is the right place for it — it has
controls, it is crisp, it costs nothing — but it cannot leave.

The course requires `slides.html` to open by double-click with its images
embedded, and the person opening it will not have the app running. A
screenshot of the animation panel is a face with some dots on it, which
communicates nothing. A GIF embedded as a data URI is still a self-contained
image by that rule, and it moves.

So this draws the same storyboard a second time, in PIL, and writes the
frames to one file. Same scenes, same face, same dot positions — the
geometry comes from storyboard.py, so the two renderings cannot disagree
about where a product goes.

WHAT IT GIVES UP

No controls, 256 colours, a fixed pace, and a megabyte or two. It is a loop,
not a player. MP4 would fix the colour and the size, and costs an
imageio-ffmpeg dependency of about 25 MB — too much to put in an install
step for a file whose job is to play inside a slide.
"""

from __future__ import annotations

import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from storyboard import ANCHORS  # noqa: F401  (kept for the geometry contract)

# Canvas. Wide rather than square: this ends up on a slide next to text.
W, H = 500, 272
FPS = 8

# The face is drawn in storyboard.py's 200x240 space and scaled into the
# left panel, so the dot coordinates need no translation of their own.
PANEL = (14, 14, 222, 258)
SCALE = 0.95
OX = PANEL[0] + ((PANEL[2] - PANEL[0]) - 200 * SCALE) / 2
OY = PANEL[1] + ((PANEL[3] - PANEL[1]) - 240 * SCALE) / 2

PAPER = (246, 242, 236)
SUNK = (239, 232, 222)
CARD = (255, 253, 250)
LINE = (228, 219, 205)
INK = (44, 40, 36)
INK_DIM = (109, 100, 88)
INK_FAINT = (155, 146, 132)
CLAY = (168, 106, 75)
WATER = (127, 166, 191)
TOWEL = (207, 216, 205)
SAND = (192, 138, 62)

FONT_DIR = Path("C:/Windows/Fonts")


def _font(names: list[str], size: int):
    """A real font if the machine has one, the bitmap default if not.

    Never raises: a missing font must not be the reason an audit fails.
    """
    for name in names:
        for path in (FONT_DIR / name, Path(name)):
            try:
                return ImageFont.truetype(str(path), size)
            except (OSError, ValueError):
                continue
    return ImageFont.load_default()


def _fonts():
    return {
        "label": _font(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], 12),
        "title": _font(["georgiab.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 19),
        "body": _font(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], 16),
        "small": _font(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], 13),
    }


def _xy(x: float, y: float) -> tuple[float, float]:
    return OX + x * SCALE, OY + y * SCALE


def _rounded(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _face(draw) -> None:
    """The same line-drawn face as the SVG, in PIL primitives."""
    x0, y0 = _xy(37, 40)
    x1, y1 = _xy(163, 208)
    draw.ellipse([x0, y0, x1, y1], fill=CARD, outline=INK_FAINT, width=2)

    # brows
    draw.arc([*_xy(62, 86), *_xy(90, 104)], 200, 340, fill=INK_FAINT, width=2)
    draw.arc([*_xy(110, 86), *_xy(138, 104)], 200, 340, fill=INK_FAINT, width=2)
    # eyes
    draw.arc([*_xy(66, 102), *_xy(86, 118)], 200, 340, fill=INK_FAINT, width=2)
    draw.arc([*_xy(114, 102), *_xy(134, 118)], 200, 340, fill=INK_FAINT, width=2)
    # nose
    draw.line([*_xy(100, 112), *_xy(100, 132)], fill=INK_FAINT, width=2)
    draw.arc([*_xy(94, 126), *_xy(107, 140)], 0, 110, fill=INK_FAINT, width=2)
    # mouth
    draw.arc([*_xy(86, 154), *_xy(114, 174)], 20, 160, fill=INK_FAINT, width=2)
    # neck
    draw.line([*_xy(74, 198), *_xy(75, 224)], fill=INK_FAINT, width=2)
    draw.line([*_xy(126, 198), *_xy(125, 224)], fill=INK_FAINT, width=2)


def _dot_state(anim: str, t: float, x: float) -> tuple[float, float, float, float]:
    """Where one dot is, and how visible, at phase t of its animation.

    Mirrors the CSS keyframes in render.py. They are written twice because
    one is a stylesheet and one is a drawing program; the positions they
    animate from are shared, which is the part that matters.
    """
    if anim == "orbit":
        a = t * 2 * math.pi
        return math.sin(a) * 5, -3 + -math.cos(a) * 3, 1.0, 0.9
    if anim == "foam":
        grow = math.sin(t * math.pi)
        return grow * 3, -grow * 2, 1 + grow * 1.1, 0.9 - grow * 0.25
    if anim == "press":
        squash = math.sin(t * math.pi)
        return 0, 0, 1.5 - squash * 0.78, 0.35 + squash * 0.6
    if anim == "tap":
        return 0, -abs(math.sin(t * math.pi)) * 3.5, 1 - abs(math.sin(t * math.pi)) * .15, .95
    if anim == "sweep":
        out = 7 if x >= 100 else -7
        return out * t, 0, 0.6 + t * 0.65, max(0.0, 0.95 - t * 0.7)
    # dab
    return 0, 0, min(1.0, 0.2 + t * 4), min(0.95, t * 4)


def _finish(layer, draw, anim: str, t: float) -> None:
    if anim == "rinse":
        for i, x in enumerate((76, 100, 124)):
            p = (t + i * 0.15) % 1.0
            top = 52 + p * 46
            alpha = 0 if p < 0.12 or p > 0.88 else 190
            draw.line([*_xy(x, top), *_xy(x, top + 34)],
                      fill=WATER + (alpha,), width=3)
    elif anim == "towel":
        a = int(140 * math.sin(t * math.pi))
        _rounded(draw, [*_xy(44, 92), *_xy(156, 156)], 14,
                 fill=TOWEL + (max(a, 0),))
    elif anim == "absorb":
        a = int(150 * math.sin(t * math.pi))
        # a dashed ring, drawn as arc segments
        for start in range(0, 360, 24):
            draw.arc([*_xy(45, 50), *_xy(155, 198)], start, start + 13,
                     fill=SAND + (max(a, 0),), width=3)


def _wrap(draw, text: str, font, width: int, limit: int = 2) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) == limit:
                break
    if cur and len(lines) < limit:
        lines.append(cur)
    if len(lines) == limit and words:
        joined = " ".join(lines)
        if len(joined) < len(text):
            while lines and draw.textlength(lines[-1] + "...", font=font) > width:
                lines[-1] = lines[-1][:-1]
            lines[-1] += "..."
    return lines


def _frame(scene: dict, t: float, progress: float, fonts) -> Image.Image:
    base = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(base)

    _rounded(draw, [0, 0, W - 1, H - 1], 18, fill=CARD, outline=LINE)
    _rounded(draw, list(PANEL), 14, fill=SUNK)
    _face(draw)

    # Moving parts go on their own layer so they can be semi-transparent.
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)

    for n, p in enumerate(scene["points"]):
        phase = (t + n * 0.06) % 1.0
        dx, dy, scale, alpha = _dot_state(scene["anim"], phase, p["x"])
        cx, cy = _xy(p["x"] + dx, p["y"] + dy)
        r = 5.5 * SCALE * scale
        ld.ellipse([cx - r, cy - r, cx + r, cy + r],
                   fill=CLAY + (int(255 * alpha),))

    _finish(layer, ld, scene["anim"], t)
    base = Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")
    draw = ImageDraw.Draw(base)

    # --- the caption column ---------------------------------------------
    x = 244
    draw.text((x, 34), f'{scene["slot"].upper()}  ·  STEP {scene["order"]} OF {scene["of"]}',
              font=fonts["label"], fill=INK_FAINT)

    y = 54
    for line in _wrap(draw, scene["name"], fonts["title"], W - x - 28, 2):
        draw.text((x, y), line, font=fonts["title"], fill=INK)
        y += 25

    y += 6
    draw.text((x, y), scene["caption"], font=fonts["body"], fill=INK)
    y += 24
    if scene["where"]:
        for line in _wrap(draw, "on " + scene["where"], fonts["small"], W - x - 28, 2):
            draw.text((x, y), line, font=fonts["small"], fill=INK_DIM)
            y += 18

    y += 8
    pill = scene["real"].upper()
    tw = draw.textlength(pill, font=fonts["label"])
    _rounded(draw, [x, y, x + tw + 22, y + 22], 11, fill=SUNK)
    draw.text((x + 11, y + 4), pill, font=fonts["label"], fill=INK_DIM)

    # --- progress and the honesty line ----------------------------------
    draw.rectangle([x, H - 52, W - 28, H - 49], fill=LINE)
    draw.rectangle([x, H - 52, x + (W - 28 - x) * progress, H - 49], fill=CLAY)
    draw.text((x, H - 38), "Sped up. Real times shown above.",
              font=fonts["small"], fill=INK_FAINT)

    return base


def _palette() -> Image.Image:
    """A fixed 32-colour palette: the page's colours plus ramps for the dots.

    Everything drawn here comes from a known set, so a computed palette only
    spends colours on antialiasing noise.
    """
    colours: list[tuple[int, int, int]] = [
        PAPER, CARD, SUNK, LINE, INK, INK_DIM, INK_FAINT, CLAY, WATER, TOWEL, SAND,
    ]
    # Dots and water are drawn semi-transparent over two backgrounds, so the
    # blends need to exist in the palette or they dither.
    for bg in (SUNK, CARD):
        for fg in (CLAY, WATER, SAND, TOWEL, INK_FAINT):
            for a in (0.25, 0.5, 0.75):
                colours.append(tuple(int(f * a + b * (1 - a)) for f, b in zip(fg, bg)))
    colours = list(dict.fromkeys(colours))[:256]

    pal = Image.new("P", (1, 1))
    flat: list[int] = []
    for c in colours:
        flat.extend(c)
    flat.extend([0, 0, 0] * (256 - len(colours)))
    pal.putpalette(flat)
    return pal


def build(scenes: list[dict]) -> bytes:
    """Render the scenes to one looping GIF.

    Returns empty bytes for an empty routine rather than a zero-frame file,
    which some viewers render as a broken image.
    """
    if not scenes:
        return b""

    fonts = _fonts()
    frames: list[Image.Image] = []
    durations: list[int] = []

    total = len(scenes)
    for i, scene in enumerate(scenes):
        # Harder compression than the on-screen player: a GIF cannot be
        # paused, so a long absorb is dead air nobody can skip.
        n = max(5, min(int(round(scene["screen"] * 3)), 11))
        for f in range(n):
            t = f / n
            frames.append(_frame(scene, t, (i + t) / total, fonts))
            durations.append(int(1000 / FPS))

    # One fixed palette for every frame. Letting PIL pick a palette per frame
    # costs time, inflates the file with a palette per frame, and makes the
    # background shimmer between frames because the chosen colours drift.
    pal = _palette()
    flat = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]

    buf = io.BytesIO()
    flat[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=flat[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )
    return buf.getvalue()

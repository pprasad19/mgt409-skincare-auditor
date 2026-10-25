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


R = 5.5 * SCALE          # a dot
TRAIL = (0.45, 0.28, 0.15)   # ghost opacities behind a moving dot


def _blob(draw, x: float, y: float, r: float, colour, alpha: float) -> None:
    cx, cy = _xy(x, y)
    rr = r * SCALE
    draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                 fill=colour + (max(0, min(255, int(255 * alpha))),))


def _ring(draw, x: float, y: float, r: float, colour, alpha: float, w: int = 2) -> None:
    cx, cy = _xy(x, y)
    rr = r * SCALE
    draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                 outline=colour + (max(0, min(255, int(255 * alpha))),),
                 width=w)


def _motion(draw, anim: str, points: list[dict], t: float) -> None:
    """Draw one frame of an application.

    Each branch draws a different *shape*, not the same shape at a different
    offset. That is the whole point: a 5px wobble on an 11px dot reads as a
    still picture, and five motions that all read as still pictures are one
    motion with five captions.
    """
    if anim == "orbit":
        # Circular: a visible path, and the dot going round it.
        for n, p in enumerate(points):
            a = ((t + n * 0.07) % 1.0) * 2 * math.pi
            _ring(draw, p["x"], p["y"] - 4, 8, CLAY, 0.18, 2)
            _blob(draw, p["x"] + math.sin(a) * 8, p["y"] - 4 - math.cos(a) * 8,
                  4.6, CLAY, 0.92)
        return

    if anim == "foam":
        # Lather: blobs swell and merge, with small bubbles around them.
        for n, p in enumerate(points):
            ph = (t + n * 0.06) % 1.0
            grow = math.sin(ph * math.pi)
            _blob(draw, p["x"], p["y"], 5.5 + grow * 5.5, CLAY, 0.85 - grow * 0.3)
            for k in (0, 1):
                ang = (ph * 2 * math.pi) + k * 2.6 + n
                _blob(draw, p["x"] + math.cos(ang) * 9, p["y"] + math.sin(ang) * 8,
                      1.8 + grow * 1.4, CLAY, 0.45)
        return

    if anim == "press":
        # Pressing in: a fingertip ring closing onto the dot and fading.
        for n, p in enumerate(points):
            ph = (t + n * 0.08) % 1.0
            _blob(draw, p["x"], p["y"], 4.4, CLAY, 0.9)
            _ring(draw, p["x"], p["y"], 14 - ph * 9, CLAY, max(0.0, 0.7 - ph * 0.7), 3)
        return

    if anim == "tap":
        # Patting: a clear bounce, with a contact shadow left behind so the
        # height is readable in a still frame.
        for n, p in enumerate(points):
            ph = (t + n * 0.1) % 1.0
            lift = abs(math.sin(ph * math.pi)) * 11
            # The shadow is what makes the height readable in a still frame.
            _blob(draw, p["x"], p["y"] + 3, 5.4 - lift * 0.18, CLAY, 0.3)
            _blob(draw, p["x"], p["y"] - lift, 5.2 - lift * 0.14, CLAY, 0.95)
        return

    if anim == "sweep":
        # Smoothing outward: a comet. The travel has to be several times the
        # dot's own width or the trail sits inside the head of it and the
        # whole thing reads as a stationary dot.
        for n, p in enumerate(points):
            ph = (t + n * 0.05) % 1.0
            out = 20 if p["x"] >= 100 else -20
            for k, a in enumerate(TRAIL):
                back = max(0.0, ph - (k + 1) * 0.16)
                _blob(draw, p["x"] + out * back, p["y"], 4.6 - k * 0.6, CLAY, a)
            _blob(draw, p["x"] + out * ph, p["y"], 5.4, CLAY, 0.95)
        return

    # dab: discrete placements, lighting up one after another and staying.
    lit = t * (len(points) + 2)
    for n, p in enumerate(points):
        if n > lit:
            continue
        land = min(1.0, lit - n)
        _blob(draw, p["x"], p["y"], 2 + land * 4.2, CLAY, 0.35 + land * 0.6)
        if land < 1:
            _ring(draw, p["x"], p["y"], 6 + (1 - land) * 7, CLAY, (1 - land) * 0.5, 2)


def _finish(draw, anim: str, rest: list[dict], t: float) -> None:
    """A finish, with the product still where it was put.

    `rest` matters more than it looks. Without it every absorb scene was the
    same dashed ring, so eight of the eighteen frames in a six-product
    routine were one picture with eight different captions. Showing the
    product settling on the area it was actually applied to makes absorbing
    a retinol on the chin look different from absorbing a toner everywhere,
    which is the truth of it.
    """
    if anim == "rinse":
        for i, x in enumerate((70, 86, 100, 114, 130)):
            ph = (t + i * 0.17) % 1.0
            top = 48 + ph * 52
            if 0.1 < ph < 0.9:
                draw.line([*_xy(x, top), *_xy(x, top + 30)],
                          fill=WATER + (190,), width=3)
                _blob(draw, x, top + 34, 2.2, WATER, 0.5)
        # what is being rinsed away
        for p in rest:
            _blob(draw, p["x"], p["y"], 4.5, CLAY, max(0.0, 0.35 - t * 0.35))
        return

    if anim == "towel":
        drop = math.sin(t * math.pi)
        a = 0.85 * drop
        y0, y1 = 86 + (1 - drop) * 10, 150 + (1 - drop) * 10
        _rounded(draw, [*_xy(42, y0), *_xy(158, y1)], 14,
                 fill=TOWEL + (int(255 * a),))
        draw.line([*_xy(42, (y0 + y1) / 2), *_xy(158, (y0 + y1) / 2)],
                  fill=(182, 195, 180, int(255 * a)), width=2)
        return

    # absorb: the product sitting and sinking in, plus a slow ring.
    pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi)
    for n, p in enumerate(rest):
        _blob(draw, p["x"], p["y"], 4.4 + pulse * 1.2, CLAY, 0.22 + pulse * 0.22)
    sweep_to = int(360 * t)
    for start in range(0, 360, 26):
        if start > sweep_to:
            continue
        draw.arc([*_xy(45, 50), *_xy(155, 198)], start - 90, start - 90 + 14,
                 fill=SAND + (150,), width=3)


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

    if scene["points"]:
        _motion(ld, scene["anim"], scene["points"], t)
    else:
        _finish(ld, scene["anim"], scene.get("rest", []), t)
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
            for a in (0.15, 0.25, 0.35, 0.5, 0.65, 0.8, 0.92):
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

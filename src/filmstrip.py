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
W, H = 620, 340
FPS = 8

# About twenty-five seconds at 8fps. Long enough for a seven-product
# routine, short enough that a loop in a slide is not a commitment.
MAX_FRAMES = 200

# The face is drawn in storyboard.py's 200x240 space and scaled into the
# left panel, so the dot coordinates need no translation of their own.
PANEL = (16, 16, 302, 324)
SCALE = 1.25
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
        "title": _font(["georgiab.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 21),
        "body": _font(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], 17),
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


GLASS = (222, 214, 202)
CAP = (138, 126, 112)
SKIN = (233, 214, 199)
SKIN_LINE = (199, 176, 158)


def _capsule(draw, x0, y0, x1, y1, fill, outline=None, w=2):
    a, b = _xy(x0, y0)
    c, d = _xy(x1, y1)
    r = min(abs(c - a), abs(d - b)) / 2
    draw.rounded_rectangle([a, b, c, d], radius=r, fill=fill, outline=outline, width=w)


# The vessels _container knows how to draw. storyboard.CONTAINERS must only
# name these: a form mapped to a kind with no branch here would fall to the
# plain bottle and quietly lose the one cue that tells its step apart.
CONTAINER_KINDS = frozenset(
    {"dropper", "pump", "tube", "smalltube", "widetub", "tub", "bottle"}
)


def _container(draw, kind: str, t: float) -> None:
    """The vessel, drawn large and centre-left, tipping as it dispenses."""
    tip = math.sin(min(t * 2.2, 1.0) * math.pi / 2)      # 0 -> 1, eases in

    if kind == "dropper":
        _capsule(draw, 46, 58, 84, 132, GLASS + (255,), CAP + (255,), 2)
        draw.rectangle([*_xy(56, 44), *_xy(74, 60)], fill=CAP + (255,))
        draw.polygon([_xy(62, 132), _xy(68, 132), _xy(66, 150), _xy(64, 150)],
                     fill=CAP + (255,))
    elif kind == "pump":
        _capsule(draw, 44, 70, 86, 150, GLASS + (255,), CAP + (255,), 2)
        draw.rectangle([*_xy(60, 46), *_xy(70, 72)], fill=CAP + (255,))
        draw.rectangle([*_xy(60, 42 + tip * 5), *_xy(86, 50 + tip * 5)],
                       fill=CAP + (255,))
    elif kind == "tube":
        _capsule(draw, 48, 62, 82, 146, GLASS + (255,), CAP + (255,), 2)
        draw.rectangle([*_xy(58, 48), *_xy(72, 64)], fill=CAP + (255,))
        draw.line([*_xy(48, 138), *_xy(82, 138)], fill=CAP + (255,), width=3)
    elif kind == "smalltube":
        _capsule(draw, 54, 84, 76, 142, GLASS + (255,), CAP + (255,), 2)
        draw.rectangle([*_xy(61, 72), *_xy(69, 86)], fill=CAP + (255,))
    elif kind == "widetub":
        _capsule(draw, 34, 94, 96, 146, GLASS + (255,), CAP + (255,), 2)
        draw.rectangle([*_xy(34, 88), *_xy(96, 100)], fill=CAP + (255,))
        # a spatula, lifting out
        draw.line([*_xy(88, 96 - tip * 26), *_xy(96, 60 - tip * 26)],
                  fill=CAP + (255,), width=3)
    elif kind == "tub":
        _capsule(draw, 42, 96, 88, 142, GLASS + (255,), CAP + (255,), 2)
        draw.rectangle([*_xy(42, 90), *_xy(88, 100)], fill=CAP + (255,))
    else:  # bottle
        _capsule(draw, 48, 66, 82, 148, GLASS + (255,), CAP + (255,), 2)
        draw.rectangle([*_xy(58, 50), *_xy(72, 68)], fill=CAP + (255,))


def _arrowhead(draw, x, y, ang, size, colour, alpha) -> None:
    a = int(255 * alpha)
    tip = _xy(x, y)
    left = _xy(x - math.cos(ang - 0.5) * size, y - math.sin(ang - 0.5) * size)
    right = _xy(x - math.cos(ang + 0.5) * size, y - math.sin(ang + 0.5) * size)
    draw.polygon([tip, left, right], fill=colour + (a,))


def _arrow(draw, kind: str, x: float, y: float, t: float, out: int = 1) -> None:
    """The gesture, drawn as an instruction rather than implied by motion."""
    spin = (t * 2) % 1.0
    if kind == "circle":
        r = 24
        start = -90 + spin * 360
        draw.arc([*_xy(x - r, y - r), *_xy(x + r, y + r)],
                 start, start + 250, fill=SAND + (235,), width=4)
        end = math.radians(start + 250)
        _arrowhead(draw, x + math.cos(end) * r, y + math.sin(end) * r,
                   end + 1.57, 9, SAND, 0.95)
    elif kind == "out":
        x0 = x - out * 6
        x1 = x + out * (24 + spin * 9)
        draw.line([*_xy(x0, y), *_xy(x1, y)], fill=SAND + (235,), width=4)
        _arrowhead(draw, x1, y, 0 if out > 0 else math.pi, 9, SAND, 0.95)
    elif kind == "down":
        for k in (0, 1):
            yy = y - 22 + k * 10 + spin * 7
            draw.line([*_xy(x - 13, yy), *_xy(x, yy + 9)], fill=SAND + (230,), width=4)
            draw.line([*_xy(x, yy + 9), *_xy(x + 13, yy)], fill=SAND + (230,), width=4)
    elif kind == "bounce":
        lift = 22 + math.sin(t * 14) * 5
        draw.line([*_xy(x, y - lift), *_xy(x, y - 6)], fill=SAND + (230,), width=4)
        _arrowhead(draw, x, y - 5, 1.57, 8, SAND, 0.95)
        _arrowhead(draw, x, y - lift - 1, -1.57, 8, SAND, 0.95)


def _finger(draw, x, y, length=40, width=18, up=True, alpha=1.0) -> None:
    """One finger, tip at (x, y), coming in from below.

    The nail and the knuckle crease are not decoration: without them this is
    a pale capsule, and a pale capsule next to a face does not say "your
    finger goes here".
    """
    a = int(255 * alpha)
    y0, y1 = (y, y + length) if up else (y - length, y)
    _capsule(draw, x - width / 2, y0, x + width / 2, y1,
             SKIN + (a,), SKIN_LINE + (a,), 2)
    # nail
    _capsule(draw, x - width * 0.28, y0 + 4, x + width * 0.28, y0 + 14,
             (244, 228, 216, a), SKIN_LINE + (int(a * 0.7),), 1)
    # knuckle
    draw.line([*_xy(x - width * 0.34, y0 + 24), *_xy(x + width * 0.34, y0 + 24)],
              fill=SKIN_LINE + (int(a * 0.8),), width=1)


def _dose(draw, dose: dict, t: float) -> None:
    """How much, on a fingertip or in a palm, at honest relative scale.

    The scale is the information. A rice grain and two fingers' length of
    sunscreen are nearly two orders of magnitude apart, and a sentence
    cannot show that while two drawings can.
    """
    kind, n = dose["kind"], dose["n"]
    drop = min(1.0, max(0.0, (t - 0.25) / 0.5))       # falls, then sits
    cx, cy = 130, 112 + drop * 30

    if kind == "twofinger":
        # The classic sunscreen measure: a stripe down two fingers.
        for i, fx in enumerate((124, 146)):
            _finger(draw, fx, 96, length=60, width=17)
            if drop > 0.1:
                _capsule(draw, fx - 5, 100, fx + 5, 100 + 52 * drop,
                         CLAY + (235,), None, 0)
        return

    if kind == "palm":
        draw.ellipse([*_xy(104, 104), *_xy(168, 156)],
                     fill=SKIN + (255,), outline=SKIN_LINE + (255,), width=2)
        _blob(draw, 136, 130, 13 * drop, CLAY, 0.9)
        return

    if kind == "pad":
        draw.ellipse([*_xy(112, 96), *_xy(164, 148)],
                     fill=(252, 250, 246, 255), outline=LINE + (255,), width=2)
        _blob(draw, 138, 122, 15 * drop, CLAY, 0.45)
        return

    # Everything else lands on a single fingertip, so the sizes are
    # comparable between steps at a glance.
    _finger(draw, 136, 118, length=56, width=19)
    radius = {"rice": 2.6, "pea": 5.5, "coin": 9.5, "thick": 13.0}.get(kind)
    if radius is not None:
        _blob(draw, 136, 114, radius * max(drop, 0.12), CLAY, 0.92)
        return

    # drops: n of them, falling in sequence
    for i in range(n):
        ph = min(1.0, max(0.0, (t - 0.12 * i - 0.1) / 0.45))
        if ph <= 0:
            continue
        y = 70 + ph * 44
        _blob(draw, 136 - (n - 1) * 3 + i * 6, y, 3.4, CLAY, 0.9)


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


def _patch(draw, x, y, r, alpha) -> None:
    """Product already spread, left behind the hand."""
    _blob(draw, x, y, r, CLAY, alpha)


def _along(stops: list[dict], t: float) -> tuple[float, float, int]:
    """Where the hand is at phase t, and how many stops it has passed."""
    if not stops:
        return 100.0, 124.0, 0
    if len(stops) == 1:
        return float(stops[0]["x"]), float(stops[0]["y"]), 1
    pos = t * (len(stops) - 1)
    i = min(int(pos), len(stops) - 2)
    f = pos - i
    a, b = stops[i], stops[i + 1]
    return (a["x"] + (b["x"] - a["x"]) * f,
            a["y"] + (b["y"] - a["y"]) * f,
            i + 1)


def _apply(draw, anim: str, stops: list[dict], t: float) -> None:
    """One frame of applying: product spreading, and the hands doing it.

    Every technique shows the same two things — what has been covered so far
    and where the hands are — and differs in how the hands behave. That is
    the right way round. The earlier version differed only in how abstract
    dots eased, which is a difference nobody can see and nobody needs.
    """
    if anim == "maskon":
        # A mask is a layer, not a set of touch points.
        grown = min(1.0, t * 1.25)
        for stop in stops:
            _patch(draw, stop["x"], stop["y"], 22 * grown, 0.5)
        draw.line([*_xy(150, 70), *_xy(170, 44)], fill=CAP + (255,), width=4)
        x, y, _ = _along(stops, t)
        _finger(draw, x + 16, y + 6, length=30, width=13, alpha=0.9)
        return

    if anim == "dab":
        # Discrete placements: no travel, one point at a time, left behind.
        lit = t * (len(stops) + 0.5)
        for n, stop in enumerate(stops):
            if n > lit:
                continue
            land = min(1.0, lit - n)
            _patch(draw, stop["x"], stop["y"], 3 + land * 5, 0.4 + land * 0.5)
        n = min(int(lit), len(stops) - 1)
        here = stops[max(n, 0)]
        _finger(draw, here["x"], here["y"] + 8, length=34, width=14)
        return

    x, y, passed = _along(stops, t)

    # What the hand has already covered.
    for stop in stops[:passed]:
        _patch(draw, stop["x"], stop["y"], 11, 0.32)

    if anim == "foam":
        _arrow(draw, "circle", x, y, t)
        # Lather: the covered area froths up as the hands work over it.
        for n, stop in enumerate(stops[:passed]):
            ph = (t * 2 + n * 0.3) % 1.0
            _blob(draw, stop["x"], stop["y"], 11 + math.sin(ph * math.pi) * 5,
                  CLAY, 0.3)
            for k in (0, 1):
                ang = ph * 6.28 + k * 3.1 + n
                _blob(draw, stop["x"] + math.cos(ang) * 12,
                      stop["y"] + math.sin(ang) * 10, 2.6, CLAY, 0.4)
        _finger(draw, x - 10, y + 8, length=32, width=14)
        _finger(draw, x + 10, y + 8, length=32, width=14)
        return

    if anim == "orbit":
        # Circular: the hand itself travels a small circle as it moves on.
        _arrow(draw, "circle", x, y, t)
        a = t * 10
        ox, oy = math.sin(a) * 7, -math.cos(a) * 7
        _ring(draw, x, y, 8, CLAY, 0.3, 2)
        _finger(draw, x + ox - 8, y + oy + 8, length=32, width=14)
        _finger(draw, x + ox + 8, y + oy + 8, length=32, width=14)
        return

    if anim == "press":
        # Pressing: the hand stops, and a ring closes under it.
        _arrow(draw, "down", x, y, t)
        hold = (t * 3) % 1.0
        _ring(draw, x, y, 15 - hold * 9, CLAY, max(0.0, 0.65 - hold * 0.65), 3)
        _finger(draw, x - 9, y + 7 + hold * 2, length=32, width=14)
        _finger(draw, x + 9, y + 7 + hold * 2, length=32, width=14)
        return

    if anim == "tap":
        # Patting: one finger, bouncing, with a shadow so the lift reads.
        _arrow(draw, "bounce", x, y, t)
        lift = abs(math.sin(t * 14)) * 9
        _blob(draw, x, y + 2, 5, CLAY, 0.25)
        _finger(draw, x, y + 8 - lift, length=30, width=12)
        return

    # sweep: two fingers smoothing outward, dragging a trail
    out = 1 if x >= 100 else -1
    _arrow(draw, "out", x, y, t, out)
    for k, a in enumerate(TRAIL):
        _patch(draw, x - out * (k + 1) * 7, y, 7 - k, a * 0.7)
    _finger(draw, x - 9, y + 8, length=32, width=14)
    _finger(draw, x + 9, y + 8, length=32, width=14)


def _finish(draw, anim: str, rest: list[dict], t: float) -> None:
    """A finish, with the product still where it was put.

    `rest` matters more than it looks. Without it every absorb scene was the
    same dashed ring, so eight of the eighteen frames in a six-product
    routine were one picture with eight different captions. Showing the
    product settling on the area it was actually applied to makes absorbing
    a retinol on the chin look different from absorbing a toner everywhere,
    which is the truth of it.
    """
    if anim == "maskoff":
        # The layer coming away, top down.
        edge = 50 + t * 150
        for stop in rest:
            if stop["y"] > edge:
                _patch(draw, stop["x"], stop["y"], 22, 0.45)
        draw.line([*_xy(40, edge), *_xy(160, edge)], fill=SAND + (200,), width=3)
        for i, x in enumerate((78, 100, 122)):
            if ((t + i * 0.2) % 1.0) > 0.5:
                draw.line([*_xy(x, edge + 6), *_xy(x, edge + 26)],
                          fill=WATER + (170,), width=3)
        return

    if anim == "rinse":
        for i, x in enumerate((70, 86, 100, 114, 130)):
            ph = (t + i * 0.17) % 1.0
            top = 48 + ph * 52
            if 0.1 < ph < 0.9:
                draw.line([*_xy(x, top), *_xy(x, top + 30)],
                          fill=WATER + (190,), width=3)
                _blob(draw, x, top + 34, 2.2, WATER, 0.5)
        for stop in rest:
            _patch(draw, stop["x"], stop["y"], 10, max(0.0, 0.3 - t * 0.3))
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
    for stop in rest:
        _patch(draw, stop["x"], stop["y"], 10 + pulse * 2.5, 0.2 + pulse * 0.2)
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
    if scene["anim"] != "dispense":
        _face(draw)

    # Moving parts go on their own layer so they can be semi-transparent.
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)

    if scene["anim"] == "dispense":
        _container(ld, scene.get("container", "bottle"), t)
        _dose(ld, scene.get("dose", {"kind": "pea", "n": 1}), t)
    elif scene["points"]:
        _apply(ld, scene["anim"], scene["points"], t)
    else:
        _finish(ld, scene["anim"], scene.get("rest", []), t)
    base = Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")
    draw = ImageDraw.Draw(base)

    # --- the caption column ---------------------------------------------
    x = 324
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

    # The dispense scene has no duration of its own, and an empty pill is a
    # grey smudge that looks like a label that failed to render.
    if scene["real"]:
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
        for fg in (CLAY, WATER, SAND, TOWEL, INK_FAINT, SKIN, SKIN_LINE):
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

    # A long shelf would otherwise run for a minute. The file cannot be
    # paused or skipped, so past a point more frames is not more
    # information, it is a longer wait before the loop comes round to the
    # step you wanted to see.
    wanted = [max(5, min(int(round(sc["screen"] * 3)), 11)) for sc in scenes]
    if sum(wanted) > MAX_FRAMES:
        squeeze = MAX_FRAMES / sum(wanted)
        wanted = [max(4, int(round(n * squeeze))) for n in wanted]

    for i, scene in enumerate(scenes):
        n = wanted[i]
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

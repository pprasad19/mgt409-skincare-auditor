"""Turn a routine step into something that can be drawn moving on a face.

WHY THIS IS NOT A GENERATED VIDEO

The obvious reading of "make an animated video of the routine" is: send the
routine to a video model and show what comes back. That was rejected, and the
reason is the same one the rest of this system is built on.

A generated clip shows a stranger applying an unnamed cream in an order the
model chose. It cannot cite a rule, it does not know that the user's vitamin C
was moved to the morning because SKA-003 fired, and nothing in it can be
checked against anything. It would be the only screen in this project that
asks to be taken on faith.

So the animation is drawn, from data we already have. `beats_for` in render.py
already produces the physical sequence — apply, finish, wait — and the text
list, the printed card and the spoken walkthrough all render from it. This
module adds the two things a picture needs that a sentence does not: WHERE on
the face, and HOW the hands move. Timing still comes from the beats, so the
animation cannot drift from what the page says in words.

ON TIME

Guided mode runs in real seconds, because someone is following it at a sink.
The animation is a preview — nobody watches six minutes of a cartoon face
absorbing toner — so screen time is compressed and the real duration is
printed alongside. The two are different jobs and pretending otherwise would
make the preview useless and the guide wrong.
"""

from __future__ import annotations

import re

# A face in a 200x240 box. Anchors are where product actually goes, not an
# anatomical drawing: enough points that a region reads as that region.
ANCHORS: dict[str, list[tuple[int, int]]] = {
    "forehead": [(78, 62), (100, 56), (122, 62)],
    "temples": [(60, 80), (140, 80)],
    "eyes": [(76, 106), (124, 106)],
    "undereye": [(74, 122), (126, 122)],
    "nose": [(100, 118), (100, 134)],
    "cheeks": [(66, 136), (134, 136), (74, 152), (126, 152)],
    "lips": [(100, 166)],
    "chin": [(100, 184)],
    "jaw": [(66, 172), (134, 172)],
    "neck": [(84, 214), (116, 214)],
}

# Top to bottom. Only used to keep output stable.
ORDER = list(ANCHORS)

# "whole face" is not every anchor — nobody puts moisturiser on their lips and
# eyeballs. This is the sensible default spread.
WHOLE_FACE = ["forehead", "temples", "nose", "cheeks", "chin", "jaw"]

# Phrases a routine actually uses, longest first so "under-eye" is not eaten
# by "eye". Each maps to one or more anchor groups.
PHRASES: list[tuple[str, list[str]]] = [
    ("t-zone", ["forehead", "nose"]),
    ("t zone", ["forehead", "nose"]),
    ("under-eye", ["undereye"]),
    ("under eye", ["undereye"]),
    ("orbital", ["undereye"]),
    ("eye area", ["undereye"]),
    ("eye contour", ["undereye"]),
    ("eyes", ["undereye"]),
    ("eye", ["undereye"]),
    ("forehead", ["forehead"]),
    ("temple", ["temples"]),
    ("cheek", ["cheeks"]),
    ("nose", ["nose"]),
    ("nasolabial", ["cheeks"]),
    ("lip", ["lips"]),
    ("mouth", ["lips"]),
    ("chin", ["chin"]),
    ("jaw", ["jaw"]),
    ("neck", ["neck"]),
    ("decollet", ["neck"]),
    ("throat", ["neck"]),
    ("whole face", WHOLE_FACE),
    ("entire face", WHOLE_FACE),
    ("all over", WHOLE_FACE),
    ("full face", WHOLE_FACE),
    ("face", WHOLE_FACE),
]

# "whole face, avoiding the eye area" has to lose the eyes. Without this the
# animation would show eye cream being rubbed into eyeballs on the one
# instruction that exists specifically to prevent that.
AVOID = re.compile(
    r"(?:avoid|avoiding|except|excluding|away from|not on|staying off|steer clear of)\s+"
    r"(?:the\s+)?([a-z\s-]{3,30})"
)

# How the hands move. The driver reads these names; keeping them here means a
# motion the prompt allows can never silently fall through to nothing.
MOTIONS = {
    "circular": "orbit",
    "lather": "foam",
    "press": "press",
    "patting": "tap",
    "smooth": "sweep",
    "dab": "dab",
}

# Screen seconds per beat. Enough to read the motion, short enough that a
# six-step routine is under a minute.
MIN_SCREEN = 1.3
MAX_SCREEN = 3.8


def regions_for(area: str) -> list[str]:
    """Which anchor groups an `area` string refers to.

    Deterministic and order-independent: the same phrase always gives the same
    picture, and an area nobody anticipated falls back to the whole face
    rather than to an empty frame.
    """
    text = (area or "").lower()

    # Work out the exclusion first, then match inclusions against the text
    # with the exclusion clause removed — otherwise "avoiding the eye area"
    # matches "eye area" and adds the very region it rules out.
    excluded: list[str] = []
    for clause in AVOID.findall(text):
        for phrase, groups in PHRASES:
            if phrase in clause:
                excluded.extend(groups)
                break
    kept = AVOID.sub(" ", text)

    found: list[str] = []
    for phrase, groups in PHRASES:
        if phrase in kept:
            found.extend(groups)
            kept = kept.replace(phrase, " ")

    if not found:
        found = list(WHOLE_FACE)

    out = [g for g in dict.fromkeys(found) if g not in excluded]
    # Top of the face downwards, always, so "face and neck" and "neck and
    # face" draw the same picture and the dots never appear in a different
    # order between two runs of the same routine.
    out.sort(key=lambda g: ORDER.index(g))
    return out or list(WHOLE_FACE)


def points_for(area: str) -> list[dict]:
    """The dots to draw, as plain coordinates the driver can animate."""
    pts: list[dict] = []
    for group in regions_for(area):
        for x, y in ANCHORS[group]:
            pts.append({"x": x, "y": y, "g": group})
    return pts


def screen_seconds(real: int) -> float:
    """Compress a real duration into watchable screen time.

    Sub-linear on purpose. A 25-second rinse and a 90-second wait are
    different, and the animation should show that they are different without
    standing still for ninety seconds to prove it.
    """
    real = max(int(real or 0), 1)
    return round(min(MIN_SCREEN + (real ** 0.62) * 0.22, MAX_SCREEN), 2)


def _real_time(secs: int) -> str:
    secs = int(secs or 0)
    if secs >= 90:
        mins = secs / 60
        return f"{mins:.0f} minutes" if mins >= 1.5 else "a minute"
    return f"{secs} seconds"


def scenes_for(step, spec, beats: list[dict]) -> list[dict]:
    """One step becomes a list of scenes, one per beat.

    `beats` is passed in rather than recomputed so this cannot disagree with
    the written list, the printed card or the audio, which all render from the
    same call.
    """
    area = getattr(spec, "area", "") or "whole face"
    motion = getattr(spec, "motion", "smooth") or "smooth"
    amount = getattr(spec, "amount", "") or "as usual"
    pts = points_for(area)

    out: list[dict] = []
    for beat in beats:
        kind = beat["kind"]
        if kind == "apply":
            anim, caption = MOTIONS.get(motion, "sweep"), f"{amount}, {motion}"
        elif kind == "rinse off":
            anim, caption = "rinse", "rinse and pat dry"
        elif kind == "pat dry":
            anim, caption = "towel", "pat dry"
        else:
            anim, caption = "absorb", "let it absorb"

        out.append({
            "anim": anim,
            "caption": caption,
            "where": area if kind == "apply" else "",
            "real": _real_time(beat["secs"]),
            "screen": screen_seconds(beat["secs"]),
            "points": pts if kind == "apply" else [],
            # Where the product is sitting while it absorbs or is rinsed
            # off. Without this every finish scene was an empty face, so
            # eight of the eighteen scenes in a six-product routine were the
            # same picture with different captions -- and absorbing a
            # retinol on the chin looked like absorbing a toner everywhere.
            "rest": [] if kind == "apply" else pts,
        })
    return out

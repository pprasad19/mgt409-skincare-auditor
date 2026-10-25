"""Does the animation put the product where the instruction says?

The failure that matters here is quiet: an area the mapper does not recognise
produces a frame with no dots on it, which looks like a step with nothing to
do rather than like a bug. And an "avoiding the eye area" that is read as
"the eye area" animates the exact thing the instruction forbids.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from storyboard import ANCHORS, WHOLE_FACE, points_for, regions_for, screen_seconds

ok = 0


def check(label, got, want):
    global ok
    assert got == want, f"\n  {label}\n  got:  {got}\n  want: {want}"
    ok += 1


def check_true(label, cond):
    global ok
    assert cond, f"\n  {label}"
    ok += 1


# Plain areas the agent actually writes.
check("whole face", regions_for("whole face"), WHOLE_FACE)
check("t-zone", regions_for("the T-zone"), ["forehead", "nose"])
check("under-eye", regions_for("under-eye area"), ["undereye"])
check("cheeks only", regions_for("cheeks"), ["cheeks"])
check("neck included", regions_for("face and neck"), WHOLE_FACE + ["neck"])
check("chin and jaw", regions_for("chin and jawline"), ["chin", "jaw"])

# The exclusion. This is the whole reason the parser is not a dict lookup.
check(
    "whole face avoiding eyes",
    regions_for("whole face, avoiding the eye area"),
    [g for g in WHOLE_FACE if g != "undereye"],
)
check_true(
    "eyes really excluded",
    "undereye" not in regions_for("all over, avoiding the eye area"),
)
check_true(
    "except phrasing",
    "undereye" not in regions_for("entire face except the eye contour"),
)
check_true(
    "away-from phrasing",
    "undereye" not in regions_for("face, keeping away from the eyes"),
)

# "under-eye" must not be swallowed by "eye", and an exclusion must not be
# able to empty the frame.
check_true("never empty", regions_for("avoiding the whole face") != [])
check_true("unknown area falls back", regions_for("left elbow") == WHOLE_FACE)
check_true("empty area falls back", regions_for("") == WHOLE_FACE)

# Every group a phrase can produce must be drawable.
for area in ("whole face", "t-zone", "under-eye", "neck", "lips", "temples"):
    for g in regions_for(area):
        check_true(f"{g} has anchors", g in ANCHORS and ANCHORS[g])

# Points come out as coordinates inside the viewBox.
pts = points_for("whole face")
check_true("whole face has dots", len(pts) >= 8)
check_true(
    "dots inside the box",
    all(0 < p["x"] < 200 and 0 < p["y"] < 240 for p in pts),
)

# Compression: monotonic, bounded, and never zero.
check_true("5s under 25s", screen_seconds(5) < screen_seconds(25))
check_true("25s under 90s", screen_seconds(25) < screen_seconds(90))
check_true("capped", screen_seconds(600) <= 3.8)
check_true("floored", screen_seconds(0) >= 1.3)

# Every animation the storyboard can name must actually animate something.
#
# This is here because the rinse scene silently drew nothing: its rule said
# `animation:water 1.2s linear infinite var(--d)` and `--d` is only ever set
# on the product dots, so the shorthand was invalid and the browser dropped
# the whole declaration. The scene still had a caption and a duration, so it
# looked like a step rather than a blank frame -- the same shape of failure
# as an empty audit rendering as a pass.
import re

from storyboard import MOTIONS

css = (Path(__file__).resolve().parent / "src" / "render.py").read_text(encoding="utf-8")
RULE = re.compile(r"([^{}\n][^{}]*)\{([^}]*)\}")
rules = [(sel.strip(), body) for sel, body in RULE.findall(css)]

from render import OPENING_ANIMS

# Everything the storyboard can emit, and the split between the two
# renderers. The player has no CSS for the opening act, so render() filters
# it out; if that filter is ever dropped the player would draw a bare face
# under a caption for four scenes.
PLAYER_ANIMS = sorted(set(MOTIONS.values()) |
                      {"rinse", "towel", "absorb", "dispense", "maskon", "maskoff"})
ALL_ANIMS = sorted(set(PLAYER_ANIMS) | set(OPENING_ANIMS))

# Dispensing fades the face back and shows the dose instead, so its motion
# lives on the dose elements rather than on a [data-anim] selector.
DRIVEN_BY = {"dispense": ".dosedot"}

for anim in PLAYER_ANIMS:
    needle = DRIVEN_BY.get(anim, '[data-anim="%s"]' % anim)
    moving = [
        (sel, body) for sel, body in rules
        if needle in sel and "animation:" in body and "animation:none" not in body
    ]
    check_true("%s animates something" % anim, bool(moving))

# A custom property used with no fallback must only appear on a selector that
# is actually given one -- otherwise the declaration is invalid and silently
# dropped. The JS sets --d and --out on .pd elements and nothing else.
# `var(--out,6px)` is fine anywhere: it has a fallback.
NO_FALLBACK = re.compile(r"var\(\s*(--[a-z-]+)\s*\)")
# The elements the player's JS sets --d and --out on, and no others.
GIVEN_VARS = (".pd", ".dosedot", ".dosebar")
for sel, body in rules:
    for prop in NO_FALLBACK.findall(body):
        if prop in ("--d", "--out"):
            check_true(
                "%s used only where it is set (%s)" % (prop, sel[:40]),
                any(k in sel for k in GIVEN_VARS),
            )



# Containers and doses. These are what actually tell one step from the next
# now: the first version varied how abstract dots moved, which carries no
# product-specific information at all, so every step looked alike.
import filmstrip
from storyboard import CONTAINERS, container_for, dose_for, path_for

check("serum is a dropper", container_for("serum"), "dropper")
check("mask is a wide tub", container_for("mask"), "widetub")
check("spf is a tube", container_for("spf"), "tube")
check_true("unknown form still draws something", container_for("zzz") == "bottle")
check_true("empty form still draws something", container_for("") == "bottle")

for form_id, kind in CONTAINERS.items():
    check_true(f"{form_id} container is drawable", kind in filmstrip.CONTAINER_KINDS)

check("pea", dose_for("pea-sized")["kind"], "pea")
check("rice", dose_for("a rice-grain amount")["kind"], "rice")
check("dime", dose_for("a dime-sized amount")["kind"], "coin")
check("two fingers", dose_for("two fingers' length")["kind"], "twofinger")
check("cotton pad", dose_for("a few drops on a cotton pad")["kind"], "pad")
check("thick layer", dose_for("a thick even layer")["kind"], "thick")
check("unknown amount", dose_for("some")["kind"], "pea")
check("empty amount", dose_for("")["kind"], "pea")

# "under-eye" must not be eaten by "eye", and "cotton pad" must beat "drops":
# the pad is what the drops go on, and drawing three loose droplets for it
# would show the wrong technique.
check("pad beats drops", dose_for("a few drops on a cotton pad")["kind"], "pad")
check("drop count", dose_for("three drops")["n"], 3)
check("digit count", dose_for("2 drops")["n"], 2)
check("default drops", dose_for("a few drops")["n"], 3)
check_true("drops are bounded", 1 <= dose_for("40 drops")["n"] <= 8)

# Stroke paths keep every named region. Capping by stride used to drop one:
# "forehead, cheeks and chin" came back without the chin.
for area, must in (
    ("forehead, cheeks and chin", {"forehead", "cheeks", "chin"}),
    ("whole face and neck", {"neck"}),
    ("under-eye area", {"undereye"}),
):
    groups = {p["g"] for p in path_for(area)}
    check_true(f"{area!r} keeps its regions", must <= groups)

check_true("paths are short", all(len(path_for(a)) <= 7 for a in
                                 ("whole face", "whole face and neck", "the T-zone")))
check_true("paths are never empty", len(path_for("left elbow")) > 0)


# No scene type may draw a blank frame.
#
# Asserted by rendering each one and comparing it against a frame whose
# animation name matches nothing. A new scene type added to the storyboard
# and forgotten in the drawing code still produces a caption and a
# duration, so it looks like a step rather than like a bug -- which is
# exactly how the rinse scene shipped drawing nothing at all.
_FONTS = filmstrip._fonts()
STOPS = points_for("whole face")


def _scene(anim):
    base = {
        "anim": anim, "caption": "caption", "where": "whole face",
        "real": "20 seconds", "screen": 2.0, "slot": "Morning",
        "order": 1, "of": 1, "name": "A Product", "form": "serum", "why": "",
        "container": "dropper", "dose": {"kind": "pea", "n": 1},
        "ribbon": ["a", "b"], "at": 0,
        "points": [], "rest": [],
    }
    if anim in ("shelf", "sort"):
        base["items"] = [{"label": "A", "container": "tub", "slot": "am"},
                         {"label": "B", "container": "pump", "slot": "pm"}]
    elif anim == "clash":
        base["pair"] = ["A", "B"]
        base["containers"] = ["tub", "pump"]
        base["rule"] = "SKA-001"
    elif anim == "week":
        base["rows"] = [{"label": "A", "every": 2, "offset": 0},
                        {"label": "B", "every": 2, "offset": 1}]
    elif anim in ("rinse", "towel", "absorb", "maskoff"):
        base["rest"] = STOPS
    elif anim != "dispense":
        base["points"] = STOPS
    return base


blank = filmstrip._frame(_scene("__nothing__"), 0.5, 0.5, _FONTS)
for anim in ALL_ANIMS:
    drawn = filmstrip._frame(_scene(anim), 0.55, 0.5, _FONTS)
    pair = zip(blank.get_flattened_data(), drawn.get_flattened_data())
    differs = sum(1 for a, b in pair if a != b)
    check_true("%s draws something" % anim, differs > 400)

check_true("opening act is not in the player's set",
           not (set(OPENING_ANIMS) & set(PLAYER_ANIMS)))

render_src = (Path(__file__).resolve().parent / "src" / "render.py").read_text(
    encoding="utf-8")
check_true("render filters the opening out of the player",
           'sc["anim"] not in OPENING_ANIMS' in render_src)
check_true("the gif still gets every scene",
           "_routine_gif(film_scenes)" in render_src)

# The GIF. A download button that hands over a broken file is worse than no
# button, and a failure here must cost the button and not the audit.
from render import _routine_gif

SCENES = [
    {"anim": a, "caption": "c", "where": "whole face", "real": "20 seconds",
     "screen": 1.5, "points": points_for("whole face"),
     "slot": "Morning", "order": 1, "of": 1, "name": "A Product With Quite A Long Name",
     "form": "serum", "why": "SKA-001"}
    for a in ALL_ANIMS
]

data = filmstrip.build(SCENES)
check_true("gif has bytes", len(data) > 2000)
check_true("gif magic", data[:6] in (b"GIF87a", b"GIF89a"))
check_true("gif is not enormous", len(data) < 3_000_000)

from io import BytesIO
from PIL import Image

im = Image.open(BytesIO(data))
check_true("more than one frame", getattr(im, "n_frames", 1) > 1)
check("canvas", im.size, (filmstrip.W, filmstrip.H))

# An empty routine must not produce a zero-frame file, which some viewers
# draw as a broken image.
check("no scenes, no file", filmstrip.build([]), b"")
check("no scenes, no data uri", _routine_gif([]), "")

uri = _routine_gif(SCENES)
check_true("data uri", uri.startswith("data:image/gif;base64,"))

print("ok  %d checks passed" % ok)
print("    face regions, exclusions, fallbacks, time compression,")
print("    every scene animation actually animating,")
print("    containers, doses and stroke paths, the opening act,")
print("    no scene drawing blank, and the GIF export")

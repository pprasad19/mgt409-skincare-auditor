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

for anim in sorted(set(MOTIONS.values()) | {"rinse", "towel", "absorb"}):
    needle = '[data-anim="%s"]' % anim
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
for sel, body in rules:
    for prop in NO_FALLBACK.findall(body):
        if prop in ("--d", "--out"):
            check_true(
                "%s used only where it is set (%s)" % (prop, sel[:40]),
                ".pd" in sel,
            )

print("ok  %d checks passed" % ok)
print("    face regions, exclusions, fallbacks, time compression,")
print("    and every scene animation actually animating")

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
check_true("the gif still gets the opening act the player drops",
           "opening + [sc for sc in player_scenes" in render_src)

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


# The animation must say the same duration as every other surface.
#
# Four surfaces render from beats_for — the written steps, the printed
# card, the guided player and the animation — and only the animation
# converts seconds to minutes, so only the animation can disagree. It
# did: the old threshold switched at 90 seconds and rounded 1.5 up, so a
# ninety-second wait was captioned "2 minutes" beside a step list saying
# 90s. A third longer, on the number the user is standing still for.
from storyboard import _real_time

for secs, want in (
    (20, "20 seconds"), (60, "60 seconds"), (89, "89 seconds"),
    (90, "90 seconds"),      # the one that was wrong
    (119, "119 seconds"),
    (120, "2 minutes"),
    (150, "3 minutes"),      # half-up, not banker's
    (600, "10 minutes"),
):
    check("_real_time(%d)" % secs, _real_time(secs), want)

# And the stronger property: for any beat under two minutes, the string
# the animation shows contains the exact number the other surfaces print.
for spec_secs in range(1, 120):
    shown = _real_time(spec_secs)
    check_true(
        "%ds is shown exactly, not rounded" % spec_secs,
        str(spec_secs) in shown,
    )

# --- every surface shows every step -----------------------------------
# A tester counted: "the audio and animated video do not reflect all the
# written steps of the routine but it should." They were right. The film
# walked unique products rather than the routine, so a nine-step routine
# became five scenes, and both the film and the guided player skipped
# the placeholder steps entirely.
#
# A count, not a sample, because counting is how the tester found it.
import json as _json
import re as _re

from models import AuditNarrative as _AN, InputProduct as _IP  # noqa: E402
from render import render as _render  # noqa: E402
from rules import Rules as _Rules  # noqa: E402

_R = _Rules()
_SHELF = [
    ("CeraVe Foaming Cleanser", ["Ceramide NP"]),
    ("The Ordinary Niacinamide", ["Niacinamide"]),
    ("The Ordinary Retinol", ["Retinol"]),
    ("CeraVe Moisturizing Cream", ["Glycerin"]),
    ("Daily SPF 50", ["Avobenzone"]),
]
_audit = _R.audit([_IP(name=n, listed_ingredients=i) for n, i in _SHELF], concerns=[])
_page = _render(_audit, _AN(summary="x", explanations=[], steps=[]), carry="[]")

_written = ([("Morning", st) for st in _audit.routine.am]
            + [("Evening", st) for st in _audit.routine.pm])
_player = _json.loads(
    _re.search(r"var DATA_STEPS=(\[.*?\]);var MX_DATA", _page, _re.S).group(1))
_film = _json.loads(_re.search(r"var FILM=(\[.*?\]);", _page, _re.S).group(1))

_film_steps = []
for _sc in _film:
    _k = (_sc.get("slot", ""), _sc.get("name", ""))
    if _sc.get("name") and _k not in _film_steps:
        _film_steps.append(_k)

_want = [(slot, st.product_name) for slot, st in _written]

check_true("the fixture produces a routine worth comparing", len(_written) >= 8)
check("the guided player has every written step", len(_player), len(_written))
check("so does the animation", len(_film_steps), len(_written))
check("the animation is the routine, in order", _film_steps, _want)
# The player keys slots as am/pm and the film as Morning/Evening; the
# comparison is about the sequence, not the spelling.
_SLOT = {"am": "Morning", "pm": "Evening"}
check("and so is the player",
      [(_SLOT[st["slot"]], st["name"]) for st in _player], _want)

# Two testers pulled in opposite directions here. One counted the
# written steps against the film and found the film short. The other
# said the film repeated itself, and the answer at the time was to
# collapse the second showing of a product into a "same again, as this
# morning" card.
#
# Splitting the player into a morning and an evening — which a third
# asked for — retires that card and answers both complaints properly.
# Nothing is drawn twice in anything anybody watches in one sitting,
# because the two halves are two films; and each half is complete, so
# someone who opens only the evening is not told to remember a scene
# they never saw.
_am = [n for s_, n in _film_steps if s_ == "Morning"]
_pm = [n for s_, n in _film_steps if s_ == "Evening"]
check("no product is drawn twice in the morning", len(_am), len(set(_am)))
check("nor twice in the evening", len(_pm), len(set(_pm)))
check_true("the fixture does use a product twice a day",
           bool(set(_am) & set(_pm)))
check_true("and that product is played in full in both halves",
           all(any(sc.get("slot") == slot and sc.get("name") == name
                   and sc.get("real")
                   for sc in _film)
               for name in (set(_am) & set(_pm))
               for slot in ("Morning", "Evening")))
check_true("the condensed repeat card is gone", "again" not in
           {sc.get("anim") for sc in _film})

# Each half counts its own steps. "Morning step 7 of 9" numbered the
# third thing you do before bed against the whole day.
for _slot, _steps in (("Morning", _audit.routine.am),
                      ("Evening", _audit.routine.pm)):
    _of = {sc["of"] for sc in _film if sc.get("slot") == _slot}
    check("the %s counts its own steps" % _slot.lower(), _of, {len(_steps)})
    _orders = sorted({sc["order"] for sc in _film if sc.get("slot") == _slot})
    check("and numbers them from one", _orders,
          list(range(1, len(_steps) + 1)))

# One player, one tab per half, one file per half.
check_true("the page offers a tab per half", 'id="f-tabs"' in _page)
for _slot in ("Morning", "Evening"):
    check_true("a %s tab" % _slot.lower(),
               'data-slot="%s"' % _slot in _page)
_gifs = _json.loads(_re.search(r"var GIFS=(\{.*?\});", _page, _re.S).group(1))
check("a gif per half", sorted(_gifs), ["Evening", "Morning"])
check_true("and each one is a real file",
           all(v.startswith("data:image/gif;base64,") and len(v) > 2000
               for v in _gifs.values()))

# A step the user does not own is demonstrated like any other, from
# the form's typical figures, and labelled as one they do not have.
#
# This assertion has been inverted twice, which is worth recording.
# First the step was skipped; a tester counted the written steps
# against the film and found it missing. Then it was shown untimed,
# with nothing to do, on my reasoning that counting down for a product
# someone does not own instructs them to use a thing that does not
# exist. A tester answered that directly — "I should not be able to do
# a routine without them" — and they are right: a guided routine that
# skips its own cleanser demonstrates something nobody should follow.
# The honesty belongs in the label, which every surface carries.
_gaps = [sc for sc in _film if sc.get("placeholder")]
check_true("a missing step is in the film", len(_gaps) >= 1)
check_true("drawn as a step rather than a hole",
           all(sc.get("anim") not in (None, "gap") for sc in _gaps))
check_true("and labelled as one they do not have",
           any("do not have" in sc.get("caption", "") for sc in _gaps))

_pgaps = [st for st in _player if st["freq"] == "not on your shelf"]
check_true("the player walks through it too", len(_pgaps) >= 1)
check_true("with real durations, not zero",
           all(b["secs"] > 0 for st in _pgaps for b in st["beats"]))
check_true("and a technique to follow",
           all(len(b["text"]) > 10 for st in _pgaps for b in st["beats"]))
check_true("nothing is left untimed now",
           not any(b.get("untimed") for st in _pgaps for b in st["beats"]))

# The spoken line must not contain the compact units the table uses:
# "50s" is read aloud as "fifty ess".
for _st in _pgaps:
    for _b in _st["beats"]:
        check_true("no abbreviated unit in a spoken beat",
                   not _re.search(r"\d\s*s", _b["text"]))


print("ok  %d checks passed" % ok)
print("    face regions, exclusions, fallbacks, time compression,")
print("    every scene animation actually animating,")
print("    containers, doses and stroke paths, the opening act,")
print("    no scene drawing blank, and the GIF export")

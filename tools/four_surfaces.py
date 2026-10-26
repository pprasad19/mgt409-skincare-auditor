"""Do the four surfaces really say the same durations?

Claimed repeatedly in commit messages and in storyboard.py's docstring:
the written steps, the printed card, the guided player and the animation
all render from `beats_for`, so "a duration cannot say one thing in the
text and another in the picture".

They do all call it. That is not the same as all rendering it the same
way, and nothing has checked the stronger claim.
"""
import json
import re
import sys

sys.path.insert(0, "src")

from models import AuditNarrative, InputProduct, StepApplication  # noqa: E402
from render import beats_for, render  # noqa: E402
from rules import Rules  # noqa: E402

R = Rules()

SPEC = StepApplication(
    product_name="Test Cleanser",
    motion="lather", area="whole face", amount="a dime-sized amount",
    seconds=25, finish="rinse off", finish_seconds=35, wait_after_seconds=0,
)
SPEC2 = StepApplication(
    product_name="Test Serum",
    motion="press", area="whole face", amount="three drops",
    seconds=15, finish="let it absorb", finish_seconds=20, wait_after_seconds=90,
)

# A mask, because the long durations are the ones worth comparing. Every
# beat the agent writes is under two minutes, so until a mask was in this
# fixture the four surfaces were only ever checked on numbers that render
# identically whatever you do — and the step list was printing "600s"
# while the animation said "10 minutes".
SPEC3 = StepApplication(
    product_name="Test Mask",
    motion="smooth", area="whole face", amount="a thin layer",
    seconds=30, finish="rinse off", finish_seconds=45, wait_after_seconds=0,
)

audit = R.audit([
    InputProduct(name="Test Cleanser", listed_ingredients=["Cocamidopropyl Betaine"]),
    InputProduct(name="Test Serum", listed_ingredients=["Niacinamide"]),
    InputProduct(name="Test Mask", listed_ingredients=["Kaolin"], form="mask"),
], concerns=[])

# What the engine attached to each step, so the comparison uses the same
# dwell the page does rather than assuming zero.
DWELL = {s.product_name: (s.dwell_seconds, s.dwell_note)
         for s in audit.routine.am + audit.routine.pm}

narrative = AuditNarrative(summary="t", explanations=[], steps=[SPEC, SPEC2, SPEC3])
html = render(audit, narrative)

print("  what beats_for says, per product:\n")
truth = {}
for spec in (SPEC, SPEC2, SPEC3):
    dwell, note = DWELL.get(spec.product_name, (0, ""))
    secs = [b["secs"] for b in beats_for(spec, dwell, note)]
    truth[spec.product_name] = secs
    kinds = [b["kind"] for b in beats_for(spec, dwell, note)]
    print(f"    {spec.product_name:16} {list(zip(kinds, secs))}")

print("\n  what each surface renders:\n")

# 1. written steps — class="how", "text · 25s"
how = re.findall(r'<div class="how">(.*?)</div>', html, re.S)
print(f"    written steps   {len(how)} blocks")
for h in how:
    print(f"      {re.sub('<[^>]+>', '', h)[:92]}")

# 2. printed card — class="pcd"
pcd = re.findall(r'<div class="pcd">(.*?)</div>', html, re.S)
print(f"\n    printed card    {len(pcd)} blocks")
for h in pcd:
    print(f"      {re.sub('<[^>]+>', '', h)[:92]}")

# 3. guided player + speech — DATA_STEPS carries beats verbatim
m = re.search(r"var DATA_STEPS=(\[.*?\]);var MX_DATA", html, re.S)
steps = json.loads(m.group(1))
print(f"\n    guided player   {len(steps)} steps")
for s in steps:
    print(f"      {s['name'][:20]:22} {[(b['kind'], b['secs']) for b in s['beats']]}")

# 4. animation — FILM scenes carry the real durations as prose
m = re.search(r"var FILM=(\[.*?\]);", html, re.S)
film = json.loads(m.group(1))
print(f"\n    animation       {len(film)} scenes")
for sc in film:
    if sc.get("real"):
        print(f"      {sc['name'][:20]:22} {sc['anim']:9} real={sc['real']!r}")

# --- now compare the numbers each surface shows -----------------------
print("\n  comparing the numbers:\n")


def nums(text: str) -> list[int]:
    """Durations a compact surface printed, in seconds.

    Both "25s" and "10 min" appear, and a ten-minute mask only reads
    sensibly as the second — so minutes are converted back here
    rather than forcing the surfaces to print raw seconds at the
    reader.
    """
    out = [int(n) for n in re.findall(r"(\d+)\s*s\b", text)]
    out += [int(n) * 60 for n in re.findall(r"(\d+)\s*min\b", text)]
    return out


problems = []
for name, expected in truth.items():
    # written steps and printed card both print "<n>s"
    for label, blocks in (("written steps", how), ("printed card", pcd)):
        hit = [b for b in blocks if name in re.sub("<[^>]+>", "", b)] or blocks
        got = nums(re.sub("<[^>]+>", "", " ".join(hit)))
        def near(n: int, got=got) -> bool:
            # "10 min" is exactly 600 here, but half-up rounding means a
            # 610-second dwell prints as 10 min too. Allow the rounding;
            # anything further apart is a real disagreement.
            return any(abs(n - g) <= 30 for g in got)

        missing = [n for n in expected if not near(n)]
        if missing:
            problems.append(f"{label}: {name} missing {missing} from {got}")

    st = next((s for s in steps if s["name"] == name), None)
    if st and [b["secs"] for b in st["beats"]] != expected:
        problems.append(f"guided player: {name} has "
                        f"{[b['secs'] for b in st['beats']]} not {expected}")

    scenes = [sc for sc in film if sc["name"] == name and sc.get("real")]
    for sc in scenes:
        n = re.findall(r"(\d+)", sc["real"])
        if n and int(n[0]) not in expected and "minute" not in sc["real"]:
            problems.append(f"animation: {name} shows {sc['real']!r}, "
                            f"beats are {expected}")

if problems:
    print("  DISAGREEMENTS:")
    for p in problems:
        print(f"    {p}")
else:
    print("  all four surfaces show the same seconds")

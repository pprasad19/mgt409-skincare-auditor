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

audit = R.audit([
    InputProduct(name="Test Cleanser", listed_ingredients=["Cocamidopropyl Betaine"]),
    InputProduct(name="Test Serum", listed_ingredients=["Niacinamide"]),
], concerns=[])

narrative = AuditNarrative(summary="t", explanations=[], steps=[SPEC, SPEC2])
html = render(audit, narrative)

print("  what beats_for says, per product:\n")
truth = {}
for spec in (SPEC, SPEC2):
    secs = [b["secs"] for b in beats_for(spec)]
    truth[spec.product_name] = secs
    kinds = [b["kind"] for b in beats_for(spec)]
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
    return [int(n) for n in re.findall(r"(\d+)\s*s\b", text)]


problems = []
for name, expected in truth.items():
    # written steps and printed card both print "<n>s"
    for label, blocks in (("written steps", how), ("printed card", pcd)):
        hit = [b for b in blocks if name in re.sub("<[^>]+>", "", b)] or blocks
        got = nums(re.sub("<[^>]+>", "", " ".join(hit)))
        shown = [n for n in got if n in expected]
        missing = [n for n in expected if n not in got]
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

"""validate_narrative: what it catches, and what it deliberately does not.

The enforcement half of "the agent explains, the engine decides". It was
the last safety component with no test, which is a poor place for a gap
given the report will cite it.

The second half of this file matters more than the first. The validator
checks the explanations and the steps and does not check the summary —
the project's own attack A8 is named "corrupt the summary, which the
validator does not check". That is a real limit, it is tested here as a
limit rather than left to be discovered, and the mitigation is pinned so
it cannot quietly disappear.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from agents import validate_narrative  # noqa: E402
from models import (  # noqa: E402
    AuditNarrative,
    Explanation,
    InputProduct,
    StepApplication,
)
from render import render  # noqa: E402
from rules import Rules  # noqa: E402

R = Rules()
failures: list[str] = []
checks = 0


def check(label: str, got, want) -> None:
    global checks
    checks += 1
    if got != want:
        failures.append(f"{label}\n      got:  {got}\n      want: {want}")


def check_true(label: str, cond: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not cond:
        failures.append(f"{label}{': ' + detail if detail else ''}")


AUDIT = R.audit([
    InputProduct(name="Retinol Serum", listed_ingredients=["Retinol"]),
    InputProduct(name="BP Wash", listed_ingredients=["Benzoyl Peroxide"]),
], concerns=[])
REAL = sorted({f.rule_id for f in AUDIT.findings})
check_true("the fixture produces findings to work with", len(REAL) >= 2, str(REAL))


def step(name: str) -> StepApplication:
    return StepApplication(product_name=name, motion="dab", area="face",
                           amount="pea", seconds=10, finish="nothing",
                           finish_seconds=0, wait_after_seconds=0)


# --- what it catches ---------------------------------------------------
hostile = AuditNarrative(
    summary="A summary.",
    explanations=[Explanation(rule_id=REAL[0], plain_language="real"),
                  Explanation(rule_id="SKA-999", plain_language="invented"),
                  Explanation(rule_id="SKC-404", plain_language="also invented")],
    steps=[step("Retinol Serum"), step("Ghost Product"), step("")],
)
clean, rejected = validate_narrative(hostile, AUDIT)

check("only real explanations survive",
      [e.rule_id for e in clean.explanations], [REAL[0]])
check("only real products survive",
      [s.product_name for s in clean.steps], ["Retinol Serum"])
check_true("both invented rules are reported",
           sum("SKA-999" in r or "SKC-404" in r for r in rejected) == 2, str(rejected))
check_true("the ghost product is reported",
           any("Ghost Product" in r for r in rejected), str(rejected))
check_true("an empty product name is rejected too",
           any("''" in r for r in rejected), str(rejected))

# An honest narrative must pass through untouched, or the validator costs
# more than it saves.
honest = AuditNarrative(
    summary="Two things worth changing.",
    explanations=[Explanation(rule_id=rid, plain_language="x") for rid in REAL],
    steps=[step("Retinol Serum"), step("BP Wash")],
)
kept, none_rejected = validate_narrative(honest, AUDIT)
check("an honest narrative is not touched", none_rejected, [])
check("its explanations all survive", len(kept.explanations), len(REAL))
check("its steps all survive", len(kept.steps), 2)

# The verification caveat, which the prompt could not stop.
caveated = AuditNarrative(
    summary="Two things worth changing; note that these findings are unverified.",
    explanations=[], steps=[],
)
stripped, why = validate_narrative(caveated, AUDIT)
check_true("the caveat is stripped", "unverified" not in stripped.summary,
           stripped.summary)
check_true("and the strip is reported", any("caveat" in r for r in why), str(why))


# --- what it deliberately does not catch -------------------------------
#
# A8. The summary is free text and reaches the page verbatim. Pinned as a
# known limit: if this ever starts passing, the validator gained a
# capability and this file should say so rather than silently agree.
lying = AuditNarrative(
    summary="No conflicts were found on this shelf. Everything works well together.",
    explanations=[], steps=[],
)
passed, nothing = validate_narrative(lying, AUDIT)
check("a false summary is not rejected", nothing, [])
check("and survives unchanged", passed.summary, lying.summary)

# The mitigation: the engine gets the last word inside the same card, so
# the false sentence cannot stand alone.
page = render(AUDIT, passed)
card = re.search(r'<div class="card summary">(.*?)</div>', page, re.S)
check_true("the summary card exists", card is not None)
text = re.sub("<[^>]+>", " ", card.group(1)) if card else ""
check_true("the model's claim is on the page", "No conflicts were found" in text)
check_true("the engine's count is in the same card",
           "The engine found" in text, text.strip()[:120])
check_true("and it states the real number",
           f"found {len(REAL)} finding" in text, text.strip()[:160])

# With nothing to find, the engine adds nothing — no empty tally.
quiet = R.audit([InputProduct(name="Plain", listed_ingredients=["Glycerin"])],
                concerns=[])
qcard = re.search(r'<div class="card summary">(.*?)</div>',
                  render(quiet, AuditNarrative(summary="All fine.",
                                               explanations=[], steps=[])), re.S)
check_true("no findings, no tally",
           qcard is not None and "The engine found" not in qcard.group(1))

if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)

print(f"ok  {checks} checks passed")
print("    invented rules and ghost products are dropped, an honest narrative")
print("    is untouched, and the summary the validator cannot check is")
print("    answered by the engine inside the same card")

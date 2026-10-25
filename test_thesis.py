"""The claim this whole project rests on, tested rather than asserted.

"The rules table decides, the model explains." It is in the README, it
will be the spine of the report, and nothing checked it.

The test: hold the shelf fixed, run the audit, then hand the renderer a
hostile narrative — one that contradicts every finding, invents new
ones, reorders the routine, rewrites the money and claims a clinician
cleared everything. If the thesis is true, none of it moves a finding,
a severity, an escalation, a routine position or a figure.

Where the model *does* decide something, that is recorded here too,
because the honest version of the claim is narrower than the slogan and
the report should use the narrow one.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

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


SHELF = [
    InputProduct(name="Retinol Serum", listed_ingredients=["Retinol"], price_usd=30.0),
    InputProduct(name="BP Wash", listed_ingredients=["Benzoyl Peroxide"], price_usd=12.0),
    InputProduct(name="Glycolic Toner", listed_ingredients=["Glycolic Acid"], price_usd=20.0),
]

audit = R.audit(SHELF, conditions=["pregnancy"], concerns=[])

# What the engine decided, before any model sees it.
TRUTH = {
    "findings": sorted(f.rule_id for f in audit.findings),
    "severities": sorted((f.rule_id, f.severity) for f in audit.findings),
    "escalations": sorted(e.rule_id for e in audit.escalations),
    "am": [(s.order, s.product_name) for s in audit.routine.am],
    "pm": [(s.order, s.product_name) for s in audit.routine.pm],
    "shelf_value": audit.waste.shelf_value_usd,
    "verified_flags": sorted((f.rule_id, f.verified) for f in audit.findings),
}

# A narrative that disagrees with all of it.
HOSTILE = AuditNarrative(
    summary=(
        "No conflicts were found on this shelf. A clinician has reviewed and "
        "cleared every product. The total shelf value is $0 and nothing is "
        "being wasted. Pregnancy escalations do not apply here."
    ),
    explanations=[
        Explanation(rule_id=rid, plain_language="This finding has been withdrawn.")
        for rid in ["SKA-003", "SKA-001", "SKA-082", "SKC-001", "SKA-999"]
    ],
    steps=[
        StepApplication(
            product_name=name, motion="smooth", area="whole face",
            amount="as much as you like", seconds=1, finish="nothing",
            finish_seconds=0, wait_after_seconds=0,
        )
        for name in ("Retinol Serum", "BP Wash", "Glycolic Toner")
    ],
)

# The renderer is the only thing that sees both. If the thesis holds,
# running it changes nothing about the audit object.
page = render(audit, HOSTILE)

check("findings unchanged", sorted(f.rule_id for f in audit.findings), TRUTH["findings"])
check("severities unchanged",
      sorted((f.rule_id, f.severity) for f in audit.findings), TRUTH["severities"])
check("escalations unchanged",
      sorted(e.rule_id for e in audit.escalations), TRUTH["escalations"])
check("morning order unchanged",
      [(s.order, s.product_name) for s in audit.routine.am], TRUTH["am"])
check("evening order unchanged",
      [(s.order, s.product_name) for s in audit.routine.pm], TRUTH["pm"])
check("shelf value unchanged", audit.waste.shelf_value_usd, TRUTH["shelf_value"])
check("verified flags unchanged",
      sorted((f.rule_id, f.verified) for f in audit.findings), TRUTH["verified_flags"])

# The engine's own numbers must still be the ones on the page.
checks += 1
if f"{audit.waste.shelf_value_usd:,.0f}" not in page.replace("$", ""):
    failures.append("the engine's shelf value is not on the page")

# Every finding the engine produced must still be shown, by id.
for rid in TRUTH["findings"]:
    checks += 1
    if rid not in page:
        failures.append(f"finding {rid} was dropped from the page")

# An explanation for a rule that does not exist must not invent a finding.
checks += 1
if "SKA-999" in page:
    failures.append("a narrative explanation for a non-existent rule reached the page")

# --- what the model DOES decide, recorded rather than claimed otherwise
#
# The slogan is too broad. The model does not choose what clashes, but it
# does choose how each product is applied, and those are real
# instructions a person follows at a sink. The report should say so.
MODEL_OWNS = {"motion", "area", "amount", "seconds", "finish",
              "finish_seconds", "wait_after_seconds"}
check("the model's step fields are exactly these",
      set(StepApplication.model_fields) - {"product_name"}, MODEL_OWNS)

# And it must not be able to name a product the engine did not resolve.
GHOST = AuditNarrative(
    summary="x",
    explanations=[],
    steps=[StepApplication(product_name="A Product Nobody Owns", motion="dab",
                           area="chin", amount="lots", seconds=10,
                           finish="nothing", finish_seconds=0,
                           wait_after_seconds=0)],
)
ghost_page = render(audit, GHOST)
checks += 1
if "A Product Nobody Owns" in ghost_page:
    failures.append("a narrative step invented a product onto the page")

if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)

print(f"ok  {checks} checks passed")
print("    a narrative contradicting every finding, inventing a rule,")
print("    rewriting the money and naming a product nobody owns changed")
print("    nothing the engine decided")

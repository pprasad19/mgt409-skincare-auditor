"""The MCP server must say what the app says.

It is a second way into the same rules table, with its own name
resolution and its own shaping of the output, and nothing was comparing
the two. A divergence would be invisible in the worst way: both answers
look authoritative, and nobody runs them side by side. An agent asking
the MCP server whether two products clash would get a different answer
from the one the result page gives the person holding the bottles.

Checks the tools against the engine they both read from.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "mcp_server"))

from models import InputProduct  # noqa: E402
from rules import Rules  # noqa: E402

import server as mcp  # noqa: E402

R = Rules()
failures: list[str] = []
checks = 0


def same(label: str, a, b) -> None:
    global checks
    checks += 1
    if a != b:
        failures.append(f"{label}\n      mcp: {a}\n      app: {b}")


# --- the same label resolves to the same actives ----------------------
LABELS = [
    "Water, Niacinamide, Retinol, Glycerin",
    "Aqua, Glycolic Acid, Salicylic Acid",
    "Ascorbic Acid, Tocopherol, Ferulic Acid",
    # The sunscreen filters that were unrecognised until 25 Oct.
    "Diethylamino Hydroxybenzoyl Hexyl Benzoate, Ethylhexyl Triazone",
    # The centella triterpenes, likewise.
    "Asiaticoside, Madecassic Acid, Allantoin",
    "nothing recognisable here at all",
]
for text in LABELS:
    same(f"resolve_ingredients({text[:40]!r})",
         sorted({row["id"] for row in mcp.resolve_ingredients(text)}),
         sorted(R.resolve_text(text)))

# --- the same actives produce the same rule ids -----------------------
#
# The audit also emits timing rules that pair an active with everything on
# the shelf, which check_interactions has no shelf to pair against. So the
# test is one-directional: every rule the MCP reports must be one the
# audit also finds. The reverse would fail for a reason that is not a bug.
SHELVES = [
    ["Retinol", "Glycolic Acid"],
    ["Tretinoin", "Benzoyl Peroxide"],
    ["Adapalene", "Benzoyl Peroxide"],   # the exception that overrides SKA-003
    ["Niacinamide", "Retinol"],
    ["Ascorbic Acid", "Benzoyl Peroxide"],
]
for actives in SHELVES:
    ids = sorted({i for a in actives for i in R.resolve_text(a)})
    via_mcp = {row["rule_id"] for row in mcp.check_interactions(ids)}
    audit = R.audit(
        [InputProduct(name=f"P{n}", listed_ingredients=[a])
         for n, a in enumerate(actives)],
        concerns=[],
    )
    via_app = {f.rule_id for f in audit.findings}
    same(f"check_interactions({' + '.join(actives)})",
         sorted(via_mcp - via_app), [])

# --- the same gates fire ----------------------------------------------
for actives, condition in (
    (["Retinol"], "pregnancy"),
    (["Hydroquinone"], "pregnancy"),
    (["Glycolic Acid"], "pregnancy"),   # SKC-004, added 25 Oct
    (["Niacinamide"], "pregnancy"),     # nothing should fire
):
    ids = sorted({i for a in actives for i in R.resolve_text(a)})
    same(f"check_contraindications({actives[0]}, {condition})",
         sorted({row["rule_id"] for row in
                 mcp.check_contraindications(ids, [condition])}),
         sorted({e.rule_id for e in R.audit(
             [InputProduct(name="P", listed_ingredients=actives)],
             conditions=[condition], concerns=[]).escalations}))

# --- the layering order is the order the routine is built from --------
same("layering_order",
     [(row["form"], row["order"]) for row in mcp.layering_order()],
     sorted(((fid, row["rank"]) for fid, row in R.forms.items()),
            key=lambda x: x[1]))

# --- the catalogue agrees on what exists ------------------------------
for name in ("CeraVe Foaming Facial Cleanser",
             "The Ordinary Niacinamide",
             "a product that does not exist"):
    found_mcp = bool(mcp.find_product(name).get("found"))
    same(f"find_product({name[:34]!r})",
         found_mcp, bool(R.match_catalogue(InputProduct(name=name))))

# --- coverage must not call a reviewed rule unexamined ----------------
#
# This went wrong once already. build_db counted `review != verified` and
# printed it as "still marked review: pending", announcing thirty-four
# reviewed rows as unexamined. The MCP tool had the same shape.
c = mcp.coverage()
checks += 1
if c["rules_verified"] + c["rules_reasoned"] + c["rules_pending"] != c["rules_total"]:
    failures.append(f"coverage states do not sum to the total: {c}")
checks += 1
if c["rules_total"] != len(R.interactions) + len(R.contraindications):
    failures.append("coverage rules_total disagrees with the engine")

if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)

print(f"ok  {checks} checks passed")
print("    the MCP server and the app agree on resolution, interactions,")
print("    contraindications, layering order, the catalogue and coverage")

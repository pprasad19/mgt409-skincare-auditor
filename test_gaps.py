"""What the shelf is missing — the question a routine built from it cannot ask.

A tester pasted five products, owned no cleanser and no moisturiser, and
was told only that there was no sunscreen. Everything else on the page
was built *from* their shelf: the routine ordered what they had, the
findings compared what they had against each other. Nothing looked at
the shape of the routine and noticed two of its steps were absent. For
someone deciding what to buy next, that is the question.

The restraint matters as much as the coverage. `product_forms.yaml` has
twelve forms and this flags three: cleanser, moisturiser, sunscreen —
the steps the AAD order names, and the only three rows in that file
marked `verified` rather than `reasoned`. The other nine are the
industry layering convention, which is real but is not a need. Telling
someone they are "missing" an essence would invent a purchase, which is
the failure this project exists to avoid. Both directions are pinned
below.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from models import AuditNarrative, InputProduct  # noqa: E402
from render import render  # noqa: E402
from rules import ESSENTIAL_STEPS, Rules  # noqa: E402

R = Rules()
failures: list[str] = []
checks = 0


def check(label: str, got, want) -> None:
    global checks
    checks += 1
    if got != want:
        failures.append(f"{label}\n      got:  {got!r}\n      want: {want!r}")


def check_true(label: str, cond: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not cond:
        failures.append(f"{label}{': ' + detail if detail else ''}")


def gaps_for(*products) -> dict[str, str]:
    """kind -> severity, for a shelf described as (name, [ingredients])."""
    audit = R.audit(
        [InputProduct(name=n, listed_ingredients=list(i)) for n, i in products],
        concerns=[],
    )
    return {g.kind: g.severity for g in audit.gaps}


CLEANSER = ("CeraVe Hydrating Cleanser", ["Ceramide NP", "Hyaluronic Acid"])
MOISTURISER = ("CeraVe Moisturising Lotion", ["Ceramide NP", "Glycerin"])
SPF = ("Daily SPF 50", ["Avobenzone", "Octocrylene"])
NIACINAMIDE = ("The Ordinary Niacinamide 10%", ["Niacinamide", "Zinc PCA"])
RETINOL = ("The Ordinary Retinol 0.5%", ["Retinol", "Squalane"])


# --- the tester's shelf ------------------------------------------------
# Two serums, nothing else. Every essential step absent.
bare = gaps_for(NIACINAMIDE, RETINOL)
check("no cleanser is reported", "no_cleanser" in bare, True)
check("no moisturiser is reported", "no_moisturiser" in bare, True)
check_true("and sun protection is still reported",
           "no_sun_protection" in bare, str(sorted(bare)))
check("the retinoid makes sun protection the high one",
      bare.get("no_sun_protection"), "high")

# Nothing is invented beyond the three. This is the check that stops the
# feature turning into a shopping list.
optional = {"toner", "essence", "eye", "oil", "exfoliant", "mask",
            "occlusive", "serum", "treatment"}
invented = {k for k in bare if k.removeprefix("no_") in optional}
check("no optional step is reported as missing", invented, set())


# --- a complete routine says nothing ------------------------------------
# If this fires, the feature is noise on every well-stocked shelf.
full = gaps_for(CLEANSER, NIACINAMIDE, MOISTURISER, SPF)
check("a complete routine has no gaps", full, {})


# --- one at a time -------------------------------------------------------
check("missing only a cleanser", set(gaps_for(MOISTURISER, SPF)), {"no_cleanser"})
check("missing only a moisturiser", set(gaps_for(CLEANSER, SPF)), {"no_moisturiser"})


# --- sunscreen, which depends on what else is there ----------------------
# Three different situations, three different things to say. The third
# used to say nothing at all: no photosensitising product meant the
# branch never fired, so the most-recommended product in skincare went
# unmentioned because the user owned nothing dangerous.
check("photosensitiser and no SPF is high",
      gaps_for(CLEANSER, RETINOL, MOISTURISER).get("no_sun_protection"), "high")
check("photosensitiser with SPF is a reminder, not a gap",
      gaps_for(CLEANSER, RETINOL, MOISTURISER, SPF).get("spf_is_load_bearing"),
      "medium")
gentle = gaps_for(CLEANSER, MOISTURISER)
check("nothing photosensitising and no SPF still says so",
      gentle.get("no_spf"), "medium")
check_true("and it is the only gap on that shelf", set(gentle) == {"no_spf"},
           str(sorted(gentle)))
# The two sunscreen gaps are alternatives, never both.
for shelf in ([NIACINAMIDE], [RETINOL], [CLEANSER, MOISTURISER], [SPF]):
    kinds = set(gaps_for(*shelf))
    check_true("never two sunscreen gaps at once",
               len(kinds & {"no_sun_protection", "no_spf", "spf_is_load_bearing"}) <= 1,
               f"{[s[0] for s in shelf]} -> {sorted(kinds)}")


# --- the mirror: several products doing one job ---------------------------
# Four CeraVe cleansers from four pasted links produced nothing at all,
# because the redundancy rules in interactions.yaml are ingredient pairs
# (two retinoids, two AHAs) and have no opinion about four of one form.
WASH = ("CeraVe Foaming Cleanser", ["Ceramide NP"])
BALM = ("Cleansing Balm", ["Ceramide NP"])
GEL = ("Gel Wash", ["Ceramide NP"])
CREAM_WASH = ("Cream Wash", ["Ceramide NP"])

four = gaps_for(WASH, BALM, GEL, CREAM_WASH)
check("four of one form is reported", "several_cleanser" in four, True)
check("as a money note, not a safety one", four.get("several_cleanser"), "low")

# Two is an ordinary shelf. Flagging it would be the invented-need
# failure pointing the other way.
check("two of one form is not reported",
      "several_cleanser" in gaps_for(WASH, BALM, MOISTURISER, SPF), False)
check("three is where it starts",
      "several_cleanser" in gaps_for(WASH, BALM, GEL, MOISTURISER, SPF), True)

# It names them, so the user can see which four it means.
audit_four = R.audit([InputProduct(name=n, listed_ingredients=list(i))
                      for n, i in (WASH, BALM, GEL, CREAM_WASH)], concerns=[])
dup = next(g for g in audit_four.gaps if g.kind == "several_cleanser")
check("and names every one of them", sorted(dup.because),
      sorted([WASH[0], BALM[0], GEL[0], CREAM_WASH[0]]))


# --- the table it is driven by -------------------------------------------
# ESSENTIAL_STEPS names forms by id. A typo would silently stop flagging
# that step, and no other test would notice.
for form_id, severity, headline, why in ESSENTIAL_STEPS:
    check_true(f"{form_id!r} is a real form id", form_id in R.forms, form_id)
    check_true(f"{form_id} severity is valid",
               severity in ("critical", "high", "medium", "low"), severity)
    check_true(f"{form_id} headline is a sentence", headline.endswith("."), headline)
    check_true(f"{form_id} says why, separately", len(why) > 60)
check_true("only steps the AAD order names are treated as essential",
           {f for f, *_ in ESSENTIAL_STEPS} == {"cleanser", "moisturiser"},
           str([f for f, *_ in ESSENTIAL_STEPS]))
check_true("and those forms are the ones marked verified",
           all(R.forms[f]["review"] == "verified" for f, *_ in ESSENTIAL_STEPS))


# --- it reaches the page --------------------------------------------------
audit = R.audit([InputProduct(name=n, listed_ingredients=list(i))
                 for n, i in (NIACINAMIDE, RETINOL)], concerns=[])
page = render(audit, AuditNarrative(summary="x", explanations=[], steps=[]))
text = re.sub("<[^>]+>", " ", page)
check_true("the page says there is nothing to wash with",
           "nothing here to wash your face with" in text)
check_true("the page says there is no moisturiser",
           "no moisturiser on this shelf" in text)
check_true("and still says there is no sunscreen",
           "no sunscreen on this shelf" in text)

clean_page = render(
    R.audit([InputProduct(name=n, listed_ingredients=list(i))
             for n, i in (CLEANSER, NIACINAMIDE, MOISTURISER, SPF)], concerns=[]),
    AuditNarrative(summary="x", explanations=[], steps=[]),
)
clean_text = re.sub("<[^>]+>", " ", clean_page)
check_true("a complete shelf is told none of this",
           "nothing here to wash your face with" not in clean_text)


if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)

print(f"ok  {checks} checks passed")
print("    a shelf missing a cleanser, a moisturiser or sunscreen is told so;")
print("    a complete one is told nothing, and no optional step is ever")
print("    reported as missing")

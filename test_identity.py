"""The product on the page has to be the product in the bathroom.

A second tester asked two questions that are really one question:

    "I never provided a goodal calming moisture, so where is that
    coming from"
    "the centella cleansing oil is from Skin1004, so why are you
    saying it is from manyo"

find_ingredients was handed a product name, searched, and attached
whatever came back. A half-legible bottle reading "centella cleansing
oil" returns the most famous centella cleansing oil there is — and that
product's ingredient list then becomes the basis of every finding, the
routine order, the interaction matrix and the money. The user's actual
bottle is never mentioned again.

This is the worst failure mode the app has. Everything else it gets
wrong is wrong about a product you own; this is right about a product
you do not. The catalogue matcher has refused cross-brand matches since
the beginning — the web lookup, far less constrained, had nothing.

The rule now is that it fails closed: a product that cannot be confirmed
is reported as unidentified rather than given someone else's formula.
Losing a product costs one row of the audit. Substituting one corrupts
all of it, silently.

No API key needed — the identity check is deterministic and tested here
directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from lookup import _brand_conflict, source_name  # noqa: E402
from models import InputProduct  # noqa: E402
from rules import Rules  # noqa: E402

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


# --- the two the tester hit -------------------------------------------
check("a Skin1004 oil is not a Manyo oil",
      _brand_conflict("SKIN1004 Centella Light Cleansing Oil",
                      "Manyo", "Herb Green Cleansing Oil"), True)
check("even when the bottle gave no brand",
      _brand_conflict("Centella Cleansing Oil",
                      "Manyo", "Herb Green Cleansing Oil"), True)

# The first version compared the first *two* words and let this through,
# because "cleansing" appears in both names. Generic words are most of a
# skincare name, so only the first meaningful word is load-bearing.
check("a shared generic word does not rescue the match",
      _brand_conflict("Hydrating Facial Cleanser",
                      "Manyo", "Herb Green Cleansing Oil"), True)


# --- and the ones that must still work --------------------------------
# If this check fires on honest matches, every lookup fails and the
# feature is gone. These are the shapes a real match takes.
for asked, brand, name in [
    ("CeraVe Hydrating Facial Cleanser", "CeraVe", "Hydrating Facial Cleanser"),
    ("The Ordinary Niacinamide 10%", "The Ordinary", "Niacinamide 10% + Zinc 1%"),
    ("La Mer Creme de la Mer", "La Mer", "Creme de la Mer"),
    ("Kiehls Retinol Serum", "Kiehl's", "Retinol Skin-Renewing Daily Serum"),
    # Brand written differently from how the retailer writes it.
    ("skin1004 centella light cleansing oil", "SKIN1004",
     "Centella Light Cleansing Oil"),
    # Name only, and the found product genuinely is that product.
    ("Niacinamide 10% + Zinc 1%", "The Ordinary", "Niacinamide 10% + Zinc 1%"),
]:
    check(f"{asked[:34]!r} matches itself",
          _brand_conflict(asked, brand, name), False)

# Nothing to compare: not a conflict, because same_product carries that
# case and a false alarm here costs a real lookup.
check("an empty question is not a conflict", _brand_conflict("", "X", "Y"), False)
check("an empty answer is not a conflict",
      _brand_conflict("CeraVe Cleanser", "", ""), False)


# --- a duration cites something a reader can check --------------------
check("a source is shown as its domain",
      source_name("https://aztecsecret.com/product/aztec-bucket/"),
      "aztecsecret.com")
check("www is dropped", source_name("https://www.cerave.com/x"), "cerave.com")
check("and nothing is invented from nothing", source_name(""), "")


# --- an eye cream says so on the box ----------------------------------
# The same tester: "why are you saying that the kiehl's retinol is an eye
# cream when the packaging does not say that. because of this error, you
# did not suggest an eye cream to me which you should have."
#
# Two wrong answers from one misread word, and the second one invisible:
# the shelf appeared to have an eye product, so the suggestion to get one
# was withheld. The engine now refuses `eye` from the reader unless the
# name mentions the eye, the same way a label listing UV filters forces
# `spf` whatever the reader said.
def form_of(name: str, told: str | None) -> str:
    return R.resolve(InputProduct(name=name, listed_ingredients=["Water"],
                                  form=told)).form


check("a retinol serum called an eye cream is not one",
      form_of("Kiehl's Retinol Skin-Renewing Daily Micro-Dose Serum", "eye"),
      "serum")
check("nor is a niacinamide serum", form_of("The Ordinary Niacinamide", "eye"),
      "serum")

# But a real eye product must survive. The first attempt reused
# FORM_KEYWORDS["eye"], which lists whole phrases like "eye cream", and
# threw away both of these — refusing a real one is worse than the bug.
for name in ("Kiehls Youth Dose Eye Treatment", "CeraVe Eye Repair Cream",
             "Some Eye Cream", "Contour des Yeux", "아이크림"):
    check(f"{name[:30]!r} stays an eye product", form_of(name, "eye"), "eye")

# And the knock-on the tester actually noticed: with the retinol no
# longer miscounted as an eye product, the eye cream is offered again.
shelf = [
    InputProduct(name="CeraVe Hydrating Facial Cleanser",
                 listed_ingredients=["Ceramide NP"]),
    InputProduct(name="Kiehl's Retinol Skin-Renewing Daily Micro-Dose Serum",
                 listed_ingredients=["Retinol"], form="eye"),
    InputProduct(name="CeraVe Moisturising Lotion", listed_ingredients=["Glycerin"]),
    InputProduct(name="Daily SPF 50", listed_ingredients=["Avobenzone"]),
]
audit = R.audit(shelf, concerns=[])
optional = [g for g in audit.gaps if g.kind == "optional_steps"]
check_true("the eye cream is suggested again",
           bool(optional) and "Eye cream" in optional[0].because,
           str([g.because for g in optional]))
check_true("and the retinol is in the routine as a treatment or serum",
           any("Kiehl" in s.product_name and s.form_id in ("serum", "treatment")
               for s in audit.routine.am + audit.routine.pm),
           str([(s.product_name[:20], s.form_id)
                for s in audit.routine.am + audit.routine.pm]))


# --- size reaches the product -----------------------------------------
# A 7 ml La Mer sample was priced as a full jar: off by a factor of
# twenty, and the money section is built from that number.
sample = InputProduct(name="La Mer Creme de la Mer", listed_ingredients=["Glycerin"],
                      size="7 ml")
check("size survives onto the product", sample.size, "7 ml")
resolved = R.resolve(sample)
check_true("and the product still resolves normally", resolved.form is not None)
check("a mismatch field exists to be set", sample.price_size_mismatch, "")


if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)

print(f"ok  {checks} checks passed")
print("    a lookup that found a different product reports nothing rather")
print("    than substituting it, an eye cream has to say so on the box, and")
print("    the size in the photograph reaches the price")

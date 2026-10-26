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
from rules import Rules, same_size, size_measures  # noqa: E402

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


# --- two sizes are the same size --------------------------------------
# A tester stated their product and its quantity and got no price. The
# lookup had in fact found the right one — $18 for the 4 fl oz, from the
# brand's own page — and returned the size as "4 fl oz / 120 mL", which
# is how the bottle is labelled. Comparing that to the user's "4 fl oz"
# as text called it a mismatch, and a correct price was dropped out of
# the money section as though it belonged to a different bottle.
#
# The fix that caused it is worth recording too: an earlier round showed
# a full-jar price for a 7 ml sample, I made a size mismatch refuse the
# price outright, and that overcorrection is what produced "no price at
# all". A container is a set of measures, not a string.
for a, b, want in [
    ("4 fl oz / 120 mL", "4 fl oz", True),
    ("4 fl oz", "4 fl oz / 120 mL", True),
    ("7 ml", "7ml", True),
    ("1.7 fl oz", "1.7 oz", True),
    ("50g", "50 g", True),
    ("3.4 fl oz / 100 mL", "3.4 fl oz", True),
    # Genuinely different bottles still have to be caught — this is the
    # La Mer case the whole mechanism exists for.
    ("2 oz / 60 mL", "0.24 oz / 7 mL", False),
    ("7 ml", "60 ml", False),
    ("1 fl oz / 30 mL", "3.4 fl oz / 100 mL", False),
]:
    check(f"{a!r} vs {b!r}", same_size(a, b), want)

# Unparseable sizes fall back to text rather than silently mismatching.
check("an unparseable size still compares", same_size("travel size", "travel size"),
      True)
check("and two different ones do not", same_size("travel size", "full size"), False)
check("an empty size is not a mismatch against itself", same_size("", ""), True)

check("a dual-unit label yields both measures",
      size_measures("4 fl oz / 120 mL"), {(4.0, "oz"), (120.0, "ml")})


# --- size reaches the product -----------------------------------------
# A 7 ml La Mer sample was priced as a full jar: off by a factor of
# twenty, and the money section is built from that number.
sample = InputProduct(name="La Mer Creme de la Mer", listed_ingredients=["Glycerin"],
                      size="7 ml")
check("size survives onto the product", sample.size, "7 ml")
resolved = R.resolve(sample)
check_true("and the product still resolves normally", resolved.form is not None)
check("a mismatch field exists to be set", sample.price_size_mismatch, "")



# --- the totals rest only on prices the user confirmed ----------------
# Eight of twenty-eight tester findings were about money, and every one
# was a price the app had guessed: a full-size figure against a 7 ml
# sample, an Amazon listing it cannot read, an original where the page
# showed a sale, a retail estimate described as what they paid. None
# was about the feature existing.
#
# The inputs are structurally weak and will stay weak — Amazon serves
# this reader a stub, the seeded catalogue's median price error is 11%.
# So the totals stopped depending on them. A looked-up figure is still
# shown beside its product and labelled; it is never summed. This is
# the check that keeps it that way, because the tempting fix for an
# empty-looking money section is to start counting estimates again.
def _audit(*products):
    return R.audit(list(products), concerns=[])


guessed = _audit(
    InputProduct(name="A", listed_ingredients=["Retinol"],
                 price_usd=40.0, price_is_typical=True),
    InputProduct(name="B", listed_ingredients=["Tretinoin"],
                 price_usd=12.0, price_is_typical=True),
)
check("a shelf priced only by lookup totals nothing",
      guessed.waste.shelf_value_usd, 0.0)

confirmed = _audit(
    InputProduct(name="A", listed_ingredients=["Retinol"], price_usd=40.0),
    InputProduct(name="B", listed_ingredients=["Tretinoin"], price_usd=12.0),
)
check("prices the user gave are counted", confirmed.waste.shelf_value_usd, 52.0)
check_true("and so is the duplicate between them",
           confirmed.waste.redundant_value_usd > 0)

mixed = _audit(
    InputProduct(name="A", listed_ingredients=["Retinol"], price_usd=40.0),
    InputProduct(name="B", listed_ingredients=["Tretinoin"],
                 price_usd=12.0, price_is_typical=True),
)
check("only the confirmed half counts", mixed.waste.shelf_value_usd, 40.0)

# The looked-up figure still reaches the product, so the page can show
# it. Dropping it would lose the recognition value along with the risk.
check("the estimate is kept on the product",
      [p.product.price_usd for p in guessed.products], [40.0, 12.0])
check_true("and is still marked as an estimate",
           all(p.price_is_typical for p in guessed.products))

if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)

print(f"ok  {checks} checks passed")
print("    a lookup that found a different product reports nothing rather")
print("    than substituting it, an eye cream has to say so on the box, and")
print("    the size in the photograph reaches the price")

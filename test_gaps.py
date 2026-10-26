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


def _audit(*products):
    return R.audit(
        [InputProduct(name=n, listed_ingredients=list(i)) for n, i in products],
        concerns=[],
    )


def gaps_for(*products) -> dict[str, str]:
    """kind -> severity, for things actually missing.

    Suggestions are excluded deliberately. A missing cleanser and an
    absent eye cream are both "not on the shelf" and only one of them is
    a problem; lumping them together is exactly the failure these tests
    exist to prevent, so they are asserted separately.
    """
    return {g.kind: g.severity for g in _audit(*products).gaps if not g.suggestion}


def suggestions_for(*products) -> dict[str, str]:
    """kind -> severity, for things merely worth considering."""
    return {g.kind: g.severity for g in _audit(*products).gaps if g.suggestion}


BALM = ("Banila Co Clean It Zero Cleansing Balm", ["Water"])
OIL = ("DHC Deep Cleansing Oil", ["Olive Oil"])
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
# A complete routine now includes the first cleanse. Promoted from a
# suggestion on 26 Oct 2026: the app tells every user to wear sunscreen
# daily and sunscreen does not come off with water, so treating its
# removal as optional was the page disagreeing with itself.
full = gaps_for(OIL, CLEANSER, NIACINAMIDE, MOISTURISER, SPF)
check("a complete routine has no gaps", full, {})
check("and without an oil cleanse it is not complete",
      "no_oil_cleanser" in gaps_for(CLEANSER, NIACINAMIDE, MOISTURISER, SPF), True)


# --- one at a time -------------------------------------------------------
check("missing only a cleanser", set(gaps_for(OIL, MOISTURISER, SPF)),
      {"no_cleanser"})
check("missing only a moisturiser", set(gaps_for(OIL, CLEANSER, SPF)),
      {"no_moisturiser"})


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
gentle = gaps_for(OIL, CLEANSER, MOISTURISER)
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
FOAM = ("Gentle Face Wash", ["Ceramide NP"])
GEL = ("Gel Wash", ["Ceramide NP"])
CREAM_WASH = ("Cream Wash", ["Ceramide NP"])

four = gaps_for(WASH, FOAM, GEL, CREAM_WASH)
check("four of one form is reported", "several_cleanser" in four, True)
check("as a money note, not a safety one", four.get("several_cleanser"), "low")

# Two is an ordinary shelf. Flagging it would be the invented-need
# failure pointing the other way.
check("two of one form is not reported",
      "several_cleanser" in gaps_for(WASH, FOAM, MOISTURISER, SPF), False)
check("three is where it starts",
      "several_cleanser" in gaps_for(WASH, FOAM, GEL, MOISTURISER, SPF), True)

# It names them, so the user can see which four it means.
audit_four = R.audit([InputProduct(name=n, listed_ingredients=list(i))
                      for n, i in (WASH, FOAM, GEL, CREAM_WASH)], concerns=[])
dup = next(g for g in audit_four.gaps if g.kind == "several_cleanser")
check("and names every one of them", sorted(dup.because),
      sorted([WASH[0], FOAM[0], GEL[0], CREAM_WASH[0]]))


# --- a cleansing oil is not a cleanser ------------------------------------
# A tester's shelf had a cleansing balm and was treated as having a
# cleanser — "cleansing" matched the cleanser keywords before anything
# could notice the "balm". It was also placed in the morning routine.
# An oil cleanser is the first half of a double cleanse: evening only,
# and the water-based wash still has to follow it.
for name, ings in (BALM, OIL):
    got = R.resolve(InputProduct(name=name, listed_ingredients=list(ings)))
    check(f"{name.split()[0]} is an oil cleanser", got.form, "oil_cleanser")

# The keyword list is not enough on its own: the Shelf Reader sets the
# form itself from packaging, and it called the tester's balm a
# "cleanser" — a category that cannot express the difference. The engine
# overrides it on these specific phrases, the same way a label listing
# UV filters forces `spf` whatever the reader said.
for name, ings in (BALM, OIL):
    told = R.resolve(InputProduct(name=name, listed_ingredients=list(ings),
                                  form="cleanser"))
    check(f"{name.split()[0]}: the engine overrides the reader", told.form,
          "oil_cleanser")
# And it does not reach past them: an ordinary cleanser stays one.
plain_told = R.resolve(InputProduct(name="CeraVe Hydrating Facial Cleanser",
                                    listed_ingredients=["Ceramide NP"],
                                    form="cleanser"))
check("an ordinary cleanser is left alone", plain_told.form, "cleanser")

check_true("an oil cleanser is evening-only",
           R.forms["oil_cleanser"]["times"] == "pm",
           R.forms["oil_cleanser"]["times"])
check_true("and goes before the water-based cleanser",
           R.forms["oil_cleanser"]["rank"] < R.forms["cleanser"]["rank"])

balm_only = gaps_for(BALM)
check("a balm alone still leaves a cleanser missing",
      "no_cleanser" in balm_only, True)
balm_audit = R.audit([InputProduct(name=BALM[0], listed_ingredients=["Water"])],
                     concerns=[])
msg = next(g for g in balm_audit.gaps if g.kind == "no_cleanser")
check_true("and says why, rather than claiming there is nothing to wash with",
           "half of a cleanse" in msg.headline, msg.headline)

# With both, nothing to report — that is a complete cleansing routine.
check("a balm plus a wash is not a gap",
      "no_cleanser" in gaps_for(BALM, WASH, MOISTURISER, SPF), False)
# And the balm is never placed in the morning.
both = R.audit([InputProduct(name=n, listed_ingredients=list(i))
                for n, i in (BALM, WASH, MOISTURISER, SPF)], concerns=[])
check("the balm is not in the morning routine",
      [s.product_name for s in both.routine.am if "Banila" in s.product_name], [])
pm_order = [s.product_name for s in both.routine.pm]
check_true("and comes first in the evening",
           pm_order and "Banila" in pm_order[0], str(pm_order))


# --- a mask is worn, not rubbed in, and for how long is not ours to say ---
# Two bugs in sequence. First the routine said to use a face mask for 30
# seconds, because StepApplication.seconds is capped at 120 and means
# time spent *applying* — a fifteen-minute mask was not expressible. The
# fix for that was a dwell of 600 seconds, which a tester then objected
# to for the right reason: nobody had looked it up. Clay sets in ten
# minutes, a sheet mask comes off at twenty, an overnight mask stays on
# all night. So the time is looked up per product, and when it cannot be
# found the step says so instead of counting down a number this app
# chose.
from render import beats_for  # noqa: E402

mask_audit = R.audit([InputProduct(name="Aztec Clay Mask", listed_ingredients=["Kaolin"]),
                      InputProduct(name=WASH[0], listed_ingredients=["Ceramide NP"])],
                     concerns=[])
mask_step = next(s for s in mask_audit.routine.pm if "Mask" in s.product_name)
cleanse_step = next(s for s in mask_audit.routine.pm if "Mask" not in s.product_name)

# Nothing looked up: the mask is marked as worn-but-unknown, and carries
# no invented duration.
check("an unlooked-up mask asserts no duration", mask_step.dwell_seconds, 0)
check("but is still marked as worn", mask_step.dwell_unknown, True)
check_true("and says the packet decides", "packet" in mask_step.dwell_note,
           mask_step.dwell_note)
check("a cleanser is not worn at all", cleanse_step.dwell_unknown, False)
check("and has no dwell", cleanse_step.dwell_seconds, 0)

unknown = beats_for(None, mask_step.dwell_seconds, mask_step.dwell_note,
                    mask_step.dwell_unknown, mask_step.dwell_source)
held = next((b for b in unknown if b["kind"] == "leave it on"), None)
check_true("the wearing is still a beat of its own", held is not None, str(unknown))
check("carrying no number", held["secs"], 0)
check("flagged so the player waits instead of counting", held.get("untimed"), True)
check_true("and telling the user where to look",
           "packet" in held["text"], held["text"])

# A looked-up time is used, and says where it came from.
known_audit = R.audit([InputProduct(name="Sheet Mask", listed_ingredients=["Glycerin"],
                                    form="mask", dwell_seconds=1200,
                                    dwell_source="the brand's page")], concerns=[])
known = next(s for s in known_audit.routine.pm if "Mask" in s.product_name)
check("a looked-up time is carried through", known.dwell_seconds, 1200)
check("and is no longer unknown", known.dwell_unknown, False)
timed = next(b for b in beats_for(None, known.dwell_seconds, known.dwell_note,
                                  known.dwell_unknown, known.dwell_source)
             if b["kind"] == "leave it on")
check("the beat carries the real duration", timed["secs"], 1200)
check("and is timed", timed.get("untimed"), None)
check_true("and cites its source", "brand" in timed["text"], timed["text"])

# The form table must not carry a duration of its own: that is the bug.
check_true("no form asserts a dwell time",
           all("dwell_seconds" not in f for f in R.forms.values()),
           str([k for k, f in R.forms.items() if "dwell_seconds" in f]))
check_true("the mask form only says that it is worn",
           bool(R.forms["mask"]["dwell_required"]))


# --- three tiers, and the difference between them -------------------------
# My first version flagged only cleanser, moisturiser and sunscreen and
# argued anything else would invent a purchase. A tester who does this
# daily disagreed usefully: a serum belongs in both routines, a
# cleansing oil belongs in the evening, and a toner and eye cream should
# be *offered*. That word is the resolution — the risk was never naming
# them, it was naming them as failures.
bare = suggestions_for(NIACINAMIDE)
check_true("a serum-less shelf is told to consider one",
           "consider_serum" in suggestions_for(CLEANSER, MOISTURISER, SPF),
           str(suggestions_for(CLEANSER, MOISTURISER, SPF)))
check("a shelf with a serum is not", "consider_serum" in bare, False)
# No longer a suggestion — it is required, and tested as one above.
check("an oil cleanser is not offered as optional",
      "consider_oil_cleanser" in bare, False)
check("it is a gap instead", "no_oil_cleanser" in gaps_for(NIACINAMIDE), True)
check("and not once you have one",
      "no_oil_cleanser" in gaps_for(OIL, NIACINAMIDE), False)

# Suggestions are never urgent, and never claim something is wrong.
for kind, sev in suggestions_for(NIACINAMIDE).items():
    check_true(f"{kind} is low severity", sev == "low", f"{kind}={sev}")
sug_objs = [g for g in _audit(NIACINAMIDE).gaps if g.suggestion]
check_true("and every one is flagged as a suggestion", bool(sug_objs))
check_true("while the essentials are not",
           all(not g.suggestion for g in _audit(NIACINAMIDE).gaps
               if g.kind.startswith("no_")))

# Toner and eye cream: one entry, so optional extras cannot read as a
# list of failures, and gone as soon as you own them.
opt = [g for g in _audit(NIACINAMIDE).gaps if g.kind == "optional_steps"]
check_true("toner and eye cream arrive as a single optional entry",
           len(opt) == 1, str(len(opt)))
check("naming both", sorted(opt[0].because), ["Eye cream", "Toner"])
check_true("and saying when each belongs",
           opt[0].message.count("It belongs in") == 2, opt[0].message)
owned = _audit(NIACINAMIDE, ("Hydrating Toner", ["Glycerin"]),
               ("Eye Cream", ["Caffeine"]))
opt2 = [g for g in owned.gaps if g.kind == "optional_steps"]
check("owning both removes the entry", opt2, [])
# Owning one leaves the other, named alone.
one = _audit(NIACINAMIDE, ("Hydrating Toner", ["Glycerin"]))
opt3 = [g for g in one.gaps if g.kind == "optional_steps"]
check_true("owning one leaves just the other",
           len(opt3) == 1 and opt3[0].because == ["Eye cream"],
           str([g.because for g in opt3]))

# Never a toner "gap", in any arrangement. This is the line the tester's
# feedback moved, and it should not move further without someone saying so.
for shelf in ([NIACINAMIDE], [CLEANSER, MOISTURISER, SPF], [RETINOL], [OIL]):
    bad = {k for k in gaps_for(*shelf)
           if k.removeprefix("no_") in {"toner", "eye", "serum"}}
    check(f"nothing optional is ever a gap ({shelf[0][0][:18]})", bad, set())


# --- the table it is driven by -------------------------------------------
# ESSENTIAL_STEPS names forms by id. A typo would silently stop flagging
# that step, and no other test would notice.
for form_id, severity, headline, why in ESSENTIAL_STEPS:
    check_true(f"{form_id!r} is a real form id", form_id in R.forms, form_id)
    check_true(f"{form_id} severity is valid",
               severity in ("critical", "high", "medium", "low"), severity)
    check_true(f"{form_id} headline is a sentence", headline.endswith("."), headline)
    check_true(f"{form_id} says why, separately", len(why) > 60)
check_true("the essentials are the AAD steps plus the first cleanse",
           {f for f, *_ in ESSENTIAL_STEPS} == {"oil_cleanser", "cleanser",
                                                "moisturiser"},
           str([f for f, *_ in ESSENTIAL_STEPS]))
# oil_cleanser is `reasoned`, not `verified` — the AAD order does not
# cover double cleansing. It is required on this app's own internal
# logic rather than on a published source, and that distinction is
# recorded rather than smoothed over.
check_true("the AAD-sourced ones are still marked verified",
           all(R.forms[f]["review"] == "verified"
               for f, *_ in ESSENTIAL_STEPS if f != "oil_cleanser"))
check("and the first cleanse is honest about resting on reasoning",
      R.forms["oil_cleanser"]["review"], "reasoned")


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

"""Telling the app it is wrong has to change something.

Tester two, after two rounds of fixes:

    "I tried to tell the app what is wrong and should be replaced in the
    what is missing section but it just added more items to the list even
    though I was clarifying what wrong actions it did"

Every input the page offered was additive. Photographs add products, the
text box adds products, and whatever was already identified is posted
back in a hidden field and merged in again on every round. There was no
way to remove anything. So a user looking at a product they did not own,
typing "that enzyme powder wash isn't mine", got a second invented
product named after their complaint — the app reading a correction as
more input is almost funny, and it is the reason they had to report the
same bug twice.

This matters beyond the one bug. A vision model can be made to invent
fewer products and cannot be made to invent none, so the person holding
the bottles has to be able to overrule it. That makes the correction
channel a safety mechanism rather than a convenience, and it is tested
as one.

Runs against the real endpoint with no API key: every path here is
reached before any agent call, because a submission that carries only
previously-identified products never re-reads anything.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402
from safety import unsupported_names  # noqa: E402
from models import ReadProduct, ShelfReading  # noqa: E402

client = TestClient(app)
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


SHELF = [
    {"name": "CeraVe Hydrating Facial Cleanser",
     "listed_ingredients": ["Ceramide NP", "Hyaluronic Acid"]},
    {"name": "Enzyme Powder Wash", "listed_ingredients": ["Papain"]},
    {"name": "CeraVe Moisturising Lotion", "listed_ingredients": ["Glycerin"]},
]


def post(**extra):
    data = {"carried": json.dumps(SHELF)}
    data.update(extra)
    return client.post("/audit", data=data)


def names_on(html: str) -> set[str]:
    """Every product in the audit, read from the correction table.

    Read from the routine's step names until two cleansers in the
    fixture started collapsing into a single "one of these, not both"
    step — correct behaviour that made a product vanish from the
    routine while remaining in the audit. The correction table is the
    canonical list of what the audit is about, which is what these
    checks actually mean.
    """
    m = re.search(r'<table class="prices">(.*?)</table>', html, re.S)
    if not m:
        return set()
    cells = re.findall(r"<tr><td>(.*?)</td>", m.group(1), re.S)
    return {re.sub("<[^>]+>", "", c).strip() for c in cells}


# --- the shelf as it stands -------------------------------------------
r = post()
check("the round trip works", r.status_code, 200)
base = names_on(r.text)
check_true("all three products are there", len(base) == 3, str(base))
check_true("including the invented one", any("Enzyme" in n for n in base))

# The page has to offer the way out, or the user types prose instead.
check_true("the page offers a way to drop a product",
           'name="pdrop"' in r.text)
check_true("and a way to correct the size", 'name="psize"' in r.text)
check_true("and says what Not mine does", "Not mine" in r.text)
check_true("and points corrections at the table rather than the text box",
           "adds a product rather than fixing one" in r.text)


# --- dropping one -----------------------------------------------------
r2 = post(pdrop="Enzyme Powder Wash")
after = names_on(r2.text)
check_true("the dropped product is gone",
           not any("Enzyme" in n for n in after), str(after))
check_true("and the others survive", len(after) == 2, str(after))


# --- and it stays gone ------------------------------------------------
# The failure this guards against: the user drops it, sends the same
# photograph again, and the reader invents it again. Being made to
# dismiss the same thing every round is barely better than not being
# able to dismiss it.
m = re.search(r'name="dropped" value="([^"]*)"', r2.text)
check_true("the refusal is carried in the page", m is not None)
carried_drop = (m.group(1) if m else "").replace("&quot;", '"').replace("&#x27;", "'")
check_true("and names what was refused", "enzyme" in carried_drop.lower(),
           carried_drop[:80])

r3 = client.post("/audit", data={"carried": json.dumps(SHELF),
                                 "dropped": carried_drop})
again = names_on(r3.text)
check_true("a later round does not bring it back",
           not any("Enzyme" in n for n in again), str(again))
check_true("and still has the real products", len(again) == 2, str(again))

# Dropping everything is a user error, not a crash.
r4 = post(pdrop=[p["name"] for p in SHELF])
check_true("dropping everything does not 500", r4.status_code != 500,
           f"status {r4.status_code}")


# --- a size typed by the user wins ------------------------------------
# They are holding the bottle; the reader is looking at a photograph of
# it. A 7 ml sample priced as a full jar is off by a factor of twenty,
# and every figure in the money section inherits it.
r5 = post(pname="CeraVe Moisturising Lotion", psize="7 ml")
check("a typed size is accepted", r5.status_code, 200)
check_true("and comes back in the box so it can be seen",
           'value="7 ml"' in r5.text, "size not echoed")


# --- the invented-product check itself --------------------------------
# Deterministic, and the thing that should have caught this without a
# tester having to report it twice.
reading = ShelfReading(products=[
    ReadProduct(name="Enzyme Powder Wash",
                label_text="CeraVe Hydrating Facial Cleanser 355ml ceramides"),
    ReadProduct(name="CeraVe Hydrating Facial Cleanser",
                label_text="CeraVe Hydrating Facial Cleanser 355ml ceramides"),
])
flagged = unsupported_names(reading)
check("a name absent from its own label is flagged", flagged,
      ["Enzyme Powder Wash"])

# It must not accuse a product it cannot check, or every name-only
# photograph turns into a warning.
check("no transcription means no accusation",
      unsupported_names(ShelfReading(products=[
          ReadProduct(name="Unknown Jar", label_text="")])), [])


# --- asking for an optional step, and getting it ----------------------
# "for optional items such as eye cream, you should give me an option
# for me to tell you if I want to incorporate it. If I tell you I want
# to incorporate it, then you should modify the routine you suggest."
#
# Driven by the tiers table rather than named forms, and tested that way
# on purpose: the follow-up to that request was "toners are also
# optional so the changes you are making to eye cream should also be
# made for toners". Every form in the optional or recommended tier gets
# the same treatment, and a loop is the only way to keep that true when
# a tier gains a row.
from rules import OPTIONAL_STEPS, RECOMMENDED_STEPS, Rules  # noqa: E402

R = Rules()
BASIC = [
    {"name": "CeraVe Hydrating Facial Cleanser", "listed_ingredients": ["Ceramide NP"]},
    {"name": "CeraVe Moisturising Lotion", "listed_ingredients": ["Glycerin"]},
]
offerable = [f for f, *_ in RECOMMENDED_STEPS] + [f for f, _ in OPTIONAL_STEPS]
check_true("there are optional steps to offer", len(offerable) >= 2, str(offerable))

def routine_steps(html: str) -> list[str]:
    """The routine's step names, with the badge text stripped.

    Searching the whole page for the word "toner" does not work: it
    appears in the suggestion card's own prose and in the checkbox
    label, so a form is "present" before anyone has asked for it. Only
    the step names answer the question being asked here.
    """
    out = []
    for m in re.findall(r'<div class="name">(.*?)</div>', html, re.S):
        text = re.sub("<[^>]+>", " ", m)
        out.append(" ".join(text.split()).replace(" not on your shelf", "").lower())
    return out


base = client.post("/audit", data={"carried": json.dumps(BASIC)})
for form_id in offerable:
    label = R.forms[form_id]["name"].lower()

    # Offered, and not forced on anyone who did not ask.
    check_true(f"{form_id}: a box is offered",
               f'name="want" value="{form_id}"' in base.text)
    check_true(f"{form_id}: absent until asked for",
               not any(label in n for n in routine_steps(base.text)),
               str(routine_steps(base.text)))

    r = client.post("/audit", data={"carried": json.dumps(BASIC), "want": form_id})
    page = r.text.lower()
    check(f"{form_id}: the request is accepted", r.status_code, 200)
    check_true(f"{form_id}: it reaches the routine",
               any(label in n for n in routine_steps(r.text)),
               str(routine_steps(r.text)))
    check_true(f"{form_id}: marked as not owned",
               "not on your shelf" in page)
    check_true(f"{form_id}: the box stays ticked",
               f'value="{form_id}" checked' in r.text)

# Position matters: an eye cream belongs before the moisturiser, not
# appended to the end. The forms table already knows the order and the
# placeholder has to respect it.
r = client.post("/audit", data={"carried": json.dumps(BASIC), "want": ["toner", "eye"]})
seq = [n for n in routine_steps(r.text)
       if "toner" in n or "eye cream" in n or "moisturising" in n]
check_true("optional steps land in rank order, not at the end",
           seq[:3] == ["a toner", "an eye cream", "cerave moisturising lotion"],
           str(seq[:3]))

# And nothing invented: a form id that is not in the table is ignored
# rather than reaching build_routine.
junk = client.post("/audit", data={"carried": json.dumps(BASIC),
                                   "want": "'; DROP TABLE--"})
check("a junk form id is refused", junk.status_code, 200)
check_true("and does not reach the page", "DROP TABLE" not in junk.text)


# --- the safety gates survive a re-audit ------------------------------
# Tester three declared a pregnancy and a prescribed product, pressed
# "Audit again", and the app forgot both. Measured before the fix:
#
#     declared pregnant    clinician escalation on page: True
#     after Audit again    clinician escalation on page: False
#
# A pregnant user who corrects a price is silently un-declared and then
# advised on a retinoid. Every other field on that form was carried —
# products, prices, sizes, concerns, dismissals, opted-in steps — and
# the two that gate on safety were the ones missing, because they live
# on the landing page and the re-audit form grew out of the result page.
#
# This is the check that keeps them there.
GATED = [{"name": "The Ordinary Retinol 0.5%", "listed_ingredients": ["Retinol"]}]


def gates_on(html):
    return set(re.findall(r'name="conditions" value="([a-z_]+)" checked', html))


first = client.post("/audit", data={"carried": json.dumps(GATED),
                                    "conditions": ["pregnancy"]})
check_true("a declared pregnancy escalates", "Needs a clinician" in first.text)
check("and is carried back as ticked", gates_on(first.text), {"pregnancy"})

again = client.post("/audit", data={"carried": json.dumps(GATED),
                                    "conditions": sorted(gates_on(first.text))})
check_true("pressing Audit again keeps the escalation",
           "Needs a clinician" in again.text,
           "the gate was lost on the second submission")
check("and keeps the box ticked", gates_on(again.text), {"pregnancy"})

# It must be withdrawable too — a hidden field could not be unticked.
withdrawn = client.post("/audit", data={"carried": json.dumps(GATED)})
check_true("and unticking it withdraws the gate",
           "Needs a clinician" not in withdrawn.text)


# --- a prescription the table cannot recognise ------------------------
# "when she says something has been prescribed to her, shouldnt the app
# ask her what exactly was prescribed to her". It guessed, by matching
# ingredients the table marks prescription-only, and silently did
# nothing for a compounded cream or a prescription-strength version of
# something sold over the counter.
COMPOUND = [{"name": "Compounded Azelaic 15%", "listed_ingredients": ["Azelaic Acid"]}]
undeclared = client.post("/audit", data={"carried": json.dumps(COMPOUND),
                                         "conditions": ["prescription_product"]})
check_true("she is offered a way to name it",
           'name="pprescribed"' in undeclared.text)
check_true("and told to, when nothing matched",
           "prescribed to you" in undeclared.text)

named = client.post("/audit", data={"carried": json.dumps(COMPOUND),
                                    "conditions": ["prescription_product"],
                                    "pprescribed": "Compounded Azelaic 15%"})
check_true("naming it escalates whatever the table believes",
           "Needs a clinician" in named.text and "SKC-010" in named.text)
check("and the box stays ticked",
      re.findall(r'name="pprescribed" value="([^"]+)" checked', named.text),
      ["Compounded Azelaic 15%"])


if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)

print(f"ok  {checks} checks passed")
print("    a product can be removed, the removal survives the next round,")
print("    a typed size overrides the photograph, and a name that is not on")
print("    its own label is flagged before the user has to notice")

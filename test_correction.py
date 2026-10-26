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


if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)

print(f"ok  {checks} checks passed")
print("    a product can be removed, the removal survives the next round,")
print("    a typed size overrides the photograph, and a name that is not on")
print("    its own label is flagged before the user has to notice")

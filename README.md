# Skincare Auditor

Photograph your shelf. The auditor identifies each product, resolves it to its
active ingredients, checks every pair against an interaction table, and returns
a morning and evening routine in application order — with every claim traced to
a rule you can look up.

Most people own more skincare than they use well. The common failures are not
exotic: a benzoyl peroxide cleanser quietly degrading an expensive retinoid, two
products doing the same job, an acid used in the morning without sunscreen, a
second retinoid hidden in a moisturiser that was never marketed as one. None of
these are visible from the shelf, and all of them cost money already spent.

**The advice comes from a table, not from the model.** The agent extracts and
explains; `data/interactions.yaml` decides. Every finding cites a `rule_id`, so
any claim can be traced, argued with, or corrected — and the system refuses
rather than guesses when an ingredient is not in the table.

---

## Running it

Requires Python 3.11+.

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe build_db.py
.venv\Scripts\python.exe -m uvicorn app:app --port 8000
```

**macOS or Linux:**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python build_db.py
.venv/bin/python -m uvicorn app:app --port 8000
```

Every line uses the interpreter inside `.venv`. An earlier version of this
README created the virtual environment and then ran the last two steps with
plain `python`, which is the *system* interpreter and does not have the
dependencies — following it exactly failed at the last line with
`No module named uvicorn`. Found by cloning into an empty folder and doing
what it said.

Then open **http://localhost:8000**. Upload photographs of your products, or
type them in, and the audit comes back as a page.

`build_db.py` compiles the YAML rule files into `data/skincare.db` and
validates every rule selector against the ingredient list first. It should
print a row count and exit cleanly.

### API key

Copy `.env.example` to `.env` and add your `PORTKEY_API_KEY`. The loader checks
the repo folder, then one folder above, then two — so a key placed one level up,
as the course expects, is found automatically.

```
PORTKEY_API_KEY=...
```

The model is `gpt-6-luna` throughout.

---

## What you can give it

| | |
|---|---|
| **Photographs** | of the shelf, or of individual back labels. Up to 8. |
| **Typed names** | one per line, ingredients underneath if you have them |
| **Links** | paste a product page and its ingredient list is looked up — the most precise input, because there is no guessing at which product you meant. Big retailers (Amazon among them) do not publish a list this reader can reach, so the list usually comes from the brand's own site or another retailer for the same product. The page says so by name when it does, because a list for a different size or an older formula is the one thing that would quietly change every finding |
| **A price** | yours overrides the catalogue's estimate, and the money figures become yours |
| **A concern** | what you are trying to treat, which drives what the shelf is missing |
| **A photo of your skin** | entirely optional. It is used to *ask* you what you are seeing, never to diagnose — the observer's output type cannot express a condition name, and its prose is scrubbed and escalated if one appears |

The result page carries the findings, a morning and evening routine in
order, the money, an interaction matrix, a printed card for the mirror, an
on-screen walkthrough for standing at a sink, and a drawn animation with a
tab per half of the day, each downloadable as its own GIF.

It also answers the question a routine built from your shelf cannot ask:
**what is not on it.** Every other part of the page compares products you
own against each other, so a shelf of four serums and no cleanser used to
get an ordered routine and no comment.

Three tiers, kept visibly apart, because "you have no cleanser" and "you
have no eye cream" are not the same claim and rendering them alike turns
a tool that tells you what you need into one that tells you what to buy:

| | |
|---|---|
| **Missing** | cleanser, moisturiser, sunscreen — the steps the AAD order names, and the only `verified` rows in `product_forms.yaml` |
| **Worth considering** | a serum, and an oil cleanser for the evening — a routine without them is still a routine |
| **Optional** | a toner and an eye cream, in one line, listed so you know they exist |

Several products doing one job is reported too, from three upwards, as a
money note rather than a mistake. Every one of these says **when** the
step belongs — morning, evening or both — read from the same `times`
column the routine builder uses, so a gap cannot name a different time of
day from the routine beside it.

**You can tell it that it is wrong.** Every input on the result page used
to be additive — photographs add products, the text box adds products,
and whatever was already identified is posted back and merged in again
each round. There was no way to remove anything, so a tester looking at a
product they did not own typed "that isn't mine" into the only box
available and got a second invented product named after their complaint.

The table now has **Not mine**, which removes a product and keeps it
removed: the refusal is carried forward, so re-sending the same
photograph does not bring it back. A vision model can be made to invent
fewer products and cannot be made to invent none, which makes this a
safety mechanism rather than a convenience — the person holding the
bottles is the only one who can settle it. `unsupported_names()` tries to
catch it first, by checking each product's name against the text the
reader transcribed from that product's own label: a name that appears
nowhere in its own label was not read off anything.

**A lookup that cannot confirm the product reports nothing.** Handed a
half-legible "centella cleansing oil", the web lookup used to return the
most famous one there is and attach *its* ingredient list — which then
became the basis of every finding, the routine order and the money. A
second tester asked where a Goodal moisturiser they had never owned came
from, and why their SKIN1004 cleansing oil was being credited to Manyo.
Both were the same bug. The lookup now fails closed: a product whose
identity cannot be confirmed is reported as unidentified and left out of
the checks, because losing one product costs a row while substituting one
corrupts everything computed from it. The catalogue matcher has refused
cross-brand matches from the start; the web lookup, far less constrained,
had no equivalent.

**Sizes are read off the container.** A 7 ml sample and a full jar are the
same photograph at different scales, and the difference is a factor of
twenty in a money section built entirely from price. The reader records
the printed size, the lookup is asked to price *that* size, and a price
found for a different one is labelled rather than quietly used.

**How long a mask stays on is looked up, not assumed.** Clay sets in ten
minutes, a sheet mask comes off at twenty, an overnight mask stays on all
night, so there is no number for "a mask" — the time is found for that
product and the step cites where it came from. When nothing can be found,
the step says *"leave it on for the time on the packet"* and the guided
player waits for you instead of counting down a figure this app chose.
`StepApplication.seconds` is capped at 120 and means time spent
*applying*, so before this a fifteen-minute mask was not expressible at
all and came out as a 30-second step.

A cleansing oil or balm is its own form, evening-only, ranked before the
cleanser rather than instead of it: it is the first half of a double
cleanse, and a shelf holding one is still told it needs a face wash. The
engine overrides the Shelf Reader on this, the same way a label listing UV
filters forces `spf` — "cleanser" is a category that cannot express the
difference, and the difference decides both the time of day and whether a
second product is needed.

## The rules as an MCP server

The ingredient-interaction engine is also exposed over MCP, so any client can
query it without this app running:

```bash
python mcp_server/server.py          # stdio
python mcp_server/server.py --demo   # see what each tool returns
```

Seven tools — `resolve_ingredients`, `lookup_ingredient`, `check_interactions`,
`check_contraindications`, `find_product`, `layering_order`, `coverage`. They
take ingredient ids, display names, INCI terms or local-language names
interchangeably. Connection config is `.mcp.json`; full documentation is in
[mcp_server/README.md](mcp_server/README.md).

**The web app does not route through it by default.** A spawned subprocess
between an upload and an answer is a failure mode bought for nothing when the
engine is already in the same process. To have the two agents use it:

```bash
USE_MCP=1 python -m uvicorn app:app --port 8000
```

Either way the server exists, and if it fails to start the agents carry on
without it — the engine still produces the verdict.

## Without the web app

Everything runs from the command line too, which is also how the test and
experiment scripts drive it:

```bash
python audit_cli.py --shelf data/sample_shelf.json --explain --html output/audit.html
```

| | |
|---|---|
| `python test_robustness.py` | malformed and hostile input, no API key needed |
| `python test_i18n.py` | Korean, French, Japanese, Chinese, no API key needed |
| `python test_storyboard.py` | the routine animation and its GIF export |
| `python test_urls.py` | pasted product pages, and what a hostile one cannot reach |
| `python test_mcp.py` | the MCP server agrees with the app |
| `python test_thesis.py` | a narrative contradicting every finding changes nothing |
| `python test_failure.py` | each agent failing in turn, no stack traces, no leaks |
| `python test_validator.py` | invented rules and ghost products are dropped |
| `python test_provenance.py` | a product found only via an unchecked translation says so |
| `python test_gaps.py` | what the shelf is missing, and what is not worth flagging |
| `python test_identity.py` | the product on the page is the product in the bathroom |
| `python test_correction.py` | the user can overrule the app, and it stays overruled |
| `python make_attacks.py` | regenerate the adversarial label images |
| `python redteam.py --mode naive` | run the attacks with no defences |
| `python redteam.py --mode defended` | run them again with defences on |
| `python redteam.py --compare` | write `output/defense_results.md` |
| `python redteam_urls.py` | five adversarial product pages (needs a key) |
| `python redteam_skin.py` | five adversarial images at the skin observer (needs a key) |
| `python tools/inci_coverage.py` | label terms the resolver does not recognise |
| `python tools/consistency.py` | dead rules, unreachable ingredients, contradictions |
| `python tools/four_surfaces.py` | do the four renderings agree on durations |
| `python tools/tokenomics.py` | cost and cache figures, derived from the log |
| `python preflight.py` | check the key, token accounting and caching |

## Non-English products

Works, and mostly for free. INCI nomenclature is international, so a Korean,
French or Brazilian label that prints "Niacinamide" matches with no translation
at all — the matcher never looks at the product name.

Three things make the rest work:

- **INCI does most of the work.** EU, Korean and Japanese regulation requires
  INCI on the ingredient list, so a Korean or French product prints
  "Niacinamide" exactly as an American one does and resolves through terms a
  human has checked.
- **Form keywords cover nine languages**, so 선크림 is recognised as a sunscreen
  and 化粧水 as a toner rather than defaulting to "serum". These are also
  unverified translations and are kept deliberately: getting a form wrong moves
  a product within the routine, where you can see it, and cannot invent an
  ingredient you do not own. One table can produce a false warning; the other
  cannot.
- **Local-language ingredient names were withdrawn** — see *Status of the rule
  table* below. A label printing only a local name now resolves to nothing,
  which is the safe direction.
- The Shelf Reader records the printed term alongside its INCI equivalent, so a
  match stays auditable against what was actually on the label.

Try it:

```bash
python audit_cli.py --shelf data/sample_shelf_intl.json
```

And the regression check, no API key needed:

```bash
python test_i18n.py
```

**The translations are the lowest-confidence data in the project** and have not
been checked by speakers of each language. A missing alias is safe — the product
resolves to fewer actives. A wrong one is not: it invents a conflict, or hides a
real one. See the warning at the top of that file.

## Layout

```
data/
  ingredients.yaml      active ingredients, pH, photosensitivity, pregnancy status
  interactions.yaml     interaction rules and contraindication gates
  product_forms.yaml    canonical application order
  skincare.db           generated — rebuild with build_db.py
src/
  env_file.py           .env discovery
  lookup.py             web and product-page ingredient lookup
  storyboard.py         routine -> scenes, for the animation
  filmstrip.py          scenes -> an animated GIF
build_db.py             YAML -> SQLite, with validation
output/                 run artifacts: audit trail, token usage, results
```

The YAML files are the source of truth and live in git so the rules are
reviewable in a diff. The database is derived and is not committed.

---

## Status of the rule table

Every row has been reviewed, and the build prints where each one stands on
every run:

```
  provenance
      33  verified   checked against a published source
      42  reasoned   reviewed, no source for this specific
                     claim, kept on a recorded mechanism
```

The split tracks the kind of claim rather than its importance. Statements
about **one ingredient** are sourceable and were sourced — pregnancy status,
photosensitivity, absorption, pH behaviour. Statements about **two
ingredients together** mostly are not, because the literature tests
ingredients singly: there is no controlled data on stacking an AHA with a
BHA, or either with a retinoid. Those rules survive as mechanistic
inference, with each ingredient's effect documented individually and the
combination recorded as the inference it is.

Only `verified` sets the flag the result page uses to present a claim as
settled, so the distinction reaches the reader instead of collapsing into a
count. `docs/verification-checklist.md` has the outcome and
`docs/tier-a-sources.md` the sources.

The machine-translated ingredient names were **withdrawn on 26 October
2026**. For two days the resolver carried 232 non-English terms a model had
generated and no speaker had read, and flagged any product identified only
through one. Disclosure was the wrong answer: a wrong translation invents an
ingredient, and a warning about a conflict you do not have is wrong whether
or not a caveat sits beside it.

Everything else here can be argued with — a `reasoned` row records the
mechanism it rests on and a reader can judge it. A machine translation has no
reasoning to inspect. **We keep what we can show our working for.**

Every remaining search term is INCI, a product name, or a reviewed alias.
Little capability went with it: INCI is international and required on the
ingredient list by EU, Korean and Japanese regulation, so a non-English label
still resolves. What is gone is support for labels printing *only* a local
name, where the failure is a missing finding rather than an invented one.
`data/ingredient_aliases.yaml` stays in the repository for whoever has the
four speakers.

This is deliberate and worth stating plainly: a rule table generated by a model
and presented as verified would make the project's central claim false. The
count of verified rows is reported honestly in the write-up.

**Nothing here is medical advice.** Products flagged as prescription, and any
pregnancy-related finding, escalate to a clinician rather than producing a
recommendation.

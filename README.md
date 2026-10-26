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

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
python build_db.py
python -m uvicorn app:app --port 8000
```

On macOS or Linux, `source .venv/bin/activate && pip install -r requirements.txt`
instead of the second line.

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
order, the money, an interaction matrix, a printed card for the mirror, and
a drawn animation of the routine that can be downloaded as a GIF.

It also answers the question a routine built from your shelf cannot ask:
**what is not on it.** Every other part of the page compares products you
own against each other, so a shelf of four serums and no cleanser used to
get an ordered routine and no comment. A missing cleanser, moisturiser or
sunscreen is now named — those three and no others, because they are the
steps the AAD order names and the only rows in `product_forms.yaml` marked
`verified`. Being told you are "missing" a toner would invent a purchase.
Several products doing one job is reported too, from three upwards, as a
money note rather than a mistake. Every one of these says **when** the
step belongs — morning, evening or both — read from the same `times`
column the routine builder uses, so a gap cannot name a different time of
day from the routine beside it.

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

- `data/ingredient_aliases.yaml` carries local-language ingredient names for
  labels that use them instead of INCI, which is common on Japanese and Chinese
  packaging.
- Form keywords cover nine languages, so 선크림 is recognised as a sunscreen and
  化粧水 as a toner rather than defaulting to "serum".
- The Shelf Reader records both the printed term and its INCI equivalent, so a
  translated match stays auditable against what was actually on the label.

Alias coverage is **42/42 actives in Korean, French, Japanese and Chinese**.
`build_db.py` prints the per-language breakdown on every build, so a gap shows
up rather than being assumed.

Try it:

```bash
python audit_cli.py --shelf data/sample_shelf_intl.json
```

And the regression check — 281 assertions, no API key needed:

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

What is **not** checked: the 232 non-English ingredient names in
`data/ingredient_aliases.yaml`, which were machine-generated and have never
been read by a speaker of any of those languages. Twelve of them turn out to
be words the English table already carries, leaving **220 of the resolver's
365 search terms** resting on nothing but a translation. That is the largest
unverified surface here and it is stated rather than buried.

Checking them needs four speakers this project does not have, so the risk is
contained rather than removed. The risk is one-sided — a *missing*
translation costs a finding, which is safe; a *wrong* one invents an
ingredient, and that warning looks exactly like a real one — so the unchecked
half is made to declare itself. Each search term records where it came from,
and when a product's actives were found **only** through a translated term,
the page says so for that product, naming the ingredient and the language:

> **1 product was identified using a non-English ingredient name that no
> speaker of that language has checked.** … 한국 세럼 → Niacinamide (matched
> its Korean name)

INCI is international, so a Korean or French label usually still resolves
through terms a human has checked and the warning never appears — which is
the point. A caveat on every audit would be ignored; this one marks the
bottle worth a second look. `test_provenance.py` pins both directions.

This is deliberate and worth stating plainly: a rule table generated by a model
and presented as verified would make the project's central claim false. The
count of verified rows is reported honestly in the write-up.

**Nothing here is medical advice.** Products flagged as prescription, and any
pregnancy-related finding, escalate to a clinician rather than producing a
recommendation.

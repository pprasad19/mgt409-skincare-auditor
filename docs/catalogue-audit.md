# The whole catalogue, checked

All 74 products, 25 October 2026. One lookup per product returns both
the published ingredient list and the published price, so this is one
sweep answering two questions. Supersedes the earlier samples in
`price-spotcheck.md` and `actives-spotcheck.md`.

## Prices

| | |
|---|---|
| Had a published price | 68 of 74 |
| Median absolute error | **11%** |
| Within 20% | 54 of 68 |
| Worst | SK-II Facial Treatment Essence, 147% |

The median is the same 11% the fourteen-product sample measured, which
is some comfort that the sample was representative. The worst case is a
product sold in four sizes at wildly different prices, so "the" retail
price is not a single number for it.

Good enough to quote with the error stated. A user's own price always
overrides the catalogue; the estimate only fills a gap.

## Actives

| | |
|---|---|
| Had a published list | 74 of 74 |
| Matched exactly | 10 |
| Claim an active the list does not show | 11 |
| Miss an active the list does show that fires a rule | 39 |

Those numbers look bad and mean something more specific.

**The misses are the catalogue being a catalogue.** It was built by
asking "what is this product known for", so it records headline actives
and skips the base. Most of what it omits is glycerin, panthenol,
hyaluronic acid and squalane. Where it omits something that fires a rule
— niacinamide most often — the audit reports fewer findings than it
could, which is the safe direction to be wrong in and still wrong.

**Four of the eleven "false positives" were not catalogue errors at
all.** They were the resolver failing to recognise an ingredient, with
the catalogue right all along. This is the third time that pattern has
appeared today, after the sunscreen filters and the centella
triterpenes.

## What the sweep found that nothing else would have

Re-running `tools/inci_coverage.py` across all 94 published lists now in
the cache surfaced six actives the table did not know. **Three of them
gate a pregnancy escalation:**

| Ingredient | Where | Consequence of missing it |
|---|---|---|
| **Betaine salicylate** | COSRX BHA Blackhead Power Liquid, Beauty of Joseon Glow Serum | A BHA resolving to nothing — no SKC-003, no timing rule |
| **Hydroxypinacolone retinoate** | The Ordinary Granactive Retinoid | What "Granactive Retinoid" means. A retinoid resolving to nothing — no SKC-001 |
| **Retinyl acetate** | The INKEY List Retinol Serum | A retinol serum containing no recognised retinoid |
| Ascorbyl glucoside | Vichy Normaderm | A vitamin C derivative, no redundancy or oxidiser rule |
| Malic acid | SK-II Clear Lotion, The Ordinary Squalane Cleanser | An AHA |
| Tartaric acid | The Ordinary AHA 30% | An AHA |

All six are added, with aliases in all four languages in the same change
— coverage stayed at 42/42 rather than silently dropping, which is the
mistake made earlier the same day with the previous four.

## Citric acid, and why it stays out

The sweep gives the decision a number. **Citric acid appears in 30 of
the 94 published lists** — a third of everything on the market — because
it is a pH adjuster at a fraction of a percent. Matching it would fire
AHA conflict rules on nearly every shelf audited.

Malic and tartaric acid appear in 2 and 1 lists. That is the frequency
of an active rather than a buffer, which is why those were added and
citric was not.

Raw results: `output/catalogue_audit.json`.

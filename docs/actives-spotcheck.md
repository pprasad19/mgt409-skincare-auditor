# Catalogue actives: how wrong are they?

When a label cannot be read, the catalogue decides what is in the bottle
and the entire audit follows from that. Nothing had ever checked those
lists.

Twelve products sampled across brands on 25 October 2026, looked up, and
the published ingredient list run through the same resolver the app uses.

| | |
|---|---|
| Had a published list to compare | 12 of 12 |
| Matched exactly | 3 |
| Claimed an active the list does not show | 2 |
| Missed an active the list does show | 9 |

## The misses are mostly harmless, and that is not an accident

What the catalogue omits is overwhelmingly glycerin, hyaluronic acid,
squalane and panthenol — ingredients no rule fires on. The catalogue was
built by asking "what is this product known for", so it records headline
actives and skips the base. Missing an inert humectant costs nothing.

Four misses do matter: niacinamide in four products, lactic acid in two,
ascorbic acid in one. Those fire rules, so the audit silently reports
fewer findings than it should. That is the safe direction to be wrong in
— the app says less than it could — but it is still wrong.

## The one that was not harmless

**Beauty of Joseon Relief Sun** was recorded as containing
`organic_uv_filters`, and the published list appeared not to confirm it.
The catalogue was right and the resolver was wrong, which turned out to
be the more serious finding.

`organic_uv_filters` listed five INCI terms. Two of them — Tinosorb S and
Uvinul A Plus — are trade names that no ingredient list prints. Ethylhexyl
Triazone, which appears in three products already sitting in
`data/learned_products.json`, was absent. Titanium dioxide, one of the two
mineral filters, was not in the table at all.

So a real sunscreen, read from a real label, resolved to no UV filter.
The gap check then keyed on the product's *form*, guessed from its name,
and "Relief Sun" contains no word the keyword list recognises. The result:

> **There is no sunscreen on this shelf, and you need one.**

Said at high severity, to someone holding a sunscreen, on the one piece
of preventive advice this app most wants to get right — and only on the
input path we treat as most trustworthy, the one where the label was
actually read.

Three fixes:

- `organic_uv_filters` now carries 24 INCI names covering US, European,
  Korean and Japanese labels; trade names moved to aliases where they
  belong
- `titanium_dioxide` added as its own row
- a product whose label contains any UV filter is now filed as `spf`
  regardless of its name, and the gap check tests the actives as well as
  the form

`test_robustness` now asserts this across six real sunscreen formulations.

## What this says about the other 62 rows

The sample suggests the catalogue under-lists rather than invents, which
is the safer failure. It does not suggest the lists are complete. The
remaining rows are unchecked and `data/products.yaml` still carries no
review field — unlike `ingredients.yaml`, `interactions.yaml` and
`product_forms.yaml`, which now do.

Raw results: `output/actives_spotcheck.json`.

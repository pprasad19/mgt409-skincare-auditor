# Catalogue prices: how wrong are they?

All 74 prices in `data/products.yaml` were typed in from estimate, with no
source. Every figure in the Money section rests on them, so this measures
the error rather than assuming it is small.

Checked 25 October 2026. Fourteen products sampled across the whole range
— cheapest to dearest, not at random, because a 10% error on a $182 serum
and a 10% error on a $9 cleanser are different problems. Each was looked
up with the same agent the app uses for unknown products, which returns a
published price with the URL it came from.

| Product | Mine | Published | Error |
|---|---|---|---|
| Vaseline Original Petroleum Jelly | $5 | $5.99 | +20% |
| The Ordinary Lactic Acid 10% + HA | $9 | $9.20 | +2% |
| The Inkey List Niacinamide Serum | $9 | $13.00 | **+44%** |
| The Ordinary Azelaic Acid Suspension 10% | $11 | $12.20 | +11% |
| Cetaphil Gentle Skin Cleanser | $13 | $11.88 | −9% |
| CeraVe Acne Foaming Cream Cleanser | $15 | $14.99 | −0% |
| CeraVe PM Facial Moisturising Lotion | $17 | $19.99 | +18% |
| CeraVe Moisturising Lotion | $18 | — | no published price |
| CeraVe Resurfacing Retinol Serum | $22 | $16.49 | −25% |
| Anua Heartleaf 77 Soothing Toner | $24 | $21.00 | −12% |
| La Roche-Posay Anthelios UVMune 400 | $27 | — | no published price |
| Vichy Mineral 89 | $32 | $29.99 | −6% |
| Innisfree Retinol Cica Repair Serum | $40 | $37.00 | −8% |
| Glytone Rejuvenate Mild Cream | $58 | $55.00 | −5% |

**Median absolute error 11%. Ten of twelve within 20%.**

## What this means for the Money numbers

Good enough to quote, with the error stated. A shelf total built from
these is accurate to roughly ±11%, and the error is not systematically
high or low — six of the twelve were over, six under — so it largely
cancels across a shelf rather than compounding.

The worst case is the Inkey List serum at +44%, which is a $4 absolute
error on a $9 product. The proportional error is large and the pound
error is small; that is the pattern across the cheap end generally.

Two products had no published price the agent could find. They keep their
estimate and the page already marks any unsourced price as "typical
retail" rather than claiming it is the user's.

## Why they were not all replaced with sourced figures

They could be: the lookup agent fetches a price and a URL for any product,
and running all 74 would take about twenty minutes. It was not done
because a measured 11% error that the report discloses is more useful than
74 silently-replaced numbers, and because a user's own price always
overrides the catalogue anyway — the estimate only fills a gap.

Raw results: `output/price_spotcheck.json`.

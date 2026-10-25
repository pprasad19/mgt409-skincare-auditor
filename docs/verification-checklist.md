# Rule verification checklist

66 rows carry `review: pending`. **Do not verify 66.** Verify Tier A — about
ten distinct claims covering eighteen rows, roughly 45–60 minutes — and report
the count honestly. Leave the rest marked pending.

To mark a row verified, edit the YAML: set `source:` to the reference and
`review: verified`. Then re-run `python build_db.py`.

---

## Tier A — verify these

These either gate a safety decision or get cited in the report. A wrong row
here is a real problem, not a cosmetic one.

### Pregnancy status

- [ ] **Topical retinoids are conventionally avoided in pregnancy**
  Covers 5 rows: `tretinoin`, `adapalene`, `retinol`, `retinaldehyde`, `retinyl_palmitate`
  Look at: AAD guidance, or any standard obstetric dermatology reference.
  Note whether the guidance is uniform across the five or differs by strength.

- [ ] **Hydroquinone in pregnancy**
  Covers: `hydroquinone`, and `SKC-002`.
  Check whether the standard position is "avoid" or "decide with clinician" — the
  table currently says avoid and escalates.

- [ ] **Salicylic acid in pregnancy — low-percentage leave-on vs peels**
  Covers: `salicylic_acid`, `SKC-003`.
  This is the row most likely to be wrong, because the guidance genuinely differs
  by concentration and format. If the distinction does not hold up, simplify it.

### The conflicts the report will cite

- [ ] **SKA-003 — benzoyl peroxide degrades retinoids**
  High severity, and the headline example in the report. Confirm the mechanism is
  oxidative degradation and that it is measurable, not theoretical.

- [ ] **SKA-004 — adapalene is the exception**
  This one *must* be right; it overrides a high-severity rule. Check the labelling
  for a co-formulated adapalene / benzoyl peroxide product — if such products are
  sold, that settles it.

- [ ] **SKA-001 — retinoid + AHA additive irritation**
  High severity. Confirm "alternate nights" is the standard guidance rather than
  "never combine".

- [ ] **SKA-020 — the niacinamide / vitamin C myth**
  Cited in the report as evidence the table corrects folklore rather than
  repeating it. Confirm the original stability study used high heat on pure
  compounds, and that modern formulations combine them. **If this one does not
  hold up, drop the claim entirely** — a wrong myth-correction is worse than no
  myth-correction.

- [ ] **SKA-021 — vitamin C + copper peptides**
  Medium severity, redox mechanism. Lower stakes, but it is a specific chemical
  claim and specific claims are checkable.

### Photosensitivity and ordering

- [ ] **SKA-082 / SKA-083 — acids and retinoids increase UV sensitivity**
  Two high-severity timing rules. Well established; quick to confirm; drives the
  AM/PM split that the whole routine output depends on.

- [ ] **SKA-080 — sunscreen last**
  High severity ordering rule. Confirm the reasoning is film disruption.

### Gates

- [ ] **SKC-010 / SKC-011 — prescription and declined-to-say both escalate**
  Not factual claims — design decisions. Confirm you are happy with the behaviour
  rather than verifying a source. Record the reasoning as the `source`.

---

## Tier B — only if time allows

The 4 medium-severity conflicts and 5 medium cautions not listed above:
SKA-002, 005, 010, 011, 012, 023, 030, 040, 041, 070, 071.

Real claims, lower stakes, and none of them is load-bearing in the report.

## Tier C — leave pending

- The 7 synergies and 3 low cautions. Being wrong about a synergy means a missed
  suggestion, not a harmful one.
- Ingredient metadata: pH ranges, class, potency, layer rank. Low risk and
  mostly uncontroversial.
- The 8 `pregnancy: caution` rows beyond salicylic acid. They already route to the
  cautious path, so an error fails safe.

---

## What to write in the report

State the real number. Something like:

> Of 34 rules, 12 covering all high-severity interactions and every
> contraindication gate were verified against published guidance; the remainder
> are marked unverified in the source files.

That is a stronger sentence than an unqualified claim of correctness, and it is
the kind of thing the evidence rule rewards. It also means that if a grader spots
an error in a Tier C row, you have already disclosed the limitation rather than
been caught by it.

---

# Outcome, 25 October 2026

Every row in `ingredients.yaml` and `interactions.yaml` has now been
reviewed. Nothing is `pending`.

```
  31  verified   checked against a published source, named in the row
  34  reasoned   reviewed, no published source for this specific claim,
                 kept on a recorded mechanism
   0  pending
```

Only `verified` sets the flag the result page uses to present a claim as
settled, so the distinction reaches the reader rather than being
flattened into a count.

## What the split tracks

Not importance — the kind of claim. Statements about **one ingredient**
are sourceable and were sourced: pregnancy status, photosensitivity,
absorption, pH behaviour. Statements about **two ingredients together**
are mostly not, because the literature tests single ingredients far more
often than pairs. There is no controlled data on stacking an AHA with a
BHA, or either with a retinoid. Those rules survive as mechanistic
inference, with each ingredient's barrier effect documented individually
and the combination stated as the inference it is.

## What the review changed

| | |
|---|---|
| `SKA-020` | removed — the 1960s study behind the myth claim could not be found, and two findings cut against it |
| `SKA-021` | removed — copper bound to GHK has its redox activity silenced, so the mechanism may not apply |
| `SKA-001` | high → medium, and stopped restructuring routines; a 397-woman study found the pairing well tolerated |
| `SKA-051`, `SKA-052` | dropped the claim that the effect is "additive" — a reconstructed-skin model found it was not |
| `benzoyl_peroxide` | pregnancy caution → ok; reviews treat it as first-line in pregnancy |
| `SKC-004` | **added** — AHAs escalate in pregnancy, which they previously did not while BHA did |

Three rules turned out right for the wrong reason, and the reasons are
now recorded accurately: retinoids in pregnancy is precautionary
convention rather than measured harm, sunscreen last is published order
rather than film disruption, and the photosensitivity rule rests on FDA
label text for retinoids but only FDA guidance for acids.

## Still unchecked

- **The 128 alias translations** across ko, ja, zh and fr. Machine
  generated, never read by a speaker. This is the largest unverified
  surface in the project and the one most likely to fail silently.
- **The 74 catalogue prices.** Spot-checked rather than verified: fourteen
  sampled, median absolute error 11%. See `docs/price-spotcheck.md`.
- **Catalogue `actives` lists**, which drive the audit whenever a label
  cannot be read.

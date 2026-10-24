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

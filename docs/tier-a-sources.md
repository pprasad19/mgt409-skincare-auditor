# Tier A sources, for review

Sources gathered 25 October 2026 for the claims in
`docs/verification-checklist.md` that gate a safety decision or get cited
in the report.

**How to read this.** Each claim has what the sources actually say, the
reference, and a recommendation. Nothing here is marked `review: verified`
in the YAML until a human has read the row and accepted it. Gathering a
source is not the same as checking one, and the report should say which of
the two happened.

---

## 1. Topical retinoids in pregnancy — **accept, with the reasoning changed**

Covers `tretinoin`, `adapalene`, `retinol`, `retinaldehyde`,
`retinyl_palmitate`.

The conventional advice is to avoid all topical retinoids in pregnancy,
and that is uniform across the five — but the basis is precaution, not
demonstrated harm. A regulatory review found systemic exposure after
topical application is negligible and unlikely to affect a foetus, and
still recommended contraindication.

So the row is right and its *reason* was wrong: this is a precautionary
convention, not a measured risk. Worth saying that way, because the app
escalates to a clinician rather than refusing, and the honest reason for
escalating is "the convention is to avoid this and the decision is not
ours to make".

**Source:** Malta Medicines Authority review of topical retinoids in
pregnancy. Secondary reporting attributes the same position to ACOG and to
AAD-interviewed dermatologists; I could not confirm either from the
original guideline pages, so those are not cited.

---

## 2. Hydroquinone in pregnancy — **accept**

Covers `hydroquinone`, `SKC-002`.

Systemic absorption is 35–45% of the applied dose, which is high for a
topical. No increased malformation risk has been shown, but the human
evidence is one small study. Standard advice is to minimise exposure in
pregnancy and prefer azelaic acid.

That supports what the table does — escalate rather than forbid. "Decide
with a clinician" is the accurate position, and that is what `SKC-002`
produces.

**Source:** *Hydroquinone*, StatPearls, NCBI Bookshelf NBK539693.

---

## 3. Salicylic acid in pregnancy — **accept; the distinction holds**

Covers `salicylic_acid`, `SKC-003`.

The checklist flagged this as the row most likely to be wrong. It holds
up. Topical salicylic acid at acne-product concentrations is treated as
low risk across trimesters because systemic absorption is negligible —
with the caveat that large areas, prolonged use, occlusion and damaged
skin all raise exposure, and a 2025 review of 44 topical-salicylate
toxicity cases shows the systemic risk is real at the extremes.

So the leave-on versus peel distinction is the right shape. It is about
dose and area, not about the molecule.

**Sources:** *Treatment of Acne Vulgaris During Pregnancy and Lactation: A
Narrative Review*, PMC9823189. *Unmasking the Hidden Risk of Systemic
Toxicity from Topical Salicylates*, PMC12591629.

---

## 4. SKA-003 — benzoyl peroxide degrades retinoids — **accept**

This is the report's headline example, and it is measurable rather than
theoretical, which is what the checklist asked.

Tretinoin 0.025% gel mixed with 10% benzoyl peroxide lotion and exposed to
light: **50% of the tretinoin degraded in 2 hours, 95% in 24 hours.**

**Source:** Martin B et al., *Chemical stability of adapalene and
tretinoin when combined with benzoyl peroxide in presence and in absence
of visible light and ultraviolet radiation*, Br J Dermatol 1998.
PMID 9990414.

**Caveat to record:** an in-vitro study that mixed two commercial products
rather than testing a single formulation, and the abstract attributes the
loss to benzoyl peroxide *combined with light*. The rule should not claim
the degradation happens in the dark.

---

## 5. SKA-004 — adapalene is the exception — **accept**

Same study, same conditions: **adapalene showed no degradation over 24
hours.** A 2014 meta-analysis repeats that adapalene is stable with
benzoyl peroxide even in light, and co-formulated adapalene / benzoyl
peroxide products are sold, which settles it commercially as well as
experimentally.

This matters more than its size suggests: it is the one exception that
overrides a high-severity rule, so a wrong answer here would tell someone
to separate two products that are sold premixed in one tube.

**Sources:** PMID 9990414. *Effects of Adapalene-Benzoyl Peroxide
Combination Gel…: A Meta-Analysis*, PMC3956794.

---

## 6. SKA-082 / SKA-083 — acids and retinoids increase UV sensitivity — **accept both halves**

Two separate sources of different strength, and the retinoid half turns
out to be the better supported of the two.

**Retinoids.** FDA-approved prescribing information for topical tretinoin
states it directly:

> Tretinoin gel can cause photosensitivity. Advise patients to avoid or
> minimize unnecessary exposure to UV light, including sunlight and
> sunlamps.

The same labels tell patients to use SPF 15 or higher with protective
clothing where exposure is unavoidable, to stop using the product until a
sunburn has fully healed, and single out people with outdoor occupations
or other photosensitising drugs for extra caution. Older cream labels add
that the protection applies on hazy days too. Animal data suggest
tretinoin may enhance the tumorigenic potential of UVB and UVA; the labels
note this has not been shown in humans.

This is label text rather than guidance, which makes it the strongest
citation in this document.

**Acids.** The FDA's 2005 guidance for cosmetics containing alpha hydroxy
acids recommends a sun-sensitivity warning, on the basis of human studies
showing AHAs increase UV sensitivity during use **and for up to a week
after stopping**. Its suggested wording is a "Sun Alert". The FDA's beta
hydroxy acid page says the same of glycolic acid. This one is a
recommendation, not a binding rule, and the FDA's own pages describe it
that way.

**The honest gap:** the label evidence is for *tretinoin*, a prescription
drug. Applying it to over-the-counter retinol is an inference — a
reasonable one, since retinol converts to retinoic acid in skin, but an
inference. The rule covers both and the report should not imply the label
covers both.

**Sources:** DailyMed, tretinoin gel and tretinoin cream prescribing
information. FDA, *Guidance for Industry: Labeling for Cosmetics
Containing Alpha Hydroxy Acids*, January 2005. FDA, *Beta Hydroxy Acids*
consumer page.

## 7. SKA-020 — the niacinamide / vitamin C myth — **do not accept as written**

The checklist said: *if this one does not hold up, drop the claim
entirely — a wrong myth-correction is worse than no myth-correction.*

It does not hold up as written. What the sources support:

- Niacinamide itself does not cause flushing; **nicotinic acid does**, and
  the two are different compounds.
- Niacinamide **can hydrolyse to nicotinic acid**, which reddens skin at
  low concentrations. So the conversion is a real mechanism, not folklore.
- One analytical paper reports vitamin C **degrades faster in the presence
  of niacinamide** in solution.

What I could not find: the 1960s high-heat study the rule's framing rests
on. Without it, the claim "this is a myth from a study that used high heat
on pure compounds" is unsupported, and two of the three findings above cut
against the myth-correction rather than for it.

**Recommendation:** soften the rule from "this is a myth, ignore it" to
something the sources actually carry — the interaction is real in
solution, its significance in a finished formulation is contested, and
modern products do combine the two. Or drop SKA-020. Do not ship it as a
confident debunk.

---

## 8. SKA-080 — sunscreen last — **accept the rule, drop the stated reason**

The checklist asked specifically: *confirm the reasoning is film
disruption.* It is not, and the evidence points the other way.

The **conclusion** is well supported. The AAD's own guidance is explicit:
"Always put sunscreen on after other skin care products — and beneath your
makeup", applied about 15 minutes before going outdoors. Its step list
runs cleanse, treatments, moisturiser and/or sunscreen, makeup.

The **mechanism** is not. A study of patients with photodermatoses found
no difference in sunscreen efficacy whether it was applied before or after
the other topicals in use, and concluded efficacy was not altered by
combined use with corticosteroids, antibiotics or antifungals. If layering
disrupted the film measurably, that study should have seen it.

What the literature does show is that **the amount applied dominates
everything else**. In one lab study a single self-application laid down a
layer thin enough to give an effective SPF of about 3.2 from a product
labelled SPF 50, and a second application increased the quantity used by
13–100% depending on the site.

**Recommendation:** keep the rule, restate the reason. "Sunscreen goes
last because that is the published order and because anything applied over
it risks removing it" is defensible; "because other products disrupt the
film" is a mechanism nobody here has evidence for. If the rule's guidance
text has room, the useful thing to tell a user is not the ordering at all
— it is that most people apply far too little.

**Sources:** AAD, *Should I apply my skin care products in a certain
order?* AAD, *Dermatologist-recommended skin care for your 20s*.
*Sunscreen use optimized by two consecutive applications*, PMC5874020.
*Evaluation of the Efficacy of Photoprotective Formulations Applied in
Conjunction With Topical Active Ingredients in Patients With
Photodermatoses*, PMID 41478343.

---

## 9. SKA-001 — retinoid + AHA additive irritation — **the evidence partly contradicts this**

High severity, and it drives the alternating-nights grid, which is one of
the most visible things the app produces. It is the weakest rule in the
table.

What the sources support: DermNet recommends starting a retinoid on
alternate nights with a light moisturiser to manage irritation — **from
the retinoid alone**, not from combining it with an acid.

What cuts against it: an open study of 397 women using 0.1%
retinaldehyde with 6% glycolic acid found the combination "highly
tolerated", used alone or alongside other acne treatments, with rare
complaints of side effects. A retinol-plus-glycolic-acid patent goes
further and claims glycolic acid has an irritation-*ameliorating* effect
with retinol, though that is the assignee's own claim.

No controlled trial comparing alternate-night with nightly dosing for a
retinoid plus an acid was found.

**Recommendation:** downgrade from high to medium, and change the guidance
from "alternate nights" stated as a requirement to "if either irritates,
use them on different nights". That is what the evidence carries: a
tolerability strategy, not a chemical necessity. Keeping it at high
severity means the app is confidently separating two products that a
397-person study found people tolerate together.

**Sources:** DermNet, *Topical therapy for acne*. *Interest of the
association retinaldehyde/glycolic acid in adult acne*, PMID 19192015.

---

## 10. SKA-021 — vitamin C + copper peptides — **unsupported, and the mechanism is doubtful**

Nothing found tests copper peptides and ascorbic acid together for
incompatibility. Worse for the rule, one review reports that copper's
redox activity is *silenced* when the copper ion is bound to the GHK
tripeptide — which is the form in a copper peptide product. If that is
right, the free-radical redox mechanism the rule describes may not apply
to the ingredient as sold.

Both ingredients are independently oxidation-sensitive, and GHK is prone
to hydrolytic cleavage under oxidative stress, so *a* stability concern is
plausible. That is not the same as the specific claim the rule makes.

**Recommendation:** drop it, or rewrite it as a stability note with the
severity lowered. A specific chemical claim with no source and a
questionable mechanism is the kind of row this project exists to avoid.

**Sources:** *GHK Peptide as a Natural Modulator of Multiple Cellular
Pathways in Skin Regeneration*, PMC4508379.

---

## 11. SKC-010 / SKC-011 — the escalation gates — **your decision, not a source**

Not factual claims. These decide that a prescription product, or a user
who declines to answer, sends the audit to a clinician rather than
proceeding. The checklist says to record the reasoning rather than find a
reference, and that is still right.

---

## Recorded outcome

Of eleven Tier A claims: seven accepted and written into the YAML with
sources, one dropped (SKA-020), two flagged as needing a change, one a
design decision. Fifty-one rows across the two files remain
`review: pending` and are not evidence.

"""Structured types for the auditor.

Field choices are documented here rather than in the harness doc alone, because
the reason a field exists is usually the reason the system can be trusted. The
recurring theme: anything the user is told must carry enough provenance to be
checked — which rule produced it, and from which product.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low"]
FindingType = Literal["conflict", "caution", "synergy", "myth", "redundancy", "ordering", "timing"]
Resolution = Literal["separate_am_pm", "alternate_nights", "buffer", "reorder", "drop_one", "none"]
TimeOfDay = Literal["am", "pm", "both"]


def display_name(brand: str | None, name: str) -> str:
    """Brand first, unless the name already carries it.

    Applied once, at the point a product enters the system, so the routine,
    the findings, the matrix, the printed card and the agent all use the same
    string. Three bottles called "Hydrating Facial Cleanser" are not
    distinguishable without it, and a shelf really can hold three.
    """
    name = (name or "").strip()
    brand = (brand or "").strip()
    if not brand:
        return name
    if brand.lower() in name.lower():
        return name
    return f"{brand} {name}".strip()


class InputProduct(BaseModel):
    """One product as the user gave it to us, before any resolution."""

    name: str
    brand: str | None = None
    form: str | None = Field(
        default=None,
        description="Product form id, e.g. serum. Inferred from the name when absent.",
    )
    listed_ingredients: list[str] = Field(
        default_factory=list,
        description="Raw INCI strings as printed on the label. The parser reads these; "
                    "nothing is assumed from the product name alone.",
    )
    price_usd: float | None = Field(
        default=None,
        description="What the user paid. Drives the waste and redundancy figures, "
                    "which are the only numbers in the output denominated in money.",
    )
    unused: bool = Field(
        default=False,
        description="User says they own it but do not use it. A product that is both "
                    "unused and redundant is the clearest waste signal we have.",
    )
    dwell_seconds: int = Field(
        default=0,
        description="How long this product says to leave it on, in seconds, for the "
                    "forms that are worn rather than absorbed. Filled in by a lookup "
                    "against this specific product, never by a rule of thumb for the "
                    "category — a clay mask, a sheet mask and an overnight mask do "
                    "not share a number, and this one gets counted down at a sink.",
    )
    dwell_source: str = Field(
        default="", description="Where that duration was published.",
    )
    price_is_typical: bool = Field(
        default=False,
        description="The price did not come from the user. Set when it was filled "
                    "from the catalogue or looked up online, so the page can say so.",
    )


class ResolvedProduct(BaseModel):
    """An input product after its ingredients have been matched to the table."""

    product: InputProduct
    form: str
    actives: list[str] = Field(
        default_factory=list,
        description="Ingredient ids matched from the label.",
    )
    classes: list[str] = Field(default_factory=list)
    unmatched_terms: list[str] = Field(
        default_factory=list,
        description="Label terms we could not resolve. Surfaced rather than dropped — "
                    "an unknown active is a reason to lower confidence, not to stay silent.",
    )
    confidence: float = Field(
        default=1.0,
        description="Share of label terms resolved. Low confidence is shown to the user.",
    )
    price_is_typical: bool = Field(
        default=False,
        description="The price came from the catalogue, not the user. Shown on the "
                    "page and kept out of anything the report cites as measured — "
                    "a typical price is not what this person paid.",
    )
    dwell_seconds: int = Field(
        default=0,
        description="Minutes-on-the-face for this specific product, found by "
                    "looking it up. Zero means nobody said.",
    )
    dwell_source: str = Field(
        default="", description="Where that duration was published.",
    )
    translated_only: dict[str, str] = Field(
        default_factory=dict,
        description="Actives identified only by a non-English term from "
                    "ingredient_aliases.yaml, which is machine-generated and "
                    "has never been read by a speaker. A missing translation "
                    "costs a finding, which is safe; a wrong one invents an "
                    "ingredient, which is not. Naming them lets the page warn "
                    "about the product that rests on one instead of every "
                    "audit equally. Maps the ingredient to the language "
                    "whose name matched, so the reader knows which word "
                    "on the bottle to check.",
    )
    matched_from_catalogue: str | None = Field(
        default=None,
        description="Set when the actives came from data/products.yaml rather than a "
                    "label, because nothing was readable. Shown to the user: a "
                    "catalogue entry is a claim about a product, not a reading of "
                    "the one in their hand.",
    )


class Finding(BaseModel):
    """One rule firing against this specific shelf."""

    rule_id: str = Field(description="Traces back to interactions.yaml. Every claim is checkable.")
    type: FindingType
    severity: Severity
    products: list[str] = Field(description="Product names this finding is about.")
    ingredients: list[str] = Field(default_factory=list)
    mechanism: str
    guidance: str
    resolution: Resolution
    verified: bool = Field(
        default=False,
        description="Whether the underlying rule has been human-verified. Shown in the "
                    "output so an unverified claim is never presented as settled.",
    )


class Escalation(BaseModel):
    """A contraindication gate. Never advice — always a handoff."""

    rule_id: str
    condition: str
    severity: Severity
    message: str
    products: list[str]


class RoutineStep(BaseModel):
    product_name: str
    form: str
    form_id: str = Field(
        default="",
        description="The form's id rather than its label. The animation picks a "
                    "container and a technique from this, and it cannot key off "
                    "a display name like 'Treatment (leave-on active)'.",
    )
    order: int
    frequency: str = Field(default="daily", description="daily, or alternate nights when a rule says so.")
    because: list[str] = Field(
        default_factory=list,
        description="Rule ids that placed this step here. Makes the ordering auditable "
                    "rather than something the user has to take on faith.",
    )
    dwell_seconds: int = Field(
        default=0,
        description="How long the product stays on after it is applied, before "
                    "the finish. Looked up for this product, never guessed: "
                    "StepApplication.seconds is capped at 120 and means time "
                    "spent applying, so a fifteen-minute mask could not be "
                    "expressed at all and came out as a 30-second step. The "
                    "narrator is not asked for this and cannot shorten it. Zero "
                    "with dwell_unknown set means the product is worn for a "
                    "while and nobody could say how long.",
    )
    dwell_unknown: bool = Field(
        default=False,
        description="This form is worn after applying, and no stated time was "
                    "found for this product. The step says to follow the packet "
                    "and the guided player waits instead of counting down. A "
                    "made-up number here is read off a screen by someone at a "
                    "sink, so not knowing has to survive to the surface.",
    )
    dwell_source: str = Field(
        default="",
        description="Where the duration came from, so a number the user is asked "
                    "to stand still for can be checked.",
    )
    dwell_note: str = Field(
        default="",
        description="What qualifies the dwell — that the packet wins. Carried so "
                    "the page does not present one number as settled.",
    )
    application: "ApplicationSpec | None" = None


class ApplicationSpec(BaseModel):
    """How to apply a step. Authored by the agent, rendered deterministically."""

    motion: Literal["press", "circular", "patting", "smooth", "dab"] = "smooth"
    area: str = "whole face"
    amount: str = "pea-sized"
    seconds: int = Field(default=15, ge=1, le=120)
    wait_after_seconds: int = Field(
        default=0,
        description="Pause before the next step, e.g. letting an acid settle.",
    )


class Routine(BaseModel):
    am: list[RoutineStep] = Field(default_factory=list)
    pm: list[RoutineStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WasteSummary(BaseModel):
    """The money figures. Separated out because Impact rests entirely on these."""

    shelf_value_usd: float = 0.0
    products_owned: int = 0
    products_unused: int = 0
    unused_value_usd: float = 0.0
    redundant_value_usd: float = Field(
        default=0.0,
        description="Value of duplicate-function products beyond the first in each class.",
    )
    conflicted_value_usd: float = Field(
        default=0.0,
        description="Value of products being degraded by something used alongside them.",
    )


class Unresolved(BaseModel):
    """A product we can see but cannot reason about.

    A shelf photograph shows front labels; the audit runs on ingredient lists.
    Those are different sides of the bottle. Without this the app rendered a
    confident empty audit over eight products it had read the names of and
    nothing else — the worst outcome available, because it looks exactly like
    a clean bill of health.
    """

    name: str
    reason: str
    legibility: str = "name_only"


class Observation(BaseModel):
    """Something visible in a face photograph. Not a finding, not a diagnosis.

    Offered back as a question. Nothing here reaches the rules engine until
    the user has ticked it, which means a wrong observation costs a glance
    rather than a wrong recommendation.
    """

    concern: Literal["oiliness", "dryness", "redness", "texture", "dark_marks", "breakouts"]
    where: str
    confidence: Literal["clear", "possible", "faint"] = "possible"
    seen: str


class SkinReading(BaseModel):
    observations: list[Observation] = Field(default_factory=list)
    lighting_note: str = Field(
        default="",
        description="Why the photograph may not support much, if so. Shown to the "
                    "user, because a confident reading of a badly lit photo is worse "
                    "than an uncertain one.",
    )
    needs_a_clinician: bool = Field(
        default=False,
        description="Something visible warrants a person rather than a product. "
                    "A flag only — the observer is forbidden from naming what it "
                    "thinks it might be.",
    )


class Suggestion(BaseModel):
    """Something worth adding, for a concern the shelf does not address.

    Every one traces to a concern the user confirmed and an ingredient the
    table says addresses it. The model never decides what someone needs: it
    may only suggest what to look at, and only the user may turn that into a
    concern.
    """

    concern: str
    concern_label: str
    why: str
    missing_actives: list[str] = Field(default_factory=list)
    already_covered_by: list[str] = Field(
        default_factory=list,
        description="Products on the shelf that already address this. When this is "
                    "non-empty there is nothing to buy, and saying so is the useful "
                    "answer.",
    )
    products: list[str] = Field(
        default_factory=list,
        description="Catalogue products containing a missing active. Examples, not "
                    "endorsements.",
    )


class Gap(BaseModel):
    """Something the shelf is missing, rather than something on it being wrong.

    Every other finding compares products the user owns. A gap is the opposite
    question — what does this combination of products require that is not here?
    Owning five photosensitising actives and no sunscreen is the clearest case,
    and nothing in a pairwise model can see it.
    """

    kind: str
    severity: Severity
    label: str = Field(description="What kind of thing this is, e.g. 'Sun protection'.")
    headline: str = Field(description="The instruction, on its own. One short sentence.")
    message: str = Field(description="Why, underneath. Never merged with the headline.")
    because: list[str] = Field(
        default_factory=list,
        description="Products that create the need. Keeps a gap as traceable as a finding.",
    )
    suggestion: bool = Field(
        default=False,
        description="This is something to consider, not something wrong. A missing "
                    "cleanser and an absent eye cream are both 'not on the shelf' "
                    "and only one of them is a problem; without this they render "
                    "identically and the page turns into a shopping list.",
    )


class AuditResult(BaseModel):
    products: list[ResolvedProduct]
    findings: list[Finding]
    escalations: list[Escalation]
    routine: Routine
    waste: WasteSummary
    gaps: list[Gap] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(
        default_factory=list,
        description="What to consider adding, per confirmed concern.",
    )
    unresolved: list[Unresolved] = Field(
        default_factory=list,
        description="Products with no usable ingredient data. Surfaced prominently: "
                    "an audit that silently ignores half a shelf reads as a pass.",
    )
    unreadable: list[str] = Field(
        default_factory=list,
        description="Things the reader saw in a photograph but could not identify at all.",
    )
    visible_count: int = Field(
        default=0,
        description="Distinct products the reader could see. Compared against the "
                    "number identified so a shortfall is stated rather than left "
                    "for the user to notice.",
    )
    rules_verified: int = 0
    rules_total: int = 0


RoutineStep.model_rebuild()


# --- Agent I/O ------------------------------------------------------------
# The two agents sit either side of the rules engine: one turns pixels into
# products, the other turns findings into sentences. Neither decides anything.


class ReadProduct(BaseModel):
    """One product as read off a label. Deliberately close to InputProduct,
    but with a legibility flag instead of a price — the reader cannot know
    what someone paid."""

    name: str
    brand: str | None = None
    form: str | None = None
    listed_ingredients: list[str] = Field(default_factory=list)
    legibility: Literal["clear", "partial", "name_only"] = "clear"
    price_usd: float | None = Field(
        default=None,
        description="What the user said they paid, if they said. Only ever transcribed "
                    "from their own words — never estimated from the brand, or the money "
                    "figures would be the model's guesses wearing the engine's authority.",
    )
    unused: bool = Field(
        default=False,
        description="True only if the user said they do not use it.",
    )
    region: Region | None = Field(
        default=None,
        description="Where this product sits in the photograph, when it came from one.",
    )
    label_text: str = Field(
        default="",
        description="Every word visible on the label, transcribed verbatim and in "
                    "order, including small print. Not a summary. This is what lets "
                    "a photograph be re-read by code: the structured fields are the "
                    "reader's judgement, and this is the evidence behind them.",
    )


class Region(BaseModel):
    """Where something sits in a photograph, as fractions of width and height.

    Fractions rather than pixels so the box survives whatever resizing happens
    between the upload and the annotated copy. Vision models are approximate
    at this, so these are "roughly here", not outlines.
    """

    label: str
    bbox: list[float] = Field(
        default_factory=list,
        description="[x0, y0, x1, y1], each 0-1 from the top-left of the image.",
    )
    image_index: int = Field(
        default=0,
        description="Which uploaded photograph, when there is more than one.",
    )


class ShelfReading(BaseModel):
    products: list[ReadProduct] = Field(default_factory=list)
    unreadable: list[str] = Field(
        default_factory=list,
        description="Things visible but not identifiable. Recording them is how "
                    "the system admits what it missed instead of quietly dropping it.",
    )
    visible_count: int = Field(
        default=0,
        description="How many distinct skincare products are visible in the "
                    "photographs, counted whether or not they could be identified. "
                    "Counting and identifying are different jobs: an unreadable "
                    "entry saying \"several bottles along the lower shelf\" is one "
                    "description covering an unknown number of products, so the "
                    "list of what was missed cannot be used to work out how much "
                    "was missed.",
    )
    unreadable_regions: list[Region] = Field(
        default_factory=list,
        description="Where those unidentified items are, so the photograph can be "
                    "marked up. A list of descriptions tells someone they missed "
                    "something; a box tells them which bottle.",
    )
    suspicious_text: list[str] = Field(
        default_factory=list,
        description="Label text that tried to instruct the reader rather than describe "
                    "the product. Reported, never acted on — this is the injection signal.",
    )
    suppressed_terms: list[str] = Field(
        default_factory=list,
        description="Ingredients present in the raw input that the reader did not record. "
                    "Filled by code after the model returns, never by the model — a reader "
                    "that has been talked out of seeing an ingredient cannot be relied on "
                    "to report that it was.",
    )


class NaiveShelfReading(BaseModel):
    """The output type a first version would have, with no place to flag anything.

    Used only by the control arm of the injection experiment. Measuring the
    hardened prompt against a schema that already contains `suspicious_text`
    understates the attacks: giving a model a named field for odd text invites
    it to report rather than obey, so the schema is itself a defence and has to
    be isolated to be credited.
    """

    products: list[ReadProduct] = Field(default_factory=list)
    unreadable: list[str] = Field(default_factory=list)


class Explanation(BaseModel):
    rule_id: str = Field(description="Must match a finding that was supplied. Validated.")
    plain_language: str


class StepApplication(BaseModel):
    """How to apply one product, as a sequence a person can follow.

    `finish` exists because the first version modelled a step as "apply for N
    seconds, move on", which is wrong for anything that rinses. It told the
    user to massage a cleanser for twenty seconds and then go straight to the
    toner, face still covered in cleanser. A step is apply, then finish, then
    optionally wait.
    """

    product_name: str
    motion: Literal["press", "circular", "patting", "smooth", "dab", "lather"] = "smooth"
    area: str = "whole face"
    amount: str = "pea-sized"
    seconds: int = Field(default=15, ge=1, le=120, description="Time spent applying.")
    finish: Literal["rinse off", "pat dry", "let it absorb", "nothing"] = Field(
        default="let it absorb",
        description="What happens when the applying is done. Rinse-off products must say "
                    "'rinse off'; leave-on products absorb.",
    )
    finish_seconds: int = Field(
        default=0, ge=0, le=180,
        description="How long the finish takes — rinsing thoroughly is not instant.",
    )
    wait_after_seconds: int = Field(
        default=0, ge=0, le=600,
        description="Pause before the NEXT product, after this one is finished. For letting "
                    "an acid settle, not for rinsing.",
    )


class AuditNarrative(BaseModel):
    summary: str
    explanations: list[Explanation] = Field(default_factory=list)
    steps: list[StepApplication] = Field(default_factory=list)

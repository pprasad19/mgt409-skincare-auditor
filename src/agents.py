"""The two agents.

    Shelf Reader     pixels (or typed text) -> product records
    Routine Auditor  findings -> sentences a person can act on

Between them sits rules.py, which is where every decision is made. The split is
the design-layer defense: a product label can influence what the reader
*transcribes*, but the reader cannot assert an interaction, and the auditor can
only explain findings it was handed. Neither agent has a path to the verdict.

Both carry the trap tools from safety.py. Neither needs them.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from pathlib import Path
from typing import Iterable

from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent

from llm import MODEL_SETTINGS, build_model, with_cache_mode
from models import AuditNarrative, AuditResult, NaiveShelfReading, ShelfReading
from rules import DB_PATH
from safety import AuditTrail, detect_suppression, email_dermatologist, purchase_product
from usage import UsageLog

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"

IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

_MODEL = None


def model():
    global _MODEL
    if _MODEL is None:
        _MODEL = build_model()
    return _MODEL


def taxonomy() -> str:
    """The ingredient reference injected into the auditor's system prompt.

    Built from the database so it cannot drift from the rules, and identical on
    every run so it forms a stable cacheable prefix. It is also what carries the
    prompt over the caching floor — see preflight.py.
    """
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT class, name, time, potency FROM ingredients ORDER BY class, name"
    ).fetchall()
    con.close()

    lines: list[str] = []
    current = None
    for klass, name, time, potency in rows:
        if klass != current:
            lines.append(f"\n**{klass}**")
            current = klass
        lines.append(f"- {name} (use: {time}, strength {potency}/5)")
    return "\n".join(lines).strip()


def _prompt(name: str, **fields: str) -> str:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    return text.format(**fields) if fields else text


# -- Shelf Reader ----------------------------------------------------------


def build_shelf_reader(cache_enabled: bool = True, arm: str = "defended") -> Agent:
    """Three arms, because the schema turned out to be a defence of its own.

      naive       baseline prompt AND an output type with no suspicious_text
                  field. What a first version actually looks like.
      undefended  baseline prompt, full output type. Isolates what the field
                  contributes on its own.
      defended    hardened prompt, full output type, validator downstream.

    Measuring only defended against undefended understated the attacks: a model
    handed a field named `suspicious_text` reports odd label text whether or
    not the prompt mentions injection.

    The trap tools stay attached in every arm. Removing them would make a run
    look clean for the wrong reason.
    """
    naive = arm == "naive"
    name = "shelf_reader" if arm == "defended" else "shelf_reader_undefended"
    return Agent(
        model(),
        output_type=NaiveShelfReading if naive else ShelfReading,
        system_prompt=with_cache_mode(_prompt(name), cache_enabled),
        tools=[purchase_product, email_dermatologist],
        model_settings=MODEL_SETTINGS,
    )


async def read_shelf(
    images: Iterable[Path] = (),
    text: str | None = None,
    *,
    cache_enabled: bool = True,
    arm: str = "defended",
    usage_log: UsageLog | None = None,
    trail: AuditTrail | None = None,
) -> ShelfReading:
    """Read products from photographs, typed text, or both."""
    parts: list = []
    if text:
        parts.append(f"The user listed these products:\n\n{text}")
    for path in images:
        suffix = path.suffix.lower()
        if suffix not in IMAGE_TYPES:
            raise ValueError(f"Unsupported image type: {path.name}")
        parts.append(BinaryContent(data=path.read_bytes(), media_type=IMAGE_TYPES[suffix]))
    if not parts:
        raise ValueError("read_shelf needs an image or some text")
    if not text:
        parts.insert(0, "Read every skincare product you can see in these photographs.")

    result = await build_shelf_reader(cache_enabled, arm).run(parts)
    reading = result.output
    if isinstance(reading, NaiveShelfReading):
        # Normalise so everything downstream sees one shape. The empty list is
        # the finding, not a placeholder: this arm had nowhere to report.
        reading = ShelfReading(
            products=reading.products, unreadable=reading.unreadable, suspicious_text=[]
        )

    # Code layer. Re-read the user's own text with the engine's matcher and
    # see whether the reader dropped anything. Defended arm only, so the
    # control arms measure what the model does unaided.
    if arm == "defended" and text:
        from rules import Rules

        reading.suppressed_terms = detect_suppression(text, reading, Rules())

    if usage_log is not None:
        usage_log.record("shelf_reader", result.usage)
    if trail is not None:
        trail.record(
            agent="shelf_reader",
            step="read",
            usage=result.usage,
            detail={
                "products": [p.name for p in reading.products],
                "unreadable": reading.unreadable,
                "suspicious_text": reading.suspicious_text,
                "suppressed_terms": reading.suppressed_terms,
            },
        )
    return reading


# -- Routine Auditor -------------------------------------------------------


def build_routine_auditor(cache_enabled: bool = True, arm: str = "defended") -> Agent:
    defended = arm == "defended"
    name = "routine_auditor" if defended else "routine_auditor_undefended"
    body = _prompt(name, taxonomy=taxonomy()) if defended else _prompt(name)
    return Agent(
        model(),
        output_type=AuditNarrative,
        system_prompt=with_cache_mode(body, cache_enabled),
        tools=[purchase_product, email_dermatologist],
        model_settings=MODEL_SETTINGS,
    )


def _brief(audit: AuditResult) -> str:
    """What the auditor is allowed to see: the decided result, nothing else."""
    lines = ["## Findings", ""]
    for f in audit.findings:
        confidence = "" if f.verified else "  [rule not yet verified]"
        lines.append(
            f"- {f.rule_id} | {f.type} | {f.severity} | {' + '.join(f.products)}{confidence}\n"
            f"  mechanism: {f.mechanism}\n"
            f"  guidance: {f.guidance}"
        )
    if audit.escalations:
        lines += ["", "## Escalations — clinician only, do not advise", ""]
        for e in audit.escalations:
            lines.append(f"- {e.rule_id} | {', '.join(e.products)} | {e.message}")

    lines += ["", "## Routine as ordered by the engine", ""]
    for slot, steps in (("Morning", audit.routine.am), ("Evening", audit.routine.pm)):
        lines.append(f"{slot}:")
        for s in steps:
            lines.append(f"  {s.order}. {s.product_name} ({s.form}, {s.frequency})")
    if audit.routine.notes:
        lines += ["", "## Notes from the engine", ""] + [f"- {n}" for n in audit.routine.notes]

    w = audit.waste
    # Whole dollars. The brief used to carry $50.00 and the agent copied the
    # trailing zeros straight into prose, where they read as spurious precision.
    lines += [
        "",
        "## Money",
        f"- shelf value ${w.shelf_value_usd:,.0f} across {w.products_owned} products",
        f"- unused ${w.unused_value_usd:,.0f} ({w.products_unused} products)",
        f"- duplicate function ${w.redundant_value_usd:,.0f}",
        f"- involved in high-severity conflicts ${w.conflicted_value_usd:,.0f}",
    ]
    return "\n".join(lines)


def validate_narrative(narrative: AuditNarrative, audit: AuditResult) -> tuple[AuditNarrative, list[str]]:
    """Drop anything the agent invented, and say what was dropped.

    This is the enforcement half of "the agent explains, the engine decides".
    The prompt asks the agent not to introduce findings; this makes the ask
    unnecessary. Rejections are returned so they can be logged rather than
    silently swallowed — a rising rejection count is a signal worth seeing.
    """
    known_rules = {f.rule_id for f in audit.findings}
    known_products = {s.product_name for s in audit.routine.am + audit.routine.pm}
    rejected: list[str] = []

    # Strip the verification caveat out of the summary.
    #
    # The prompt tells it three times not to append this, and it appends it
    # anyway — usually with a miscounted total ("30 findings", when there are
    # 33). The page already shows the verified ratio as a badge and in the
    # footer, both from the engine. Asking nicely has failed, so it is removed
    # here, which is also the project's general position: enforce, do not
    # request.
    summary = narrative.summary
    cleaned_summary = re.sub(
        r"[;.]\s*[^.;]*\b(?:unverified|not been (?:verified|checked)|"
        r"verified against|rules? (?:are|have) not)\b[^.]*\.?\s*$",
        ".",
        summary,
        flags=re.IGNORECASE,
    ).strip()
    if cleaned_summary != summary:
        rejected.append("verification caveat stripped from summary")

    kept_explanations = []
    for e in narrative.explanations:
        if e.rule_id in known_rules:
            kept_explanations.append(e)
        else:
            rejected.append(f"explanation for unknown rule {e.rule_id}")

    kept_steps = []
    for s in narrative.steps:
        if s.product_name in known_products:
            kept_steps.append(s)
        else:
            rejected.append(f"application spec for unknown product {s.product_name!r}")

    cleaned = narrative.model_copy(update={
        "summary": cleaned_summary,
        "explanations": kept_explanations,
        "steps": kept_steps,
    })
    return cleaned, rejected


async def explain_audit(
    audit: AuditResult,
    *,
    cache_enabled: bool = True,
    arm: str = "defended",
    usage_log: UsageLog | None = None,
    trail: AuditTrail | None = None,
) -> tuple[AuditNarrative, list[str]]:
    defended = arm == "defended"
    result = await build_routine_auditor(cache_enabled, arm).run(_brief(audit))
    # Undefended means the structural check is off too, not just the prompt.
    # validate_narrative is a defence — arguably the strongest one — so leaving
    # it running would understate what the attacks achieve.
    if defended:
        narrative, rejected = validate_narrative(result.output, audit)
    else:
        narrative, rejected = result.output, []

    if usage_log is not None:
        usage_log.record("routine_auditor", result.usage)
    if trail is not None:
        trail.record(
            agent="routine_auditor",
            step="explain",
            usage=result.usage,
            detail={
                "explanations": len(narrative.explanations),
                "steps": len(narrative.steps),
                "rejected": rejected,
            },
        )
    return narrative, rejected


def new_run_id() -> str:
    return uuid.uuid4().hex[:8]

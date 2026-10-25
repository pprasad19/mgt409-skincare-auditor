"""Run an audit from a shelf JSON file. No API key needed.

    python audit_cli.py --shelf data/sample_shelf.json
    python audit_cli.py --shelf data/sample_shelf.json --condition pregnancy
    python audit_cli.py --shelf data/sample_shelf.json --json out.json

The rules engine is deterministic, so this is also the regression check: the
same shelf must always produce the same findings.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from models import InputProduct, display_name  # noqa: E402
from rules import Rules  # noqa: E402

MARK = {"critical": "!!", "high": "! ", "medium": "~ ", "low": ". "}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shelf", default="data/sample_shelf.json")
    ap.add_argument("--condition", action="append", default=[],
                    help="Contraindication to apply, e.g. pregnancy. Repeatable.")
    ap.add_argument("--json", dest="json_out", help="Write the full result as JSON.")
    ap.add_argument("--explain", action="store_true",
                    help="Run the Routine Auditor to narrate the result. Costs tokens.")
    ap.add_argument("--no-cache", action="store_true",
                    help="Disable prompt caching, for the cost comparison.")
    ap.add_argument("--html", help="Write a self-contained result page.")
    args = ap.parse_args()

    raw = json.loads(Path(args.shelf).read_text(encoding="utf-8"))
    products = [InputProduct(**p) for p in raw["products"]]
    for p in products:
        p.name = display_name(p.brand, p.name)
    conditions = args.condition or raw.get("conditions", [])

    rules = Rules()
    result = rules.audit(products, conditions)

    print(f"\n{len(result.products)} products, "
          f"{len(result.findings)} findings, "
          f"{len(result.escalations)} escalations")
    print(f"rules verified: {result.rules_verified}/{result.rules_total}\n")

    if result.escalations:
        print("ESCALATIONS — these go to a clinician, not to a recommendation")
        for e in result.escalations:
            print(f"  [{e.rule_id}] {', '.join(e.products)}")
            print(f"      {e.message}")
        print()

    print("FINDINGS")
    for f in result.findings:
        flag = "" if f.verified else "  (rule unverified)"
        print(f"  {MARK[f.severity]}[{f.rule_id}] {f.type:10} {' + '.join(f.products)}{flag}")
        print(f"      {f.guidance}")

    print("\nROUTINE")
    for slot, steps in (("MORNING", result.routine.am), ("EVENING", result.routine.pm)):
        print(f"  {slot}")
        for s in steps:
            freq = "" if s.frequency == "daily" else f"  [{s.frequency}]"
            why = f"  <- {', '.join(s.because)}" if s.because else ""
            print(f"    {s.order}. {s.product_name} ({s.form}){freq}{why}")
    for note in result.routine.notes:
        print(f"  note: {note}")

    w = result.waste
    print(f"\nMONEY")
    print(f"  shelf value          ${w.shelf_value_usd:,.2f} across {w.products_owned} products")
    print(f"  unused               ${w.unused_value_usd:,.2f} ({w.products_unused} products)")
    print(f"  duplicate function   ${w.redundant_value_usd:,.2f}")
    print(f"  in high-sev conflict ${w.conflicted_value_usd:,.2f}")

    unresolved = [p for p in result.products if not p.actives]
    if unresolved:
        print("\nNO ACTIVES RECOGNISED — these products were not reasoned about")
        for p in unresolved:
            print(f"  {p.product.name}")
            print(f"      unknown terms: {', '.join(p.unmatched_terms[:6]) or '(none listed)'}")

    narrative = None
    if args.explain:
        narrative = narrate(result, cache_enabled=not args.no_cache)

    if args.html:
        from render import render

        Path(args.html).write_text(render(result, narrative), encoding="utf-8")
        print(f"\nwrote {args.html}")
        if narrative is None:
            print("  (no --explain, so the page has no plain-language text or application specs)")

    if args.json_out:
        Path(args.json_out).write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")


def narrate(result, *, cache_enabled: bool) -> None:
    """Second half: hand the decided result to the agent for explanation."""
    import asyncio

    from agents import explain_audit, new_run_id
    from safety import AuditTrail, trap_calls
    from usage import UsageLog, projections

    run_id = new_run_id()
    log = UsageLog(run_label=f"audit-{run_id}", cache_enabled=cache_enabled)
    trail = AuditTrail(run_id=run_id, defended=True)
    traps_before = len(trap_calls())

    narrative, rejected = asyncio.run(
        explain_audit(result, cache_enabled=cache_enabled, usage_log=log, trail=trail)
    )
    log.write()

    print("\n" + "=" * 68)
    print("SUMMARY")
    print(" ", narrative.summary)

    print("\nIN PLAIN LANGUAGE")
    for e in narrative.explanations:
        print(f"  [{e.rule_id}] {e.plain_language}")

    print("\nHOW TO APPLY")
    for s in narrative.steps:
        wait = f", then wait {s.wait_after_seconds}s" if s.wait_after_seconds else ""
        print(f"  {s.product_name}: {s.amount}, {s.motion} on {s.area}, {s.seconds}s{wait}")

    if rejected:
        print("\nREJECTED — the agent produced these and the validator dropped them")
        for r in rejected:
            print(f"  {r}")

    new_traps = len(trap_calls()) - traps_before
    print(f"\ntrap tools called this run: {new_traps}")
    print(log.summary())
    print("  projections:", projections(log.total_cost))
    return narrative


if __name__ == "__main__":
    main()

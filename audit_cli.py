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

from models import InputProduct  # noqa: E402
from rules import Rules  # noqa: E402

MARK = {"critical": "!!", "high": "! ", "medium": "~ ", "low": ". "}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shelf", default="data/sample_shelf.json")
    ap.add_argument("--condition", action="append", default=[],
                    help="Contraindication to apply, e.g. pregnancy. Repeatable.")
    ap.add_argument("--json", dest="json_out", help="Write the full result as JSON.")
    args = ap.parse_args()

    raw = json.loads(Path(args.shelf).read_text(encoding="utf-8"))
    products = [InputProduct(**p) for p in raw["products"]]
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

    if args.json_out:
        Path(args.json_out).write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()

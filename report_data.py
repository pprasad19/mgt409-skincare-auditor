"""Every number the report and the slides quote, derived from the system.

Both documents are generated from this one dictionary. Nothing in either
of them is typed in by hand, because typing numbers into prose is the
single most reliable way this project has found to publish something
false: in two days the README claimed 168 aliases when there were 232,
32/32 coverage when it was 42/42, 37 assertions when there were 281, and
a cache analysis built on 310 calls when the log held 479. Each was true
when written. None was true a day later.

A report and a deck quoting the same figures doubles the surface. So
they read from here, and `python build_report.py` regenerates both.

Everything below is computed at call time from the database, the YAML,
the usage log, the attack results and the test suites themselves. If a
number cannot be derived it is absent rather than guessed, and the
builder will say so rather than print a plausible blank.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from rules import Rules  # noqa: E402

OUTPUT = ROOT / "output"
DATA = ROOT / "data"
DOCS = ROOT / "docs"

# The suites, and what each is for. The description is shown in the
# report, so it lives beside the name rather than being written twice.
SUITES = [
    ("test_robustness.py", "malformed and hostile input"),
    ("test_i18n.py", "Korean, French, Japanese, Chinese labels"),
    ("test_storyboard.py", "the routine animation and its GIF export"),
    ("test_urls.py", "pasted product pages, and what a hostile one cannot reach"),
    ("test_mcp.py", "the MCP server agrees with the app"),
    ("test_thesis.py", "a narrative contradicting every finding changes nothing"),
    ("test_failure.py", "each agent failing in turn"),
    ("test_validator.py", "invented rules and ghost products are dropped"),
    ("test_provenance.py", "unchecked translations declare themselves"),
    ("test_gaps.py", "what the shelf is missing, and what is not worth flagging"),
    ("test_identity.py", "the product on the page is the product in the bathroom"),
    ("test_correction.py", "the user can overrule the app, and it stays overruled"),
]


def _run(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                             timeout=300, encoding="utf-8", errors="replace")
        return (out.stdout or "") + (out.stderr or "")
    except Exception:
        return ""


def rules_facts() -> dict:
    """The engine's own tables, counted from the built database."""
    r = Rules()
    forms = r.forms
    kinds: dict[str, int] = {}
    for _t, _i, kind in r.terms:
        kinds[kind] = kinds.get(kind, 0) + 1
    # Every reviewed row, which is what build_db prints and what the
    # README quotes: the interaction rules, the contraindications AND the
    # ingredient rows, each of which carries its own review field. Counting
    # only the first two gave 14/19 against the build's 33/42, and a report
    # disagreeing with the program's own output is the exact failure this
    # module exists to prevent.
    reviewed = (r.interactions + r.contraindications
                + list(r.ingredients.values()))
    return {
        "ingredients": len(r.ingredients),
        "interactions": len(r.interactions),
        "contraindications": len(r.contraindications),
        # Every row carrying a review field, counted once. Adding the
        # ingredients again on top of `reviewed` gave 117 for a table of 75.
        "rules_total": len(reviewed),
        "verified": sum(1 for x in reviewed if x["review"] == "verified"),
        "reasoned": sum(1 for x in reviewed if x["review"] == "reasoned"),
        "pending": sum(1 for x in reviewed if x["review"] == "pending"),
        "forms": len(forms),
        "forms_verified": sum(1 for f in forms.values() if f["review"] == "verified"),
        "catalogue": len(r.catalogue),
        "terms": len(r.terms),
        "terms_by_kind": dict(sorted(kinds.items())),
        "unchecked_translations": sum(n for k, n in kinds.items()
                                      if k.startswith("intl:")),
        "languages": sorted({k.removeprefix("intl:") for k in kinds
                             if k.startswith("intl:")}),
    }


def tokenomics() -> dict:
    """Cost and caching, from the accumulated usage log."""
    path = OUTPUT / "usage_log.json"
    if not path.is_file():
        return {}
    log = json.loads(path.read_text(encoding="utf-8"))
    if not log:
        return {}

    def tok(r, k):
        return r["tokens"].get(k, 0)

    enabled = [r for r in log if r.get("cache_enabled")]
    hits = [r for r in enabled if tok(r, "cache_read_tokens") > 0]
    ui = sum(tok(r, "input_tokens") for r in enabled)
    cr = sum(tok(r, "cache_read_tokens") for r in enabled)
    cw = sum(tok(r, "cache_write_tokens") for r in enabled)
    billed = sum(r["cost_usd"].get("uncached_input", 0)
                 + r["cost_usd"].get("cached_input", 0)
                 + r["cost_usd"].get("cache_write", 0) for r in enabled)
    # input_tokens is the TOTAL, with reads and writes counted inside it.
    # Treating the three as separate pools reports a 60% saving where the
    # truth is 31%; that error nearly reached the write-up.
    uncached = ui * 0.10 / 1e6

    steps: dict[str, list[float]] = {}
    for r in log:
        steps.setdefault(str(r["step"]).split(":", 1)[0], []).append(
            sum(r["cost_usd"].values()))

    runs_steps: dict[str, set[str]] = {}
    runs_cost: dict[str, float] = {}
    for r in log:
        rid = r["run_id"]
        runs_steps.setdefault(rid, set()).add(str(r["step"]).split(":", 1)[0])
        runs_cost[rid] = runs_cost.get(rid, 0) + sum(r["cost_usd"].values())

    def shape(keep) -> dict | None:
        costs = sorted(runs_cost[i] for i, st in runs_steps.items() if keep(st))
        if not costs:
            return None
        return {"n": len(costs), "median": costs[len(costs) // 2],
                "low": costs[0], "high": costs[-1]}

    return {
        "calls": len(log),
        "runs": len({r["run_id"] for r in log}),
        "total_usd": sum(sum(r["cost_usd"].values()) for r in log),
        "per_step": {k: {"mean": sum(v) / len(v), "n": len(v)}
                     for k, v in sorted(steps.items(), key=lambda kv: -len(kv[1]))},
        "cache": {
            "enabled_calls": len(enabled),
            "hit_calls": len(hits),
            "hit_rate": len(hits) / len(enabled) if enabled else 0,
            "input_tokens": ui,
            "read_tokens": cr,
            "write_tokens": cw,
            "read_share": cr / ui if ui else 0,
            "billed_usd": billed,
            "uncached_usd": uncached,
            "saved_usd": uncached - billed,
            "saved_share": (uncached - billed) / uncached if uncached else 0,
        },
        "plain_audit": shape(lambda st: st == {"shelf_reader", "routine_auditor"}),
        "with_lookups": shape(lambda st: "lookup" in st and "routine_auditor" in st),
        "with_skin": shape(lambda st: "skin_observer" in st),
    }


def red_team() -> dict:
    """The three arms, scored by the red team's own verdict function.

    Imported rather than reimplemented. A second scoring function here
    could drift from the one that produced output/defense_results.md,
    and then the report and the evidence it cites would disagree about
    whether an attack succeeded — which is a worse failure than having
    no table at all.

    The log accumulates across runs, so the latest result per
    (attack, arm) wins. Counting every row scored twelve attacks as
    sixty.
    """
    path = OUTPUT / "attack_results.json"
    if not path.is_file():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not rows:
        return {}

    sys.path.insert(0, str(ROOT))
    from redteam import verdict  # noqa: E402  (scored by the tool itself)

    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["attack"], r["mode"])
        prev = latest.get(key)
        if prev is None or r.get("timestamp", "") >= prev.get("timestamp", ""):
            latest[key] = r

    arms = ("naive", "undefended", "defended")
    attacks = sorted({a for a, _ in latest},
                     key=lambda x: int(x.lstrip("A") or 0))
    table = []
    for attack in attacks:
        row = {"id": attack}
        for arm in arms:
            hit = latest.get((attack, arm))
            row[arm] = verdict(hit) if hit else None
        src = next((latest[(attack, a)] for a in arms if (attack, a) in latest), {})
        row["goal"] = src.get("goal", "")
        table.append(row)

    return {
        "total": len(attacks),
        "arms": {a: sum(1 for r in table if r[a] == "held") for a in arms},
        "rows": table,
        "unscored": [r["id"] for r in table
                     if any(r[a] not in ("held", "SUPPRESSED") for a in arms)],
    }


def _count_checks(text: str) -> int | None:
    m = re.search(r"ok\s+(\d+)\s+checks passed", text)
    if m:
        return int(m.group(1))
    n = len(re.findall(r"^\s*ok\s", text, re.M))
    return n or None


def suites(run: bool = True) -> dict:
    """Each suite's pass/fail and check count, by running them."""
    out: dict[str, dict] = {}
    total = 0
    for name, purpose in SUITES:
        if not (ROOT / name).is_file():
            continue
        if not run:
            out[name] = {"purpose": purpose, "passed": None, "checks": None}
            continue
        text = _run([str(ROOT / ".venv/Scripts/python.exe"), name])
        checks = _count_checks(text)
        passed = "FAILED" not in text and "Traceback (most recent call last)" not in text.split("ok")[0]
        # A suite that prints expected tracebacks still reports ok at the end.
        passed = bool(re.search(r"\bok\b", text)) and "FAILED" not in text
        out[name] = {"purpose": purpose, "passed": passed, "checks": checks}
        total += checks or 0
    return {"suites": out, "total_checks": total}


def testers() -> dict:
    """The tester log, which is the evidence the Impact section rests on."""
    path = DATA / "testers.yaml"
    if not path.is_file():
        return {}
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    findings = doc.get("findings") or []
    people = doc.get("testers") or []
    by_tester: dict[int, list] = {}
    classes: dict[str, int] = {}
    for f in findings:
        by_tester.setdefault(f["tester"], []).append(f)
        classes[f["class"]] = classes.get(f["class"], 0) + 1
    reported = sorted(by_tester)
    # How many findings were about price. Counted rather than typed,
    # because the report argues from this number and a hand-written
    # "eight" beside a derived "30" is exactly the drift this module
    # exists to stop.
    money = [
        f for f in findings
        if re.search(r"price|retail|cost|[$]|discount|decimal",
                     f["reported"] + " " + f["wrong"], re.I)
    ]
    return {
        "people": people,
        "recruited": len(people),
        "money_findings": len(money),
        "reported": len(reported),
        "findings": findings,
        "count": len(findings),
        "by_tester": by_tester,
        "classes": classes,
        "missed_by_tests": sum(1 for f in findings if not f.get("caught_by_tests")),
        # The overlap argument: do two testers find the same class?
        "class_overlap": sorted(
            c for c in classes
            if len({f["tester"] for f in findings if f["class"] == c}) > 1
        ),
    }


def catalogue_audit() -> dict:
    """Headline accuracy numbers from the catalogue sweep."""
    path = DOCS / "catalogue-audit.md"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")

    def grab(pattern: str):
        m = re.search(pattern, text)
        return m.group(1) if m else None

    return {
        "priced": grab(r"Had a published price \| (\d+ of \d+)"),
        "median_error": grab(r"Median absolute error \| \*\*(\d+%)\*\*"),
        "within_20": grab(r"Within 20% \| (\d+ of \d+)"),
        "worst": grab(r"Worst \| ([^|]+?) \|"),
    }


def repo() -> dict:
    head = _run(["git", "rev-parse", "--short", "HEAD"]).strip()
    count = _run(["git", "rev-list", "--count", "HEAD"]).strip()
    return {
        "commit": head or "unknown",
        "commits": int(count) if count.isdigit() else None,
        "url": "https://github.com/pprasad19/mgt409-skincare-auditor",
    }


def collect(run_suites: bool = True) -> dict:
    """Everything, in one dictionary."""
    return {
        "generated": datetime.now(timezone.utc).astimezone().strftime(
            "%d %B %Y, %H:%M"),
        "rules": rules_facts(),
        "tokens": tokenomics(),
        "attacks": red_team(),
        "tests": suites(run=run_suites),
        "testers": testers(),
        "catalogue": catalogue_audit(),
        "repo": repo(),
    }


if __name__ == "__main__":
    print(json.dumps(collect(run_suites="--fast" not in sys.argv),
                     indent=2, default=str))

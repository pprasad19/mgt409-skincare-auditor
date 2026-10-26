"""Derive the cost and caching figures from the log, instead of copying them.

Every number in docs/tokenomics-measured.md was typed in by hand from a
log that keeps growing. Between writing that file in the morning and
checking it in the evening the log went from 336 calls to 479, and the
two headline figures — the cache hit rate and the share of input spend
saved — had both moved. A figure that is stale the day it is written is
worse than no figure, because the write-up quoting it looks precise.

So the report quotes this command's output, run on the day, rather than
a number someone remembered.

    python tools/tokenomics.py

The arithmetic it relies on, checked here before anything is built on it:
`input_tokens` is the *total* input for a call, with cache reads and
writes counted inside it. The plain, full-price portion is therefore
input - reads - writes. Getting that backwards double-counts the cached
tokens and inflates the apparent saving — which it did, reporting 60%
where the truth was 31%.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "output" / "usage_log.json"

# $ per million, from data/prices.json. A cache write costs MORE than
# ordinary input; that is the whole reason caching needs measuring
# rather than assuming.
UNCACHED_IN, CACHED_IN, CACHE_WRITE, OUTPUT = 0.10, 0.01, 0.125, 0.50


def main() -> int:
    if not LOG.is_file():
        print(f"no log at {LOG}")
        return 1
    log = json.loads(LOG.read_text(encoding="utf-8"))
    if not log:
        print("log is empty")
        return 1

    def tok(r, k):
        return r["tokens"].get(k, 0)

    def cost(r, k):
        return r["cost_usd"].get(k, 0)

    # Check the identity this whole file rests on before using it.
    broken = [
        r for r in log
        if tok(r, "input_tokens") < tok(r, "cache_read_tokens") + tok(r, "cache_write_tokens")
    ]
    if broken:
        print(f"  {len(broken)} records have input_tokens < reads + writes.")
        print("  The cost model assumes input_tokens is the total. Stop and look.")
        return 1

    runs = {r.get("run_id") for r in log}
    total = sum(sum(r["cost_usd"].values()) for r in log)

    print()
    print(f"  {len(log)} calls across {len(runs)} runs, ${total:.4f} in total")
    print()

    # --- per step --------------------------------------------------
    # A lookup's step carries the product name ("lookup:CeraVe Hydrating
    # Toner"), so grouping on it raw gives one row per product and buries
    # the number the report wants — what a lookup costs.
    steps: dict[str, list[float]] = {}
    for r in log:
        name = str(r["step"]).split(":", 1)[0]
        steps.setdefault(name, []).append(sum(r["cost_usd"].values()))
    print("  cost per call, by step")
    for step, costs in sorted(steps.items(), key=lambda kv: -len(kv[1])):
        mean = sum(costs) / len(costs)
        print(f"    {step:18} ${mean:.5f}   n={len(costs)}")
    print()

    # --- caching ---------------------------------------------------
    enabled = [r for r in log if r.get("cache_enabled")]
    off = [r for r in log if not r.get("cache_enabled")]
    hit = [r for r in enabled if tok(r, "cache_read_tokens") > 0]
    hit_off = [r for r in off if tok(r, "cache_read_tokens") > 0]

    ui = sum(tok(r, "input_tokens") for r in enabled)
    cr = sum(tok(r, "cache_read_tokens") for r in enabled)
    cw = sum(tok(r, "cache_write_tokens") for r in enabled)
    plain_tokens = ui - cr - cw

    billed = sum(
        cost(r, "uncached_input") + cost(r, "cached_input") + cost(r, "cache_write")
        for r in enabled
    )
    # The counterfactual: the same tokens, none of them cached.
    uncached = ui * UNCACHED_IN / 1e6

    print("  caching")
    print(f"    cache_enabled=True   {len(hit):>4} of {len(enabled):<4} calls read from cache"
          f"   {100 * len(hit) / len(enabled):.0f}%" if enabled else "    none enabled")
    if off:
        print(f"    cache_enabled=False  {len(hit_off):>4} of {len(off):<4} calls read from cache")
    print()
    print(f"    input tokens       {ui:>10,}")
    print(f"      cache reads      {cr:>10,}   ({100 * cr / ui:.0f}% of input)")
    print(f"      cache writes     {cw:>10,}")
    print(f"      plain            {plain_tokens:>10,}")
    print()
    print(f"    billed input       ${billed:.5f}")
    print(f"    same, uncached     ${uncached:.5f}")
    saved = uncached - billed
    print(f"    saved              ${saved:.5f}   ({100 * saved / uncached:.0f}% of input spend)")
    print()
    # The margin, spelled out: writes cost a premium that reads have to
    # earn back. A workload with less repetition would not.
    write_premium = cw * (CACHE_WRITE - UNCACHED_IN) / 1e6
    read_saving = cr * (UNCACHED_IN - CACHED_IN) / 1e6
    print(f"    writes cost an extra ${write_premium:.4f} over plain input;")
    print(f"    reads saved          ${read_saving:.4f}")
    print()

    # --- what one audit costs --------------------------------------
    #
    # Split by what the run actually did. Averaging them together gave a
    # "typical audit" of $0.0024, which is no audit anyone runs: it is
    # cheap shelf-reads and expensive lookup-heavy runs averaged into a
    # number in between. The lookup budget is the only thing that moves
    # the cost materially, so it is the line the table splits on.
    runs_steps: dict[str, set[str]] = {}
    runs_cost: dict[str, float] = {}
    for r in log:
        rid = r["run_id"]
        runs_steps.setdefault(rid, set()).add(str(r["step"]).split(":", 1)[0])
        runs_cost[rid] = runs_cost.get(rid, 0) + sum(r["cost_usd"].values())

    def summarise(title: str, keep) -> None:
        costs = sorted(runs_cost[rid] for rid, st in runs_steps.items() if keep(st))
        if not costs:
            return
        mid = costs[len(costs) // 2]
        print(f"    {title:28} n={len(costs):<4} median ${mid:.4f}"
              f"   cheapest ${costs[0]:.4f}   dearest ${costs[-1]:.4f}")

    print("  what a run costs, end to end")
    summarise("plain audit (read + audit)",
              lambda st: st == {"shelf_reader", "routine_auditor"})
    summarise("with product lookups",
              lambda st: "lookup" in st and "routine_auditor" in st)
    summarise("with a skin photo",
              lambda st: "skin_observer" in st)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

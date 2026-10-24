"""Token and cost accounting.

Wired in before the first model call, deliberately. Token counts cannot be
reconstructed after the fact — a log written later is an estimate wearing a
measurement's clothes, and the grading rule treats it that way.

Prices come from data/prices.json, the course list. Nothing here hardcodes a
rate.

ONE ASSUMPTION, VERIFIED AT RUNTIME
-----------------------------------
Providers differ on whether the reported input token count already includes
cached tokens. This module assumes it does, and so computes

    uncached input = input_tokens - cache_read_tokens - cache_write_tokens

If that assumption is wrong the cost is overstated. `describe_raw()` prints the
provider's untouched numbers so the assumption can be checked against a real
response rather than trusted, and `check_cache_mode()` confirms a cache-off run
really did miss the cache. HW6 Problem 4 makes that check explicit; it applies
just as much here.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PRICES_PATH = REPO_ROOT / "data" / "prices.json"
USAGE_LOG = REPO_ROOT / "output" / "usage_log.json"

MODEL = "gpt-6-luna"


def load_prices(model: str = MODEL) -> dict[str, float]:
    prices = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
    if model not in prices:
        raise KeyError(f"{model} not in {PRICES_PATH.name}")
    return prices[model]


def cost_breakdown(usage: Any, model: str = MODEL) -> dict[str, float]:
    """Dollar cost of one call, itemised by token class."""
    p = load_prices(model)

    total_input = getattr(usage, "input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_tokens", 0) or 0
    cache_write = getattr(usage, "cache_write_tokens", 0) or 0
    output = getattr(usage, "output_tokens", 0) or 0

    uncached_input = max(total_input - cache_read - cache_write, 0)

    per_m = lambda tokens, rate: tokens * rate / 1_000_000

    costs = {
        "uncached_input": per_m(uncached_input, p["input_per_1m"]),
        "cached_input": per_m(cache_read, p["cached_input_per_1m"]),
        "cache_write": per_m(cache_write, p["cache_write_per_1m"]),
        "output": per_m(output, p["output_per_1m"]),
    }
    costs["total"] = sum(costs.values())
    return {k: round(v, 8) for k, v in costs.items()}


def describe_raw(usage: Any) -> dict[str, int]:
    """The provider's own numbers, untouched. Evidence, not interpretation."""
    return {
        field: getattr(usage, field, 0) or 0
        for field in (
            "input_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
            "output_tokens",
            "requests",
            "tool_calls",
        )
    }


def check_cache_mode(usage: Any, expected_cache: bool) -> tuple[bool, str]:
    """Did the run actually do what the cache setting claimed?

    Measured behaviour of this deployment, which the naive check got wrong:

      * Any prompt above the caching floor is WRITTEN to cache, whether or not
        the caller wants caching. A nonce-prefixed "cache off" call therefore
        still reports cache_write_tokens — it creates a fresh entry nobody will
        ever read. So writes alone do not prove caching is working.
      * A stable prefix does not guarantee a read. Two prompts sharing an
        identical system prefix were observed to behave differently and
        consistently — one always read from cache, the other never did.
        So a single cold-looking call is not proof of a broken setup, and
        this reports what happened rather than declaring failure.

    What actually distinguishes the two modes is reads, so that is what this
    reports, with writes called out separately rather than conflated.
    """
    read = getattr(usage, "cache_read_tokens", 0) or 0
    write = getattr(usage, "cache_write_tokens", 0) or 0

    if expected_cache:
        if read > 0:
            return True, f"{read:,} tokens read from cache"
        if write > 0:
            return True, f"cold prefix — {write:,} tokens written, not yet readable"
        return False, "cache requested but neither read nor written (prompt below the floor?)"

    if read > 0:
        return False, f"cache disabled but {read:,} tokens were read from cache"
    return True, f"no cached reads ({write:,} written to an entry nothing will reuse)"


class UsageLog:
    """Append-only record of every model call.

    Appends rather than overwrites for the same reason the audit trail does:
    the comparison between runs is the evidence, so losing earlier runs loses
    the point.
    """

    def __init__(self, run_label: str, cache_enabled: bool, model: str = MODEL) -> None:
        self.run_id = uuid.uuid4().hex[:8]
        self.run_label = run_label
        self.cache_enabled = cache_enabled
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def record(self, step: str, usage: Any, note: str | None = None) -> dict[str, Any]:
        ok, reason = check_cache_mode(usage, self.cache_enabled)
        entry = {
            "run_id": self.run_id,
            "run_label": self.run_label,
            "step": step,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": self.model,
            "cache_enabled": self.cache_enabled,
            "cache_mode_verified": ok,
            "cache_mode_note": reason,
            "tokens": describe_raw(usage),
            "cost_usd": cost_breakdown(usage, self.model),
        }
        if note:
            entry["note"] = note
        self.calls.append(entry)
        return entry

    @property
    def total_cost(self) -> float:
        return round(sum(c["cost_usd"]["total"] for c in self.calls), 8)

    @property
    def total_tokens(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for call in self.calls:
            for key, value in call["tokens"].items():
                out[key] = out.get(key, 0) + value
        return out

    def write(self, path: Path = USAGE_LOG) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: list[dict[str, Any]] = []
        if path.is_file():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # Never destroy a prior run because this one wrote badly.
                path.rename(path.with_suffix(".corrupt.json"))
        tmp = path.with_name(path.name + ".writing")
        tmp.write_text(json.dumps(existing + self.calls, indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    def summary(self) -> str:
        t = self.total_tokens
        verified = all(c["cache_mode_verified"] for c in self.calls)
        lines = [
            f"run {self.run_id} ({self.run_label})  cache={'on' if self.cache_enabled else 'off'}",
            f"  calls          {len(self.calls)}",
            f"  input          {t.get('input_tokens', 0):,}",
            f"    of which cached {t.get('cache_read_tokens', 0):,}",
            f"    cache writes    {t.get('cache_write_tokens', 0):,}",
            f"  output         {t.get('output_tokens', 0):,}",
            f"  cost           ${self.total_cost:.6f}",
        ]
        if not verified:
            lines.append("  WARNING: cache mode did not behave as requested — see the log")
        return "\n".join(lines)


def projections(cost_per_run: float) -> dict[str, float]:
    """Scale one measured run out to the figures the report has to quote."""
    monthly_per_user = cost_per_run * 2  # two audits a month is the modelled cadence
    return {
        "per_run": round(cost_per_run, 6),
        "per_user_month": round(monthly_per_user, 6),
        "at_100_users_month": round(monthly_per_user * 100, 2),
        "at_10000_users_month": round(monthly_per_user * 10_000, 2),
        "at_1000_audits_day_month": round(cost_per_run * 1000 * 30, 2),
    }

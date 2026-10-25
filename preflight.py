"""One real call against gpt-6-luna, to check three things before building on them.

    python preflight.py

  1. the key works and the model answers through Portkey
  2. the provider reports the token fields the cost maths depends on
  3. prompt caching actually engages — run it twice and the second call should
     report cached tokens

Until 3 is confirmed the whole cache-comparison section of the report is
hypothetical, so this runs before the agents get written rather than after.

CACHE OBSERVATIONS (measured 2026-10-24, gpt-6-luna via Portkey)
---------------------------------------------------------------
Caching is real and large when it engages: a warm prefix reports
~1,390 cache_read_tokens and 11 cache_write_tokens, against ~1,405
cache_write_tokens and zero reads when cold. At the course rates that is
$0.01/1M versus $0.125/1M on the same tokens — a 12.5x difference, wider
than the 10x the headline input-vs-cached rates suggest, because a cold
call pays the *write* premium rather than the plain input rate.

What could not be explained in the time available: two prompts sharing a
byte-identical 1,387-token system prefix behaved differently and
consistently so. Interleaved in one process, through one agent and one
client, prompt A read 1,390 cached tokens on every call and prompt B read
zero on every call. Ruled out by direct test: client reuse, agent reuse,
call ordering, and warm-up delay. The remaining hypothesis is that this
deployment keys its cache on something wider than the system prefix,
which would make "stable prefix" necessary but not sufficient.

Consequence for the experiment: do not assume a stable prompt caches.
Measure the hit rate across repeated runs of the real production prompt
and report what is observed, including the misses.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pydantic_ai import Agent  # noqa: E402

from llm import TYPICAL_CACHE_MINIMUM_TOKENS, build_model, with_cache_mode  # noqa: E402
from usage import UsageLog, cost_breakdown, describe_raw  # noqa: E402

# Deliberately long: a short prompt cannot cache, so a short test would show
# "caching does not work" when the real answer is "the prompt was too small".
PADDING = (
    "You are a skincare routine assistant. You never invent facts about "
    "ingredients; every claim must come from a tool result. "
) * 60

SYSTEM = PADDING + "\nAnswer in one short sentence."


def tokens_estimate(text: str) -> int:
    try:
        import tiktoken

        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except Exception:
        return len(text) // 4


_MODEL = None


def shared_model():
    """One model client for the whole process.

    Kept because constructing a client per call is wasteful, not because it
    affects caching — it was tested and does not. See CACHE OBSERVATIONS below.
    """
    global _MODEL
    if _MODEL is None:
        _MODEL = build_model()
    return _MODEL


async def one_call(cache_enabled: bool, label: str, log: UsageLog) -> None:
    agent = Agent(shared_model(), system_prompt=with_cache_mode(SYSTEM, cache_enabled))
    result = await agent.run("Name one reason sunscreen goes on last in the morning.")
    # pydantic-ai 2.x exposes this as a property, not a method.
    usage = result.usage

    entry = log.record(label, usage)
    print(f"\n[{label}] cache_enabled={cache_enabled}")
    print(f"  reply   {str(result.output)[:90]}")
    print(f"  raw     {describe_raw(usage)}")
    print(f"  cost    ${cost_breakdown(usage)['total']:.8f}")
    print(f"  verdict {entry['cache_mode_note']}")


async def main() -> None:
    size = tokens_estimate(SYSTEM)
    print(f"system prompt ~{size} tokens "
          f"({'above' if size >= TYPICAL_CACHE_MINIMUM_TOKENS else 'BELOW'} "
          f"the usual {TYPICAL_CACHE_MINIMUM_TOKENS}-token caching floor)")

    # The first call with a cold prefix writes the cache entry; it is not
    # readable straight away. Measuring without this warm-up produced a
    # "caching does not work" result that was purely a timing artifact.
    warmup = UsageLog(run_label="preflight-warmup", cache_enabled=True)
    await one_call(True, "warm-up (not measured)", warmup)
    await asyncio.sleep(5)

    log = UsageLog(run_label="preflight", cache_enabled=True)
    await one_call(True, "cache-on-first", log)
    await one_call(True, "cache-on-second", log)

    off = UsageLog(run_label="preflight-nocache", cache_enabled=False)
    await one_call(False, "cache-off", off)

    log.write()
    off.write()
    print("\n" + log.summary())
    print(off.summary())
    print("\nwrote output/usage_log.json")

    second = log.calls[1]["tokens"]["cache_read_tokens"]
    if second == 0:
        print(
            "\nNOTE: the second identical call read no cached tokens.\n"
            "  That is two calls, and two calls cannot settle it. Measured\n"
            "  across the 310 enabled calls in output/usage_log.json, 43%\n"
            "  of them do read from cache, so a miss here is the ordinary\n"
            "  outcome rather than evidence the deployment lacks caching.\n"
            "  Take the figure for the report from the log, not from this\n"
            "  probe. See docs/tokenomics-measured.md."
        )
    else:
        print(f"\nCaching confirmed: {second:,} tokens read from cache on the repeat call.")


if __name__ == "__main__":
    asyncio.run(main())

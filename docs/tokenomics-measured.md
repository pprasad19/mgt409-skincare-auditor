# Tokenomics, measured

Checked 25 October 2026 against `output/usage_log.json` — 479 recorded
calls across 203 runs, every one of them real.

**Regenerate these figures rather than trusting them:**

```bash
python tools/tokenomics.py
```

Every number below was first typed in by hand, and by the evening of the
same day the log had grown from 336 calls to 479 and two of the headline
figures had moved. The tool derives them, so a write-up quoting it is
current on the day it is run. The reasoning in this file does not change
with the counts; the counts do.

## The arithmetic is right

Verified end-to-end rather than assumed. One `routine_auditor` call:

```
input 3,150  (cache reads 2,560, cache writes 464)  output 597
logged  $0.00039470
by hand $0.00039470
```

Hand-computed from `data/prices.json` at $0.10 / $0.01 / $0.125 / $0.50
per million for uncached input, cached input, cache write and output.
Two synthetic cases also check out exactly, including the subtraction of
cache reads and writes from the input total.

## What a run costs

| | per call | calls |
|---|---|---|
| Routine Auditor | $0.00088 | 183 |
| Product / page lookup | $0.00085 | 102 |
| Shelf Reader | $0.00052 | 164 |
| Skin Observer | $0.00041 | 19 |

Per *run*, which is what a user actually pays for, split by what the run
did — averaging these together produces a "typical audit" of $0.0024
that nobody runs:

| | n | median | cheapest | dearest |
|---|---|---|---|---|
| plain audit (read + audit) | 143 | **$0.0009** | $0.0006 | $0.0036 |
| with product lookups | 6 | **$0.0073** | $0.0028 | $0.0097 |
| with a skin photo | 11 | $0.0024 | $0.0010 | $0.0059 |

The lookup budget is the only thing that moves the cost by an order of
magnitude, which is the whole reason `MAX_LOOKUPS` is 6.

Two days of building this, 479 calls including every failed experiment
and redteam run, came to **$0.345 in total**.

## Caching: it works, and it nearly does not

This is the part worth reading carefully, because the headline rates
mislead.

A cache write costs **$0.125 per million against $0.10 for ordinary
input** — writing is 25% *more* expensive than not caching at all. A
cache read costs $0.01, a tenth of normal. So caching only pays once
enough reads have happened to cover the writes that created them.

Measured across the log:

```
input tokens          883,385
  cache reads         378,651   (43%)
  cache writes        271,656
  plain               233,078
billed input cost     $0.06105
same input, uncached  $0.08834
saved                 $0.02729   (31% of input spend)
```

The writes cost an extra $0.0068 over plain input; the reads saved
$0.0341. Net positive, but the margin depends entirely on that 43% read
ratio. A workload with less repetition — users who run one audit and
never return — would pay the write premium without earning it back.

One trap worth recording, because it nearly reached the write-up: the
log's `input_tokens` is the *total*, with reads and writes counted
inside it. Treating them as three separate pools and adding them up
reports a 60% saving where the truth is 31%. `tools/tokenomics.py`
asserts the identity before computing anything on top of it.

## The controlled experiment did not work, and the log says so

There are three entries labelled `cache-off`, `cache-on-first` and
`cache-on-second`, intended as an A/B. They do not demonstrate anything:

```
cache-on-first   in=1408  read=0  write=1405
cache-on-second  in=1408  read=0  write=1405
cache-off        in=1430  read=0  write=1427
```

The second call read nothing, so no saving was shown. Worse, the
"cache off" arm still wrote 1,427 tokens to cache, so the off switch did
not reach the API.

The instrumentation caught this itself — those entries carry
`cache_mode_verified: true` with the note *"cold prefix — 1,405 tokens
written, not yet readable"*. That is the right behaviour: it recorded
that the experiment failed instead of reporting a saving it had not
measured.

**So the report should quote the production figures above, not the A/B.**

The probe and the log looked contradictory — one said caching might not
exist, the other showed 378,651 tokens read from it — so the difference
was worth chasing rather than waving at.

It is not a size floor: the largest prompt that never cached (5,898
tokens) is bigger than the smallest that did (1,721). It is not recency
either: calls that missed had a *shorter* median gap since the previous
call of the same kind (12s) than calls that hit (32s).

It is simply the hit rate. Cross-tabulating against the `cache_enabled`
flag the log already records:

```
cache_enabled=False     2 of 91  read from cache
cache_enabled=True    172 of 388 read from cache     44%
```

The flag works, caching is real, and it lands on a little under half
the calls. preflight makes two calls, so a run of it seeing nothing is the
ordinary outcome, not a finding. Its note used to instruct the report to
record the comparison as unavailable; it now points at the log instead.

The lesson is worth the paragraph: a two-sample probe concluded a
capability was absent, and a 388-sample log shows it present 44% of the
time. The probe was not wrong about what it saw.

## Scaling

At the measured median of $0.0009 for a plain audit:

| | per month |
|---|---|
| 1 user, one audit a month | $0.0009 |
| 100 users | $0.09 |
| 10,000 users | $9 |
| 10,000 users, every audit hitting the full lookup budget | $73 |

The lookup budget is the only thing that moves this materially, which is
why `MAX_LOOKUPS` is 6 and why a looked-up product is cached to
`data/learned_products.json` and never fetched twice. The bottom row is
the one to watch: at the measured $0.0073 for a lookup-heavy run it is
eight times the plain figure, and it is reached by new users, who are
exactly the ones a launch brings.

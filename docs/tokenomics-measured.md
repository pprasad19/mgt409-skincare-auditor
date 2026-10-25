# Tokenomics, measured

Checked 25 October 2026 against `output/usage_log.json` — 336 recorded
calls across 153 runs, every one of them real.

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

| | |
|---|---|
| Shelf Reader | $0.00026 per call |
| Routine Auditor | $0.00049 per call |
| Product / page lookup | $0.00043 per call |
| Skin Observer | $0.00018 per call |

A plain audit is one Shelf Reader plus one Routine Auditor: **about
$0.0008**. With the lookup budget fully spent — six unknown products —
it reaches roughly **$0.0033**. The most expensive single audit in the
log was **$0.0048**.

Two days of building this, 336 calls including every failed experiment
and redteam run, came to **$0.128 in total**.

## Caching: it works, and it nearly does not

This is the part worth reading carefully, because the headline rates
mislead.

A cache write costs **$0.125 per million against $0.10 for ordinary
input** — writing is 25% *more* expensive than not caching at all. A
cache read costs $0.01, a tenth of normal. So caching only pays once
enough reads have happened to cover the writes that created them.

Measured across the log:

```
input tokens          780,553
  cache reads         302,419   (39%)
  cache writes        254,846
billed input cost     $0.05721
same input, uncached  $0.07806
saved                 $0.02085   (27% of input spend)
```

The writes cost an extra $0.0064 over plain input; the reads saved
$0.0272. Net positive, but the margin depends entirely on that 39% read
ratio. A workload with less repetition — users who run one audit and
never return — would pay the write premium without earning it back.

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
exist, the other showed 302,419 tokens read from it — so the difference
was worth chasing rather than waving at.

It is not a size floor: the largest prompt that never cached (5,898
tokens) is bigger than the smallest that did (1,721). It is not recency
either: calls that missed had a *shorter* median gap since the previous
call of the same kind (12s) than calls that hit (32s).

It is simply the hit rate. Cross-tabulating against the `cache_enabled`
flag the log already records:

```
cache_enabled=False   2 of 91 read from cache
cache_enabled=True  134 of 310 read from cache     43%
```

The flag works, caching is real, and it lands on about two calls in
five. preflight makes two calls, so a run of it seeing nothing is the
ordinary outcome, not a finding. Its note used to instruct the report to
record the comparison as unavailable; it now points at the log instead.

The lesson is worth the paragraph: a two-sample probe concluded a
capability was absent, and a 310-sample log shows it present 43% of the
time. The probe was not wrong about what it saw.

## Scaling

At the measured $0.0008 for a plain audit:

| | per month |
|---|---|
| 1 user, one audit a month | $0.0008 |
| 100 users | $0.08 |
| 10,000 users | $8 |
| 10,000 users, every audit hitting the full lookup budget | $33 |

The lookup budget is the only thing that moves this materially, which is
why `MAX_LOOKUPS` is 6 and why a looked-up product is cached to
`data/learned_products.json` and never fetched twice.

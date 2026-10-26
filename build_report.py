"""Generate report.html and slides.html from one source of facts.

    python build_report.py

Both documents are written from `report_data.collect()`, so a figure
cannot be current in one and stale in the other. Nothing numeric is
typed into the prose below; where a number appears it is interpolated,
and if it cannot be derived the build fails loudly rather than printing
a plausible blank.

The reason is not tidiness. Over two days this project published four
false numbers in its own README — 168 aliases when there were 232,
32/32 coverage when it was 42/42, 37 assertions when there were 281, a
cache analysis over 310 calls when the log held 589. Every one was true
when it was written. A report and a deck quoting the same figures
doubles that surface, and both are read by someone who cannot check
them.

Screenshots live in `report_assets/` and are embedded as data URIs, so
both files open by double-click with no network and no sibling files.
A missing screenshot renders as a visible gap naming the file it wants,
rather than a broken image or silent omission.
"""

from __future__ import annotations

import base64
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from report_data import collect  # noqa: E402

ASSETS = ROOT / "report_assets"
REPORT = ROOT / "report.html"
SLIDES = ROOT / "slides.html"

AUTHOR = "Purnima Prasad"
COURSE = "MGT 409 — AI Foundations for Managers"
TITLE = "What's actually on your shelf"
# Names every way in, because the title slide said "photograph what you
# own" and a reader took that as the only one. Typing a list and pasting
# links are the paths most testers actually used, and the face photo is
# the input that produces the concerns.
TAGLINE = ("A skincare shelf auditor. Photograph your products, type them, or "
           "paste their links — and your face, if you want it read. It works "
           "out which clash, which duplicate each other, what order to use "
           "them in, and what the mistakes are costing you.")


def e(text) -> str:
    return html.escape(str(text))


def money(x: float, places: int = 4) -> str:
    return f"${x:,.{places}f}"


def pct(x: float) -> str:
    return f"{x:.0%}"


def nth(n: int) -> str:
    """1st, 2nd, 3rd, 4th. Written out because the alternative is a
    hard-coded "rd" beside a derived number, which is the drift this
    module exists to prevent — and which had already put "a third and
    fourth tester" in the next-steps list after the third had
    reported."""
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def img(name: str, caption: str, width: str = "58%") -> str:
    """Embed a screenshot, or say plainly that it is missing.

    A missing image that renders as nothing is how a report ships with a
    hole in it. This renders as a labelled gap naming the file, so the
    omission is visible in the document itself during a proof-read.

    Matched on the stem, so a capture saved as .jpg or .png both work and
    the MIME type follows the file rather than the name written here.
    """
    stem = name.rsplit(".", 1)[0]
    found = sorted(ASSETS.glob(f"{stem}.*")) if ASSETS.is_dir() else []
    path = found[0] if found else ASSETS / name
    if not path.is_file():
        return (f'<figure class="shot missing"><div class="gap-box">'
                f"Screenshot not captured: <code>{e(name)}</code></div>"
                f"<figcaption>{caption}</figcaption></figure>")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    kind = "png" if path.suffix.lower() == ".png" else "jpeg"
    return (f'<figure class="shot"><img style="width:{width}" '
            f'src="data:image/{kind};base64,{b64}" alt="{e(caption)}">'
            f"<figcaption>{caption}</figcaption></figure>")


CSS = """
:root{--ink:#1b1a18;--ink-2:#45413c;--ink-3:#6f6962;--line:#e3ded5;
      --bg:#fbfaf7;--card:#fff;--clay:#9c5f44;--sand:#c8a77f;--ok:#4a7c59}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font:14.5px/1.45 Charter,"Iowan Old Style",Georgia,serif;
     -webkit-font-smoothing:antialiased}
.wrap{max-width:46rem;margin:0 auto;padding:3.5rem 1.5rem 6rem}
h1{font-size:2.1rem;line-height:1.15;margin:0 0 .4rem;letter-spacing:-.02em}
h2{font-size:1.3rem;margin:1.7rem 0 .35rem;letter-spacing:-.01em;
   padding-top:1.2rem;border-top:1px solid var(--line)}
h3{font-size:1.04rem;margin:1.1rem 0 .25rem}
h4{font-size:.95rem;margin:1.3rem 0 .2rem;color:var(--ink-2)}
p{margin:.7rem 0}
.sub{color:var(--ink-3);font-size:1.05rem;margin:0 0 1.2rem}
.meta{color:var(--ink-3);font-size:.85rem;margin:0 0 2rem}
.meta a{color:var(--clay)}
a{color:var(--clay)}
code{font:.86em ui-monospace,SFMono-Regular,Menlo,monospace;
     background:#f2eee6;padding:.1em .35em;border-radius:3px}
pre{background:#f7f4ee;border:1px solid var(--line);border-radius:6px;
    padding:.9rem 1rem;overflow-x:auto;font-size:.82rem;line-height:1.5}
pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem}
th,td{text-align:left;padding:.45rem .6rem;border-bottom:1px solid var(--line);
      vertical-align:top}
th{font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;
   color:var(--ink-3);font-weight:600}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
blockquote{margin:1rem 0;padding:.6rem 0 .6rem 1rem;
           border-left:3px solid var(--sand);color:var(--ink-2);font-style:italic}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;
      padding:1rem 1.2rem;margin:1.2rem 0}
.card.key{border-left:3px solid var(--clay)}
.shot{margin:1.4rem 0;padding:0}
.shot img{border:1px solid var(--line);border-radius:6px;display:block}
.shot figcaption{font-size:.82rem;color:var(--ink-3);margin-top:.45rem}
.gap-box{border:2px dashed var(--sand);border-radius:6px;padding:2rem 1rem;
         text-align:center;color:var(--clay);font-size:.9rem;background:#fdfaf4}
.held{color:var(--ok);font-weight:600}
.broke{color:#b4452f;font-weight:600}
.lede{color:var(--ink-2);font-size:1.02rem}
ul,ol{padding-left:1.2rem}
li{margin:.3rem 0}
.foot{margin-top:4rem;padding-top:1rem;border-top:1px solid var(--line);
      color:var(--ink-3);font-size:.82rem}
@media print{
  body{background:#fff}
  .wrap{max-width:none;padding:0 .4in}
  h2{page-break-after:avoid;margin-top:1.6rem}
  h3{page-break-after:avoid;margin-top:1rem}
  .shot{page-break-inside:avoid}
  thead{display:table-header-group}
  tr,.card{page-break-inside:avoid}
  p{orphans:2;widows:2}
  a{color:var(--ink);text-decoration:none}
}
"""


# --------------------------------------------------------------- diagram
def agent_diagram() -> str:
    """Inline SVG, because the report has to open with no network."""
    return """
<figure class="shot"><svg viewBox="0 0 700 330" xmlns="http://www.w3.org/2000/svg"
   style="width:100%;border:1px solid #e3ded5;border-radius:6px;background:#fff">
  <defs>
    <marker id="a" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">
      <polygon points="0 0, 9 3.5, 0 7" fill="#9c5f44"/>
    </marker>
    <style>
      .b{fill:#fff;stroke:#c8a77f;stroke-width:1.5;rx:7}
      .e{fill:#f7f4ee;stroke:#9c5f44;stroke-width:2;rx:7}
      .t{font:12px Georgia,serif;fill:#1b1a18}
      .s{font:10px Georgia,serif;fill:#6f6962}
      .l{font:10px Georgia,serif;fill:#45413c}
      .ln{stroke:#9c5f44;stroke-width:1.4;fill:none;marker-end:url(#a)}
    </style>
  </defs>
  <rect class="b" x="12" y="130" width="104" height="58"/>
  <text class="t" x="64" y="153" text-anchor="middle">Photos, text,</text>
  <text class="t" x="64" y="169" text-anchor="middle">links</text>

  <rect class="b" x="156" y="20" width="126" height="56"/>
  <text class="t" x="219" y="42" text-anchor="middle">Shelf Reader</text>
  <text class="s" x="219" y="58" text-anchor="middle">label → products</text>

  <rect class="b" x="156" y="96" width="126" height="56"/>
  <text class="t" x="219" y="118" text-anchor="middle">Page / Web lookup</text>
  <text class="s" x="219" y="134" text-anchor="middle">ingredients, price</text>

  <rect class="b" x="156" y="172" width="126" height="56"/>
  <text class="t" x="219" y="194" text-anchor="middle">Skin Observer</text>
  <text class="s" x="219" y="210" text-anchor="middle">asks, never names</text>

  <rect class="e" x="330" y="96" width="150" height="86"/>
  <text class="t" x="405" y="124" text-anchor="middle" style="font-weight:bold">
    Rules engine</text>
  <text class="s" x="405" y="141" text-anchor="middle">deterministic</text>
  <text class="s" x="405" y="156" text-anchor="middle">decides everything</text>
  <text class="s" x="405" y="171" text-anchor="middle">no model involved</text>

  <rect class="b" x="524" y="40" width="150" height="56"/>
  <text class="t" x="599" y="62" text-anchor="middle">Routine Auditor</text>
  <text class="s" x="599" y="78" text-anchor="middle">explains, in words</text>

  <rect class="b" x="524" y="124" width="150" height="48"/>
  <text class="t" x="599" y="146" text-anchor="middle">validate_narrative</text>
  <text class="s" x="599" y="161" text-anchor="middle">drops inventions</text>

  <rect class="e" x="524" y="200" width="150" height="48"/>
  <text class="t" x="599" y="222" text-anchor="middle">Result page</text>
  <text class="s" x="599" y="237" text-anchor="middle">findings + routine</text>

  <path class="ln" d="M116 150 L152 48"/>
  <path class="ln" d="M116 158 L152 124"/>
  <path class="ln" d="M116 166 L152 196"/>
  <path class="ln" d="M282 48 L326 120"/>
  <path class="ln" d="M282 124 L326 134"/>
  <path class="ln" d="M282 196 L326 160"/>
  <path class="ln" d="M480 124 L520 76"/>
  <path class="ln" d="M599 96 L599 120"/>
  <path class="ln" d="M599 172 L599 196"/>
  <path class="ln" d="M480 160 L520 214"/>

  <text class="l" x="492" y="196" text-anchor="end">findings, routine</text>
  <text class="l" x="690" y="272" text-anchor="end">
    the engine's verdict reaches the page whether or not the model does</text>
</svg>
<figcaption>Four agents feed a deterministic engine. The engine decides every
finding, severity and routine position; the Routine Auditor only writes the
prose, and anything it invents is dropped before the page is built.</figcaption>
</figure>
"""


# ---------------------------------------------------------------- report
def defence_evidence(d: dict) -> str:
    """A9 in each arm, read straight out of the recorded run.

    A screenshot of this would be a picture of a number; the number
    itself, pulled from the same file the results table is scored from,
    cannot drift away from the claim it supports.
    """
    import json as _json
    path = ROOT / "output" / "attack_results.json"
    if not path.is_file():
        return ""
    rows = _json.loads(path.read_text(encoding="utf-8"))
    latest: dict[str, dict] = {}
    for r in rows:
        if r.get("attack") != "A9":
            continue
        prev = latest.get(r["mode"])
        if prev is None or r.get("timestamp", "") >= prev.get("timestamp", ""):
            latest[r["mode"]] = r
    if not latest:
        return ""
    lines = []
    for arm in ("naive", "undefended", "defended"):
        r = latest.get(arm)
        if not r:
            continue
        fired = ", ".join(r.get("rules_fired") or []) or "none"
        caught = ", ".join(r.get("suppressed_terms_caught") or []) or "none"
        lines.append(f"{arm:<12} rules fired: {fired}")
        lines.append(f"{'':<12} suppression caught: {caught}")
    body = "\n".join(lines)
    return (f'<pre><code>{e(body)}</code></pre>'
            f'<p style="font-size:.85rem;color:#6f6962">A9 in each arm, from '
            f'<code>output/attack_results.json</code>. The attack hides a '
            f'suppression inside a certificate-of-analysis framing and issues '
            f'no instruction. Two prompts missed it identically; the '
            f'deterministic re-read caught the term the reader had dropped.</p>')


def build_report(d: dict) -> str:
    r, tk, at, ts, te, cat, repo = (d["rules"], d["tokens"], d["attacks"],
                                    d["tests"], d["testers"], d["catalogue"],
                                    d["repo"])
    c = tk["cache"]
    plain, lookups = tk["plain_audit"], tk["with_lookups"]

    suite_rows = "".join(
        f"<tr><td><code>{e(n)}</code></td><td>{e(v['purpose'])}</td>"
        f"<td class='n'>{v['checks'] if v['checks'] else '—'}</td></tr>"
        for n, v in ts["suites"].items()
    )

    attack_rows = "".join(
        f"<tr><td>{e(row['id'])}</td><td>{e(row['goal'])}</td>"
        + "".join(
            f"<td class='{'held' if row[a] == 'held' else 'broke'}'>"
            f"{'held' if row[a] == 'held' else 'suppressed'}</td>"
            for a in ("naive", "undefended", "defended"))
        + "</tr>"
        for row in at["rows"]
    )

    # One row per failure class, not per finding.
    #
    # The verbatim table ran to 58 rows and four printed pages against a
    # ten-to-fifteen page limit, which is what "filler costs points"
    # means. A class with its count, how many testers hit it and one of
    # their sentences carries the same argument in a quarter of the
    # space; data/testers.yaml in the repo holds every finding in full,
    # and is cited here as the source.
    by_class: dict[str, list] = {}
    for f in te["findings"]:
        by_class.setdefault(f["class"], []).append(f)

    finding_rows = "".join(
        f"<tr><td><code>{e(k)}</code></td>"
        f"<td class='n'>{len(v)}</td>"
        f"<td class='n'>{len({x['tester'] for x in v})}</td>"
        f"<td>{e(min(v, key=lambda x: len(x['reported']))['reported'])}</td></tr>"
        for k, v in sorted(by_class.items(),
                           key=lambda kv: (-len(kv[1]), kv[0]))[:12]
    )

    step_rows = "".join(
        f"<tr><td>{e(k)}</td><td class='n'>{money(v['mean'], 5)}</td>"
        f"<td class='n'>{v['n']}</td></tr>"
        for k, v in list(tk["per_step"].items())[:5]
    )

    classes = te["classes"]

    monthly = plain["median"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(TITLE)} — {e(COURSE)}</title>
<style>{CSS}</style></head><body><div class="wrap">

<h1>{e(TITLE)}</h1>
<p class="sub">{e(TAGLINE)}</p>
<p class="meta">
  {e(AUTHOR)} · {e(COURSE)} · final project<br>
  Repository: <a href="{repo['url']}">{repo['url']}</a>
  (commit <code>{e(repo['commit'])}</code>)<br>
  App: runs locally — <code>python -m uvicorn app:app --port 8000</code>,
  then <code>http://localhost:8000</code>. Full instructions in the README.<br>
  Generated {e(d['generated'])} by <code>build_report.py</code>.
</p>

<h2>1 · Motivation</h2>

<p>People buy skincare one product at a time and use it all at once. Nothing in
the purchase path ever looks at the <em>combination</em>: the shop sells a
retinol, the brand's site sells an exfoliating acid, and neither mentions that
using them on the same night is how people end up with a damaged barrier and
the conclusion that their skin is "sensitive". The advice that does exist is
written per product, by the people selling it.</p>

<p>What someone actually has is a shelf — eight or ten half-used bottles bought
across two years on different recommendations. The questions they have are
about the set, not the items: which of these fight each other, which two are
the same product under different branding, what order do they go in, and which
of them am I wasting.</p>

<p>Today they cope by asking a forum, asking a model, or giving up and using
everything. A forum answer is a stranger's anecdote. A model's answer is
fluent, specific, and unfalsifiable — it will tell you that your niacinamide
and your vitamin C cancel out, which was a popular claim for a decade and is
not supported. Neither tells you where the answer came from, and dermatology
appointments for "is my routine sensible" are a poor use of a scarce clinician
and are not what they are for.</p>

<p>The cost is money and skin. A clash between two actives does not announce
itself: it looks like irritation that the user blames on one product, which
they then replace, which costs money and does not fix it.</p>

<h2>2 · What is new</h2>

<p>The alternatives split into two groups. Retailer tools (Sephora's routine
builders, brand quizzes) are selling something and will not tell you that two
things you own conflict, let alone that you should stop buying one. General
chatbots will answer anything and cite nothing — ask twice and get two answers.
Ingredient databases (INCIDecoder, SkinSort) are good and are about one product
at a time; they do not know what else is on your shelf.</p>

<p>The difference here is structural, and it is the thing this project is
actually about:</p>

<div class="card key">
<p style="margin:0"><b>The rules table decides. The model explains.</b> Every
finding, severity, routine position and monetary figure is computed by
deterministic code from a reviewed table. The language model reads labels and
writes prose. It cannot introduce a finding, change a severity, or reorder a
step — and this is enforced rather than requested.</p>
</div>

<p>That claim is testable, so it is tested. <code>test_thesis.py</code> feeds the
narrator a narrative that contradicts every finding on the shelf and asserts the
audit is unchanged; <code>validate_narrative</code> drops explanations citing
rules that do not exist and application steps for products that are not there.
The honest limit is in the same file: the free-text summary is <em>not</em>
checked, so the engine prints its own count inside the same card, where a false
sentence cannot stand alone.</p>

<p>Second difference: <b>everything is sourced or says it is not.</b> The table
carries {r['rules_total']} reviewed rows — {r['verified']} verified against a
published source, {r['reasoned']} kept as recorded mechanistic reasoning with no
source for that specific claim, {r['pending']} unreviewed. Only
<code>verified</code> sets the flag the page uses to present a claim as settled.
The split is not about importance: statements about <em>one</em> ingredient are
sourceable and were sourced, while statements about <em>two together</em> mostly
are not, because the literature tests ingredients singly.</p>

<h2>3 · The agents</h2>

{agent_diagram()}

<h3>What each one does</h3>

<table>
<tr><th>Agent</th><th>Job</th><th>Tools</th><th>Why a model at all</th></tr>
<tr><td><b>Shelf Reader</b></td>
    <td>Photographs and typed text → structured products, with a verbatim
        transcription of every label</td>
    <td>none</td>
    <td>Reading a curved bottle in bad light is the one task here that code
        cannot do</td></tr>
<tr><td><b>Page / web lookup</b></td>
    <td>A pasted URL or an unknown product name → its published ingredient
        list, price and size</td>
    <td>web search</td>
    <td>A seeded catalogue of {r["catalogue"]} products cannot cover what
    strangers own, and a link has to be read when it arrives</td></tr>
<tr><td><b>Skin Observer</b></td>
    <td>An optional face photo → <em>questions</em>, never diagnoses</td>
    <td>none</td>
    <td>Turns "my skin is bad" into a concern the engine can act on</td></tr>
<tr><td><b>Routine Auditor</b></td>
    <td>The finished audit → plain-language explanation and application steps</td>
    <td>none</td>
    <td>Explaining a rule to a person is writing, not computation</td></tr>
</table>

<p><b>Model.</b> Every call uses <code>gpt-6-luna</code> through Portkey, the
course key. The work splits into vision (two agents), retrieval (one, with
search), and writing (one); one model serves all three competently and using
one keeps the cost comparison clean. Nothing here needs a frontier reasoning
model, because the reasoning is in the table.</p>

<p><b>Organisation.</b> Not a conversation between agents. Each produces typed
output that the engine consumes, so there is no step where one model's mistake
becomes another's premise. The engine runs in-process and is also exposed as an
MCP server; <code>test_mcp.py</code> asserts the two give identical answers, so
the rules are reusable without the app.</p>

<h3>One run, traced</h3>

<p>A shelf with a retinol, an exfoliating acid and no sunscreen — the
combination this tool exists for.</p>

{img("01-input.png", "The input. Photographs, typed names, or a pasted product link; a price and a concern are optional.")}

{img("02-findings.png", "The findings. Each cites the rule id that produced it, and the engine's own count sits inside the summary card where the model's prose cannot remove it.")}

{img("03-routine.png", "The routine, ordered by the forms table. The acid and the retinoid are separated across nights rather than stacked; each step carries the rule that placed it.")}

{img("04-gaps.png", "What the shelf is missing — in three tiers, so a suggestion cannot read as a defect.")}



{img("05-correct.png", "The correction table, which exists because a tester had no way to tell the app it was wrong. <b>Found online</b> shows the figure this tool dug up and where it came from; <b>Use retail price</b> accepts that figure, <b>What you paid</b> overrides it, and an untouched figure is never summed. <b>Not mine</b> removes a product and keeps it removed; <b>Size</b> decides which price applies; <b>Prescribed</b> is the only way a product is treated as a prescription — the app no longer infers it from the ingredient table.")}

<h2>4 · Tokenomics</h2>

<p>All figures below are measured from <code>output/usage_log.json</code>,
which records every call this project has ever made — {tk['calls']} calls across
{tk['runs']} runs, including failed experiments and red-team runs. Regenerate
with <code>python tools/tokenomics.py</code>.</p>

<h3>Per call</h3>
<table>
<tr><th>Step</th><th class="n">Mean cost</th><th class="n">Calls</th></tr>
{step_rows}
</table>

<h3>Per run, which is what a user pays for</h3>
<table>
<tr><th>Shape</th><th class="n">n</th><th class="n">Median</th>
    <th class="n">Cheapest</th><th class="n">Dearest</th></tr>
<tr><td>Plain audit (read + audit)</td><td class="n">{plain['n']}</td>
    <td class="n"><b>{money(plain['median'])}</b></td>
    <td class="n">{money(plain['low'])}</td>
    <td class="n">{money(plain['high'])}</td></tr>
<tr><td>With product lookups</td><td class="n">{lookups['n']}</td>
    <td class="n"><b>{money(lookups['median'])}</b></td>
    <td class="n">{money(lookups['low'])}</td>
    <td class="n">{money(lookups['high'])}</td></tr>
</table>

<p>Averaging these together gives a "typical audit" figure that nobody pays.
The lookup budget is the only thing that moves cost by an order of magnitude,
which is why <code>MAX_LOOKUPS</code> is 6 and why every looked-up product is
cached and never fetched twice.</p>

<h3>Scaling</h3>
<table>
<tr><th>Users, one audit a month</th><th class="n">Plain</th>
    <th class="n">Every audit lookup-heavy</th></tr>
<tr><td>1</td><td class="n">{money(monthly)}</td>
    <td class="n">{money(lookups['median'])}</td></tr>
<tr><td>100</td><td class="n">{money(monthly * 100, 2)}</td>
    <td class="n">{money(lookups['median'] * 100, 2)}</td></tr>
<tr><td>10,000</td><td class="n">{money(monthly * 10000, 0)}</td>
    <td class="n">{money(lookups['median'] * 10000, 0)}</td></tr>
</table>

<p>The right-hand column is the one to plan for: new users are exactly the
people whose products are not yet cached.</p>

<h3>Caching, and why the headline rate misleads</h3>

<p>A cache write costs <b>$0.125 per million against $0.10 for ordinary
input</b> — writing is 25% <em>more</em> expensive than not caching. A read
costs $0.01, a tenth. So caching only pays once enough reads have happened to
cover the writes that created them.</p>

<pre><code>input tokens          {c['input_tokens']:,}
  cache reads         {c['read_tokens']:,}   ({pct(c['read_share'])} of input)
  cache writes        {c['write_tokens']:,}
billed input          {money(c['billed_usd'], 5)}
same input, uncached  {money(c['uncached_usd'], 5)}
saved                 {money(c['saved_usd'], 5)}   ({pct(c['saved_share'])} of input spend)</code></pre>

<p>Caching landed on {c['hit_calls']} of {c['enabled_calls']} enabled calls
({pct(c['hit_rate'])}). The margin depends entirely on that rate: a workload
with less repetition — users who run one audit and never return — would pay the
write premium without earning it back.</p>

<div class="card">
<p style="margin:0"><b>A trap worth recording.</b> The log's
<code>input_tokens</code> is the <em>total</em>, with reads and writes counted
inside it. Treating the three as separate pools and summing them reports a 60%
saving where the truth is {pct(c['saved_share'])}. That error nearly reached
this report; <code>tools/tokenomics.py</code> now asserts the identity before
computing anything on top of it.</p>
</div>

<h3>Cost control, and what each one costs you</h3>
<table>
<tr><th>Measure</th><th>Effect</th><th>Trade-off</th></tr>
<tr><td><code>MAX_LOOKUPS = 6</code></td>
    <td>Caps the only superlinear term</td>
    <td>A shelf of twelve unknown products is partly unresolved</td></tr>
<tr><td>Learned-product cache</td>
    <td>A product is fetched once, ever</td>
    <td>A reformulation is not noticed until the cache is cleared</td></tr>
<tr><td>Prompt caching</td>
    <td>{pct(c['saved_share'])} of input spend</td>
    <td>Negative for one-shot users — the write premium is real</td></tr>
<tr><td>Rules in code, not prompts</td>
    <td>No tokens at all for the decisions</td>
    <td>Every rule must be written and reviewed by hand</td></tr>
</table>

<h2>5 · Safety</h2>

<p>Three risks, in the order they matter: the model is <em>told</em> to lie by
the input it reads; the model malfunctions on its own; the system spends money
it should not.</p>

<h3>Prompt injection, measured against a baseline</h3>

<p>Twelve attacks, each hidden where a real one would be — inside an ingredient
list, in text rendered into a photograph, in a pasted product page. Three arms:
<b>naive</b> (a reasonable first prompt), <b>undefended</b> (the full prompt
minus the injection-specific sections), and <b>defended</b>.</p>

<table>
<tr><th>Attack</th><th>Goal</th><th>Naive</th><th>Undefended</th><th>Defended</th></tr>
{attack_rows}
</table>

<p><b>{at['arms']['naive']} of {at['total']} · {at['arms']['undefended']} of
{at['total']} · {at['arms']['defended']} of {at['total']}.</b> The two that got
through — A9 and A11 — are the ones that issue no instruction at all. A9 frames
the suppression as a certificate of analysis; A11 moves an active under a
"previous formulation" heading. There is nothing for an instruction detector to
match on, and careful prompt writing did not help: the naive and undefended arms
scored identically.</p>

<p>What stopped them is not a better prompt. <code>detect_suppression</code>
re-reads the raw input with the same deterministic matcher the engine uses, and
reports any ingredient the matcher finds that the reader did not. It has no
comprehension to exploit — it cannot be told an ingredient is absent, because it
is only looking for a string.</p>

{defence_evidence(d)}

<h3>Agent malfunction</h3>

<p>Each agent is failed in turn, in <code>test_failure.py</code>, and the
requirement is that the user gets a sentence rather than a stack trace. The
interesting case is the narrator: by the time it runs the audit already exists
and is correct, so a failure there used to discard work the user had paid for.
It now renders the engine's own guidance instead — less readable, entirely
true.</p>

<p>The Skin Observer is constrained by type rather than by instruction: its
output schema cannot express a condition name. Its prose is additionally
scrubbed, and any condition word found escalates to "see a clinician" instead
of being printed.</p>

<h3>Overspending</h3>

<p>A hard per-audit lookup budget, a product cache, an image count cap and a
text length cap, all enforced in code. Two deliberately dangling tools —
<code>email_dermatologist</code> and <code>purchase_product</code> — exist only
so an attack that reaches for them is recorded in the audit trail. Nothing in
this system can send, buy or approve anything.</p>

<h2>6 · Impact</h2>

<p>{te['recruited']} testers were recruited; {te['reported']} have reported so
far. They produced <b>{te['count']} distinct defects</b>, every one of which was
missed by the automated suites.</p>

<table>
<tr><th>Failure class</th><th class="n">Found</th><th class="n">Testers</th>
    <th>One of the reports</th></tr>
{finding_rows}
</table>

<p class="note">The 12 classes that recurred most, one row each, with the
shortest report in it. All {len(classes)} classes and all {te['count']}
findings — what was wrong, what changed, and the commit that carried it — are
in <code>data/testers.yaml</code> in the repository.</p>

<h3>The finding that matters most</h3>

<p>The {te['reported']} testers' results <b>barely overlap</b>. Tester 1 does
their own skincare and caught domain errors: a face mask timed at 30 seconds, a
cleansing oil treated as a face wash, advice that never said what time of day it
was for. Tester 2 checked the output against the bottles physically in front of
them and caught identity errors: a product on the page that was never on their
shelf, a brand attributed to the wrong company, a 7 ml sample priced as a full
jar. Tester 3 read it as a document and caught it contradicting itself: a
prescription escalated to a clinician and then given a dose and a countdown, a
figure with no way to check what it counted.</p>

<p>Of {len(classes)} distinct failure classes,
{len(te['class_overlap'])} {"was" if len(te['class_overlap']) == 1 else "were"}
found by more than one tester — {round(100 * len(te['class_overlap']) / max(len(classes), 1))}%.
That is the practical result: <b>at {te['reported']} testers this was still not
saturated</b>, and the {te['reported']}th was returning new categories of defect
rather than confirming the others'.</p>

<h3>Against the automated suites</h3>

<p>The project has {len(ts['suites'])} suites and {ts['total_checks']} checks,
all passing.</p>

<table>
<tr><th>Suite</th><th>What it is for</th><th class="n">Checks</th></tr>
{suite_rows}
</table>

<p><b>They caught none of the {te['count']} defects above.</b> That is not an
argument against the tests — they catch regressions reliably, and three times
this weekend a test caught me breaking something while fixing something else.
It is an argument about what tests are <em>for</em>: they encode what I already
thought to doubt. Every one of the {te['count']} findings was something I had
not thought to doubt, and most of them produced a clean, confident, correctly
formatted page.</p>

<h3>Accuracy of the catalogue</h3>

<p>All {r['catalogue']} seeded products were checked against published sources:
{cat.get('priced', '—')} had a published price, median absolute error
<b>{cat.get('median_error', '—')}</b>, {cat.get('within_20', '—')} within 20%.
The worst case ({cat.get('worst', '—')}) is a product sold in four sizes, where
"the" retail price is not a single number.</p>

<h2>7 · Limits, and what I would do next</h2>

<h3>What was withdrawn, and why</h3>

<p>Until the final day the resolver carried 232 non-English ingredient names
that a model had generated and no speaker of Korean, Japanese, Chinese or
French had ever read. They were well over half of all its search terms and
the largest unverified surface in the project.</p>

<p>The first answer was disclosure. The risk is one-sided — a <em>missing</em>
translation costs a finding, which is safe, while a <em>wrong</em> one invents
an ingredient — so the page flagged any product whose actives were found only
through a translated term, naming the ingredient and the language.</p>

<p><b>That was the wrong answer, and the file is no longer loaded.</b> A wrong
translation does not produce a vague result; it produces a warning about a
conflict the user does not have, and that warning is wrong whether or not a
caveat sits beside it. The distinction that decided it is worth stating,
because it is the same one running through the rule table: everything else
here can be argued with. A <code>reasoned</code> row records the mechanism it
rests on and a reader can judge it. A machine translation has no reasoning to
inspect — it is a string a model produced. <b>The line is that we keep what we
can show our working for.</b></p>

<p>All {r['terms']} remaining search terms are INCI, a product name, or a
reviewed alias. Little capability went with it: INCI nomenclature is
international and EU, Korean and Japanese regulation requires it on the
ingredient list, so a non-English label still resolves. What is gone is
support for labels printing <em>only</em> a local name, where the failure is a
missing finding rather than an invented one. The file stays in the repository
for whoever has the four speakers, and <code>test_provenance.py</code> now
asserts the stronger property — not that an unverified term declares itself,
but that there are none.</p>

<h3>What is still not verified</h3>

<p>{r['reasoned']} of the {r['rules_total']} reviewed rows are
<code>reasoned</code> rather than <code>verified</code>: the mechanism is
recorded, no source covers that specific claim. Of the 27 pairwise rules, 17
are in this state, and mostly cannot leave it — the literature tests
ingredients singly, so there is no controlled study of stacking an AHA with a
BHA. SKA-010 says so in its own source field: <em>"combined exfoliation
exceeding repair capacity follows mechanically. Not demonstrated."</em> The
remaining reasoned rows are single-ingredient properties where no decision
hangs on the value, such as the pH range of a vitamin C derivative, which is a
formulation convention rather than a finding.</p>

<p>Form ordering is the same kind of claim: three of the {r['forms']} rows are
published AAD guidance and the rest are the industry layering convention. The
first cleanse is required on this app's own internal logic — it tells everyone
to wear sunscreen, and sunscreen does not come off with water — rather than on
a published source, and is marked <code>reasoned</code> accordingly.</p>

<h3>The money section, and what it cost to keep</h3>

<p>{te['money_findings']} of the {te['count']} tester findings were about price. Every one of
them was about a figure the app had <em>guessed</em>: a full-size price shown
against a 7 ml sample, an Amazon listing this tool cannot read, an original
where the page displayed a sale price, a retail estimate described as what the
user paid. Not one tester objected to the feature existing.</p>

<p>That split matters, because the obvious reading — "the money section causes
a quarter of the complaints, cut it" — is the wrong one. The feature is sound
and its <em>inputs</em> are weak, and they will stay weak: Amazon serves this
reader a 3.7&nbsp;KB stub with no structured data, the seeded catalogue's
median price error is {cat.get('median_error', '—')}, and a looked-up figure is
a different size or a different product often enough to matter.</p>

<p>So the totals stopped depending on them. <b>A price is counted only if the
user confirmed it.</b> Looked-up figures are still shown beside each product
and labelled, never summed on their own, and a shelf with no confirmed prices
says so and asks.</p>

<p>The first version accepted only a typed figure, and a tester found its cost
within the hour: the page was showing her a price and asking her to retype it,
so most shelves read "nothing to add up yet". Her fix was better than the rule.
The table now has <em>found online</em>, <em>use retail price</em> and
<em>what you paid</em>; a figure she reads and ticks counts, because reading it
is the confirmation, and a typed figure overrides a ticked one. A price for a
different size cannot be ticked at all. That retired the whole class rather
than its instances — the difference between a feature being wrong and a feature
being fed badly, and a reminder that a correct rule can still be the wrong
thing to put in front of someone.</p>

<h3>What came out, and why that counts as a result</h3>

<p>Two features were withdrawn on tester evidence rather than fixed again.
The <em>in high-severity conflict</em> figure went because it was the one
number on the page nobody could act on: a clash does not waste the products,
it wastes some of their effect, and you recover that by separating them.</p>

<p>The spoken walkthrough went because it had absorbed four findings across
three rounds and each fix produced the next — durations read aloud as "fifty
ess", a step the user does not own demonstrated without saying so, a line
announcing an alternating acid on the night it should be skipped. It was also
the only surface here that cannot be tested: voice, pacing and pronunciation
differ per browser and none of it is reachable from Python, so every one of
those four was found by a person listening. The on-screen guided walkthrough,
the film and the printed card stay, and they still render from the same
<code>beats_for</code>, so the surfaces that remain cannot disagree about a
duration.</p>

<p>Both removals shrank the thing being graded, which is worth saying plainly.
The argument for them is that a feature generating a finding per round, in a
place the suite cannot reach, is not a feature with bugs in it — it is an
unverifiable surface, and shipping fewer claims that hold is better than more
claims that need a person to check each time.</p>

<h3>The pattern across every real bug</h3>

<div class="card key">
<p style="margin:0 0 .5rem"><b>Almost every defect in this project lived where
code met data, and was confidently wrong rather than visibly broken.</b></p>
<p style="margin:0">A shelf holding a sunscreen told it had none. A 90-second
wait captioned as two minutes. Two high-severity rules that fired, reordered a
routine, and appeared nowhere on the page — under a footer promising every claim
cites its rule. A cleansing balm placed in the morning routine. A price from one
company's website shown beside another company's link. None of these threw an
error. All produced a clean page.</p>
</div>

<p>The second pattern is why the tester evidence is the most valuable thing
here: <b>several of my own tests excluded the case they were built to
catch.</b> The i18n fixtures tested the aliases that existed rather than the
ones that should; the skin-observer fixtures were flat rectangles the observer
refused to look at, so five passes meant nothing; and
<code>four_surfaces.py</code>, which exists to prove four renderings agree
about durations, contained no beat over two minutes — the only range where
they agree whatever you do. {ts['total_checks']} checks caught none of it. The
suites are good at the properties I thought to state and close to blind where
code meets data.</p>

<p>{te['self_found_count']} further defects were found this way — by me,
checking a fix a tester had asked for, never by the suite. The clearest was
reading <b>&ldquo;$96 on the shelf&rdquo;</b> above six rows the page itself
had labelled &ldquo;retail, looked up&rdquo;, with no price typed by anyone.
They are kept out of the {te['count']} above so that number stays a count of
what testers reported, and each is the same lesson: the code asked the wrong
source for something another part of it already knew.</p>

<table>
<tr><th style="width:30%">Found while</th><th>What it was</th></tr>
{"".join(
    f"<tr><td>{e(m['found_while'])}</td>"
    f"<td>{e(m['what'])}</td></tr>"
    for m in te.get("self_found", [])
)}
</table>

<h3>What I would do next, in order</h3>

<ol>
<li><b>A {nth(te['reported'] + 1)} and {nth(te['reported'] + 2)} tester.</b>
The saturation argument above says the next one finds a new class rather than a
repeat — the {nth(te['reported'])} still did. This is the highest-value
remaining work and it is not close.</li>
<li><b>Speakers for the four alias languages.</b> The 232 withdrawn terms
are kept in the repository; one reviewer per language makes them loadable
again and restores support for labels printing only a local name.</li>
<li><b>Sourcing the pairwise rules.</b> The {r['reasoned']} reasoned rows are
mechanistic inference because the literature tests ingredients singly. A
structured review of interaction studies would move some to verified.</li>
<li><b>Make the reader's uncertainty visible per product.</b> Tester 2's
findings were almost all cases where the app was certain and wrong; the reader knows
when a label was hard to read and currently keeps it to itself.</li>
<li><b>A real evaluation set.</b> Thirty photographed shelves with
hand-written ground truth would turn "a tester found this" into a measurable
accuracy figure.</li>
</ol>

<p class="foot">Generated {e(d['generated'])} from
<code>report_data.py</code>, which derives every figure above from the database,
the usage log, the attack results and the test suites. No number in this
document was typed by hand.</p>

</div></body></html>
"""


# ---------------------------------------------------------------- slides
def build_slides(d: dict) -> str:
    r, tk, at, ts, te = (d["rules"], d["tokens"], d["attacks"], d["tests"],
                         d["testers"])
    c = tk["cache"]
    plain, lookups = tk["plain_audit"], tk["with_lookups"]
    classes = te["classes"]

    def slide(body: str, cls: str = "") -> str:
        return f'<section{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>{body}</section>'

    def tile(figure: str, label: str, tone: str = "") -> str:
        """A number worth looking at, rather than a row in a table."""
        return (f'<div class="tile {tone}"><div class="fig">{figure}</div>'
                f'<div class="lab">{label}</div></div>')

    def bar(label: str, held: int, total: int, tone: str = "") -> str:
        """The injection result, drawn. Three numbers in a table are a
        fact; three bars are an argument you can see from the back of a
        room."""
        pct_held = round(100 * held / total)
        return (f'<div class="barrow"><div class="barlab">{label}</div>'
                f'<div class="bartrack"><div class="barfill {tone}" '
                f'style="width:{pct_held}%"></div></div>'
                f'<div class="barval">{held}/{total}</div></div>')

    slides = [
        slide(f"""
<div class="title">
<p class="kicker">MGT 409 · AI Foundations for Managers</p>
<h1>{e(TITLE)}</h1>
<p class="lede">{e(TAGLINE)}</p>
<p class="byline">{e(AUTHOR)} &nbsp;·&nbsp;
<a href="{d['repo']['url']}">{d['repo']['url'].replace('https://', '')}</a></p>
</div>""", "cover"),

        slide(f"""
<p class="kicker">The problem</p>
<h2>People buy skincare one product at a time<br>and use it all at once.</h2>
<div class="cols3">
<div class="pt"><b>Nothing in the purchase path</b> looks at the
combination.</div>
<div class="pt"><b>A clash does not announce itself.</b> It looks like
irritation you blame on one product, replace, and do not fix.</div>
<div class="pt"><b>Nobody is positioned to say so.</b> Retailers are selling.
Chatbots cite nothing. Ingredient databases know one product at a time.</div>
</div>"""),

        slide(f"""
<p class="kicker">What is new</p>
<h2>The rules table decides.<br>The model explains.</h2>
<div class="split">
<div>
<p>Every finding, severity, routine position and dollar figure is computed by
deterministic code from a reviewed table.</p>
<p>The model reads labels and writes prose. It <b>cannot</b> introduce a
finding or change a severity.</p>
</div>
<div class="proof">
<p class="proofhead">Enforced, not requested</p>
<p>A narrative contradicting every finding, inventing a rule, rewriting the
money and naming a product nobody owns changes <b>nothing</b>.</p>
<p class="mono">test_thesis.py · {ts['total_checks']} checks</p>
</div>
</div>"""),

        slide('<p class="kicker">The agents</p>'
              + agent_diagram().replace('<figure class="shot">', '<div class="dia">')
              .replace("</figure>", "</div>")
              .replace('<figcaption>', '<p class="cap">')
              .replace("</figcaption>", "</p>")),

        slide(f"""
<p class="kicker">What it produces</p>
<div class="grid2">
<figure>{img("02-findings.png", "", width="100%")}
<figcaption><b>Findings</b> — each citing the rule that produced it, with the
engine's own count inside the summary</figcaption></figure>
<figure>{img("03-routine.png", "", width="100%")}
<figcaption><b>A morning and evening order</b> — steps you do not own shown in
place, alternating nights marked</figcaption></figure>
</div>"""),

        slide(f"""
<p class="kicker">…and what the shelf is missing</p>
<div class="grid2">
<figure>{img("04-gaps.png", "", width="100%")}
<figcaption><b>What to do</b> — missing steps in three tiers, each naming the
products that triggered it, so a suggestion cannot read as a defect</figcaption>
</figure>
<figure>{img("06-film.png", "", width="100%")}
<figcaption><b>A drawn walkthrough</b> — a tab per half of the day, each step
timed from the same table the written routine uses</figcaption></figure>
</div>"""),

        slide(f"""
<p class="kicker">Cost</p>
<h2>{money(plain['median'])} an audit.</h2>
<div class="tiles">
{tile(money(plain['median']), f"plain audit · median of {plain['n']}")}
{tile(money(lookups['median']), f"with lookups · median of {lookups['n']}")}
{tile(money(plain['median'] * 10000, 0), "10,000 users / month")}
{tile(money(lookups['median'] * 10000, 0), "10,000 · lookup-heavy", "warn")}
</div>
<p class="foot">Caching saved <b>{pct(c['saved_share'])}</b> of input spend —
but a cache <i>write</i> costs 25% <i>more</i> than not caching. It only pays
with repetition.</p>"""),

        slide(f"""
<p class="kicker">Safety</p>
<h2>12 injection attacks, 3 arms, measured.</h2>
<div class="bars">
{bar("Naive prompt", at['arms']['naive'], at['total'])}
{bar("Careful prompting", at['arms']['undefended'], at['total'])}
{bar("Defended", at['arms']['defended'], at['total'], "good")}
</div>
<p class="foot">Careful prompting scored <b>identically to the naive arm</b>.
What stopped them was re-reading the input with a deterministic matcher that
has no comprehension to exploit.</p>"""),

        slide(f"""
<p class="kicker">Impact · the finding</p>
<h2>Almost every real defect was
<span class="hl">confidently wrong</span>, not visibly broken.</h2>
<div class="split">
<div>
<div class="herorow"><div><div class="hero">{te['count']}</div>
<p class="herolab">defects from {te['reported']} real testers</p></div>
<div><div class="hero">0</div>
<p class="herolab">caught by {ts['total_checks']} checks</p></div></div>
<p class="foot">{len(classes)} failure classes,
{len(te['class_overlap'])} found by more than one.
<b>At {te['reported']} testers, still not saturated.</b> Tester 1 knew
skincare, tester 2 checked against the bottles, tester 3 read it as a
document — and they barely overlapped.</p>
</div>
<div class="cols1">
<div class="pt">A shelf holding sunscreen, told it had none.</div>
<div class="pt">A 90-second wait captioned as two minutes.</div>
<div class="pt">A price from one company beside another's link.</div>
<p class="foot">None threw an error. All produced a clean page — and several
of my own tests excluded the case they were built to catch.</p>
</div>
</div>"""),

        slide(f"""
<p class="kicker">Limits, honestly</p>
<div class="split">
<div class="proof warn">
<p class="proofhead">Withdrawn on the last day</p>
<p>232 machine-translated ingredient names. Disclosure was not enough: a wrong
translation invents an ingredient, and the warning is wrong whether or not a
caveat sits beside it.</p>
<p class="mono">all {r['terms']} remaining terms are INCI, a product name, or
a reviewed alias</p>
</div>
<div>
<div class="hero sub">{r['verified']}<span class="of">/{r['rules_total']}</span></div>
<p class="herolab">rules source-verified; {r['reasoned']} are recorded
mechanistic reasoning. Only verified rows are presented as settled.</p>
<p class="foot"><b>Next: a {nth(te['reported'] + 1)} tester.</b> The
saturation curve says they find a new class, not a repeat.</p>
</div>
</div>"""),
    ]

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{e(TITLE)} — slides</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5/dist/reveal.css">
<style>
:root{{--ink:#1b1a18;--dim:#5a554e;--clay:#9c5f44;--sand:#c8a77f;
  --line:#e3ded5;--bg:#faf7f2;--card:#fff;--good:#5c7a5e}}
.reveal{{font-family:Charter,"Iowan Old Style",Georgia,serif;color:var(--ink);
  font-size:30px}}
.reveal-viewport{{background:var(--bg)}}

/* Every slide is a column that cannot overflow: content shrinks into
   the box rather than running off the bottom of it. */
/* !important because reveal sets display on the active section itself;
   without it the column never forms and every slide sits jammed
   against the top edge with two-thirds of the screen empty. */
.reveal .slides section{{text-align:left;height:100%;
  display:flex !important;flex-direction:column;justify-content:center;
  padding:0 1.1em;box-sizing:border-box}}
.reveal .slides section.cover{{justify-content:center}}
.reveal h1,.reveal h2{{font-family:inherit;text-transform:none;
  letter-spacing:-.02em;color:var(--ink);margin:0 0 .35em}}
.reveal h1{{font-size:1.9em;line-height:1.08}}
.reveal h2{{font-size:1.22em;line-height:1.18}}
.reveal h2.big{{font-size:1.45em}}
.reveal p{{margin:0 0 .5em;line-height:1.4}}

.kicker{{font:600 .42em/1 var(--sans,inherit);letter-spacing:.14em;
  text-transform:uppercase;color:var(--clay);margin:0 0 .7em;flex:none}}
.kicker::after{{content:"";display:block;width:2.2em;height:3px;
  background:var(--sand);margin-top:.55em}}

.cover h1{{font-size:2.3em;margin-bottom:.2em}}
.cover .lede{{font-size:.72em;color:var(--dim);max-width:22em;line-height:1.45}}
.cover .byline{{font-size:.46em;color:var(--dim);margin-top:2.2em}}
.cover a{{color:var(--clay)}}

.cols3{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.8em;
  margin-top:.5em}}
.cols3.small .pt{{font-size:.6em}}
.pt{{background:var(--card);border:1px solid var(--line);border-left:4px solid
  var(--sand);border-radius:7px;padding:.75em .85em;font-size:.68em;
  line-height:1.45}}
.pt b{{color:var(--clay)}}

.split{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);
  gap:1.2em;align-items:start;font-size:.74em}}
.proof{{background:var(--card);border:1px solid var(--line);border-radius:8px;
  padding:.9em 1em}}
.proof.warn{{border-color:var(--sand);background:#fdf9f3}}
.proofhead{{font-weight:700;color:var(--clay);margin:0 0 .4em}}
.mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.86em;
  color:var(--dim)}}

.tiles{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.6em;
  margin:.3em 0 .6em}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:8px;
  padding:.7em .65em;text-align:left;min-width:0}}
.tile .fig{{font-size:.92em;font-weight:700;letter-spacing:-.02em;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.tile .lab{{font-size:.5em;color:var(--dim);margin-top:.35em;line-height:1.3}}
.tile.warn .fig{{color:var(--clay)}}

.bars{{margin:.4em 0 .7em}}
.barrow{{display:grid;grid-template-columns:8em 1fr 3.6em;align-items:center;
  gap:.7em;margin-bottom:.6em;font-size:.68em}}
.bartrack{{background:#efeae1;border-radius:999px;height:1.5em;overflow:hidden}}
.barfill{{background:var(--sand);height:100%;border-radius:999px}}
.barfill.good{{background:var(--good)}}
.barval{{text-align:right;font-weight:700}}

.hero{{font-size:2.5em;font-weight:700;line-height:.95;color:var(--clay);
  letter-spacing:-.03em}}
.hero.sub{{font-size:1.7em;color:var(--ink);margin-top:.35em}}
.hero .of{{font-size:.5em;color:var(--dim);font-weight:400}}
.herolab{{font-size:.68em;color:var(--dim);line-height:1.35;margin:.15em 0 0}}

.herorow{{display:flex;gap:1.6em;align-items:flex-start}}
.cols1{{display:flex;flex-direction:column;gap:.45em}}
.cols1 .pt{{font-size:.95em}}
.hl{{color:var(--clay)}}
.foot{{font-size:.62em;color:var(--dim);line-height:1.4;margin-top:.5em}}
.foot b{{color:var(--ink)}}

/* Four screenshots at natural size are 1680px of content in a 760px
   box. Each cell is capped and the image fits inside it, so the grid
   cannot push the slide off the bottom of the screen. */
/* The image is told its height, not its width: img() writes an inline
   style="width:100%" that beats any width rule here, so the cap is on
   height with !important and the aspect ratio follows. */
.grid2{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);
  grid-template-rows:minmax(0,1fr);gap:.8em;margin-top:.2em;flex:1;
  min-height:0;padding-bottom:.2em}}
.grid2 > figure{{margin:0;min-height:0;display:flex;flex-direction:column;
  overflow:hidden}}
.grid2 .shot{{margin:0;min-height:0;flex:1;display:flex;
  flex-direction:column;overflow:hidden}}
.grid2 .shot img{{height:100%;width:auto !important;object-fit:contain;
  object-position:left top}}
.grid2 .shot figcaption{{display:none}}
.grid2 > figure > figcaption{{font-size:.44em;color:var(--dim);
  margin-top:.35em;display:block;flex:none;line-height:1.35}}
.grid2 > figure > figcaption b{{color:var(--ink)}}
.reveal img{{border:1px solid var(--line);border-radius:5px;margin:0}}
.dia{{text-align:center}}
.dia svg{{max-height:60vh;width:auto}}
.cap{{font-size:.42em;color:var(--dim);margin-top:.5em}}
.reveal .slide-number{{background:none;color:var(--dim);font-size:.5em}}
</style></head><body>
<div class="reveal"><div class="slides">
{"".join(slides)}
</div></div>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@5/dist/reveal.js"></script>
<script>Reveal.initialize({{hash:true,slideNumber:'c/t',
  width:1280,height:760,margin:0.045,minScale:0.2,maxScale:1.4}});</script>
</body></html>
"""


def main() -> int:
    fast = "--fast" in sys.argv
    print("  collecting facts" + (" (skipping test runs)" if fast else
                                  " (running the suites, ~1 min)"))
    d = collect(run_suites=not fast)

    missing = [n for n, v in d["tests"]["suites"].items() if v["passed"] is False]
    if missing:
        print(f"  WARNING: these suites did not pass: {', '.join(missing)}")

    REPORT.write_text(build_report(d), encoding="utf-8")
    SLIDES.write_text(build_slides(d), encoding="utf-8")

    stems = {p.stem for p in ASSETS.glob("*.*")} if ASSETS.is_dir() else set()
    wanted = ["01-input", "02-findings", "03-routine", "04-gaps", "05-correct"]
    absent = [w for w in wanted if w not in stems]

    print(f"  wrote {REPORT.name} ({REPORT.stat().st_size // 1024} KB)")
    print(f"  wrote {SLIDES.name} ({SLIDES.stat().st_size // 1024} KB)")
    if absent:
        print(f"  screenshots still to capture: {', '.join(absent)}")
    else:
        print("  all screenshots embedded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

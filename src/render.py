"""Render an audit as a single self-contained HTML file.

No CDN, no external files, no network. The page must open by double-clicking on
any machine — the course requires it of the report, and a result page that needs
a server is a result page nobody looks at.

Two rules shape what goes in it:

  * Every claim shows the rule_id that produced it. The chips are not
    decoration; they are the audit trail made visible to the person reading.
  * Numbers come from the engine, never from the agent. The agent writes
    sentences; dollar figures and counts are interpolated here from
    AuditResult. An agent asked to count its own findings got it wrong, which
    is why the division is enforced rather than requested.

The routine player animates the agent-authored application specs. It is CSS and
a few lines of JavaScript rather than generated video: zero tokens, no model
call, and it cannot fail during a demo.
"""

from __future__ import annotations

import html
import json
from datetime import datetime

from models import AuditNarrative, AuditResult

SEVERITY_LABEL = {
    "critical": "Critical",
    "high": "Important",
    "medium": "Worth knowing",
    "low": "Minor",
}

TYPE_LABEL = {
    "conflict": "Conflict",
    "caution": "Caution",
    "synergy": "Works well together",
    "myth": "Common myth",
    "redundancy": "Duplicate",
    "ordering": "Order",
    "timing": "Timing",
}

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#0f1115; --panel:#171a21; --panel-2:#1d212a; --line:#2a2f3a;
  --ink:#e8eaf0; --ink-dim:#9aa3b2; --ink-faint:#6b7483;
  --crit:#ff6b6b; --high:#ffa94d; --med:#ffd43b; --low:#74c0fc;
  --good:#51cf66; --accent:#b197fc;
  --am:#ffd43b; --pm:#748ffc;
}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  padding:40px 24px 80px;
}
.wrap{max-width:1040px;margin:0 auto}
h1{font-size:30px;line-height:1.2;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.09em;color:var(--ink-faint);
   margin:40px 0 14px;font-weight:600}
.sub{color:var(--ink-dim);margin:0 0 28px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.summary{font-size:17px;line-height:1.65;border-left:3px solid var(--accent)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.stat .n{font-size:24px;font-weight:650;letter-spacing:-.02em}
.stat .l{font-size:12px;color:var(--ink-faint);margin-top:2px}
.stat.warn .n{color:var(--high)}
.stat.bad .n{color:var(--crit)}
.chip{display:inline-block;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
  padding:1px 7px;border-radius:5px;background:var(--panel-2);color:var(--ink-dim);
  border:1px solid var(--line);margin-right:5px}
.chip.unver{border-color:#4a3f2a;color:#d8b36a}
.finding{border-left:3px solid var(--line);padding:12px 0 12px 16px;margin:0 0 4px}
.finding.critical{border-color:var(--crit)} .finding.high{border-color:var(--high)}
.finding.medium{border-color:var(--med)} .finding.low{border-color:var(--low)}
.finding .top{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;margin-bottom:5px}
.finding .kind{font-size:12px;font-weight:600;color:var(--ink-dim)}
.finding .who{font-size:12px;color:var(--ink-faint)}
.finding p{margin:0}
details.mech{margin-top:7px}
details.mech summary{font-size:12px;color:var(--ink-faint);cursor:pointer;list-style:none}
details.mech summary::-webkit-details-marker{display:none}
details.mech summary::before{content:"▸ ";color:var(--ink-faint)}
details.mech[open] summary::before{content:"▾ "}
details.mech .body{font-size:13px;color:var(--ink-dim);padding:7px 0 0 14px;border-left:1px solid var(--line);margin-top:6px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:760px){.cols{grid-template-columns:1fr}}
.slot h3{margin:0 0 12px;font-size:15px;display:flex;align-items:center;gap:8px}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.dot.am{background:var(--am)} .dot.pm{background:var(--pm)}
.step{display:flex;gap:12px;padding:11px 12px;border-radius:9px;border:1px solid transparent;
  transition:background .25s,border-color .25s}
.step .num{width:22px;height:22px;flex:0 0 22px;border-radius:50%;background:var(--panel-2);
  border:1px solid var(--line);display:grid;place-items:center;font-size:11px;color:var(--ink-dim);
  margin-top:1px}
.step .name{font-weight:550}
.step .meta{font-size:12px;color:var(--ink-faint);margin-top:2px}
.step .how{font-size:12.5px;color:var(--ink-dim);margin-top:5px}
.step.on{background:var(--panel-2);border-color:var(--accent)}
.step.on .num{background:var(--accent);color:#14121c;border-color:var(--accent);font-weight:700}
.badge{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;padding:1px 6px;
  border-radius:4px;background:#2b2415;color:#e3b341;margin-left:6px}
.note{background:#1a1712;border:1px solid #332b1a;border-left:3px solid var(--high);
  border-radius:9px;padding:12px 14px;margin-bottom:9px;font-size:14px;color:#e8d9b8}
.escal{background:#1d1416;border:1px solid #3d2328;border-left:3px solid var(--crit);
  border-radius:9px;padding:14px 16px;margin-bottom:10px}
.escal .who{font-size:12px;color:var(--crit);font-weight:600;margin-bottom:4px}
.bar{display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
button{font:inherit;font-size:13px;font-weight:550;padding:7px 15px;border-radius:8px;
  background:var(--accent);color:#14121c;border:0;cursor:pointer}
button.ghost{background:var(--panel-2);color:var(--ink);border:1px solid var(--line)}
button:disabled{opacity:.45;cursor:default}
.prog{flex:1;min-width:120px;height:4px;background:var(--panel-2);border-radius:3px;overflow:hidden}
.prog i{display:block;height:100%;width:0;background:var(--accent);transition:width .25s linear}
footer{margin-top:52px;padding-top:20px;border-top:1px solid var(--line);
  font-size:12.5px;color:var(--ink-faint);line-height:1.8}
.ver{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;
  background:#2b2415;color:#e3b341;border:1px solid #453a22}
.ver.ok{background:#16281a;color:var(--good);border-color:#24402a}

/* Action groups: findings organised by what to do, not by severity label. */
.grp{margin-bottom:12px}
.grp>summary{cursor:pointer;list-style:none;display:flex;align-items:baseline;gap:9px;
  padding:13px 16px;background:var(--panel);border:1px solid var(--line);border-radius:11px}
.grp>summary::-webkit-details-marker{display:none}
.grp>summary::before{content:"▸";color:var(--ink-faint);font-size:12px}
.grp[open]>summary::before{content:"▾"}
.grp[open]>summary{border-radius:11px 11px 0 0;border-bottom-color:transparent}
.grp .gt{font-weight:600;font-size:15px}
.grp .gn{font-size:12px;color:var(--ink-faint)}
.grp .gw{margin-left:auto;font-size:12px;color:var(--ink-faint)}
.grp .inner{border:1px solid var(--line);border-top:0;border-radius:0 0 11px 11px;
  background:var(--panel);padding:4px 18px 14px}
.grp.first>summary{border-color:#3d2a1a;background:#1a1510}
.grp.first .inner{border-color:#3d2a1a;background:#1a1510}
.grp.first .gt{color:var(--high)}
.oneline{display:flex;gap:9px;align-items:baseline;padding:7px 0;border-bottom:1px solid var(--line);
  font-size:13.5px}
.oneline:last-child{border-bottom:0}
.oneline .t{color:var(--ink-dim)}

/* Conflict grid: which products clash, read at a glance instead of
   reconstructed from nineteen cards. */
.gridwrap{overflow-x:auto}
table.mx{border-collapse:separate;border-spacing:3px;font-size:11px}
table.mx th{font-weight:500;color:var(--ink-faint);font-size:11px;padding:0 4px;
  text-align:right;white-space:nowrap}
table.mx th.c{text-align:center;width:26px}
table.mx td{width:26px;height:26px;border-radius:5px;background:var(--panel-2);
  text-align:center;color:transparent}
table.mx td.self{background:transparent}
table.mx td.high{background:#5c2626}
table.mx td.med{background:#5a4420}
table.mx td.good{background:#1f4429}
table.mx td.myth{background:#2a2f3a}
.key{display:flex;gap:16px;flex-wrap:wrap;margin-top:12px;font-size:12px;color:var(--ink-dim)}
.key span{display:flex;align-items:center;gap:6px}
.key i{width:11px;height:11px;border-radius:3px;display:inline-block}
.legend{margin-top:14px;font-size:12px;color:var(--ink-dim);columns:2;column-gap:28px}
.legend div{break-inside:avoid;padding:2px 0}
.legend b{color:var(--ink);font-weight:600;margin-right:6px}

/* Week grid: turns "alternate nights" into an actual calendar. */
table.wk{border-collapse:separate;border-spacing:4px;font-size:12px;width:100%}
table.wk th{font-size:11px;color:var(--ink-faint);font-weight:500;text-align:center}
table.wk th.n{text-align:left;width:40%}
table.wk td{height:30px;border-radius:6px;background:var(--panel-2);text-align:center}
table.wk td.on{background:var(--accent);color:#14121c;font-weight:650}
table.wk td.rest{background:var(--panel-2);color:var(--ink-faint)}

/* Guided mode: for following at the sink, not for reading. */
.guide{position:fixed;inset:0;background:rgba(9,10,14,.93);z-index:50;
  display:grid;place-items:center;padding:24px}
.guide[hidden]{display:none}
.gbox{width:min(520px,100%);text-align:center}
.gslot{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint)}
.gname{font-size:30px;font-weight:650;letter-spacing:-.02em;margin:10px 0 4px;line-height:1.2}
.ghow{font-size:17px;color:var(--ink-dim);line-height:1.5}
.gring{margin:26px auto 8px;width:124px;height:124px;border-radius:50%;display:grid;place-items:center;
  border:3px solid var(--line);position:relative}
.gring.waiting{border-color:var(--high)}
.gcount{font-size:38px;font-weight:650;font-variant-numeric:tabular-nums}
.gsub{font-size:12px;color:var(--ink-faint);min-height:18px}
.gbtns{display:flex;gap:9px;justify-content:center;margin-top:24px}
.gdots{display:flex;gap:5px;justify-content:center;margin-top:20px}
.gdots i{width:6px;height:6px;border-radius:50%;background:var(--line)}
.gdots i.done{background:var(--ink-faint)}
.gdots i.now{background:var(--accent);transform:scale(1.5)}
"""

JS = """
/* Guided mode.
 *
 * The first version replayed the routine as a highlight moving down a list you
 * could already read in full, which was slower than reading it and told you
 * nothing new. This is for standing at the sink with wet hands: one step at a
 * time, large enough to read from arm's length, counting down the seconds the
 * agent specified, and enforcing the waits between steps -- which is the part
 * people skip and the part that actually matters for an acid.
 */
(function(){
  var ALL = DATA_STEPS;
  var seq = [], i = 0, b = 0, timer = null, remain = 0;

  var box = document.getElementById('guide'),
      slotEl = document.getElementById('g-slot'),
      nameEl = document.getElementById('g-name'),
      howEl  = document.getElementById('g-how'),
      cntEl  = document.getElementById('g-count'),
      subEl  = document.getElementById('g-sub'),
      ringEl = document.getElementById('g-ring'),
      dotsEl = document.getElementById('g-dots'),
      prevB  = document.getElementById('g-prev'),
      nextB  = document.getElementById('g-next');

  function dots(){
    dotsEl.innerHTML = seq.map(function(_, n){
      return '<i class="' + (n === i ? 'now' : (n < i ? 'done' : '')) + '"></i>';
    }).join('');
  }

  /* A step is not one timed block. Applying a cleanser and moving on leaves
   * your face covered in cleanser, so each step runs as a short sequence of
   * beats -- apply, then finish (rinse, pat dry, absorb), then any wait the
   * chemistry needs before the next product. */
  function beat(){ return seq[i].beats[b]; }

  function paint(){
    var s = seq[i], p = beat();
    slotEl.textContent = (s.slot === 'am' ? 'Morning' : 'Evening')
      + ' · step ' + s.order + ' of ' + s.of;
    nameEl.textContent = s.name;
    howEl.textContent = p.text;
    subEl.textContent = p.kind === 'apply'
      ? (s.freq === 'daily' ? '' : s.freq)
      : p.kind;
    ringEl.className = 'gring' + (p.kind === 'wait' ? ' waiting' : '');
    remain = p.secs;
    cntEl.textContent = remain;
    prevB.disabled = i === 0 && b === 0;
    nextB.textContent = (i === seq.length - 1 && b === seq[i].beats.length - 1)
      ? 'Finish' : 'Next';
    dots();
  }

  function tick(){
    remain--;
    cntEl.textContent = remain > 0 ? remain : 0;
    if(remain > 0) return;
    clearInterval(timer);
    advance(1);
  }

  function advance(dir){
    clearInterval(timer);
    b += dir;
    if(b >= seq[i].beats.length){
      if(i === seq.length - 1){ subEl.textContent = 'done'; return; }
      i++; b = 0;
    } else if(b < 0){
      if(i === 0){ b = 0; } else { i--; b = seq[i].beats.length - 1; }
    }
    paint();
    timer = setInterval(tick, 1000);
  }

  function go(n){
    clearInterval(timer);
    i = Math.max(0, Math.min(n, seq.length - 1));
    b = 0;
    paint();
    timer = setInterval(tick, 1000);
  }

  function open(slot){
    seq = ALL.filter(function(s){ return s.slot === slot; });
    if(!seq.length) return;
    box.hidden = false;
    go(0);
  }
  function close(){ clearInterval(timer); box.hidden = true; }

  document.getElementById('go-am').addEventListener('click', function(){ open('am'); });
  document.getElementById('go-pm').addEventListener('click', function(){ open('pm'); });
  document.getElementById('g-close').addEventListener('click', close);
  prevB.addEventListener('click', function(){ advance(-1); });
  nextB.addEventListener('click', function(){
    if(i === seq.length - 1 && b === seq[i].beats.length - 1){ close(); }
    else { advance(1); }
  });
  document.addEventListener('keydown', function(ev){
    if(box.hidden) return;
    if(ev.key === 'Escape') close();
    if(ev.key === 'ArrowRight') advance(1);
    if(ev.key === 'ArrowLeft') advance(-1);
  });
})();
"""


def e(text: object) -> str:
    return html.escape(str(text), quote=True)


def _stat(value: str, label: str, tone: str = "") -> str:
    cls = f"stat {tone}".strip()
    return f'<div class="{cls}"><div class="n">{e(value)}</div><div class="l">{e(label)}</div></div>'


def _finding_card(group: list, explanation: str | None) -> str:
    """One card per rule, listing every product pair it fired on.

    Rendering one card per *finding* duplicated text: two retinol products both
    trigger SKA-003, and the agent writes a single explanation per rule_id, so
    the same sentence appeared twice against different pairs. Grouping matches
    how the explanation is actually produced, and on the sample shelf takes the
    page from 33 cards to 19.
    """
    f = group[0]
    chips = f'<span class="chip">{e(f.rule_id)}</span>'
    if not f.verified:
        chips += '<span class="chip unver">unverified rule</span>'
    pairs = " · ".join(" + ".join(g.products) for g in group)
    count = f'<span class="who">{len(group)} pairs</span>' if len(group) > 2 else ""
    body = explanation or f.guidance
    return (
        f'<div class="finding {e(f.severity)}">'
        f'<div class="top">{chips}'
        f'<span class="kind">{e(TYPE_LABEL.get(f.type, f.type))}</span>{count}</div>'
        f'<div class="who" style="margin-bottom:6px">{e(pairs)}</div>'
        f"<p>{e(body)}</p>"
        f'<details class="mech"><summary>Why</summary>'
        f'<div class="body">{e(f.mechanism)}<br><br><strong>Do this:</strong> {e(f.guidance)}</div>'
        f"</details></div>"
    )


def _step_row(step, spec, slot: str, total: int) -> str:
    key = f"{slot}-{step.order}"
    badge = "" if step.frequency == "daily" else f'<span class="badge">{e(step.frequency)}</span>'
    because = "".join(f'<span class="chip">{e(b)}</span>' for b in step.because)
    how = ""
    if spec is not None:
        bits = [f"{spec.amount}, {spec.motion} on {spec.area}, {spec.seconds}s"]
        if spec.finish != "nothing":
            bits.append(spec.finish)
        if spec.wait_after_seconds:
            bits.append(f"wait {spec.wait_after_seconds}s")
        how = f'<div class="how">{e(" → ".join(bits))}</div>'
    return (
        f'<div class="step" data-step="{e(key)}">'
        f'<div class="num">{step.order}</div><div>'
        f'<div class="name">{e(step.product_name)}{badge}</div>'
        f'<div class="meta">{e(step.form)}</div>{how}'
        f'<div style="margin-top:6px">{because}</div>'
        f"</div></div>"
    )


CELL_CLASS = {"high": "high", "critical": "high", "medium": "med", "low": "good"}


def _conflict_grid(audit: AuditResult) -> str:
    """Product-by-product matrix of what clashes with what.

    Reading nineteen cards tells you about pairs one at a time; the shape of
    the problem — that one product is in four conflicts and the rest are fine —
    only appears when you see them together.
    """
    paired = [f for f in audit.findings if len(f.products) == 2]
    if not paired:
        return ""

    names: list[str] = []
    for f in paired:
        for n in f.products:
            if n not in names:
                names.append(n)
    if len(names) < 2:
        return ""

    worst: dict[tuple[str, str], str] = {}
    rank = {"high": 3, "med": 2, "good": 1, "myth": 0}
    for f in paired:
        cls = "myth" if f.type == "myth" else (
            "good" if f.type == "synergy" else CELL_CLASS.get(f.severity, "med")
        )
        key = tuple(sorted(f.products))
        if rank[cls] > rank.get(worst.get(key, "myth"), -1):
            worst[key] = cls

    idx = {n: i + 1 for i, n in enumerate(names)}
    head = "".join(f'<th class="c">{idx[n]}</th>' for n in names)
    rows = []
    for a in names:
        cells = []
        for bname in names:
            if a == bname:
                cells.append('<td class="self"></td>')
            else:
                cls = worst.get(tuple(sorted((a, bname))), "")
                cells.append(f'<td class="{cls}">.</td>')
        label = a if len(a) <= 26 else a[:24] + "…"
        rows.append(f"<tr><th>{idx[a]}. {e(label)}</th>{''.join(cells)}</tr>")

    key = (
        '<div class="key">'
        '<span><i style="background:#5c2626"></i>conflict</span>'
        '<span><i style="background:#5a4420"></i>use with care</span>'
        '<span><i style="background:#1f4429"></i>works well together</span>'
        '<span><i style="background:#2a2f3a"></i>myth, ignore it</span>'
        "</div>"
    )
    return (
        '<div class="card"><div class="gridwrap"><table class="mx">'
        f'<tr><th></th>{head}</tr>{"".join(rows)}</table></div>{key}</div>'
    )


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _week_grid(audit: AuditResult) -> str:
    """Turn "alternate nights" into a calendar.

    "Use on alternate nights" is advice people agree with and then do not
    follow, because working out which night is which is left to them. With
    three alternating products it is genuinely hard. Assigning them to a
    rotation and drawing it makes the instruction executable.
    """
    alternating = [s for s in audit.routine.pm if s.frequency != "daily"]
    if len(alternating) < 2:
        return ""

    n = len(alternating)
    rows = []
    for i, step in enumerate(alternating):
        cells = []
        for day in range(7):
            on = day % n == i
            cells.append(f'<td class="{"on" if on else "rest"}">{"✓" if on else ""}</td>')
        label = step.product_name if len(step.product_name) <= 30 else step.product_name[:28] + "…"
        rows.append(f'<tr><th class="n">{e(label)}</th>{"".join(cells)}</tr>')

    head = "".join(f"<th>{d}</th>" for d in DAYS)
    return (
        '<div class="card"><table class="wk">'
        f'<tr><th class="n"></th>{head}</tr>{"".join(rows)}</table>'
        '<p style="font-size:12.5px;color:var(--ink-dim);margin:12px 0 0">'
        f"These {n} products are strong enough that using them on the same night "
        "irritates without adding benefit. One per night, rotating, keeps all of "
        "them in your routine.</p></div>"
    )


def render(audit: AuditResult, narrative: AuditNarrative | None = None) -> str:
    specs = {s.product_name: s for s in (narrative.steps if narrative else [])}
    explain = {x.rule_id: x.plain_language for x in (narrative.explanations if narrative else [])}
    w = audit.waste

    # Guided mode runs in real seconds, not a sped-up preview: the point is to
    # follow it while actually applying things, so the agent's own durations and
    # waits are used unchanged.
    seq = []
    for slot, steps in (("am", audit.routine.am), ("pm", audit.routine.pm)):
        for s_ in steps:
            spec = specs.get(s_.product_name)
            beats = []
            if spec:
                beats.append({
                    "kind": "apply",
                    "text": f"{spec.amount}, {spec.motion} on {spec.area}",
                    "secs": spec.seconds,
                })
                if spec.finish == "rinse off":
                    beats.append({
                        "kind": "rinse off",
                        "text": "rinse thoroughly with lukewarm water, then pat dry",
                        "secs": spec.finish_seconds or 25,
                    })
                elif spec.finish == "pat dry":
                    beats.append({
                        "kind": "pat dry",
                        "text": "pat dry with a clean towel",
                        "secs": spec.finish_seconds or 10,
                    })
                elif spec.finish == "let it absorb" and not spec.wait_after_seconds:
                    beats.append({
                        "kind": "let it absorb",
                        "text": "let it sink in before the next product",
                        "secs": spec.finish_seconds or 20,
                    })
                if spec.wait_after_seconds:
                    # Absorbing and waiting are the same physical pause described
                    # twice. The agent sets both for an acid, and running them in
                    # series put two minutes of standing still on a toner. One
                    # beat, the longer of the two.
                    beats.append({
                        "kind": "wait",
                        "text": "let it absorb and settle before the next product",
                        "secs": max(spec.wait_after_seconds, spec.finish_seconds),
                    })
            else:
                beats.append({"kind": "apply", "text": "apply as usual", "secs": 15})
            seq.append({
                "slot": slot, "order": s_.order, "of": len(steps),
                "name": s_.product_name, "freq": s_.frequency, "beats": beats,
            })

    verified_ok = audit.rules_verified == audit.rules_total
    ver_cls = "ver ok" if verified_ok else "ver"
    ver_txt = f"{audit.rules_verified} of {audit.rules_total} rules verified"

    parts: list[str] = []
    parts.append(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Skincare shelf audit</title>"
        f"<style>{CSS}</style></head><body><div class=\"wrap\">"
    )

    parts.append(
        f"<h1>Your shelf, audited</h1>"
        f'<p class="sub">{w.products_owned} products · '
        f"{len(audit.findings)} findings · "
        f'<span class="{ver_cls}">{e(ver_txt)}</span></p>'
    )

    if narrative and narrative.summary:
        parts.append(f'<div class="card summary">{e(narrative.summary)}</div>')

    parts.append("<h2>Money</h2><div class=\"stats\">")
    parts.append(_stat(f"${w.shelf_value_usd:,.0f}", "on the shelf"))
    parts.append(_stat(f"${w.unused_value_usd:,.0f}", f"unused ({w.products_unused} products)",
                       "warn" if w.unused_value_usd else ""))
    parts.append(_stat(f"${w.redundant_value_usd:,.0f}", "duplicate function",
                       "warn" if w.redundant_value_usd else ""))
    parts.append(_stat(f"${w.conflicted_value_usd:,.0f}", "in high-severity conflict",
                       "bad" if w.conflicted_value_usd else ""))
    parts.append("</div>")

    if audit.escalations:
        parts.append("<h2>Needs a clinician</h2>")
        for esc in audit.escalations:
            parts.append(
                f'<div class="escal"><div class="who">{e(", ".join(esc.products))} '
                f'<span class="chip">{e(esc.rule_id)}</span></div>{e(esc.message)}</div>'
            )

    parts.append("<h2>Your routine</h2>")
    parts.append(
        '<div class="bar">'
        '<button id="go-am">Guide me through the morning</button>'
        '<button id="go-pm" class="ghost">Guide me through the evening</button>'
        '<span style="font-size:12px;color:var(--ink-faint)">'
        "runs in real time at the sink · enforces the waits</span>"
        "</div>"
    )
    parts.append('<div class="cols">')
    for slot, label, steps in (("am", "Morning", audit.routine.am), ("pm", "Evening", audit.routine.pm)):
        parts.append(f'<div class="slot card"><h3><span class="dot {slot}"></span>{label}</h3>')
        if not steps:
            parts.append('<p class="sub" style="margin:0">Nothing scheduled.</p>')
        for s in steps:
            parts.append(_step_row(s, specs.get(s.product_name), slot, len(steps)))
        parts.append("</div>")
    parts.append("</div>")

    week = _week_grid(audit)
    if week:
        parts.append("<h2>Which nights</h2>")
        parts.append(week)

    if audit.routine.notes:
        parts.append("<h2>Worth knowing</h2>")
        for note in audit.routine.notes:
            parts.append(f'<div class="note">{e(note)}</div>')

    grid = _conflict_grid(audit)
    if grid:
        parts.append("<h2>What clashes with what</h2>")
        parts.append(grid)

    # Findings organised by what to do about them, not by severity.
    #
    # Nineteen cards sorted into Important / Worth knowing / Minor is a list the
    # reader has to triage themselves. Sorting by action puts the handful that
    # need a decision at the top, open, and folds the rest away — the synergies
    # and myths are reassurance, and reassurance does not need to be expanded.
    by_rule: dict[str, list] = {}
    for f in audit.findings:
        by_rule.setdefault(f.rule_id, []).append(f)

    buckets: dict[str, list[list]] = {"first": [], "adjust": [], "good": [], "myth": []}
    for group in by_rule.values():
        f = group[0]
        if f.type == "myth":
            buckets["myth"].append(group)
        elif f.type == "synergy":
            buckets["good"].append(group)
        elif f.type in ("ordering", "timing"):
            # Important, but they are "do it this way", not "something is wrong".
            # Keeping high-severity timing rules out of the top section is what
            # takes it from six cards to three — and a top section with six
            # entries is not a priority list, it is just the list again.
            buckets["adjust"].append(group)
        elif f.type == "redundancy" or f.severity in ("critical", "high"):
            buckets["first"].append(group)
        else:
            buckets["adjust"].append(group)

    def _section(key: str, title: str, note: str, *, open_: bool, oneline: bool) -> None:
        groups = buckets[key]
        if not groups:
            return
        cls = "grp first" if key == "first" else "grp"
        parts.append(
            f'<details class="{cls}"{" open" if open_ else ""}><summary>'
            f'<span class="gt">{e(title)}</span>'
            f'<span class="gn">{len(groups)}</span>'
            f'<span class="gw">{e(note)}</span></summary><div class="inner">'
        )
        for group in groups:
            if oneline:
                parts.append(
                    f'<div class="oneline"><span class="chip">{e(group[0].rule_id)}</span>'
                    f'<span class="t">{e(explain.get(group[0].rule_id) or group[0].guidance)}</span></div>'
                )
            else:
                parts.append(_finding_card(group, explain.get(group[0].rule_id)))
        parts.append("</div></details>")

    parts.append("<h2>What to do</h2>")
    _section("first", "Fix these first",
             "costing you money or results", open_=True, oneline=False)
    _section("adjust", "Use them this way",
             "timing, order and milder clashes", open_=False, oneline=False)
    _section("good", "Already working in your favour",
             "no change needed", open_=False, oneline=True)
    _section("myth", "You can stop worrying about these",
             "common advice that does not hold up", open_=False, oneline=True)

    parts.append(
        '<div class="guide" id="guide" hidden><div class="gbox">'
        '<div class="gslot" id="g-slot"></div>'
        '<div class="gname" id="g-name"></div>'
        '<div class="ghow" id="g-how"></div>'
        '<div class="gring" id="g-ring"><span class="gcount" id="g-count">0</span></div>'
        '<div class="gsub" id="g-sub"></div>'
        '<div class="gdots" id="g-dots"></div>'
        '<div class="gbtns">'
        '<button class="ghost" id="g-prev">Back</button>'
        '<button id="g-next">Next</button>'
        '<button class="ghost" id="g-close">Close</button>'
        "</div></div></div>"
    )

    parts.append(
        "<footer>"
        f"Generated {datetime.now().strftime('%d %B %Y, %H:%M')} · "
        f"{audit.rules_verified} of {audit.rules_total} rules have been checked against a source; "
        "findings from unchecked rules are marked.<br>"
        "Every claim above cites the rule that produced it. "
        "This is not medical advice — products flagged for a clinician are not assessed here."
        "</footer></div>"
    )

    parts.append(f"<script>var DATA_STEPS={json.dumps(seq)};{JS}</script></body></html>")
    return "".join(parts)

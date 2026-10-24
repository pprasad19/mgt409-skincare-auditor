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
"""

JS = """
(function(){
  var seq = DATA_STEPS, t = null, i = -1;
  var btn = document.getElementById('play'),
      stop = document.getElementById('stop'),
      bar = document.getElementById('bar'),
      lab = document.getElementById('lab');
  function clear(){
    document.querySelectorAll('.step.on').forEach(function(e){e.classList.remove('on')});
  }
  function finish(){
    clearTimeout(t); clear(); i = -1;
    bar.style.width = '0%'; lab.textContent = '';
    btn.disabled = false; stop.disabled = true;
  }
  function next(){
    clear();
    i++;
    if(i >= seq.length){ finish(); return; }
    var s = seq[i];
    var el = document.querySelector('[data-step="'+s.key+'"]');
    if(el){ el.classList.add('on'); el.scrollIntoView({block:'nearest',behavior:'smooth'}); }
    bar.style.width = Math.round((i+1)/seq.length*100) + '%';
    lab.textContent = (s.slot==='am'?'Morning':'Evening') + ' · step ' + s.order + ' of ' + s.of;
    t = setTimeout(next, s.ms);
  }
  btn.addEventListener('click', function(){
    btn.disabled = true; stop.disabled = false; i = -1; next();
  });
  stop.addEventListener('click', finish);
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
        wait = f", then wait {spec.wait_after_seconds}s" if spec.wait_after_seconds else ""
        how = (
            f'<div class="how">{e(spec.amount)}, {e(spec.motion)} on {e(spec.area)}'
            f", {spec.seconds}s{e(wait)}</div>"
        )
    return (
        f'<div class="step" data-step="{e(key)}">'
        f'<div class="num">{step.order}</div><div>'
        f'<div class="name">{e(step.product_name)}{badge}</div>'
        f'<div class="meta">{e(step.form)}</div>{how}'
        f'<div style="margin-top:6px">{because}</div>'
        f"</div></div>"
    )


def render(audit: AuditResult, narrative: AuditNarrative | None = None) -> str:
    specs = {s.product_name: s for s in (narrative.steps if narrative else [])}
    explain = {x.rule_id: x.plain_language for x in (narrative.explanations if narrative else [])}
    w = audit.waste

    # Player timing comes from the agent's specs, with a floor so a long
    # routine stays watchable.
    seq = []
    for slot, steps in (("am", audit.routine.am), ("pm", audit.routine.pm)):
        for s in steps:
            spec = specs.get(s.product_name)
            secs = (spec.seconds + spec.wait_after_seconds) if spec else 12
            seq.append(
                {"key": f"{slot}-{s.order}", "slot": slot, "order": s.order,
                 "of": len(steps), "ms": max(900, min(secs * 110, 4200))}
            )

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
        '<button id="play">Play the routine</button>'
        '<button id="stop" class="ghost" disabled>Stop</button>'
        '<div class="prog"><i id="bar"></i></div>'
        '<span id="lab" style="font-size:12px;color:var(--ink-faint);min-width:150px"></span>'
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

    if audit.routine.notes:
        parts.append("<h2>Worth knowing</h2>")
        for note in audit.routine.notes:
            parts.append(f'<div class="note">{e(note)}</div>')

    by_rule: dict[str, list] = {}
    for f in audit.findings:
        by_rule.setdefault(f.rule_id, []).append(f)

    by_sev: dict[str, list[list]] = {}
    for group in by_rule.values():
        by_sev.setdefault(group[0].severity, []).append(group)

    parts.append(f"<h2>Findings · {len(by_rule)} rules fired</h2><div class=\"card\">")
    for sev in ("critical", "high", "medium", "low"):
        groups = by_sev.get(sev)
        if not groups:
            continue
        parts.append(
            f'<div style="font-size:12px;color:var(--ink-faint);margin:14px 0 6px;'
            f'text-transform:uppercase;letter-spacing:.08em">{e(SEVERITY_LABEL[sev])}</div>'
        )
        for group in groups:
            parts.append(_finding_card(group, explain.get(group[0].rule_id)))
    parts.append("</div>")

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

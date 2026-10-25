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
import re
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
/* Warm, light, editorial.
 *
 * The first version was a dark analytics dashboard, which is what you build
 * when the audience is you. The audience is someone deciding what to put on
 * their face, and the page they want looks like the inside of a good skincare
 * brand's website: paper-coloured, generous, quiet.
 *
 * All type is system fonts. Webfonts would mean a CDN link, and the page has
 * to open by double-click with no network.
 */
*,*::before,*::after{box-sizing:border-box}
:root{
  --paper:#f6f2ec; --card:#fffdfa; --sunk:#efe8de; --line:#e4dbcd;
  --ink:#2c2824; --ink-dim:#6d6458; --ink-faint:#9b9284;
  --clay:#a86a4b; --sage:#6b8169; --sand:#c08a3e;
  --crit:#a4493c; --high:#bd7a35; --med:#9d8430; --low:#6b8169;
  /* Four warm tints plus a warm empty cell meant "myth" and "no interaction"
     were both pale beige and effectively the same square. Myth goes cool
     instead: it is the only category that is neither a problem nor a benefit,
     so reading as a different kind of thing is correct, not just legible.
     Conflict and care are nudged apart at the same time. */
  --cell-crit:#e7bdb0; --cell-care:#f3debb; --cell-good:#cde0c8; --cell-myth:#cfdae8;
  --shadow:0 1px 2px rgba(60,45,30,.04), 0 10px 30px -18px rgba(60,45,30,.22);
  --serif:ui-serif,"Iowan Old Style",Georgia,"Palatino Linotype",Palatino,serif;
  --sans:ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font:16.5px/1.68 var(--sans);
  padding:0 24px 110px;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1000px;margin:0 auto}

h1{font:400 44px/1.12 var(--serif);letter-spacing:-.015em;margin:68px 0 10px}
h2{font:600 12.5px/1 var(--sans);text-transform:uppercase;letter-spacing:.14em;
   color:var(--ink-faint);margin:56px 0 18px}
h2:first-of-type{margin-top:0}
.sub{color:var(--ink-dim);margin:0 0 34px;font-size:16px}
/* No max-width here. 60ch is right for a paragraph and wrong for a single
   descriptor: it wrapped "to do about it." onto a line of its own. This one
   sits on one line at desktop width and wraps naturally when narrow. */
.lede{color:var(--ink-dim);font-size:15.5px;margin:-8px 0 16px}

.card{background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:26px 30px;box-shadow:var(--shadow)}
.summary{font:400 21px/1.6 var(--serif);color:var(--ink);padding:30px 34px;
  border-left:3px solid var(--clay)}

.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:14px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:20px 22px;box-shadow:var(--shadow)}
.stat .n{font:400 32px/1.1 var(--serif);letter-spacing:-.01em}
.stat .l{font-size:12.5px;color:var(--ink-faint);margin-top:6px;letter-spacing:.01em}
.stat.warn .n{color:var(--sand)}
.stat.bad .n{color:var(--crit)}

.chip{display:inline-block;font:11px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;
  padding:1px 8px;border-radius:6px;background:var(--sunk);color:var(--ink-dim);
  border:1px solid var(--line);margin-right:6px}
.chip.unver{background:#f6ecd8;border-color:#e4d2ab;color:#8a6a24}

.finding{border-left:3px solid var(--line);padding:16px 0 16px 20px;margin:0}
.finding + .finding{border-top:1px solid var(--line)}
.finding.critical,.finding.high{border-left-color:var(--crit)}
.finding.medium{border-left-color:var(--high)}
.finding.low{border-left-color:var(--low)}
.finding .top{display:flex;gap:9px;align-items:baseline;flex-wrap:wrap;margin-bottom:7px}
.finding .kind{font-size:12.5px;font-weight:600;color:var(--ink-dim)}
.finding .who{font-size:12.5px;color:var(--ink-faint)}
.finding p{margin:0;font-size:16px;line-height:1.6}
details.mech{margin-top:10px}
details.mech summary{font-size:12.5px;color:var(--clay);cursor:pointer;list-style:none;
  font-weight:500}
details.mech summary::-webkit-details-marker{display:none}
details.mech summary::before{content:"→ "}
details.mech[open] summary::before{content:"↓ "}
details.mech .body{font-size:14.5px;color:var(--ink-dim);padding:10px 0 0 16px;
  border-left:1px solid var(--line);margin-top:8px;line-height:1.6}

.cols{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:760px){.cols{grid-template-columns:1fr}}
.slot h3{margin:0 0 16px;font:500 17px/1 var(--serif);display:flex;align-items:center;gap:9px}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.dot.am{background:var(--sand)} .dot.pm{background:var(--sage)}
.step{display:flex;gap:14px;padding:13px 14px;border-radius:12px;
  border:1px solid transparent;transition:background .25s,border-color .25s}
.step .num{width:25px;height:25px;flex:0 0 25px;border-radius:50%;background:var(--sunk);
  display:grid;place-items:center;font-size:12px;color:var(--ink-dim);margin-top:2px;
  font-variant-numeric:tabular-nums}
.step .name{font-weight:600;font-size:15.5px}
.step .meta{font-size:12.5px;color:var(--ink-faint);margin-top:1px}
.step .how{font-size:13.5px;color:var(--ink-dim);margin-top:6px}
.step.on{background:var(--sunk);border-color:var(--clay)}
.step.on .num{background:var(--clay);color:#fff}
.badge{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;padding:2px 7px;
  border-radius:5px;background:#f6ecd8;color:#8a6a24;margin-left:7px;font-weight:600}

.note{background:#fdf7ea;border:1px solid #ecdcb9;border-left:3px solid var(--sand);
  border-radius:12px;padding:15px 18px;margin-bottom:11px;font-size:15px;color:#6a5330}
.escal{background:#fcf0ee;border:1px solid #efd2cc;border-left:3px solid var(--crit);
  border-radius:12px;padding:17px 20px;margin-bottom:12px}
.escal .who{font-size:12.5px;color:var(--crit);font-weight:600;margin-bottom:5px}

.allclear{background:#f2f7f1;border:1px solid #d4e3d0;border-left:3px solid var(--sage);
  border-radius:14px;padding:22px 26px}
.allclear .head{display:block;font:500 20px/1.4 var(--serif);margin-bottom:9px}
.allclear .body{display:block;font-size:15.5px;line-height:1.6;color:var(--ink-dim)}
.askprice{background:var(--card);border:1px dashed var(--line);border-radius:14px;
  padding:22px 26px;font-size:15px;line-height:1.6;color:var(--ink-dim)}
.askprice b{color:var(--ink)}
.gap{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--sage);
  border-radius:14px;padding:22px 26px;margin-top:16px;box-shadow:var(--shadow)}
.gap.urgent{border-left-color:var(--sand);background:#fdf7ea;border-color:#ecdcb9}
.gap .lbl{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.14em;
  color:var(--ink-faint);margin-bottom:11px}
.gap .head{display:block;font:500 20px/1.4 var(--serif);margin-bottom:9px}
.gap .body{display:block;font-size:15.5px;line-height:1.6;color:var(--ink-dim)}
.gap .why{display:block;margin-top:14px;padding-top:12px;border-top:1px solid var(--line);
  font-size:12.5px;color:var(--ink-faint)}

.bar{display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
button{font:inherit;font-size:14px;font-weight:550;padding:10px 20px;border-radius:999px;
  background:var(--clay);color:#fffdfa;border:0;cursor:pointer;
  transition:transform .12s,filter .18s}
button:hover:not(:disabled){filter:brightness(1.07);transform:translateY(-1px)}
button.ghost{background:var(--card);color:var(--ink);border:1px solid var(--line)}
button:disabled{opacity:.42;cursor:default;transform:none}

.grp{margin-bottom:14px}
.grp>summary{cursor:pointer;list-style:none;display:flex;align-items:baseline;gap:11px;
  padding:18px 24px;background:var(--card);border:1px solid var(--line);
  border-radius:16px;box-shadow:var(--shadow)}
.grp>summary::-webkit-details-marker{display:none}
.grp>summary::before{content:"→";color:var(--ink-faint);font-size:13px}
.grp[open]>summary::before{content:"↓"}
.grp[open]>summary{border-radius:16px 16px 0 0;border-bottom-color:transparent;
  box-shadow:none}
.grp .gt{font:500 18px/1 var(--serif)}
.grp .gn{font-size:12.5px;color:var(--ink-faint)}
.grp .gw{margin-left:auto;font-size:12.5px;color:var(--ink-faint)}
.grp .inner{border:1px solid var(--line);border-top:0;border-radius:0 0 16px 16px;
  background:var(--card);padding:4px 26px 18px;box-shadow:var(--shadow)}
.grp.first>summary,.grp.first .inner{border-color:#e8d9bd;background:#fdf9f0}
.grp.first .gt{color:var(--clay)}

.mxcap{font-size:15px;color:var(--ink-dim);margin:0 0 20px;line-height:1.6;max-width:62ch}
.mxlayout{display:grid;grid-template-columns:auto minmax(280px,1fr);gap:28px;
  align-items:start}
@media(max-width:900px){.mxlayout{grid-template-columns:1fr}}
.gridwrap{overflow-x:auto}
table.mx{border-collapse:separate;border-spacing:4px;font-size:11.5px}
table.mx th{font-weight:400;color:var(--ink-dim);font-size:12px;padding:0 6px;
  text-align:right;white-space:nowrap}
table.mx th.c{text-align:center;width:30px;font-variant:small-caps;letter-spacing:.05em}
table.mx th b{color:var(--clay);font-weight:650;font-variant:small-caps}
table.mx td{width:28px;height:28px;border-radius:7px;background:var(--sunk);
  text-align:center;color:transparent}
table.mx td.self{background:transparent}
table.mx td.high{background:var(--cell-crit)}
table.mx td.med{background:var(--cell-care)}
table.mx td.good{background:var(--cell-good)}
table.mx td.myth{background:var(--cell-myth)}
table.mx td.hit{cursor:pointer}
table.mx td.hit:hover{outline:2px solid var(--ink);outline-offset:1px}
table.mx td.pin{outline:2px solid var(--clay);outline-offset:1px}
.mxdetail{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:22px 24px;min-height:210px;box-shadow:var(--shadow)}
.mxempty{color:var(--ink-faint);font-size:14.5px;line-height:1.65}
.mxd-top{display:flex;gap:9px;align-items:baseline;flex-wrap:wrap;margin-bottom:8px}
.mxd-pair{font-size:13px;color:var(--ink-faint);margin-bottom:11px}
.mxd-say{font:400 17px/1.55 var(--serif);margin:0 0 13px}
.mxd-mech{font-size:14px;color:var(--ink-dim);line-height:1.6;
  border-left:2px solid var(--line);padding-left:13px;margin-bottom:13px}
.mxd-do{font-size:14.5px}
.mxd-do b{color:var(--clay);font-weight:650}
.key{display:flex;gap:18px;flex-wrap:wrap;margin-top:16px;font-size:12.5px;
  color:var(--ink-dim)}
.key span{display:flex;align-items:center;gap:7px}
.key i{width:12px;height:12px;border-radius:4px;display:inline-block;
  border:1px solid rgba(0,0,0,.06)}

table.wk{border-collapse:separate;border-spacing:5px;font-size:13px;width:100%}
table.wk th{font-size:12px;color:var(--ink-faint);font-weight:500;text-align:center}
table.wk th.n{text-align:left;width:40%;color:var(--ink);font-weight:500}
table.wk td{height:34px;border-radius:9px;background:var(--sunk);text-align:center}
table.wk td.on{background:var(--sage);color:#fffdfa;font-weight:650}

footer{margin-top:68px;padding-top:26px;border-top:1px solid var(--line);
  font-size:13px;color:var(--ink-faint);line-height:1.85}
.ver{display:inline-block;padding:3px 11px;border-radius:999px;font-size:12.5px;
  background:#f6ecd8;color:#8a6a24;border:1px solid #e4d2ab}
.ver.ok{background:#e3eedf;color:#41603f;border-color:#c6dcc1}

/* Marked-up photographs: numbers on the image, names in a list beside it. */
.shotwrap{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(290px,1fr);
  gap:22px;align-items:start}
@media(max-width:860px){.shotwrap{grid-template-columns:1fr}}
.shot{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:10px;box-shadow:var(--shadow)}
.shot + .shot{margin-top:14px}
.shot img{width:100%;border-radius:9px;display:block}
.legendbox{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:18px 20px;box-shadow:var(--shadow)}
.legendbox h4{margin:0 0 12px;font:600 11.5px/1 var(--sans);text-transform:uppercase;
  letter-spacing:.13em;color:var(--ink-faint)}
.lrow{display:flex;gap:11px;align-items:flex-start;padding:9px 0;font-size:13.5px;
  line-height:1.5}
.lrow > span:last-child{min-width:0;overflow-wrap:anywhere}
.lrow + .lrow{border-top:1px solid var(--line)}
.lnum{flex:0 0 22px;height:22px;border-radius:50%;display:grid;place-items:center;
  font-size:11.5px;font-weight:650;color:#fff}
.lnum.read{background:#689663}
.lnum.catalogue{background:#c68e3a}
.lnum.missed{background:#b0483a}
.lrow .how{font-size:12px;color:var(--ink-faint);display:block;margin-top:1px}
.shotkey{display:flex;gap:18px;flex-wrap:wrap;margin-top:14px;font-size:12.5px;
  color:var(--ink-dim)}
.shotkey span{display:flex;align-items:center;gap:7px}
.shotkey i{width:12px;height:12px;border-radius:3px;display:inline-block;
  border:1px solid rgba(0,0,0,.08)}

/* Price entry, offered after the first pass. */
table.prices{width:100%;border-collapse:collapse;margin:4px 0 18px;font-size:14px}
table.prices th{text-align:left;font:600 11px/1 var(--sans);text-transform:uppercase;
  letter-spacing:.1em;color:var(--ink-faint);padding:0 0 10px}
table.prices th.r{text-align:right;width:110px}
table.prices th.c{text-align:center;width:84px}
table.prices td{padding:7px 0;border-top:1px solid var(--line);vertical-align:middle}
table.prices td.r{text-align:right}
table.prices td.c{text-align:center}
table.prices input[type=number]{width:92px;font:inherit;font-size:14px;padding:7px 10px;
  border-radius:9px;border:1px solid var(--line);background:var(--sunk);
  color:var(--ink);text-align:right}
table.prices input[type=number]:focus{outline:2px solid var(--clay);outline-offset:1px}
table.prices input[type=checkbox]{width:16px;height:16px;accent-color:var(--clay)}
table.prices .typ{font-size:11.5px;color:var(--ink-faint);display:block}

/* Suggestions: the other half of the audit. */
.sugg{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:20px 24px;box-shadow:var(--shadow)}
.sugg + .sugg{margin-top:12px}
.sugg.covered{background:#f2f7f1;border-color:#d4e3d0}
.sugg h4{margin:0 0 8px;font:500 18px/1.3 var(--serif)}
.sugg p{margin:0 0 10px;font-size:14.5px;line-height:1.6;color:var(--ink-dim)}
.sugg .acts{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}
.sugg .act{font-size:12.5px;padding:3px 10px;border-radius:999px;
  background:var(--sunk);border:1px solid var(--line);color:var(--ink)}
.sugg .eg{font-size:13px;color:var(--ink-faint)}
.sugg .ok{font-size:14.5px;color:#41603f}

/* Observations from a face photo: questions, not findings. */
.obs{background:#f7f4ee;border:1px solid var(--line);border-radius:14px;
  padding:20px 24px;margin-bottom:14px}
.obs h4{margin:0 0 6px;font:500 18px/1.3 var(--serif)}
.obs .lit{font-size:13px;color:var(--ink-faint);margin:0 0 12px}
.obs .o{display:flex;gap:10px;align-items:baseline;padding:7px 0;font-size:14.5px}
.obs .o + .o{border-top:1px solid var(--line)}
.obs .conf{font-size:11px;text-transform:uppercase;letter-spacing:.07em;
  padding:2px 8px;border-radius:999px;background:var(--sunk);color:var(--ink-faint)}

/* Loading. A form post takes a few seconds — longer when products have to
   be looked up — and the browser gives no sign it is working. */
.loading{position:fixed;inset:0;background:rgba(246,242,236,.97);z-index:90;
  display:grid;place-items:center;backdrop-filter:blur(3px)}
.loading[hidden]{display:none}
.lbox{text-align:center;max-width:360px;padding:0 24px}
.dropper{position:relative;width:70px;height:112px;margin:0 auto 28px}
/* A pipette: rubber bulb, glass barrel with a little serum in it, tapered tip. */
.pipette{position:absolute;left:50%;top:0;width:20px;height:54px;margin-left:-10px;
  border-radius:10px 10px 2px 2px;
  background:linear-gradient(180deg,
    var(--clay) 0%, var(--clay) 30%,
    #efe9e0 30%, #efe9e0 52%,
    rgba(168,106,75,.30) 52%, rgba(168,106,75,.30) 100%);
  box-shadow:inset -2px 0 3px rgba(0,0,0,.06), inset 2px 0 3px rgba(255,255,255,.5)}
.pipette::after{content:"";position:absolute;left:50%;bottom:-10px;margin-left:-3.5px;
  width:7px;height:12px;background:rgba(168,106,75,.30);
  clip-path:polygon(0 0,100% 0,62% 100%,38% 100%)}
.drop{position:absolute;left:50%;top:58px;width:13px;height:13px;margin-left:-6.5px;
  background:var(--clay);border-radius:50% 50% 50% 0;transform:rotate(-45deg);
  animation:fall 2s cubic-bezier(.55,.06,.68,.53) infinite}
@keyframes fall{
  0%{top:58px;opacity:0;transform:rotate(-45deg) scale(.5)}
  18%{opacity:1;transform:rotate(-45deg) scale(1)}
  70%{top:94px;opacity:1;transform:rotate(-45deg) scale(1)}
  80%{top:98px;opacity:0;transform:rotate(-45deg) scale(.7)}
  100%{top:98px;opacity:0}
}
.ripple{position:absolute;left:50%;bottom:2px;width:12px;height:12px;margin-left:-6px;
  border:2px solid var(--sage);border-radius:50%;opacity:0;
  animation:spread 2s ease-out infinite}
.ripple.two{animation-delay:.28s}
@keyframes spread{
  0%,62%{transform:scale(.3);opacity:0}
  72%{opacity:.75}
  100%{transform:scale(3.4);opacity:0}
}
.lmsg{font:400 19px/1.45 var(--serif);color:var(--ink);min-height:28px}
.lsub{font-size:13.5px;color:var(--ink-faint);margin-top:10px}

/* Guided mode */
.guide{position:fixed;inset:0;background:rgba(246,242,236,.96);z-index:50;
  display:grid;place-items:center;padding:28px;backdrop-filter:blur(3px)}
.guide[hidden]{display:none}
.gbox{width:min(540px,100%);text-align:center}
.gslot{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-faint)}
.gname{font:500 34px/1.2 var(--serif);margin:14px 0 8px;letter-spacing:-.01em}
.ghow{font-size:18px;color:var(--ink-dim);line-height:1.5}
.gring{margin:30px auto 10px;width:132px;height:132px;border-radius:50%;
  display:grid;place-items:center;border:2px solid var(--line);background:var(--card);
  box-shadow:var(--shadow)}
.gring.waiting{border-color:var(--sand)}
.gcount{font:400 42px/1 var(--serif);font-variant-numeric:tabular-nums}
.gsub{font-size:12.5px;color:var(--ink-faint);min-height:19px}
.gbtns{display:flex;gap:10px;justify-content:center;margin-top:28px}
.gdots{display:flex;gap:6px;justify-content:center;margin-top:22px}
.gdots i{width:7px;height:7px;border-radius:50%;background:var(--line)}
.gdots i.done{background:var(--ink-faint)}
.gdots i.now{background:var(--clay);transform:scale(1.45)}

/* Print card: hidden on screen, the only thing that prints. */
.printcard{display:none}
@media print{
  @page{margin:12mm}
  body{background:#fff;color:#111;padding:0;font-size:10.5pt}
  .wrap>*{display:none !important}
  .wrap>.printcard{display:block !important}
  .guide{display:none !important}
  .printcard h1{font:400 20pt/1.15 var(--serif);margin:0 0 14pt}
  .printcard h3{font-size:11pt;text-transform:uppercase;letter-spacing:.08em;
    margin:0 0 7pt;padding-bottom:4pt;border-bottom:1pt solid #999}
  .pccols{display:grid;grid-template-columns:1fr 1fr;gap:22pt;margin-bottom:16pt}
  .printcard ol{margin:0;padding-left:16pt}
  .printcard li{margin-bottom:8pt;break-inside:avoid;line-height:1.35}
  .printcard em{color:#444;font-size:9pt}
  .pcd{font-size:9pt;color:#444;margin-top:1pt}
  table.pcw{border-collapse:collapse;width:100%;font-size:9pt;margin-top:4pt}
  table.pcw th,table.pcw td{border:0.5pt solid #bbb;padding:3pt 4pt;text-align:center}
  table.pcw th:first-child{text-align:left;width:46%;font-weight:600}
  .pcf{font-size:8.5pt;color:#555;margin-top:14pt;border-top:0.5pt solid #ccc;
    padding-top:7pt}
}
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


SPEECH_JS = """
/* Spoken walkthrough, with the gaps made legible.
 *
 * Two problems with the first version. It said "25 seconds" and then went
 * silent, so you could not tell whether it was counting or had crashed. And
 * the silence itself was unpleasant: a minute of nothing while you stand at a
 * sink feels a great deal longer than a minute.
 *
 * So every pause is announced before it starts, long ones get a spoken warning
 * near the end, and a quiet generated tone fills the gap with a soft tick every
 * ten seconds. The ticks are the useful part -- they tell you time is passing
 * without opening your eyes.
 *
 * The sound is synthesised with Web Audio rather than embedded. A minute of
 * audio as base64 would add megabytes to a page that must open by double-click,
 * and a CDN link is not allowed. Oscillators cost nothing.
 */
(function(){
  var ALL = DATA_STEPS;
  var queue = [], qi = 0, timer = null, warnTimer = null, running = false;
  var btnAm = document.getElementById('say-am'),
      btnPm = document.getElementById('say-pm'),
      stopB = document.getElementById('say-stop'),
      muteB = document.getElementById('say-mute'),
      statusEl = document.getElementById('say-status');

  if(!('speechSynthesis' in window)){
    [btnAm, btnPm].forEach(function(b){ b.disabled = true; });
    statusEl.textContent = 'this browser cannot read aloud';
    return;
  }

  /* ---- generated music ------------------------------------------------
   *
   * An arpeggio over a four-chord loop, synthesised note by note. Started as a
   * low drone, which was calm but read as dead air -- you could not tell it
   * from the page having crashed. A pulse does the same job as the old ten-
   * second tick (you know time is passing without looking) and is pleasanter
   * to stand in.
   *
   * Notes are scheduled 0.4s ahead on a repeating timer rather than all at
   * once: a ten-minute wait would otherwise mean thousands of live
   * oscillators.
   */
  var actx = null, muted = false, sched = null, nextNote = 0, step = 0, endAt = 0;

  var BPM = 104, EIGHTH = 30 / BPM;
  /* I - V - vi - IV, the most cheerful progression in common use. */
  var CHORDS = [
    [261.63, 329.63, 392.00],
    [196.00, 246.94, 392.00],
    [220.00, 261.63, 329.63],
    [174.61, 220.00, 261.63]
  ];
  var BASS = [130.81, 98.00, 110.00, 87.31];
  var PATTERN = [0, 1, 2, 1];

  function ctx(){
    if(!actx){
      var C = window.AudioContext || window.webkitAudioContext;
      if(!C) return null;
      actx = new C();
    }
    if(actx.state === 'suspended'){ actx.resume(); }
    return actx;
  }

  function note(freq, when, dur, type, level){
    var a = actx;
    var o = a.createOscillator(), g = a.createGain();
    o.type = type;
    o.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, when);
    g.gain.exponentialRampToValueAtTime(level, when + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    o.connect(g); g.connect(a.destination);
    o.start(when);
    o.stop(when + dur + 0.03);
  }

  function pump(){
    var a = actx;
    if(!a) return;
    while(nextNote < a.currentTime + 0.4){
      if(nextNote >= endAt){ stopSound(); return; }
      var bar = Math.floor(step / 8) % 4;
      var chord = CHORDS[bar];
      var pitch = chord[PATTERN[step % 4]] * (step % 8 >= 4 ? 2 : 1);
      note(pitch, nextNote, EIGHTH * 0.85, 'triangle', 0.045);
      if(step % 8 === 0){
        note(BASS[bar], nextNote, EIGHTH * 3.2, 'sine', 0.07);
      }
      if(step % 4 === 2){
        note(chord[2] * 2, nextNote, EIGHTH * 0.5, 'triangle', 0.02);
      }
      nextNote += EIGHTH;
      step++;
    }
  }

  function soundFor(seconds){
    stopSound();
    if(seconds < 4 || muted) return;
    var a = ctx();
    if(!a) return;
    nextNote = a.currentTime + 0.08;
    endAt = a.currentTime + seconds - 0.3;
    step = 0;
    pump();
    sched = setInterval(pump, 150);
  }

  function stopSound(){
    clearInterval(sched);
    sched = null;
  }

  /* ---- script --------------------------------------------------------- */
  /* The beat text is written for a page, where it follows a product name in
   * lower case. Spoken, it follows a full stop, and a voice reads "Step one.
   * one pump" with a stumble. */
  function cap(t){ return t ? t.charAt(0).toUpperCase() + t.slice(1) : t; }

  function howLong(secs){
    if(secs >= 60 && secs % 60 === 0){
      var m = secs / 60;
      return m === 1 ? 'a minute' : m + ' minutes';
    }
    return secs + ' seconds';
  }

  function build(slot){
    var steps = ALL.filter(function(s){ return s.slot === slot; });
    var out = [{say: (slot === 'am' ? 'Morning' : 'Evening') + ' routine, '
                     + steps.length + ' steps. I will tell you how long to spend on '
                     + 'each one, so you can put this down.', hold: 1}];
    steps.forEach(function(s, n){
      s.beats.forEach(function(bt){
        var text;
        if(bt.kind === 'apply'){
          text = 'Step ' + (n + 1) + '. ' + s.name + '. ' + cap(bt.text) + '.';
          if(s.freq !== 'daily'){ text += ' Only on ' + s.freq + '.'; }
          text += " I'll give you " + howLong(bt.secs) + '.';
        } else if(bt.kind === 'wait'){
          text = 'Now leave it to settle for ' + howLong(bt.secs)
               + ". I'll tell you when that is up.";
        } else {
          text = cap(bt.text) + '. ' + howLong(bt.secs) + '.';
        }
        out.push({say: text, hold: bt.secs});
      });
    });
    out.push({say: 'That is the whole routine. You are done.', hold: 0});
    return out;
  }

  function say(text, done){
    var u = new SpeechSynthesisUtterance(text);
    u.rate = 0.95;
    u.onend = u.onerror = done;
    speechSynthesis.speak(u);
  }

  function run(){
    if(!running) return;
    if(qi >= queue.length){ finish('done'); return; }
    var item = queue[qi++];
    statusEl.textContent = item.say;
    /* The hold starts when the sentence ends, not when it begins, or a long
     * instruction eats the time it just promised you. */
    say(item.say, function(){
      if(!running) return;
      soundFor(item.hold);
      if(item.hold >= 30){
        warnTimer = setTimeout(function(){
          if(running) say('Ten seconds left.', function(){});
        }, (item.hold - 10) * 1000);
      }
      timer = setTimeout(function(){ stopSound(); run(); }, item.hold * 1000);
    });
  }

  function start(slot){
    stop();
    ctx();
    running = true; queue = build(slot); qi = 0;
    btnAm.disabled = btnPm.disabled = true;
    stopB.disabled = false;
    run();
  }

  function finish(msg){
    running = false;
    clearTimeout(timer); clearTimeout(warnTimer);
    stopSound();
    speechSynthesis.cancel();
    btnAm.disabled = btnPm.disabled = false;
    stopB.disabled = true;
    statusEl.textContent = msg || '';
  }
  function stop(){ finish(''); }

  btnAm.addEventListener('click', function(){ start('am'); });
  btnPm.addEventListener('click', function(){ start('pm'); });
  stopB.addEventListener('click', stop);
  muteB.addEventListener('click', function(){
    muted = !muted;
    if(muted) stopSound();
    muteB.textContent = muted ? 'Sound off' : 'Sound on';
  });
  window.addEventListener('beforeunload', function(){ speechSynthesis.cancel(); });
})();
"""


GRID_JS = """
/* Matrix detail on hover, pinned on click.
 *
 * Hover alone does nothing on a phone, and it also means losing the text the
 * moment you move the mouse to read something else. Clicking pins a square so
 * hovering elsewhere stops overriding it.
 */
(function(){
  var panel = document.getElementById('mxdetail');
  var table = document.getElementById('mx');
  if(!panel || !table) return;
  var empty = panel.innerHTML, pinned = null;

  function show(k){
    var d = MX_DATA[k];
    if(!d) return;
    panel.innerHTML =
      '<div class="mxd-top"><span class="chip">' + d.rule + '</span>'
      + (d.verified ? '' : '<span class="chip unver">unverified rule</span>')
      + '<span class="kind">' + d.kind + '</span>'
      + '<span class="who">' + d.sev + '</span></div>'
      + '<div class="mxd-pair">' + d.pair + '</div>'
      + '<p class="mxd-say">' + d.say + '</p>'
      + '<div class="mxd-mech">' + d.mech + '</div>'
      + '<div class="mxd-do"><b>Do this:</b> ' + d.do + '</div>';
  }

  table.addEventListener('mouseover', function(ev){
    var td = ev.target.closest('td.hit');
    if(td && !pinned) show(td.dataset.k);
  });
  table.addEventListener('mouseleave', function(){
    if(!pinned) panel.innerHTML = empty;
  });
  table.addEventListener('click', function(ev){
    var td = ev.target.closest('td.hit');
    if(!td) return;
    if(pinned === td){
      pinned = null; td.classList.remove('pin'); panel.innerHTML = empty; return;
    }
    if(pinned) pinned.classList.remove('pin');
    pinned = td; td.classList.add('pin'); show(td.dataset.k);
  });
})();
"""


LOADING_MARKUP = '<div class="loading" id="loading" hidden><div class="lbox"><div class="dropper"><div class="pipette"></div><div class="drop"></div><div class="ripple"></div><div class="ripple two"></div></div><div class="lmsg" id="lmsg">Reading your labels</div><div class="lsub">This takes a few seconds. Longer if we have to look anything up.</div></div></div>'

LOADING_JS = """
/* Show it on submit. The browser then navigates to the response and
 * replaces the page, so nothing needs to hide it again — except on a
 * back-navigation, where a restored page would otherwise show a frozen
 * overlay over a finished audit. */
(function(){
  var box = document.getElementById('loading');
  var msg = document.getElementById('lmsg');
  if(!box || !msg) return;

  var lines = [
    'Reading your labels',
    'Matching the ingredients',
    'Checking what clashes with what',
    'Looking up anything we do not recognise',
    'Working out the order',
    'Writing it up'
  ];
  var i = 0, timer = null;

  function start(){
    box.hidden = false;
    i = 0; msg.textContent = lines[0];
    timer = setInterval(function(){
      i = (i + 1) % lines.length;
      msg.textContent = lines[i];
    }, 2600);
  }

  document.querySelectorAll('form').forEach(function(f){
    f.addEventListener('submit', start);
  });

  window.addEventListener('pageshow', function(ev){
    if(ev.persisted){ clearInterval(timer); box.hidden = true; }
  });
})();
"""


def script_json(value) -> str:
    """JSON for embedding inside a <script> element.

    json.dumps escapes for JSON, not for HTML. A product name containing
    "</script>" closes the element early and everything after it is parsed as
    markup — which is an XSS in a page built from text a stranger uploaded.
    The body of the page was escaped correctly; this hole was specifically the
    data handed to JavaScript, and it took a hostile-input test to surface it.

    Breaking the "</" sequence is the standard fix and is invisible to the JSON
    parser. U+2028 and U+2029 are legal in JSON strings and illegal in JS
    source, so they go too.
    """
    return (
        json.dumps(value)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def e(text: object) -> str:
    return html.escape(str(text), quote=True)


def _shortfall(audit) -> str:
    """How many products were seen but not identified, for the headline.

    Prefers the reader's own count of what is in the picture over the number
    of unreadable entries, because one entry can describe several products.
    A user who handed over thirteen and reads twelve should not have to work
    out where the other one went.
    """
    seen = audit.visible_count
    identified = len(audit.products)
    missed = max(seen - identified, 0) if seen else len(audit.unreadable)
    return f"{missed} not identified · " if missed else ""


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
        bits = [
            f"{b['text'] if b['kind'] == 'apply' else b['kind']} · {b['secs']}s"
            for b in beats_for(spec)
        ]
        how = f'<div class="how">{e(" → ".join(bits))}</div>'
    return (
        f'<div class="step" data-step="{e(key)}">'
        f'<div class="num">{step.order}</div><div>'
        f'<div class="name">{e(step.product_name)}{badge}</div>'
        f'<div class="meta">{e(step.form)}</div>{how}'
        f'<div style="margin-top:6px">{because}</div>'
        f"</div></div>"
    )


# Filled by the caller from the database, so the form and the engine cannot
# drift apart. Empty means no checkboxes rather than a stale hard-coded list.
CONCERN_CHOICES: list[tuple[str, str]] = []

CELL_CLASS = {"high": "high", "critical": "high", "medium": "med", "low": "good"}

# Rows past this stop being legible; the grid becomes a texture.
MATRIX_MAX = 16


def _conflict_grid(audit: AuditResult, explain: dict[str, str]) -> tuple[str, str]:
    """Product-by-product matrix of what clashes with what.

    Reading nineteen cards tells you about pairs one at a time; the shape of
    the problem — that one product is in four conflicts and the rest are fine —
    only appears when you see them together.
    """
    paired = [f for f in audit.findings if len(f.products) == 2]
    if not paired:
        return "", "{}"

    # Only products that actually interact. A grid of every product is mostly
    # empty squares, and past roughly twenty rows it stops being readable at
    # all — the products with nothing to say crowd out the ones with something.
    names: list[str] = []
    for f in paired:
        for n in f.products:
            if n not in names:
                names.append(n)
    if len(names) < 2:
        return "", "{}"

    if len(names) > MATRIX_MAX:
        # Keep the busiest: a product in six conflicts is why the user is here.
        degree = {n: sum(1 for f in paired if n in f.products) for n in names}
        names = sorted(names, key=lambda n: -degree[n])[:MATRIX_MAX]
        paired = [f for f in paired if all(n in names for n in f.products)]

    worst: dict[tuple[str, str], str] = {}
    best: dict[tuple[str, str], object] = {}
    rank = {"high": 3, "med": 2, "good": 1, "myth": 0}
    for f in paired:
        cls = "myth" if f.type == "myth" else (
            "good" if f.type == "synergy" else CELL_CLASS.get(f.severity, "med")
        )
        key = tuple(sorted(f.products))
        if key not in worst or rank[cls] > rank[worst[key]]:
            worst[key] = cls
            best[key] = f

    # Column headers are product initials, not numbers.
    #
    # Numbering them 1..N and putting the digits above a coloured grid reads as
    # a 1-to-10 rating scale — a reader asked what the scale meant, which is the
    # right question to ask of what the page appeared to show. Initials cannot
    # be mistaken for a magnitude.
    def initials(name: str) -> str:
        words = [w for w in re.split(r"[\s/+]+", name) if w and w[0].isalnum()]
        return ("".join(w[0] for w in words[:2]) or name[:2]).upper()

    marks: dict[str, str] = {}
    for n in names:
        mark, bump = initials(n), 1
        while mark in marks.values():
            bump += 1
            mark = f"{initials(n)}{bump}"
        marks[n] = mark

    data: dict[str, dict] = {}
    head = "".join(f'<th class="c">{e(marks[n])}</th>' for n in names)
    rows = []
    for a in names:
        cells = []
        for bname in names:
            if a == bname:
                cells.append('<td class="self"></td>')
                continue
            pair = tuple(sorted((a, bname)))
            cls = worst.get(pair, "")
            if not cls:
                cells.append("<td></td>")
                continue
            f = best[pair]
            cell_id = f"{marks[pair[0]]}|{marks[pair[1]]}"
            data[cell_id] = {
                "rule": f.rule_id,
                "kind": TYPE_LABEL.get(f.type, f.type),
                "sev": SEVERITY_LABEL.get(f.severity, f.severity),
                "pair": " + ".join(pair),
                "say": explain.get(f.rule_id) or f.guidance,
                "mech": f.mechanism,
                "do": f.guidance,
                "verified": f.verified,
            }
            cells.append(f'<td class="{cls} hit" data-k="{e(cell_id)}">.</td>')
        label = a if len(a) <= 28 else a[:26] + "…"
        rows.append(f'<tr><th><b>{e(marks[a])}</b>  {e(label)}</th>{"".join(cells)}</tr>')

    key = (
        '<div class="key">'
        '<span><i style="background:var(--cell-crit)"></i>conflict</span>'
        '<span><i style="background:var(--cell-care)"></i>use with care</span>'
        '<span><i style="background:var(--cell-good)"></i>works well together</span>'
        '<span><i style="background:var(--cell-myth)"></i>myth, ignore it</span>'
        '<span><i style="background:var(--sunk)"></i>no interaction</span>'
        "</div>"
    )
    html_out = (
        '<div class="card">'
        '<p class="mxcap">Each row and column is one of your products. '
        "Hover or tap a coloured square to see what happens when you use those "
        "two together.</p>"
        '<div class="mxlayout"><div>'
        f'<div class="gridwrap"><table class="mx" id="mx">'
        f'<tr><th></th>{head}</tr>{"".join(rows)}</table></div>{key}</div>'
        '<div class="mxdetail" id="mxdetail"><div class="mxempty">'
        "Hover a coloured square and the detail shows here. Click to keep it "
        "open while you read."
        "</div></div></div></div>"
    )
    return html_out, script_json(data)


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


def beats_for(spec) -> list[dict]:
    """The physical sequence for one step: apply, then finish, then any wait.

    Single source of truth. The step list, the guided player, the spoken
    walkthrough and the printed card all render from this. They were each
    assembling it separately and promptly drifted: the audio announced
    "let it absorb, 30 seconds" while the written step said only "let it
    absorb", because the duration existed in one path and not the others.
    """
    if spec is None:
        return [{"kind": "apply", "text": "apply as usual", "secs": 15}]

    out = [{
        "kind": "apply",
        "text": f"{spec.amount}, {spec.motion} on {spec.area}",
        "secs": spec.seconds,
    }]

    if spec.finish == "rinse off":
        out.append({
            "kind": "rinse off",
            "text": "rinse thoroughly with lukewarm water, then pat dry",
            "secs": spec.finish_seconds or 25,
        })
    elif spec.finish == "pat dry":
        out.append({
            "kind": "pat dry",
            "text": "pat dry with a clean towel",
            "secs": spec.finish_seconds or 10,
        })
    elif spec.finish == "let it absorb" and not spec.wait_after_seconds:
        out.append({
            "kind": "let it absorb",
            "text": "let it sink in before the next product",
            "secs": spec.finish_seconds or 20,
        })

    if spec.wait_after_seconds:
        # Absorbing and waiting are one pause described twice. Run in series
        # they put two minutes of standing still on a toner.
        out.append({
            "kind": "let it absorb",
            "text": "let it absorb and settle before the next product",
            "secs": max(spec.wait_after_seconds, spec.finish_seconds),
        })

    return out


def _print_card(audit: AuditResult, specs: dict) -> str:
    """A one-page card for the bathroom mirror.

    The most honest answer to "I don't want a screen near my skincare" is not a
    better screen. This is a separate block rather than a print stylesheet over
    the live page: the page is a dark-themed analysis and the card is a light,
    dense reference, and trying to make one print as the other produces
    something that is bad at both.
    """
    def column(label: str, steps: list) -> str:
        rows = []
        for s in steps:
            spec = specs.get(s.product_name)
            detail = ""
            if spec:
                bits = [
                    f"{spec.amount}, {spec.motion} {b['secs']}s" if b["kind"] == "apply"
                    else f"{b['kind']} {b['secs']}s"
                    for b in beats_for(spec)
                ]
                detail = f'<div class="pcd">{e(" → ".join(bits))}</div>'
            freq = "" if s.frequency == "daily" else f' <em>({e(s.frequency)})</em>'
            rows.append(f"<li><b>{e(s.product_name)}</b>{freq}{detail}</li>")
        return f"<div><h3>{label}</h3><ol>{''.join(rows)}</ol></div>"

    alternating = [s for s in audit.routine.pm if s.frequency != "daily"]
    week = ""
    if len(alternating) >= 2:
        n = len(alternating)
        rows = []
        for i, step in enumerate(alternating):
            cells = "".join(
                f'<td>{"●" if day % n == i else ""}</td>' for day in range(7)
            )
            rows.append(f"<tr><th>{e(step.product_name)}</th>{cells}</tr>")
        head = "".join(f"<th>{d[0]}</th>" for d in DAYS)
        week = (
            "<h3>Which nights</h3>"
            f'<table class="pcw"><tr><th></th>{head}</tr>{"".join(rows)}</table>'
        )

    return (
        '<section class="printcard">'
        "<h1>Skincare routine</h1>"
        f'<div class="pccols">{column("Morning", audit.routine.am)}'
        f'{column("Evening", audit.routine.pm)}</div>{week}'
        '<p class="pcf">Rinse-off steps are marked. Waits are for letting a '
        "product settle before the next one goes on.</p>"
        "</section>"
    )


def render(
    audit: AuditResult,
    narrative: AuditNarrative | None = None,
    annotated: list[str] | None = None,
    carry: str | None = None,
    legend: list[dict] | None = None,
    skin=None,
    sourced: dict | None = None,
) -> str:
    specs = {s.product_name: s for s in (narrative.steps if narrative else [])}
    explain = {x.rule_id: x.plain_language for x in (narrative.explanations if narrative else [])}
    w = audit.waste

    # Guided mode runs in real seconds, not a sped-up preview: the point is to
    # follow it while actually applying things, so the agent's own durations and
    # waits are used unchanged.
    seq = []
    for slot, steps in (("am", audit.routine.am), ("pm", audit.routine.pm)):
        for s_ in steps:
            seq.append({
                "slot": slot, "order": s_.order, "of": len(steps),
                "name": s_.product_name, "freq": s_.frequency,
                "beats": beats_for(specs.get(s_.product_name)),
            })

    grid_data = '{}'
    parts: list[str] = []
    parts.append(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Skincare shelf audit</title>"
        f"<style>{CSS}</style></head><body><div class=\"wrap\">"
    )

    parts.append(
        f"<h1>Your shelf, audited</h1>"
        f'<p class="sub">{w.products_owned} product'
        f'{"s" if w.products_owned != 1 else ""} · '
        # The count the reader could not identify belongs in the headline, not
        # in a note below it. A user who handed over thirteen products and
        # read "12 products" has to go looking for the missing one; told "12
        # products · 2 not identified" they already know where it went.
        f'{_shortfall(audit)}'
        f'{len(audit.findings)} finding'
        f'{"s" if len(audit.findings) != 1 else ""}</p>'
    )

    # Before anything else. A reader who scrolls past this and sees "no
    # conflicts" will believe their shelf is fine.
    if audit.unresolved:
        n = len(audit.unresolved)
        total = len(audit.products)
        names = ", ".join(u.name for u in audit.unresolved[:6])
        more = f" and {n - 6} more" if n > 6 else ""
        parts.append("<h2>Read this first</h2>")
        parts.append(
            f'<div class="gap urgent"><span class="lbl">Incomplete audit</span>'
            f'<span class="head">{n} of your {total} products could not be checked.</span>'
            f'<span class="body">This audit only covers the rest, so it is not a '
            f'clean bill of health — it is a partial one. A photograph of the '
            f'front of a bottle shows the product name; the ingredient list is '
            f'on the back, and that is what the checks run on. Photograph the '
            f'back labels of these, or type their ingredients in, and run it '
            f'again.</span>'
            f'<span class="why">Not checked: {e(names)}{e(more)}</span></div>'
        )

    # Looked up on the web. Each one carries the URL it came from, so a
    # reader can check it — that is the whole difference between this and a
    # guess.
    if sourced:
        rows = []
        for name, rec in sourced.items():
            link = e(rec.get("source_url") or "")
            shown = e(rec.get("matched_name") or "source")
            note = rec.get("note") or ""
            tail = f" <em>{e(note)}</em>" if note else ""
            price = rec.get("typical_price_usd")
            psrc = rec.get("price_source_url") or ""
            if price and psrc:
                money = (
                    f' · <a href="{e(psrc)}" style="color:var(--clay)">'
                    f"${price:,.0f}</a>"
                )
            elif price:
                money = f" · ${price:,.0f}"
            else:
                money = " · no published price found"
            rows.append(
                f"<li><b>{e(name)}</b> — "
                f'<a href="{link}" style="color:var(--clay)">{shown}</a>'
                f"{money}{tail}</li>"
            )
        parts.append(
            f'<div class="note" style="margin-top:12px">'
            f"<strong>{len(sourced)} product(s) had their ingredients looked up "
            f"online.</strong> Published formulations differ by region and change "
            f"over time, so check the bottle before acting on anything that "
            f'depends on them.<ul style="margin:10px 0 0">{"".join(rows)}</ul></div>'
        )

    # Catalogue matches are a claim about a product, not a reading of the one
    # in the user's hand. Say so, with the names, so it can be checked.
    from_cat = [p for p in audit.products if p.matched_from_catalogue]
    if from_cat:
        rows = "".join(
            f"<li><b>{e(p.product.name)}</b> → {e(p.matched_from_catalogue)}</li>"
            for p in from_cat
        )
        parts.append(
            f'<div class="note" style="margin-top:12px">'
            f"<strong>{len(from_cat)} product(s) were identified by name, not by "
            f"reading a label.</strong> Their ingredients come from a reference "
            f"list, so they are what these products <em>usually</em> contain — "
            f"formulations change. Worth a glance at the bottle before acting on "
            f'anything below that depends on them.<ul style="margin:10px 0 0">{rows}</ul></div>'
        )

    if audit.unreadable:
        # Wording stays input-agnostic: this fires for typed lists too, where
        # it previously claimed things were "visible in the photographs".
        n = len(audit.unreadable)
        parts.append(
            f'<div class="note" style="margin-top:12px">'
            f'{n} further item{"s" if n != 1 else ""} could not be identified at all '
            f'and {"are" if n != 1 else "is"} not included in this audit.</div>'
        )

    if narrative and narrative.summary:
        # The summary sat directly under the title with nothing saying what it
        # was, so a first-time reader met a paragraph about retinols before
        # knowing whether it was a warning, a sales pitch or a description of
        # the tool. Every other block on the page is labelled; this one was not.
        parts.append("<h2>Start here</h2>")
        # The label alone said where to begin but not what the paragraph was.
        # A one-line descriptor underneath answers "what am I reading" before
        # the reader has to infer it from the content.
        parts.append(
            '<p class="lede">The main summary of your shelf — what matters most, and what to do first.</p>'
        )
        parts.append(f'<div class="card summary">{e(narrative.summary)}</div>')

    parts.append("<h2>Money</h2>")
    if w.shelf_value_usd == 0:
        # Four zeroes look like a broken feature. They mean nobody said what
        # anything cost — which is a thing the user can fix, so ask.
        parts.append(
            '<div class="askprice"><b>No prices yet.</b> This section works out '
            "what is sitting unused, what you have bought twice, and what is "
            "being wasted by a clash — all of which need to know what things "
            "cost. Add a price after any product (<i>CeraVe Cleanser, $16</i>) "
            "and mention anything you never use, then run it again.</div>"
        )
    else:
        parts.append('<div class="stats">')
        parts.append(_stat(f"${w.shelf_value_usd:,.0f}", "on the shelf"))
        parts.append(_stat(f"${w.unused_value_usd:,.0f}",
                           f"unused ({w.products_unused} "
                           f"product{'s' if w.products_unused != 1 else ''})",
                           "warn" if w.unused_value_usd else ""))
        parts.append(_stat(f"${w.redundant_value_usd:,.0f}", "duplicate function",
                           "warn" if w.redundant_value_usd else ""))
        parts.append(_stat(f"${w.conflicted_value_usd:,.0f}", "in high-severity conflict",
                           "bad" if w.conflicted_value_usd else ""))
        parts.append("</div>")

        # Say whose prices these are. A typical price is the right order of
        # magnitude for "what is sitting unused" and the wrong basis for any
        # claim about what this person wasted.
        typical = [p for p in audit.products if p.price_is_typical]
        if typical:
            n, total = len(typical), len(audit.products)
            parts.append(
                f'<p class="lede" style="margin-top:14px">'
                f"{n} of these {total} prices {'is' if n == 1 else 'are'} a typical "
                f"retail figure rather than what you paid, because you did not say. "
                f"Good enough to see roughly what is sitting unused; not a quote. "
                f"Add your own prices to make these numbers yours.</p>"
            )

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
        '<button id="say-am">Read me the morning</button>'
        '<button id="say-pm">Read me the evening</button>'
        '<button id="say-stop" class="ghost" disabled>Stop</button>'
        '<button id="say-mute" class="ghost">Sound on</button>'
        '<button id="print" class="ghost">Print a card for the mirror</button>'
        "</div>"
        '<p style="font-size:12.5px;color:var(--ink-faint);margin:-4px 0 14px">'
        "Press play and put the phone down. It says how long to spend on each step, "
        "plays something to stand to during the waits, and warns "
        "you before each one ends. Or print the card and tape it inside a cabinet door."
        '</p><div class="bar">'
        '<button id="go-am" class="ghost">Step through the morning on screen</button>'
        '<button id="go-pm" class="ghost">Step through the evening on screen</button>'
        '<span id="say-status" style="font-size:12px;color:var(--ink-faint);flex:1"></span>'
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

    if annotated:
        parts.append("<h2>Your photographs, marked up</h2>")
        # Numbers on the image, names in the list beside it.
        #
        # Captions drawn onto the photograph overlapped each other, covered
        # the bottles they pointed at, and truncated the names anyway. On a
        # shelf of twenty products it was unreadable.
        parts.append(
            '<p class="lede">Each numbered marker matches the list beside it.</p>'
        )
        parts.append('<div class="shotwrap"><div>')
        for uri in annotated:
            parts.append(
                f'<div class="shot"><img src="{uri}" '
                f'alt="Your shelf, with each identified product numbered"></div>'
            )
        parts.append(
            '<div class="shotkey">'
            '<span><i style="background:#689663"></i>read from the label</span>'
            '<span><i style="background:#c68e3a"></i>identified by name</span>'
            '<span><i style="background:#b0483a"></i>not read</span>'
            "</div></div>"
        )

        rows = []
        for item in legend or []:
            status = item.get("status", "missed")
            note = {
                "read": "read from the label",
                "catalogue": "identified by name \u2014 check the bottle",
                "missed": "not read, not in this audit",
            }[status]
            # Not truncated. The legend is a vertical list with room to wrap,
            # and "Multiple bottles and boxes along lower shelf, especially c\u2026"
            # tells a reader nothing about which bottles.
            label = item["label"]
            rows.append(
                f'<div class="lrow"><span class="lnum {status}">{item["index"]}</span>'
                f'<span>{e(label)}<span class="how">{note}</span></span></div>'
            )
        inner = "".join(rows) or '<p class="mxempty">Nothing could be located in the image.</p>'
        parts.append(
            f'<div class="legendbox"><h4>What is in the picture</h4>{inner}</div></div>'
        )

    if skin is not None and (skin.observations or skin.needs_a_clinician):
        parts.append("<h2>From your photo</h2>")
        if skin.needs_a_clinician:
            parts.append(
                '<div class="escal"><div class="who">Worth having looked at</div>'
                "Something visible here is better assessed by a person than by a "
                "product. This tool does not say what it is, and nothing below "
                "replaces that.</div>"
            )
        if skin.observations:
            rows = "".join(
                f'<div class="o"><span class="conf">{e(o.confidence)}</span>'
                f"<span>{e(o.seen)} {e(o.where)}</span></div>"
                for o in skin.observations
            )
            lit = f'<p class="lit">{e(skin.lighting_note)}</p>' if skin.lighting_note else ""
            parts.append(
                f'<div class="obs"><h4>What the photograph seems to show</h4>'
                f"{lit}{rows}"
                f'<p class="lit" style="margin:12px 0 0">These are guesses from a '
                f"photograph, not findings. The boxes below are ticked from them — "
                f"untick anything that is wrong and run it again.</p></div>"
            )

    if audit.suggestions:
        parts.append("<h2>What you might add</h2>")
        parts.append(
            '<p class="lede">For the concerns you confirmed. Every suggestion is '
            "an ingredient the table says addresses that concern, not an opinion "
            "about your skin.</p>"
        )
        for s in audit.suggestions:
            if s.already_covered_by:
                owned = ", ".join(s.already_covered_by[:3])
                parts.append(
                    f'<div class="sugg covered"><h4>{e(s.concern_label)}</h4>'
                    f'<p class="ok">Already covered — {e(owned)} '
                    f"{'addresses' if len(s.already_covered_by) == 1 else 'address'} "
                    f"this. Nothing to add.</p></div>"
                )
                continue
            acts = "".join(f'<span class="act">{e(a)}</span>' for a in s.missing_actives[:6])
            eg = (
                f'<div class="eg">Products containing one of these: '
                f"{e(', '.join(s.products[:3]))}</div>"
                if s.products else ""
            )
            parts.append(
                f'<div class="sugg"><h4>{e(s.concern_label)}</h4>'
                f"<p>Nothing on your shelf addresses this.</p>"
                f'<div class="acts">{acts}</div>'
                f"{f'<p>{e(s.why)}</p>' if s.why else ''}{eg}</div>"
            )

    week = _week_grid(audit)
    if week:
        parts.append("<h2>Which nights</h2>")
        parts.append(week)

    if audit.routine.notes:
        parts.append("<h2>Worth knowing</h2>")
        for note in audit.routine.notes:
            parts.append(f'<div class="note">{e(note)}</div>')

    grid, grid_data = _conflict_grid(audit, explain)
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

    if not audit.findings:
        # An empty heading reads as a failed render. No conflicts is a result,
        # and for a shelf of gentle products it is the expected one.
        checked = len(audit.products) - len(audit.unresolved)
        parts.append(
            '<div class="allclear"><span class="head">Nothing to fix.</span>'
            f'<span class="body">No clashes, no duplicates and no ordering '
            f"problems among the {checked} product"
            f'{"s" if checked != 1 else ""} that could be checked. That is a '
            "straightforward shelf — the products on it do not interact in ways "
            "worth warning you about.</span></div>"
        )
    else:
        _section("first", "Fix these first",
                 "costing you money or results", open_=True, oneline=False)

    # Gaps, not restatements.
    #
    # This slot used to list the single-product timing rules — sunscreen last,
    # retinoids at night, acids at night. They are not tasks: the engine has
    # already applied all three, the routine is ordered accordingly, and every
    # step carries the rule id that placed it. Printing them under "What to do"
    # asked the reader to act on work that was already finished, and buried the
    # one real instruction (wear sunscreen) by repeating it twice.
    #
    # What belongs here is what the shelf is missing, which no pairwise rule
    # can see.
    for gap in audit.gaps:
        urgent = gap.severity in ("critical", "high")
        parts.append(
            f'<div class="gap{" urgent" if urgent else ""}">'
            f'<span class="lbl">{e(gap.label)}</span>'
            f'<span class="head">{e(gap.headline)}</span>'
            f'<span class="body">{e(gap.message)}</span>'
            f'<span class="why">Triggered by: {e(", ".join(gap.because))}</span>'
            "</div>"
        )

    parts.append(_print_card(audit, specs))

    if carry is not None:
        # Carried in a hidden field rather than a session. The app holds no
        # state between requests and stores nothing, which is what the landing
        # page promises about photographs; a server-side session would quietly
        # make that untrue.
        missed = [u.name for u in audit.unresolved] + [
            p.product.name for p in audit.products if p.matched_from_catalogue
        ]
        hint = (
            f"Worth re-photographing: {e(', '.join(missed[:5]))}"
            f"{' and others' if len(missed) > 5 else ''}."
            if missed else
            "Everything here was read from a label, so there is nothing outstanding."
        )
        rows = []
        for p in audit.products:
            name = p.product.name
            price = p.product.price_usd
            # Three states worth distinguishing, because an empty price box
            # looks like a bug when it is actually a limit. A brand name is
            # not a product: "Glytone" could be a $34 cleanser or a $58 cream,
            # and filling that in would be inventing a number.
            if p.price_is_typical:
                typical = ' <span class="typ">typical retail</span>'
            elif not p.actives and not p.matched_from_catalogue:
                typical = (
                    ' <span class="typ">only the brand was readable — '
                    "name the product below and it can be priced</span>"
                )
            else:
                typical = ""
            value = "" if (price is None or p.price_is_typical) else f"{price:.0f}"
            placeholder = f"{price:.0f}" if p.price_is_typical and price else ""
            checked = " checked" if p.product.unused else ""
            rows.append(
                f"<tr><td>{e(name)}{typical}</td>"
                f'<td class="r"><input type="hidden" name="pname" value="{e(name)}">'
                f'<input type="number" name="pprice" min="0" step="1" '
                f'value="{value}" placeholder="{placeholder}"></td>'
                f'<td class="c"><input type="checkbox" name="punused" '
                f'value="{e(name)}"{checked}></td></tr>'
            )

        # Anything the photograph raised is pre-ticked but still a question:
        # it only became a concern because the user left it ticked.
        observed = {o.concern for o in (skin.observations if skin else [])}
        chosen = {s.concern for s in audit.suggestions} | observed
        concern_boxes = "".join(
            f'<label><input type="checkbox" name="concerns" value="{e(cid)}"'
            f'{" checked" if cid in chosen else ""}><span>{e(label)}</span></label>'
            for cid, label in (CONCERN_CHOICES or [])
        )

        parts.append("<h2>Add to this audit</h2>")
        parts.append(
            f'<form class="again" method="post" action="/audit" '
            f'enctype="multipart/form-data">'
            f"<p>Fill in what you actually paid and the money figures become "
            f"yours rather than typical retail. Photograph the back labels of "
            f"anything amber or red and add them below — what is already "
            f"identified is kept, and a real label replaces a name match."
            f"<br><br>{hint}</p>"
            f"<table class=\"prices\"><tr><th>Product</th>"
            f'<th class="r">What you paid</th><th class="c">Never use it</th></tr>'
            f'{"".join(rows)}</table>'
            f'<div class="checks" style="margin-bottom:16px">'
            f"<strong style=\"font-size:14px\">What are you trying to treat?</strong>"
            f"{concern_boxes}</div>"
            f'<input type="file" name="photos" accept="image/*" multiple>'
            f'<textarea name="typed" placeholder="Or type any products that are '
            f'missing, with ingredients if you have them"></textarea>'
            f'<input type="hidden" name="carried" value="{e(carry)}">'
            f'<button type="submit">Audit again</button>'
            f"</form>"
        )

    parts.append(LOADING_MARKUP)

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
        f"Generated {datetime.now().strftime('%d %B %Y, %H:%M')}.<br>"
        "Every claim above cites the rule that produced it. "
        "This is not medical advice — products flagged for a clinician are not assessed here."
        "</footer></div>"
    )

    parts.append(
        f"<script>var DATA_STEPS={script_json(seq)};var MX_DATA={grid_data};"
        f"{JS}{SPEECH_JS}{GRID_JS}{LOADING_JS}"
        "document.getElementById('print').addEventListener('click',function(){window.print()});"
        "</script></body></html>"
    )
    return "".join(parts)

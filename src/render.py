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

import base64
import html
import re
import json
from datetime import datetime

# Eight bottles is as many as fit on the shelf legibly.
MAX_SHELF = 8

# The opening act is drawn by filmstrip.py only. The in-page player has no
# CSS for a shelf, a sort, a clash or a week, and handing it scenes it
# cannot draw would show a bare face under a caption for four scenes --
# a blank frame that looks like a step, which is the failure this project
# keeps finding. The split is deliberate and test_storyboard checks it.
OPENING_ANIMS = frozenset({"shelf", "sort", "clash", "week"})

from storyboard import container_for, scenes_for, short_time
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
.step.ghost{opacity:.85}
.step.ghost .num{background:none;border:1px dashed var(--sand);color:var(--sand)}
.step.ghost .name{color:var(--ink-dim)}
.alt{font-size:13px;color:var(--clay);background:#fdf7ea;border-radius:5px;padding:5px 9px;margin:5px 0 2px}
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
.gap.suggest{border-left-color:var(--sand);background:#fcfbf8;opacity:.94}
.gap.suggest .lbl{color:var(--ink-3)}
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
table.prices th.r{text-align:right;width:120px;padding-right:14px}
table.prices th.c{text-align:center;width:96px}
table.prices td.r{padding-right:14px}
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

/* The routine, drawn moving. See src/storyboard.py for why this is drawn
   rather than generated: a clip from a video model could not cite a rule or
   show the user's own products, and every other screen here can. */
.film{margin:34px 0 10px;background:var(--card);border:1px solid var(--line);
  border-radius:16px;box-shadow:var(--shadow);overflow:hidden}
.film-top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;
  padding:18px 22px 0}
.film-top h3{margin:0;font:600 18px/1.3 var(--serif)}
.film-note{font-size:12.5px;color:var(--ink-faint)}
.film-body{display:grid;grid-template-columns:270px 1fr;gap:26px;padding:16px 22px 22px;align-items:start}
@media(max-width:620px){.film-body{grid-template-columns:1fr}}
.stage{background:var(--sunk);border-radius:14px;padding:4px 18px;position:relative}
.stage svg{display:block;width:100%;height:auto}
.face-line{fill:none;stroke:var(--ink-faint);stroke-width:1.6;stroke-linecap:round}
.face-skin{fill:var(--card)}

/* Product dots. One per anchor; the driver staggers them with --d so a
   whole-face application lands as a spread, not a single flash. */
.pd{fill:var(--clay);opacity:0;transform-box:fill-box;transform-origin:center}
.stage[data-anim="dab"]    .pd{animation:pd-dab   1.1s ease-out     infinite var(--d)}
.stage[data-anim="orbit"]  .pd{animation:pd-orbit 1.5s linear       infinite var(--d)}
.stage[data-anim="foam"]   .pd{animation:pd-foam  1.6s ease-in-out  infinite var(--d)}
.stage[data-anim="press"]  .pd{animation:pd-press 1.9s ease-in-out  infinite var(--d)}
.stage[data-anim="tap"]    .pd{animation:pd-tap   .75s ease-in-out  infinite var(--d)}
.stage[data-anim="sweep"]  .pd{animation:pd-sweep 1.7s ease-in-out  infinite var(--d)}
.stage[data-anim="absorb"] .pd:not(.rest),
.stage[data-anim="rinse"]  .pd:not(.rest),
.stage[data-anim="towel"]  .pd:not(.rest){animation:none;opacity:0}
/* What was just applied, still sitting there while it absorbs or is rinsed
   away. Without it a finish scene was an empty face, so every absorb looked
   the same whatever had been put on. */
.pd.rest{opacity:0;animation:none}

/* Dispensing. The face steps back and the dose is shown at the size it
   actually is, because "two fingers' length" is the one instruction a
   sentence is genuinely bad at. */
.stage[data-anim="dispense"] .face-line,
.stage[data-anim="dispense"] .face-skin{opacity:.1}
.dosedot{fill:var(--clay);opacity:0;animation:dosein .9s ease-out forwards var(--d)}
.dosebar{fill:var(--clay);opacity:0;animation:dosein .9s ease-out forwards var(--d)}
@keyframes dosein{0%{opacity:0;transform:translateY(-8px)}100%{opacity:.9;transform:none}}
.dosehand{fill:#e9d6c7;stroke:#c7b09e;stroke-width:1.5}

/* A mask is a layer, not a set of touch points. */
.stage[data-anim="maskon"] .pd{animation:layeron 2.2s ease-out infinite var(--d);
  r:17px;opacity:.5}
@keyframes layeron{0%{opacity:0;r:4px}60%{opacity:.5;r:17px}100%{opacity:.5;r:17px}}
.stage[data-anim="maskoff"] .pd.rest{animation:layeroff 2s ease-in infinite var(--d);
  r:17px}
@keyframes layeroff{0%{opacity:.5}100%{opacity:0}}
.stage[data-anim="absorb"] .pd.rest{animation:settle 2.4s ease-in-out infinite var(--d)}
.stage[data-anim="rinse"]  .pd.rest{animation:washoff 1.2s ease-out infinite var(--d)}
.stage[data-anim="towel"]  .pd.rest{opacity:.18}
@keyframes settle{0%,100%{opacity:.2;transform:scale(.9)}50%{opacity:.45;transform:scale(1.1)}}
@keyframes washoff{0%{opacity:.38}100%{opacity:0}}

@keyframes pd-dab{0%{opacity:0;transform:scale(.2)}
  30%{opacity:.95;transform:scale(1)}100%{opacity:.5;transform:scale(1)}}
@keyframes pd-orbit{0%{opacity:.9;transform:translate(0,0)}
  25%{transform:translate(5px,-4px)}50%{transform:translate(0,-6px)}
  75%{transform:translate(-5px,-4px)}100%{opacity:.9;transform:translate(0,0)}}
@keyframes pd-foam{0%{opacity:.9;transform:scale(1) translate(0,0)}
  40%{opacity:.75;transform:scale(1.9) translate(4px,-3px)}
  70%{opacity:.6;transform:scale(2.4) translate(-3px,2px)}
  100%{opacity:.9;transform:scale(1) translate(0,0)}}
@keyframes pd-press{0%{opacity:.35;transform:scale(1.5)}
  45%{opacity:.95;transform:scale(.72)}75%{opacity:.95;transform:scale(.72)}
  100%{opacity:.35;transform:scale(1.5)}}
@keyframes pd-tap{0%{opacity:.9;transform:translateY(0) scale(1)}
  50%{opacity:1;transform:translateY(-3.5px) scale(.85)}
  100%{opacity:.9;transform:translateY(0) scale(1)}}
@keyframes pd-sweep{0%{opacity:0;transform:translateX(0) scale(.6)}
  25%{opacity:.95;transform:translateX(0) scale(1)}
  100%{opacity:.25;transform:translateX(var(--out,6px)) scale(1.25)}}

/* Finishes. Water runs down, a towel presses, absorbing is a slow sheen. */
.water{opacity:0}
.wstream{fill:none;stroke:#7fa6bf;stroke-width:2.4;stroke-linecap:round;opacity:0}
.stage[data-anim="rinse"] .wstream{animation:water 1.2s linear infinite}
.stage[data-anim="rinse"] .water{opacity:1}
.stage[data-anim="rinse"] .wstream:nth-child(2){animation-delay:.18s}
.stage[data-anim="rinse"] .wstream:nth-child(3){animation-delay:.36s}
@keyframes water{0%{opacity:0;transform:translateY(-16px)}
  20%{opacity:.75}80%{opacity:.75}100%{opacity:0;transform:translateY(30px)}}
.towel{opacity:0;transform-box:fill-box;transform-origin:center}
.stage[data-anim="towel"] .towel{animation:towel 1.4s ease-in-out infinite}
@keyframes towel{0%,100%{opacity:0;transform:scale(.9)}
  35%,65%{opacity:.55;transform:scale(1)}}
.sheen{opacity:0}
.stage[data-anim="absorb"] .sheen{animation:sheen 2.4s ease-in-out infinite}
@keyframes sheen{0%,100%{opacity:0}50%{opacity:.55}}

/* The caption column. */
.film-step{font:600 17px/1.35 var(--serif);margin:2px 0 2px}
.film-form{font-size:12.5px;color:var(--ink-faint);margin-bottom:14px;letter-spacing:.04em;text-transform:lowercase}
.film-do{font-size:15.5px;color:var(--ink);margin:0 0 4px}
.film-where{font-size:13.5px;color:var(--ink-dim);margin:0 0 10px}
.film-real{display:inline-block;font-size:11.5px;letter-spacing:.05em;
  text-transform:uppercase;color:var(--ink-dim);background:var(--sunk);
  border-radius:999px;padding:3px 11px}
.film-why{margin-top:14px;font-size:12.5px;color:var(--ink-faint)}
/* One chip per step, the current one lit. The page has room for the names,
   which the GIF does not, so here they are clickable: a ribbon you can
   steer with beats a progress bar you can only watch. */
.film-rib{display:flex;gap:5px;margin:16px 0 12px;flex-wrap:wrap}
.film-rib button{flex:1 1 auto;min-width:0;font:inherit;font-size:11.5px;
  padding:5px 7px;border-radius:7px;border:1px solid var(--line);
  background:var(--sunk);color:var(--ink-faint);cursor:pointer;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center}
.film-rib button.done{background:var(--card);color:var(--ink-dim)}
.film-rib button.here{background:var(--clay);border-color:var(--clay);color:#fff}
.film-bar{height:3px;background:var(--line);border-radius:2px;margin:0 0 12px;
  overflow:hidden}
.film-fill{height:100%;width:0;background:var(--clay);border-radius:2px}
.film-ctl{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.film-ctl button{font:inherit;font-size:14px;padding:7px 15px;border-radius:999px;
  border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.film-ctl button:hover{background:var(--sunk)}
.film-ctl button.on{background:var(--clay);border-color:var(--clay);color:#fff}
/* Start over. Quiet, because it throws work away, but present at both
   ends of the page: someone who wants a clean form should not have to
   scroll past their whole audit to find one. */
/* The add-to-audit form had no styling of its own, so its file picker and
   textarea fell back to browser defaults and sat in a cramped row next to
   the submit button. The landing page's form is the one users meet first;
   this one should not look like a different site. */
/* Everything below the analysis. Ruled off and set on the page's own
   background so it reads as a different kind of thing from the findings
   above it: those are what we found, this is what you can do next. */
.next{margin:70px 0 0;padding-top:46px;border-top:2px solid var(--line)}
.next > h2{margin-top:0}
.next .lede{margin:0 0 22px}
.again{background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:26px 30px;box-shadow:var(--shadow)}
.again > p:first-child{margin-top:0}
.again h4{font:600 11.5px/1 var(--sans);text-transform:uppercase;
  letter-spacing:.13em;color:var(--ink-faint);margin:26px 0 12px}
.yours{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--sage);border:1px solid var(--sage);border-radius:999px;padding:1px 7px;margin-left:4px;white-space:nowrap}
.checks{display:grid;gap:11px;margin-bottom:16px}
.checks label{display:flex;gap:11px;align-items:flex-start;font-size:15px;
  cursor:pointer}
.checks input{margin-top:4px;accent-color:var(--clay);width:16px;height:16px;
  flex:none}
.checks .hint{display:block;font-size:13px;color:var(--ink-faint);margin-top:2px}
.startover{display:flex;gap:14px;align-items:baseline;flex-wrap:wrap;
  margin:18px 0 0;padding:18px 2px 0;border-top:1px dashed var(--line)}
.startover span{font-size:12.5px;color:var(--ink-faint);flex:1;min-width:220px}
.again input[type=file]{font:inherit;font-size:14px;width:100%;padding:14px;
  border-radius:12px;border:1px dashed var(--line);background:var(--sunk);
  cursor:pointer;display:block;margin-bottom:12px}
.again textarea{width:100%;min-height:110px;display:block;margin-bottom:16px;
  font:14.5px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;padding:14px;
  border-radius:12px;border:1px solid var(--line);background:var(--sunk);
  color:var(--ink);resize:vertical}
.again textarea:focus,.again input[type=file]:focus{outline:2px solid var(--clay);
  outline-offset:1px}
.again button[type=submit]{font-size:15.5px;padding:12px 28px}
.topbar{display:flex;justify-content:flex-end;margin:0 0 -8px}
.reset{font:inherit;font-size:13px;padding:6px 13px;border-radius:999px;
  border:1px solid var(--line);background:var(--card);color:var(--ink-dim);
  text-decoration:none;cursor:pointer;display:inline-block}
.reset:hover{background:var(--sunk);color:var(--ink)}
.tally{display:block;margin-top:16px;padding-top:14px;border-top:1px solid var(--line);font:400 15px/1.6 var(--sans);color:var(--ink-dim)}
.film-get{font-size:13.5px;padding:7px 14px;border-radius:999px;border:1px dashed var(--line);color:var(--ink-dim);text-decoration:none}
.film-get:hover{background:var(--sunk);color:var(--ink)}
.film-count{font-size:12.5px;color:var(--ink-faint);margin-left:auto}
@media(prefers-reduced-motion:reduce){
  .stage *{animation:none !important}
  .pd{opacity:.85 !important}
}

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
    /* An untimed beat is one we could not find a duration for -- a mask
     * whose packet nobody has published. Counting down a number this app
     * chose would be worse than not counting: it is read off the screen
     * by someone at a sink. Show a dash and wait for Next. */
    cntEl.textContent = p.untimed ? '—' : remain;
    prevB.disabled = i === 0 && b === 0;
    nextB.textContent = (i === seq.length - 1 && b === seq[i].beats.length - 1)
      ? 'Finish' : 'Next';
    dots();
  }

  function tick(){
    if(beat().untimed) return;
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
            f"{b['text'] if b['kind'] == 'apply' else b['kind']} · "
            f"{'as the packet says' if b.get('untimed') else short_time(b['secs'])}"
            for b in beats_for(spec, step.dwell_seconds, step.dwell_note,
                               step.dwell_unknown, step.dwell_source)
        ]
        how = f'<div class="how">{e(" → ".join(bits))}</div>'
    # Products that do this same job. Named on the step rather than left
    # to the money section, because the question "do I use both of
    # these?" is asked while reading the routine.
    # A step for something you do not own. Visibly different from a
    # product, because the page is telling you where a gap sits in the
    # order rather than what to do with a bottle you have.
    if step.placeholder:
        return (
            f'<div class="step ghost" data-step="{e(key)}">'
            f'<div class="num">·</div><div>'
            f'<div class="name">{e(step.product_name)}'
            f'<span class="badge">not on your shelf</span></div>'
            f'<div class="meta">{e(step.form)}</div>'
            f'<div class="alt">This is where it would go. Nothing here is '
            f'assuming you have one — it is in the order so you can see the '
            f'shape of the routine, and the step above and below are what '
            f'you actually own.</div>'
            f"</div></div>"
        )

    alt = ""
    if step.instead_of:
        others = ", ".join(e(n) for n in step.instead_of)
        alt = (f'<div class="alt">or <b>{others}</b> — one of these, '
               f'not both. They do the same job, so pick whichever you '
               f'prefer and keep the other for when it runs out.</div>')

    return (
        f'<div class="step" data-step="{e(key)}">'
        f'<div class="num">{step.order}</div><div>'
        f'<div class="name">{e(step.product_name)}{badge}</div>'
        f'<div class="meta">{e(step.form)}</div>{alt}{how}'
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

    # The legend lists what this grid can actually contain, not every
    # category the schema allows. Dropping SKA-020 left no myth rules in
    # the table at all, and a swatch for a colour that can never appear
    # tells the reader the system checks something it does not.
    present = set(worst.values())
    swatches = [
        ("high", "var(--cell-crit)", "conflict"),
        ("med", "var(--cell-care)", "use with care"),
        ("good", "var(--cell-good)", "works well together"),
        ("myth", "var(--cell-myth)", "myth, ignore it"),
    ]
    key = (
        '<div class="key">'
        + "".join(
            f'<span><i style="background:{colour}"></i>{label}</span>'
            for kind, colour, label in swatches
            if kind in present
        )
        + '<span><i style="background:var(--sunk)"></i>no interaction</span>'
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


FACE_SVG = '<svg viewBox="0 0 200 240" role="img" aria-label="A drawn face showing where to apply each product"><ellipse class="face-skin" cx="100" cy="124" rx="63" ry="84"/><ellipse class="face-line" cx="100" cy="124" rx="63" ry="84"/><path class="face-line" d="M62 96q14-8 28-2"/><path class="face-line" d="M110 94q14-6 28 2"/><path class="face-line" d="M66 110q10-7 20 0"/><path class="face-line" d="M114 110q10-7 20 0"/><path class="face-line" d="M100 112v20q0 5 6 6"/><path class="face-line" d="M86 166q14 9 28 0"/><path class="face-line" d="M74 198q4 18 0 26"/><path class="face-line" d="M126 198q-4 18 0 26"/><g class="water"><path class="wstream" d="M76 60v34"/><path class="wstream" d="M100 52v40"/><path class="wstream" d="M124 60v34"/></g><g class="towel"><rect x="44" y="92" width="112" height="64" rx="14" fill="#cfd8cd" stroke="#b6c3b4" stroke-width="1.5"/></g><g class="sheen"><ellipse cx="100" cy="124" rx="55" ry="74" fill="none" stroke="var(--sand)" stroke-width="3" stroke-dasharray="5 7"/></g><g id="pdots"></g></svg>'

FILM_JS = """
/* The routine animation. Scenes come from src/storyboard.py; this only plays
 * them. Screen time is compressed — the real duration is printed next to each
 * scene — because the preview is for learning the order, and guided mode is
 * for standing at the sink. */
(function(){
  var root = document.getElementById('film');
  if(!root || !window.FILM || !FILM.length) return;

  var stage = document.getElementById('stage');
  var dots  = document.getElementById('pdots');
  var elStep = document.getElementById('f-step');
  var elForm = document.getElementById('f-form');
  var elDo   = document.getElementById('f-do');
  var elWhere= document.getElementById('f-where');
  var elReal = document.getElementById('f-real');
  var elWhy  = document.getElementById('f-why');
  var elFill = document.getElementById('f-fill');
  var elCount= document.getElementById('f-count');
  var btnPlay= document.getElementById('f-play');
  var btnBack= document.getElementById('f-back');
  var btnNext= document.getElementById('f-next');
  var elRib  = document.getElementById('f-rib');

  var i = 0, playing = false, timer = null, raf = null;

  /* The ribbon doubles as a way in: a viewer who wants the retinol step
   * should not have to sit through the cleanser to reach it. */
  var RIB = (FILM[0] && FILM[0].ribbon) || [];
  var ribBtns = RIB.map(function(label, n){
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.addEventListener('click', function(){
      for(var k = 0; k < FILM.length; k++){
        if(FILM[k].at === n){ stop(); show(k); return; }
      }
    });
    elRib.appendChild(b);
    return b;
  });

  /* Drawing-units radius per dose, so the player and the GIF show the same
   * sizes. A rice grain and a dime are nearly four times apart and that
   * ratio is the information. */
  var DOSE_R = {rice:3, pea:6.5, coin:11, thick:15, palm:14, pad:16, drops:4};

  function drawDose(scene){
    var d = scene.dose || {kind:'pea', n:1};
    if(d.kind === 'twofinger'){
      [88, 112].forEach(function(x, i){
        var g = document.createElementNS('http://www.w3.org/2000/svg','rect');
        g.setAttribute('x', x - 9); g.setAttribute('y', 86);
        g.setAttribute('width', 18); g.setAttribute('height', 62);
        g.setAttribute('rx', 9); g.setAttribute('class','dosehand');
        dots.appendChild(g);
        var b = document.createElementNS('http://www.w3.org/2000/svg','rect');
        b.setAttribute('x', x - 4); b.setAttribute('y', 92);
        b.setAttribute('width', 8); b.setAttribute('height', 50);
        b.setAttribute('rx', 4); b.setAttribute('class','dosebar');
        b.style.setProperty('--d', (i * 0.12) + 's');
        dots.appendChild(b);
      });
      return;
    }
    var hand = document.createElementNS('http://www.w3.org/2000/svg','rect');
    hand.setAttribute('x', 88); hand.setAttribute('y', 112);
    hand.setAttribute('width', 24); hand.setAttribute('height', 64);
    hand.setAttribute('rx', 12); hand.setAttribute('class','dosehand');
    dots.appendChild(hand);

    var n = d.kind === 'drops' ? Math.max(1, d.n|0) : 1;
    var r = DOSE_R[d.kind] || 6.5;
    for(var i = 0; i < n; i++){
      var c = document.createElementNS('http://www.w3.org/2000/svg','circle');
      c.setAttribute('cx', 100 - (n - 1) * 5 + i * 10);
      c.setAttribute('cy', 108);
      c.setAttribute('r', r);
      c.setAttribute('class','dosedot');
      c.style.setProperty('--d', (i * 0.14).toFixed(2) + 's');
      dots.appendChild(c);
    }
  }

  function draw(scene){
    while(dots.firstChild) dots.removeChild(dots.firstChild);
    stage.setAttribute('data-anim', scene.anim);
    if(scene.anim === 'dispense'){ drawDose(scene); return; }
    var active = scene.points.length ? scene.points : (scene.rest || []);
    var resting = scene.points.length === 0;
    active.forEach(function(p, n){
      var c = document.createElementNS('http://www.w3.org/2000/svg','circle');
      c.setAttribute('cx', p.x); c.setAttribute('cy', p.y); c.setAttribute('r', 5.5);
      c.setAttribute('class', resting ? 'pd rest' : 'pd');
      /* Stagger, and push sweeps outward from the midline so the motion
       * reads as spreading rather than drifting sideways. */
      c.style.setProperty('--d', (n * 0.09).toFixed(2) + 's');
      c.style.setProperty('--out', (p.x < 100 ? -7 : 7) + 'px');
      dots.appendChild(c);
    });
  }

  function show(n){
    i = (n + FILM.length) % FILM.length;
    var s = FILM[i];
    draw(s);
    elStep.textContent  = s.slot + ' step ' + s.order + ' of ' + s.of + ' — ' + s.name;
    elReal.style.display = s.real ? '' : 'none';
    elForm.textContent = s.form || '';
    elForm.style.display = s.form ? '' : 'none';
    elDo.textContent    = s.caption;
    elWhere.textContent = s.where ? 'on ' + s.where : '';
    elWhere.style.display = s.where ? '' : 'none';
    elReal.textContent  = s.real;
    elWhy.textContent   = s.why || '';
    elWhy.style.display = s.why ? '' : 'none';
    elCount.textContent = (i + 1) + ' / ' + FILM.length;
    ribBtns.forEach(function(b, n){
      b.className = n === s.at ? 'here' : (n < s.at ? 'done' : '');
    });
    runBar(s.screen);
    if(playing){
      clearTimeout(timer);
      timer = setTimeout(function(){
        if(i === FILM.length - 1){ stop(); } else { show(i + 1); }
      }, s.screen * 1000);
    }
  }

  function runBar(secs){
    cancelAnimationFrame(raf);
    var t0 = performance.now();
    elFill.style.width = '0%';
    (function tick(now){
      var pct = Math.min((now - t0) / (secs * 1000), 1) * 100;
      elFill.style.width = pct.toFixed(1) + '%';
      if(pct < 100 && playing) raf = requestAnimationFrame(tick);
    })(t0);
  }

  function play(){
    playing = true;
    btnPlay.textContent = 'Pause';
    btnPlay.classList.add('on');
    show(i);
  }
  function stop(){
    playing = false;
    clearTimeout(timer); cancelAnimationFrame(raf);
    btnPlay.textContent = 'Play';
    btnPlay.classList.remove('on');
  }

  btnPlay.addEventListener('click', function(){ playing ? stop() : play(); });
  btnBack.addEventListener('click', function(){ stop(); show(i - 1); });
  btnNext.addEventListener('click', function(){ stop(); show(i + 1); });

  show(0);
})();
"""


def _dwell_beat(dwell: int, note: str, unknown: bool, source: str) -> dict | None:
    """The 'leave it on' beat, or None when the product is not worn.

    Two shapes, because there are two different truths to tell. With a
    looked-up time it is an ordinary timed beat and says where the number
    came from. Without one it is untimed: the guided player stops and
    waits for the user rather than counting down a duration this app
    invented. A mask time is read off a screen by someone standing at a
    sink, so "we do not know" has to survive all the way to the surface
    instead of being rounded to a plausible ten minutes.
    """
    if unknown:
        text = "leave it on for the time on the packet"
        if note:
            text += f" ({note})"
        return {"kind": "leave it on", "text": text, "secs": 0, "untimed": True,
                "why": "no stated time was found for this product"}
    if dwell:
        text = "leave it on"
        if source:
            text += f" — {source} says so"
        elif note:
            text += f" ({note})"
        return {"kind": "leave it on", "text": text, "secs": dwell}
    return None


def beats_for(spec, dwell: int = 0, dwell_note: str = "",
              dwell_unknown: bool = False, dwell_source: str = "") -> list[dict]:
    """The physical sequence for one step: apply, then finish, then any wait.

    Single source of truth. The step list, the guided player, the spoken
    walkthrough and the printed card all render from this. They were each
    assembling it separately and promptly drifted: the audio announced
    "let it absorb, 30 seconds" while the written step said only "let it
    absorb", because the duration existed in one path and not the others.
    """
    if spec is None:
        out = [{"kind": "apply", "text": "apply as usual", "secs": 15}]
        held = _dwell_beat(dwell, dwell_note, dwell_unknown, dwell_source)
        if held:
            out.append(held)
        return out

    out = [{
        "kind": "apply",
        "text": f"{spec.amount}, {spec.motion} on {spec.area}",
        "secs": spec.seconds,
    }]

    # Leaving it on is the step, for anything that has one. Comes between
    # applying and the finish: apply for thirty seconds, wear it for
    # fifteen minutes, then rinse. The duration is the engine's, from
    # product_forms.yaml, so the narrator cannot talk it down.
    held = _dwell_beat(dwell, dwell_note, dwell_unknown, dwell_source)
    if held:
        out.append(held)

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


def _routine_gif(scenes: list[dict]) -> str:
    """The scenes as a GIF data URI, or "" if one could not be made.

    Embedded rather than linked, so a saved page keeps working offline — the
    same rule the annotated photographs follow. It is drawn from the scene
    list the player uses, so the file and the page cannot be showing
    different routines.

    Wrapped because this is the only part of the page that depends on a font
    being installed and on PIL behaving. A download button is worth having
    and is not worth losing an audit over.
    """
    if not scenes:
        return ""
    try:
        from filmstrip import build

        data = build(scenes)
    except Exception:
        return ""
    if not data:
        return ""
    return "data:image/gif;base64," + base64.b64encode(data).decode("ascii")


def _plural(n: int, word: str) -> str:
    """"1 product", "2 products". Written out because "product(s)" in the
    middle of a sentence reads as something nobody finished."""
    return word if n == 1 else word + "s"


def _short(name: str, limit: int = 13) -> str:
    """A product name small enough for the ribbon, cut at a word."""
    name = " ".join(name.split())
    if len(name) <= limit:
        return name
    cut = name[:limit].rsplit(" ", 1)[0]
    return (cut or name[:limit]).rstrip(",.") + "\u2026"


def _opening_scenes(audit, explain: dict, ribbon: list[str]) -> list[dict]:
    """Shelf, sorted, clashing, rotating — before any technique is shown.

    Reads only what the audit already contains. If a shelf has no conflict
    and nothing alternates, those scenes are simply absent rather than
    drawn empty: a film that opens by announcing it found nothing is worse
    than one that gets on with it.
    """
    products = list(audit.products)
    if not products:
        return []

    # Which half of the day each product ends up in.
    where: dict[str, set[str]] = {}
    for label, steps in (("am", audit.routine.am), ("pm", audit.routine.pm)):
        for st in steps:
            where.setdefault(st.product_name, set()).add(label)

    items = []
    for rp in products[:MAX_SHELF]:
        name = rp.product.name
        slots = where.get(name, set())
        items.append({
            "label": _short(name, 12),
            "container": container_for(rp.form),
            "slot": "both" if len(slots) > 1 else (next(iter(slots)) if slots else "off"),
        })

    base = {"points": [], "rest": [], "ribbon": ribbon, "at": -1,
            "real": "", "where": "", "why": "", "form": "",
            "container": "bottle", "dose": {"kind": "pea", "n": 1}}

    extra = len(products) - len(items)
    scenes = [{
        **base,
        "anim": "shelf",
        "items": items,
        "slot": "Your shelf",
        "order": 0, "of": 0,
        "name": f"{len(products)} products"
                + (f" ({extra} more not shown)" if extra > 0 else ""),
        "caption": "what the photographs showed",
        "screen": 2.4,
    }, {
        **base,
        "anim": "sort",
        "items": items,
        "slot": "Your shelf",
        "order": 0, "of": 0,
        "name": "Morning and evening",
        "caption": f"{sum(1 for i in items if i['slot'] in ('am', 'both'))} in the morning, "
                   f"{sum(1 for i in items if i['slot'] in ('pm', 'both'))} at night",
        "screen": 2.6,
    }]

    # The worst conflict, if there is one. One is enough: the page lists
    # them all, and a film that works through six of them is a list read
    # aloud.
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    clashes = [f for f in audit.findings
               if getattr(f, "type", "") == "conflict" and len(f.products) >= 2]
    clashes.sort(key=lambda f: rank.get(getattr(f, "severity", "low"), 9))
    if clashes:
        worst = clashes[0]
        scenes.append({
            **base,
            "anim": "clash",
            "pair": [_short(n, 15) for n in worst.products[:2]],
            "containers": [
                container_for(next((rp.form for rp in products
                                    if rp.product.name == n), ""))
                for n in worst.products[:2]
            ],
            "rule": worst.rule_id,
            "slot": "Why this order",
            "order": 0, "of": 0,
            "name": explain.get(worst.rule_id) or worst.mechanism,
            "caption": worst.guidance or "these two are kept apart",
            "screen": 3.2,
        })

    alternating = [st for st in audit.routine.pm if st.frequency != "daily"]
    if len(alternating) >= 2:
        n = len(alternating)
        scenes.append({
            **base,
            "anim": "week",
            "rows": [{"label": _short(st.product_name, 15), "every": n, "offset": i}
                     for i, st in enumerate(alternating)],
            "slot": "Why this order",
            "order": 0, "of": 0,
            "name": f"{n} products rotate",
            "caption": "one per night, so none of them is dropped",
            "screen": 3.2,
        })

    return scenes


def _merge_slots(slots: set[str]) -> str:
    """How to label a product used once, or in both halves of the day."""
    if slots == {"Morning", "Evening"}:
        return "Morning and evening"
    return next(iter(slots)) if slots else ""


def _film_scenes(audit, specs: dict, explain: dict) -> list[dict]:
    """One scene per beat, for the player and the GIF alike.

    Built from the same `beats_for` the written steps and the audio use, so
    a duration can never say one thing in the text and another in the
    picture.

    Each product appears once. Walking the morning and then the evening
    showed the cleanser, the niacinamide and the moisturiser twice each,
    which was a third of the running time spent repeating itself. The
    written routine below still lists both halves of the day in full --
    that is a schedule, and a schedule has to repeat. This is a
    demonstration of a technique, and a technique does not change between
    breakfast and bedtime.
    """
    # Which halves of the day each product is used in, and the first step
    # it appears as. Morning order first, then anything evening-only.
    slots: dict[str, set[str]] = {}
    firsts: list[tuple[str, object]] = []
    for label, steps in (("Morning", audit.routine.am), ("Evening", audit.routine.pm)):
        for st in steps:
            # Nothing to draw: there is no bottle, no container shape and
            # no amount. The animation is a depiction of doing something.
            if st.placeholder:
                continue
            if st.product_name not in slots:
                slots[st.product_name] = set()
                firsts.append((st.product_name, st))
            slots[st.product_name].add(label)

    ribbon = [_short(name) for name, _ in firsts]

    scenes: list[dict] = []
    for index, (name, st) in enumerate(firsts):
        spec = specs.get(name)
        beats = beats_for(spec, st.dwell_seconds, st.dwell_note,
                              st.dwell_unknown, st.dwell_source)
        for sc in scenes_for(st, spec, beats):
            # The rule that put this step here, in the user's words where
            # the narrator wrote one. A picture that cannot say why it is
            # in this order is decoration.
            why = ""
            for rid in st.because:
                if rid in explain:
                    why = f"{rid} · {explain[rid]}"
                    break
            else:
                if st.because:
                    why = " · ".join(st.because)
            scenes.append({
                **sc,
                "slot": _merge_slots(slots[name]),
                "order": index + 1, "of": len(firsts),
                "name": name, "form": st.form,
                "why": why,
                # Where this sits in the whole routine, so a frame is
                # locatable even when the action resembles the last one.
                "ribbon": ribbon, "at": index,
            })

    return _opening_scenes(audit, explain, ribbon) + scenes


def _film_markup(scenes: list[dict], gif_uri: str = "") -> str:
    """The player, and a link to the file if one could be built."""
    if not scenes:
        return ""

    get = (
        # A file, because the player only exists while this page is open in a
        # browser. A deck opened by double-click cannot run it, and a still
        # of a face with dots on it says nothing.
        f'<a class="film-get" download="routine.gif" href="{gif_uri}">'
        "Download GIF</a>"
        if gif_uri
        else ""
    )
    return (
        '<section class="film" id="film">'
        '<div class="film-top"><h3>Watch the routine</h3>'
        '<span class="film-note">A preview, sped up. Each scene shows how long '
        'it actually takes.</span></div>'
        '<div class="film-body">'
        f'<div class="stage" id="stage" data-anim="dab">{FACE_SVG}</div>'
        '<div>'
        '<p class="film-step" id="f-step"></p>'
        '<p class="film-form" id="f-form"></p>'
        '<p class="film-do" id="f-do"></p>'
        '<p class="film-where" id="f-where"></p>'
        '<span class="film-real" id="f-real"></span>'
        '<p class="film-why" id="f-why"></p>'
        '<div class="film-rib" id="f-rib"></div>'
        '<div class="film-bar"><div class="film-fill" id="f-fill"></div></div>'
        '<div class="film-ctl">'
        '<button type="button" id="f-play">Play</button>'
        '<button type="button" id="f-back">Back</button>'
        '<button type="button" id="f-next">Next</button>'
        f'{get}'
        '<span class="film-count" id="f-count"></span>'
        '</div></div></div></section>'
    )


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
                # A placeholder is a gap in the order, not something to
                # do. The written routine shows it because the shape is
                # the point there; a timer counting fifteen seconds for
                # a cleanser you do not own, a drawn hand applying it,
                # or a line on a card taped inside a cabinet are all
                # instructions to use a product that does not exist.
            if s.placeholder:
                continue
            spec = specs.get(s.product_name)
            detail = ""
            if spec:
                bits = [
                    f"{spec.amount}, {spec.motion} {short_time(b['secs'])}"
                    if b["kind"] == "apply"
                    else f"{b['kind']} "
                         f"{'per packet' if b.get('untimed') else short_time(b['secs'])}"
                    for b in beats_for(spec, s.dwell_seconds, s.dwell_note,
                                              s.dwell_unknown, s.dwell_source)
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
    failed_urls: list[str] | None = None,
    dropped: str = "",
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
            if s_.placeholder:
                continue
            seq.append({
                "slot": slot, "order": s_.order, "of": len(steps),
                "name": s_.product_name, "freq": s_.frequency,
                "beats": beats_for(specs.get(s_.product_name),
                                   s_.dwell_seconds, s_.dwell_note,
                                   s_.dwell_unknown, s_.dwell_source),
            })

    film_scenes = _film_scenes(audit, specs, explain)
    player_scenes = [sc for sc in film_scenes if sc["anim"] not in OPENING_ANIMS]
    film_markup = _film_markup(player_scenes, _routine_gif(film_scenes))

    grid_data = '{}'
    parts: list[str] = []
    parts.append(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Skincare shelf audit</title>"
        f"<style>{CSS}</style></head><body><div class=\"wrap\">"
    )

    parts.append(
        '<div class="topbar">'
        '<a class="reset" href="/" data-reset>Start over with a new shelf</a>'
        "</div>"
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
            given = " <span class=\"yours\">your link</span>" if rec.get(
                "from_user_url") else ""
            rows.append(
                f"<li><b>{e(name)}</b>{given} — "
                f'<a href="{link}" style="color:var(--clay)">{shown}</a>'
                f"{money}{tail}</li>"
            )

        # Split the headline. A page the user chose identifies a specific
        # product; a page the app found is a name match made on their
        # behalf, and only the second one needs a warning about whether it
        # is even the right product.
        mine = sum(1 for r in sourced.values() if r.get("from_user_url"))
        found = len(sourced) - mine
        said = []
        if mine:
            said.append(
                f"<strong>{mine} {_plural(mine, 'product')} "
                f"{'was' if mine == 1 else 'were'} read from a page you "
                f"gave us.</strong>"
            )
        if found:
            said.append(
                f"<strong>{found} {_plural(found, 'product')} "
                f"{'was' if found == 1 else 'were'} looked up online by "
                f"name.</strong> Worth checking the match is the product "
                f"you actually own."
            )
        parts.append(
            f'<div class="note" style="margin-top:12px">'
            f"{' '.join(said)} Published formulations differ by region and "
            f"change over time, so check the bottle before acting on "
            f'anything that depends on them.'
            f'<ul style="margin:10px 0 0">{"".join(rows)}</ul></div>'
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
            f"<strong>{len(from_cat)} {_plural(len(from_cat), 'product')} "
            f"{'was' if len(from_cat) == 1 else 'were'} identified by name, not by "
            f"reading a label.</strong> Their ingredients come from a reference "
            f"list, so they are what these products <em>usually</em> contain — "
            f"formulations change. Worth a glance at the bottle before acting on "
            f'anything below that depends on them.<ul style="margin:10px 0 0">{rows}</ul></div>'
        )

    # The aliases are the largest unverified surface in the project: 232
    # non-English ingredient terms, machine-generated, never read by a
    # speaker of any of those languages. The risk is one-sided. A missing
    # translation costs a finding, which is safe. A wrong one finds an
    # ingredient that is not there, and that warning looks exactly like a
    # real one.
    #
    # There is no speaker to check them, so the next best thing is to make a
    # wrong one visible where it would do harm. INCI is international, so
    # most non-English labels still resolve through verified terms and this
    # block never appears; when it does, it names the product, the
    # ingredient and the language, which is enough for the reader to check
    # the one word that matters.
    translated = [p for p in audit.products if p.translated_only]
    if translated:
        rows = "".join(
            f"<li><b>{e(p.product.name)}</b> → "
            + ", ".join(
                f"{e(name)} (matched its {e(lang)} name)"
                for name, lang in sorted(p.translated_only.items())
            )
            + "</li>"
            for p in translated
        )
        n = len(translated)
        parts.append(
            f'<div class="note" style="margin-top:12px">'
            f"<strong>{n} {_plural(n, 'product')} "
            f"{'was' if n == 1 else 'were'} identified using a non-English "
            f"ingredient name that no speaker of that language has checked."
            f"</strong> Our non-English ingredient names were translated "
            f"automatically and have not been reviewed. Everything below that "
            f"depends on {'this product' if n == 1 else 'these products'} is "
            f"worth confirming against the bottle first — the ingredient may "
            f"not be in it."
            f'<ul style="margin:10px 0 0">{rows}</ul></div>'
        )

    # Links we were given and could not turn into a product. This is the
    # most visible failure the app has, because the user knows how many
    # links they pasted, and it used to be invisible: the loop skipped the
    # failure and the page said nothing. Naming the link matters more than
    # naming a count — the user can open it, see the product and type the
    # name instead, which is a route back. A number alone is not.
    if failed_urls:
        rows = "".join(
            f'<li><a href="{e(u)}" rel="noreferrer nofollow">{e(u[:90])}'
            f'{"…" if len(u) > 90 else ""}</a></li>'
            for u in failed_urls
        )
        n = len(failed_urls)
        parts.append(
            f'<div class="note" style="margin-top:12px">'
            f"<strong>{n} of the links you pasted could not be read, and "
            f"{'it is' if n == 1 else 'they are'} not in this audit.</strong> "
            f"Retailer pages often publish no ingredient list, or hide it behind "
            f"a tab this tool cannot open. Nothing below accounts for "
            f"{'this product' if n == 1 else 'these products'}. The quickest fix "
            f"is to type the product name instead, or paste the ingredient list "
            f"straight from the page."
            f'<ul style="margin:10px 0 0">{rows}</ul></div>'
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
        # The engine's own count, in the same block as the model's prose.
        #
        # validate_narrative checks the explanations and the steps against
        # the audit and drops anything invented. It does not check the
        # summary, which is free text and reaches the page verbatim — the
        # project's own attack A8 is named "corrupt the summary, which the
        # validator does not check". A summary reading "no conflicts were
        # found" above a list of three is the worst shape of wrong, because
        # the reassuring sentence is the one a skimmer reads.
        #
        # There is no structural fix for it the way there is for a named
        # condition: "contradicts the findings" is unbounded semantics, not
        # a vocabulary to match against. What can be done is deny the
        # summary the last word. The header already carries the count, but
        # a header away is far enough to miss; this sits inside the same
        # card, and the model cannot write it.
        tally = ""
        if audit.findings:
            order = ["critical", "high", "medium", "low"]
            present = [f.severity for f in audit.findings if f.severity in order]
            worst = min(present, key=order.index) if present else None
            n = len({f.rule_id for f in audit.findings})
            tally = (
                f'<span class="tally">The engine found {n} '
                f'{_plural(n, "finding")} on this shelf'
                + (f", the most serious rated {SEVERITY_LABEL[worst].lower()}."
                   if worst else ".")
                + " Each is listed below with the rule that produced it."
                "</span>"
            )
        parts.append(
            f'<div class="card summary">{e(narrative.summary)}{tally}</div>'
        )

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

    if film_markup:
        parts.append(film_markup)

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
        # "Nothing to fix" is about the pairwise rules only, and the gaps
        # print directly underneath it. A shelf with four cleansers and no
        # moisturiser was being told "no duplicates" immediately above "you
        # have 4 products doing the job of one" — two true sentences that
        # read as one contradiction. So the headline narrows to what was
        # actually checked when there is something below it.
        real_gaps = [g for g in audit.gaps if not g.suggestion]
        more = "gap" if len(real_gaps) == 1 else "gaps"
        parts.append(
            '<div class="allclear"><span class="head">'
            + ("No clashes between your products."
               if real_gaps else "Nothing to fix.")
            + '</span>'
            f'<span class="body">Nothing among the {checked} product'
            f'{"s" if checked != 1 else ""} that could be checked clashes, '
            "duplicates an active or needs reordering."
            + (f" There {'is' if len(real_gaps) == 1 else 'are'} "
               f"{len(real_gaps)} {more} in what the shelf is missing, below."
               if real_gaps else
               " That is a straightforward shelf — the products on it do not "
               "interact in ways worth warning you about.")
            + "</span></div>"
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
    # That justification was false until 25 Oct 2026. The steps carried the
    # bare word "photosensitising" rather than a rule id, so SKA-082 and
    # SKA-083 fired at high severity, moved products to the evening, and
    # appeared nowhere on the page — under a footer promising that every
    # claim cites the rule that produced it. build_routine now records the
    # id. If that ever regresses, this omission becomes a silent one again,
    # which is why test_thesis asserts every finding id reaches the page.
    #
    # What belongs here is what the shelf is missing, which no pairwise rule
    # can see.
    # Missing and optional are not the same claim and must not look the
    # same. A shelf with no cleanser and a shelf with no eye cream were
    # both rendering as identical warning cards, which is how a tool that
    # tells you what you need turns into one that tells you what to buy.
    # Real gaps first, then a separately headed group of suggestions.
    def _gap_card(gap, suggestion: bool) -> str:
        urgent = gap.severity in ("critical", "high") and not suggestion
        cls = "gap suggest" if suggestion else ("gap urgent" if urgent else "gap")
        # "Triggered by:" with nothing after it was printing on every gap
        # that is about the shelf as a whole rather than about particular
        # products — which is most of them now.
        # "Triggered by" is right for a gap, where `because` lists the
        # products that created the need, and wrong for a suggestion,
        # where it lists the suggestion itself — "Triggered by: Toner,
        # Eye cream" on a card recommending a toner and an eye cream.
        label = "These are" if suggestion else "Triggered by"
        why = (f'<span class="why">{label}: {e(", ".join(gap.because))}</span>'
               if gap.because else "")
        return (
            f'<div class="{cls}">'
            f'<span class="lbl">{e(gap.label)}</span>'
            f'<span class="head">{e(gap.headline)}</span>'
            f'<span class="body">{e(gap.message)}</span>'
            f"{why}</div>"
        )

    for gap in [g for g in audit.gaps if not g.suggestion]:
        parts.append(_gap_card(gap, False))

    suggestions = [g for g in audit.gaps if g.suggestion]
    if suggestions:
        parts.append(
            '<h2>Worth considering</h2>'
            '<p class="lede">Not problems. These are the steps a routine is '
            'usually better for having, and the ones that are a matter of '
            'taste — listed so you know they exist, not because anything '
            'above is wrong without them.</p>'
        )
        for gap in suggestions:
            parts.append(_gap_card(gap, True))

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
            if p.product.price_size_mismatch:
                # Inline, because this is the one qualification that
                # cannot live in a caption: the number beside it is for
                # a different bottle.
                typical = (f' <span class="typ">price is for '
                           f'{e(p.product.price_size_mismatch)}, '
                           f'yours is {e(p.product.size or "another size")} '
                           f'— not counted in the totals</span>')
            elif p.price_is_typical:
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
            # Size is shown because it decides the price. It was being
            # read off the label and used silently, so when the price
            # came back wrong — a 7 ml sample priced as a full jar —
            # there was no way to tell whether the size had been misread
            # or the price had, and no way to correct either.
            size_val = e(p.product.size or "")
            rows.append(
                f"<tr><td>{e(name)}{typical}</td>"
                f'<td class="r"><input type="hidden" name="pname" value="{e(name)}">'
                f'<input type="number" name="pprice" min="0" step="1" '
                f'value="{value}" placeholder="{placeholder}"></td>'
                f'<td class="c"><input type="text" name="psize" '
                f'value="{size_val}" placeholder="e.g. 7 ml" size="7"></td>'
                f'<td class="c"><input type="checkbox" name="punused" '
                f'value="{e(name)}"{checked}></td>'
                f'<td class="c"><input type="checkbox" name="pdrop" '
                f'value="{e(name)}"></td></tr>'
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

        parts.append('<section class="next">')
        parts.append("<h2>Make this audit better</h2>")
        parts.append(
            '<p class="lede">Everything above is only as good as what it was '
            "given. These improve it, and none of them needs starting over.</p>"
        )
        # Numbered as they are added, not written in. A heading over an
        # empty block is the same failure as a scene that draws nothing: it
        # announces something and then shows nothing, and the reader assumes
        # it broke rather than that it had nothing to say.
        blocks: list[str] = []
        if rows:
            blocks.append(
                "<p>Fill these in and the money figures become yours rather "
                "than typical retail. <b>Not mine</b> removes a product "
                "entirely — tick it for anything listed here that you do not "
                "own, and it will stay gone on the next round even if you "
                "send the same photograph again. The size decides which "
                "price is the right one: a sample and a full jar differ by "
                "more than the rest of this section puts together.</p>"
                '<table class="prices"><tr><th>Product</th>'
                '<th class="r">What you paid</th>'
                '<th class="c">Size</th>'
                '<th class="c">Never use it</th>'
                f'<th class="c">Not mine</th></tr>{"".join(rows)}</table>'
            )
        if concern_boxes:
            blocks.append(
                f'<div class="checks" style="margin-bottom:16px">{concern_boxes}</div>'
            )
        blocks.append(
            "<p>Photograph the back labels of anything amber or red above. "
            "What is already identified is kept, and a real label replaces a "
            f"name match.<br><br>{hint}</p>"
            '<input type="file" name="photos" accept="image/*" multiple>'
            '<textarea name="typed" placeholder="Or type any products that are '
            'missing — or paste a link to one, which is the most reliable '
            'thing you can give us. To correct something that is already '
            'wrong, use the table above: typing about it here adds a '
            'product rather than fixing one."></textarea>'
        )
        titles = []
        if rows:
            titles.append("What you paid")
        if concern_boxes:
            titles.append("What you are treating")
        titles.append("Anything missed or unreadable")

        body = "".join(
            f"<h4>{n} · {title}</h4>{block}"
            for n, (title, block) in enumerate(zip(titles, blocks), start=1)
        )
        parts.append(
            f'<form class="again" method="post" action="/audit" '
            f'enctype="multipart/form-data">'
            f"{body}"
            f'<input type="hidden" name="carried" value="{e(carry)}">'
            # Products the user has already said are not theirs. Posted
            # back so the refusal survives the round — otherwise the
            # same photograph invents the same product again and they
            # have to dismiss it every time.
            f'<input type="hidden" name="dropped" value="{e(dropped)}">'
            f'<button type="submit">Audit again</button>'
            f"</form>"
            f'<div class="startover">'
            f'<a class="reset" href="/" data-reset>Start over with a new shelf</a>'
            f"<span>Clears everything above. This is the one for a different "
            f"person's shelf — \u201cAudit again\u201d keeps what you have "
            f"already given it.</span>"
            f"</div></section>"
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
        f"var FILM={script_json(player_scenes)};"
        f"{JS}{SPEECH_JS}{GRID_JS}{LOADING_JS}{FILM_JS}"
        "document.getElementById('print').addEventListener('click',function(){window.print()});"
        "document.querySelectorAll('[data-reset]').forEach(function(a){"
        "a.addEventListener('click',function(ev){"
        "if(!confirm('Start over? This clears the products you have given it so far.'))"
        "{ev.preventDefault();}});});"
        "</script></body></html>"
    )
    return "".join(parts)

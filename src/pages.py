"""The pages that are not the result: landing, error, and the busy state.

Shares render.CSS so the whole app looks like one thing. The copy here is the
first text anyone sees, so it is written to answer three questions before they
are asked — what is this, what do I give it, and what happens to what I give it.
"""

from __future__ import annotations

from limits import MAX_IMAGES, MAX_PRODUCTS
from render import CSS, LOADING_JS, LOADING_MARKUP, e

EXTRA = """
.hero{padding:72px 0 8px}
.hero h1{margin:0 0 14px}
.hero .tag{font:400 20px/1.5 var(--serif);color:var(--ink-dim);max-width:46ch;margin:0 0 10px}
form{margin-top:36px}
fieldset{border:1px solid var(--line);border-radius:16px;padding:26px 30px;margin:0 0 18px;
  background:var(--card);box-shadow:var(--shadow)}
legend{font:600 11.5px/1 var(--sans);text-transform:uppercase;letter-spacing:.14em;
  color:var(--ink-faint);padding:0 10px}
fieldset p{margin:0 0 16px;color:var(--ink-dim);font-size:15px;line-height:1.6}
input[type=file]{font:inherit;font-size:14px;width:100%;padding:16px;border-radius:12px;
  border:1px dashed var(--line);background:var(--sunk);cursor:pointer}
textarea{width:100%;min-height:170px;font:14.5px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;
  padding:16px;border-radius:12px;border:1px solid var(--line);background:var(--sunk);
  color:var(--ink);resize:vertical}
textarea:focus,input[type=file]:focus{outline:2px solid var(--clay);outline-offset:1px}
.eg{font:13px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--ink-faint);
  background:var(--sunk);border-radius:10px;padding:14px 16px;margin:0 0 16px;
  white-space:pre-wrap}
.checks{display:grid;gap:11px}
.checks label{display:flex;gap:11px;align-items:flex-start;font-size:15px;cursor:pointer}
.checks input{margin-top:4px;accent-color:var(--clay);width:16px;height:16px}
.checks .hint{display:block;font-size:13px;color:var(--ink-faint);margin-top:2px}
.go{display:flex;gap:16px;align-items:center;margin-top:8px}
.go button{font-size:16px;padding:14px 32px}
.privacy{font-size:13.5px;color:var(--ink-faint);line-height:1.7;margin-top:30px;
  padding-top:22px;border-top:1px solid var(--line)}
.err{background:#fcf0ee;border:1px solid #efd2cc;border-left:3px solid var(--crit);
  border-radius:14px;padding:24px 28px}
.err h2{margin-top:0;color:var(--crit)}
"""

PLACEHOLDER = """CeraVe Foaming Facial Cleanser, $16
  water, cocamidopropyl hydroxysultaine, niacinamide, ceramide NP, hyaluronic acid

The Ordinary Retinol 0.5% in Squalane, $12
  squalane, retinol, tocopherol

Paula's Choice 2% BHA Liquid, $35 — don't really use it
  water, methylpropanediol, salicylic acid, panthenol"""


def shell(body: str, title: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{e(title)}</title><style>{CSS}{EXTRA}</style></head>"
        f'<body><div class="wrap">{body}</div>{LOADING_MARKUP}'
        f"<script>{LOADING_JS}</script></body></html>"
    )


def landing(concerns: list[tuple[str, str]] | None = None) -> str:
    concern_boxes = "".join(
        f'<label><input type="checkbox" name="concerns" value="{e(cid)}">'
        f"<span>{e(label)}</span></label>"
        for cid, label in (concerns or [])
    )
    body = f"""
<div class="hero">
  <h1>What's actually on your shelf</h1>
  <p class="tag">Photograph your skincare products. This works out which ones
  clash, which duplicate each other, and what order to use them in.</p>
</div>

<form method="post" action="/audit" enctype="multipart/form-data">

  <fieldset>
    <legend>Photographs</legend>
    <p>Lay your products out and take a picture, or photograph them where they
    are. Back labels are worth a separate shot — the ingredient list is what
    this reads. Up to {MAX_IMAGES} photos.</p>
    <input type="file" name="photos" accept="image/*" multiple>
  </fieldset>

  <fieldset>
    <legend>Or type them</legend>
    <p>One product per line. Add the ingredients underneath if you have them,
    what you paid, and say if there's one you never use — the ingredients are
    what the audit runs on, and the prices are what it uses to tell you what is
    going to waste.</p>
    <div class="eg">{e(PLACEHOLDER)}</div>
    <textarea name="typed" placeholder="Paste or type your products here"></textarea>
  </fieldset>

  <fieldset>
    <legend>A photo of your skin, if you want</legend>
    <p>Entirely optional. If you add one, it is used to <em>ask</em> you what
    you might be treating — "there seems to be shine across the forehead, is
    that something you're working on?" — and you decide what is right. It does
    not diagnose anything, and nothing it notices counts until you tick it.</p>
    <p style="font-size:13.5px;color:var(--ink-faint)">Read once, in memory,
    and gone when the audit finishes. Never stored, never sent anywhere else.</p>
    <input type="file" name="face" accept="image/*">
  </fieldset>

  <fieldset>
    <legend>What are you trying to treat?</legend>
    <p>Optional. Tick anything that applies and the audit will also tell you
    whether your shelf actually addresses it — and what would, if it does not.</p>
    <div class="checks">{concern_boxes}</div>
  </fieldset>

  <fieldset>
    <legend>Anything we should be careful about</legend>
    <p>Optional, and you can skip it. If you'd rather not say, leave these
    unticked and anything affected gets the cautious answer anyway.</p>
    <div class="checks">
      <label><input type="checkbox" name="conditions" value="pregnancy">
        <span>I'm pregnant, or trying
        <span class="hint">Some actives are conventionally avoided — those get
        flagged for your clinician rather than advised on here.</span></span></label>
      <label><input type="checkbox" name="conditions" value="prescription_product">
        <span>Something here was prescribed to me
        <span class="hint">Prescribed products are sent back to whoever
        prescribed them. This tool doesn't second-guess that.</span></span></label>
    </div>
  </fieldset>

  <div class="go">
    <button type="submit">Audit my shelf</button>
    <span style="font-size:13.5px;color:var(--ink-faint)">
      Takes about half a minute. Up to {MAX_PRODUCTS} products.</span>
  </div>
</form>

<p class="privacy">
  <strong>What happens to your photos.</strong> They're read once, in memory,
  to pull the product names and ingredient lists off the labels, and deleted
  when the audit finishes. Nothing is stored, nothing is sent anywhere else,
  and no account is involved.<br><br>
  <strong>This isn't medical advice.</strong> Prescription products and
  pregnancy-related findings are handed to a clinician rather than answered
  here. The interaction rules are published in the repository and most of them
  have not yet been checked against a primary source — the result page says
  which.
</p>
"""
    return shell(body, "Skincare shelf audit")


def error_page(message: str, detail: str = "") -> str:
    body = f"""
<div class="hero"><h1>That didn't work</h1></div>
<div class="err">
  <h2>{e(message)}</h2>
  {f"<p>{e(detail)}</p>" if detail else ""}
  <p style="margin-bottom:0"><a href="/" style="color:var(--clay)">Start again</a></p>
</div>
"""
    return shell(body, "Something went wrong")

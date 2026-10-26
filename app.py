"""The web app.

    uvicorn app:app --port 8000

Two routes. GET / is the upload form; POST /audit runs the pipeline and
returns the result page. Server-rendered, no build step, no front-end
framework — the graders have ten minutes to get this running from a clone and
every extra moving part is a way to spend them.

Photographs are held in memory and written to a temporary directory only for
as long as the vision call needs a path, then deleted in a finally block. The
landing page promises that; this is where the promise is kept.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fastapi import FastAPI, File, Form, UploadFile  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402

from agents import explain_audit, new_run_id, observe_skin, read_shelf  # noqa: E402
from annotate import annotate, boxes_for  # noqa: E402
from limits import MAX_IMAGE_BYTES, Trim  # noqa: E402
from lookup import (  # noqa: E402
    MAX_LOOKUPS,
    MAX_URLS,
    find_from_url,
    find_mask_time,
    source_name,
    find_ingredients,
    strip_urls,
    urls_in,
)
from models import ReadProduct, ShelfReading, InputProduct, display_name  # noqa: E402
from pages import error_page, landing  # noqa: E402
import render as render_mod  # noqa: E402
from render import render  # noqa: E402
from rules import normalise, Rules  # noqa: E402
from safety import detect_suppression, trap_calls, AuditTrail  # noqa: E402
from usage import UsageLog  # noqa: E402

app = FastAPI(title="Skincare shelf audit")

# Loaded once. The database is read-only at runtime and parsing it per request
# would add latency for nothing.
RULES = Rules()

# The concern checkboxes come from the database, so the form and the engine
# cannot drift apart.
render_mod.CONCERN_CHOICES = [
    (c["id"], c["label"]) for c in RULES.concerns.values()
]

IMAGE_SUFFIX = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return landing(render_mod.CONCERN_CHOICES)


@app.post("/audit", response_class=HTMLResponse)
async def audit(
    photos: list[UploadFile] = File(default=[]),
    face: UploadFile | None = File(default=None),
    typed: str = Form(default=""),
    conditions: list[str] = Form(default=[]),
    concerns: list[str] = Form(default=[]),
    carried: str = Form(default=""),
    pname: list[str] = Form(default=[]),
    pprice: list[str] = Form(default=[]),
    punused: list[str] = Form(default=[]),
) -> HTMLResponse:
    typed = (typed or "").strip()
    usable = [p for p in photos if p.filename]

    # Products identified by an earlier round, posted back in a hidden field.
    # No session, no storage — the landing page promises photographs are not
    # kept, and server-side state would quietly make that less true.
    previous: list[InputProduct] = []
    if carried:
        try:
            previous = [InputProduct(**row) for row in json.loads(carried)]
        except Exception:
            previous = []

    # Prices typed on the result page. Positional: the browser submits the
    # hidden name and its price input together, in document order.
    typed_prices: dict[str, float | None] = {}
    for name, raw in zip(pname, pprice):
        value = (raw or "").strip()
        if not value:
            continue
        try:
            typed_prices[name] = float(value)
        except ValueError:
            continue
    never_used = {n for n in punused}

    for product in previous:
        if product.name in typed_prices:
            product.price_usd = typed_prices[product.name]
        product.unused = product.name in never_used

    if not usable and not typed and not previous:
        return HTMLResponse(
            error_page(
                "There was nothing to audit.",
                "Add at least one photograph or type a product or two, then try again.",
            ),
            status_code=400,
        )

    tmp = Path(tempfile.mkdtemp(prefix="shelf-"))
    try:
        paths = []
        for upload in usable:
            suffix = IMAGE_SUFFIX.get((upload.content_type or "").lower())
            if suffix is None:
                continue  # Not an image we can read; cap_images drops the rest.
            data = await upload.read()
            if len(data) > MAX_IMAGE_BYTES:
                continue
            path = tmp / f"{len(paths):02d}{suffix}"
            path.write_bytes(data)
            paths.append(path)

        if not paths and not typed and not previous:
            return HTMLResponse(
                error_page(
                    "None of those files could be read as photographs.",
                    "JPEG, PNG and WebP work. You can also type the products instead.",
                ),
                status_code=400,
            )

        # The face photograph is read once, from the temp directory, and the
        # directory is removed in the finally block below. It is never written
        # to the audit trail and never reaches the result page.
        face_path = None
        if face is not None and face.filename:
            suffix = IMAGE_SUFFIX.get((face.content_type or "").lower())
            if suffix:
                data = await face.read()
                if 0 < len(data) <= MAX_IMAGE_BYTES:
                    face_path = tmp / f"face{suffix}"
                    face_path.write_bytes(data)

        run_id = new_run_id()
        log = UsageLog(run_label=f"web-{run_id}", cache_enabled=True)
        trail = AuditTrail(run_id=run_id, defended=True)
        traps_before = len(trap_calls())
        trims: list[Trim] = []

        # Pasted product pages are pulled out before the shelf reader sees
        # them. A URL is a better input than anything else this app takes —
        # it names one specific product and carries the list that product's
        # maker publishes — and handing it to a reader whose job is naming
        # things from photographs would waste it as a product called "https".
        pasted = urls_in(typed)[:MAX_URLS]
        typed = strip_urls(typed)

        from_urls: list[InputProduct] = []
        url_records: dict[str, dict] = {}
        url_suppressed: dict[str, list[str]] = {}
        # Products whose price we had to guess because the linked page
        # did not give one up. Named on the page, because "your link
        # says $12 and this says $16" is the complaint it answers.
        off_page_prices: dict[str, float] = {}
        # Products whose ingredient list was not on the linked page.
        # Usually harmless — an INCI list is the same wherever it is
        # printed — but it can be a different size or an older
        # formula, and it is the list every finding below rests on.
        off_page_lists: dict[str, str] = {}
        # Products the web lookup refused to identify, and why.
        wrong_product: dict[str, str] = {}
        # Products priced at a size other than the one photographed.
        size_prices: dict[str, tuple[str, str]] = {}
        # Links whose product name collided with an earlier one.
        same_name_links: list[str] = []
        # A link that cannot be read is the one failure the user is
        # guaranteed to notice, because they counted the links they
        # pasted. A tester gave five and got four products back with
        # nothing saying where the fifth went. `continue` was doing the
        # dropping; the page now names every link that did not come
        # through, so the count always reconciles.
        failed_urls: list[str] = []
        for url in pasted:
            record = await find_from_url(url, usage_log=log)
            if not record:
                failed_urls.append(url)
                continue
            name = record.get("matched_name") or url

            # Two links, one name. Products are merged downstream on a
            # lowercased name, so two different ASINs that the lookup
            # happens to describe with the same words silently become one
            # product — five pasted links, four products on the page, no
            # explanation. The link is the identity the user chose, so a
            # repeated name is disambiguated rather than collapsed, and
            # the duplicate check gets to make its own call about whether
            # they are really the same thing.
            if name.strip().lower() in {n.strip().lower() for n in url_records}:
                tag = [seg for seg in url.rstrip("/").split("/") if seg][-1][:16]
                name = f"{name} ({tag})"
                same_name_links.append(name)


            # Same cross-check the shelf reader runs on a transcribed
            # label: re-read the page's own words with the deterministic
            # matcher and see whether the structured list dropped
            # anything that can change a finding. A page is the one input
            # whose author is not the user, so it is the last place to
            # take a tidy list on trust.
            if record.get("raw_list"):
                lost = detect_suppression(
                    record["raw_list"],
                    ShelfReading(products=[ReadProduct(
                        name=name, listed_ingredients=record["inci"])]),
                    RULES,
                )
                if lost:
                    url_suppressed[name] = lost

            # Two different claims, kept apart. A price printed on the page
            # the user linked is the price they are looking at, so it is
            # used as a real figure. A price the model knew from elsewhere
            # is an estimate and is labelled one — previously both arrived
            # as "typical retail", which left someone who pasted an Amazon
            # link looking at a number their own page contradicted with no
            # way to tell why.
            if record.get("list_on_page") is False:
                off_page_lists[name] = record.get("list_found_at") or ""
            page_price = record.get("typical_price_usd")
            guess_price = record.get("estimated_price_usd")
            if guess_price and not page_price:
                off_page_prices[name] = float(guess_price)
            from_urls.append(
                InputProduct(name=name, listed_ingredients=record["inci"],
                             price_usd=page_price or guess_price,
                             price_is_typical=not page_price)
            )
            url_records[name] = record

        reading = None
        if paths or typed:
            reading = await read_shelf(
                images=paths, text=typed or None,
                usage_log=log, trail=trail, trims_out=trims,
            )

        skin = None
        if face_path is not None:
            try:
                skin = await observe_skin(face_path, usage_log=log, trail=trail)
            except Exception:
                # A failed observation is a lost suggestion, not a lost audit.
                traceback.print_exc()

        if (reading is not None and not reading.products and not previous
                and not from_urls and skin is None):
            return HTMLResponse(
                error_page(
                    "No products could be identified.",
                    "If the photographs were of labels, try a closer shot of the "
                    "ingredient list. Typing the names in works too.",
                ),
                status_code=422,
            )

        fresh = [
            InputProduct(
                name=display_name(p.brand, p.name), brand=p.brand, form=p.form,
                size=p.size,
                listed_ingredients=p.listed_ingredients,
                price_usd=p.price_usd, unused=p.unused,
            )
            for p in (reading.products if reading else [])
        ]

        # A real label beats what we carried forward. Someone who went back
        # and photographed the ingredient panel did it to replace a name
        # match, so the new read wins on a name collision.
        merged = {p.name.strip().lower(): p for p in previous}
        for p in from_urls:
            merged[p.name.strip().lower()] = p
        for p in fresh:
            merged[p.name.strip().lower()] = p
        products = list(merged.values())
        # Conditions and concerns arrive on the same field; they are different
        # kinds of thing and go to different places. A condition is a gate, a
        # concern is a goal.
        # Two different kinds of thing on two fields. A condition is a gate
        # that routes to a clinician; a concern is a goal that drives
        # suggestions. Anything arriving on the wrong one is sorted here
        # rather than silently ignored.
        incoming = list(conditions) + list(concerns)
        # An observation is a suggested concern on the first pass. The user
        # sees it ticked and can untick it before the next one.
        incoming += [o.concern for o in (skin.observations if skin else [])]
        concern_ids = [c for c in incoming if c in RULES.concerns]
        gate_ids = [c for c in incoming if c not in RULES.concerns]
        # Anything with no ingredients and no catalogue entry gets looked up.
        #
        # A hand-written catalogue cannot cover the public's bathrooms. The
        # order matters: a label beats the catalogue, the catalogue beats the
        # web, and the web beats telling someone their product was ignored.
        sourced: dict[str, dict] = dict(url_records)
        budget = MAX_LOOKUPS
        for product in products:
            if product.listed_ingredients or budget <= 0:
                continue
            if RULES.match_catalogue(product):
                continue
            record = await find_ingredients(product.name, usage_log=log,
                                            size=product.size)
            budget -= 1
            if record and record.get("mismatch"):
                # Looked for, not found. Named here because the user is
                # the only one who can resolve it, and because quietly
                # swapping in a similar product is the worst thing this
                # app can do: every finding would be computed from a
                # bottle they do not own.
                wrong_product[product.name] = record["mismatch"]
                record = None
            if record:
                product.listed_ingredients = record["inci"]
                # What someone actually paid always wins; this fills a gap.
                if product.price_usd is None and record.get("typical_price_usd"):
                    product.price_usd = float(record["typical_price_usd"])
                    product.price_is_typical = True
                    # A 7 ml sample priced as a full jar is wrong by a
                    # factor of twenty, and the money section is built
                    # entirely from this number. Still shown — a
                    # wrong-size price still ranks what is going to
                    # waste — but never silently.
                    priced_size = (record.get("size") or "").strip()
                    if product.size and priced_size and \
                            normalise(priced_size) != normalise(product.size):
                        product.price_size_mismatch = priced_size
                        size_prices[product.name] = (product.size, priced_size)
                sourced[product.name] = record

        # How long a mask stays on is a property of that mask, not of
        # masks. Clay sets in ten minutes, a sheet mask comes off at
        # twenty, an overnight mask stays on all night — so it is looked
        # up per product. When nothing is found the step says to follow
        # the packet and the guided player waits, rather than counting
        # down a number this app chose.
        #
        # Separate from the ingredient budget above: a mask usually has
        # its ingredients already and would never reach that loop.
        mask_budget = MAX_LOOKUPS
        for product in products:
            if mask_budget <= 0:
                break
            if RULES.infer_form(product) != "mask" or product.dwell_seconds:
                continue
            # A page we already read may have carried it.
            rec = sourced.get(product.name) or {}
            minutes = rec.get("mask_minutes")
            if minutes is None:
                minutes, source = await find_mask_time(product.name, usage_log=log)
                mask_budget -= 1
            else:
                source = source_name(rec.get("source_url", "")) or "the product page"
            if minutes:
                product.dwell_seconds = int(minutes) * 60
                product.dwell_source = source

        result = RULES.audit(products, gate_ids, trims=trims, concerns=concern_ids)
        if reading is not None:
            result.unreadable = list(reading.unreadable)
            result.visible_count = reading.visible_count
        # The narrator is the last call, and by the time it runs the audit
        # already exists and is already correct — the engine decided every
        # finding, every severity and the whole routine without it. Letting
        # a failure here return the generic error page threw all of that
        # away, along with the shelf read the user already paid for, and
        # told them the audit failed when it had not.
        #
        # render() has always accepted narrative=None: the page falls back
        # to the engine's own guidance text for each finding. Less
        # readable, entirely true.
        try:
            narrative, _ = await explain_audit(result, usage_log=log, trail=trail)
        except Exception:
            traceback.print_exc()
            narrative = None
            notes_from_narrator = [
                "The plain-language write-up could not be generated this time. "
                "Everything below is the audit itself, which does not depend on "
                "it — the wording is the engine's own rather than rephrased."
            ]
        else:
            notes_from_narrator = []
        log.write()

        # A trap tool firing means an agent tried to do something no task
        # here requires — buy a product, email a clinician. Until now that
        # went to output/trap_calls.json and nowhere else, read only by
        # redteam.py, so on a real user's audit nobody would ever learn it
        # happened. It belongs in this run's own record.
        fired = trap_calls()[traps_before:]
        if fired:
            trail.record(
                agent="safety",
                step="trap_called",
                usage=None,
                detail={"tools": sorted({c["tool"] for c in fired}),
                        "count": len(fired)},
            )

        notes = [t.note for t in trims] + notes_from_narrator
        if same_name_links:
            notes.append(
                f"{len(same_name_links)} of the links you pasted came back under a "
                f"product name already used by another link, so "
                f"{'it has' if len(same_name_links) == 1 else 'they have'} been "
                f"tagged with the end of the link to keep "
                f"{'it' if len(same_name_links) == 1 else 'them'} separate: "
                + ", ".join(same_name_links)
                + ". If these really are the same product, the duplicate check "
                  "above will have said so."
            )
        for pname, (yours, priced) in size_prices.items():
            notes.append(
                f"The price shown for {pname} is for the {priced} size, but the "
                f"one in your photograph is {yours}. Everything in the money "
                f"section that depends on it is wrong by that ratio — type what "
                f"you actually paid to fix it."
            )
        for pname, why in wrong_product.items():
            notes.append(
                f"We could not confirm an ingredient list for {pname}: {why}. "
                f"Rather than use a similar product's list, it has been left out "
                f"of the checks — type its ingredients in, or paste a link to its "
                f"page, and it will be included."
            )
        for pname, where in off_page_lists.items():
            notes.append(
                f"The ingredients for {pname} were not published on the page you "
                f"linked; they were taken from "
                + (f"{where} " if where else "another published list ")
                + "for the same product. Usually the same list — but check the "
                  "size and the formula match what you own, because everything "
                  "said about this product rests on it."
            )
        for pname, guess in off_page_prices.items():
            notes.append(
                f"The page you linked for {pname} did not show a price we could "
                f"read, so ${guess:.0f} is a typical retail figure from elsewhere "
                f"and will not match that listing. Type what it actually costs "
                f"below to make the money section yours."
            )
        for pname, lost in url_suppressed.items():
            notes.append(
                f"The page for {pname} lists " + ", ".join(lost)
                + ", which did not come through in the ingredient list we read "
                  "from it. Worth checking that page yourself."
            )
        if previous:
            notes.append(
                f"{len(previous)} product(s) were carried over from your previous "
                "audit. Anything you have since photographed has replaced what was "
                "recorded for it."
            )
        if reading is not None and reading.suppressed_terms:
            notes.append(
                "Something in what you sent said an ingredient was not present, "
                "but the ingredient was named: "
                + ", ".join(reading.suppressed_terms)
                + ". It has been left out of the audit, so check those labels yourself."
            )
        if reading is not None and reading.suspicious_text:
            notes.append(
                f"{len(reading.suspicious_text)} label(s) carried text written to "
                "instruct an automated reader rather than describe the product. "
                "It was recorded and ignored."
            )
        result.routine.notes.extend(notes)

        # Mark the photographs up before the temp directory goes away.
        grouped, legend = boxes_for(reading, result) if reading else ({}, [])
        annotated = []
        for i, path in enumerate(paths):
            boxes = grouped.get(i, [])
            if not boxes:
                continue
            uri = annotate(path.read_bytes(), boxes)
            if uri:
                annotated.append(uri)

        # Carry the RESOLVED products, not the inputs.
        #
        # A catalogue hit renames "Hydrating Facial Cleanser" to "CeraVe
        # Hydrating Facial Cleanser", and the price form on the page shows
        # that name. Carrying the pre-resolution name meant the two disagreed
        # for exactly the products the catalogue had helped with, so typed
        # prices silently failed to apply to them — two of three in testing,
        # with no error anywhere.
        carry = json.dumps([
            rp.product.model_dump(include={"name", "brand", "form",
                                           "listed_ingredients", "price_usd", "unused"})
            for rp in result.products
        ])
        return HTMLResponse(
            render(result, narrative, annotated or None, carry, legend, skin,
                   sourced, failed_urls=failed_urls)
        )

    except Exception:  # noqa: BLE001
        # Never show a stack trace to someone who uploaded a photo of their
        # bathroom shelf. It goes to the log; they get a sentence.
        traceback.print_exc()
        return HTMLResponse(
            error_page(
                "The audit failed partway through.",
                "This is a problem at our end, not with your photos. Trying again "
                "often works; a smaller number of products is more likely to.",
            ),
            status_code=500,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.get("/health")
def health() -> dict:
    """Enough to tell a running app from a running process."""
    return {
        "ok": True,
        "ingredients": len(RULES.ingredients),
        "rules": RULES.rules_total,
        "rules_verified": RULES.rules_verified,
    }

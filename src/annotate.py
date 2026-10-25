"""Draw the audit back onto the photograph.

A list of names tells someone four products were missed. A box around the four
bottles tells them which ones to go and photograph again — and that is the
difference between a warning they act on and one they skim.

Three states, because they need three different actions:

    green   read from the label, nothing to do
    amber   identified by name, ingredients from the catalogue — check the bottle
    red     not identified, not in the audit — photograph this one again

The annotated copy is downscaled and embedded in the result page as a data
URI. The page has to open by double-click with no network, so a linked file
would not survive being emailed or moved.
"""

from __future__ import annotations

import base64
import io

from PIL import Image, ImageDraw, ImageFont

MAX_WIDTH = 1100
JPEG_QUALITY = 82

COLOURS = {
    "read": (104, 150, 99),
    "catalogue": (198, 142, 58),
    "missed": (176, 72, 58),
}
LABELS = {
    "read": "read",
    "catalogue": "by name",
    "missed": "not read",
}


def _font(size: int):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate(image_bytes: bytes, boxes: list[dict]) -> str | None:
    """Return a data URI for the marked-up image, or None if it cannot be drawn.

    `boxes` is a list of {bbox: [x0,y0,x1,y1] as fractions, status, label}.
    Never raises: a failed annotation should cost the user a picture, not
    their audit.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
    except Exception:
        return None

    if img.width > MAX_WIDTH:
        img = img.resize(
            (MAX_WIDTH, round(img.height * MAX_WIDTH / img.width)), Image.LANCZOS
        )

    w, h = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    stroke = max(2, round(w / 380))
    text_size = max(12, round(w / 62))
    font = _font(text_size)

    for box in boxes:
        coords = box.get("bbox") or []
        if len(coords) != 4:
            continue
        x0, y0, x1, y1 = coords
        # Tolerate a model that returns pixels, or corners the wrong way round.
        if max(coords) > 1.5:
            x0, y0, x1, y1 = x0 / w, y0 / h, x1 / w, y1 / h
        x0, x1 = sorted((max(0.0, min(1.0, x0)), max(0.0, min(1.0, x1))))
        y0, y1 = sorted((max(0.0, min(1.0, y0)), max(0.0, min(1.0, y1))))
        px = (round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h))
        if px[2] - px[0] < 6 or px[3] - px[1] < 6:
            continue

        colour = COLOURS.get(box.get("status", "missed"), COLOURS["missed"])
        draw.rectangle(px, outline=colour, width=stroke)
        # A wash inside the box, so a red region reads as missed at a glance
        # rather than needing the outline to be found first.
        draw.rectangle(px, fill=(*colour, 38))

        caption = LABELS.get(box.get("status", "missed"), "")
        name = (box.get("label") or "").strip()
        text = f"{caption}: {name}" if name else caption
        if len(text) > 42:
            text = text[:40] + "…"

        tw = draw.textlength(text, font=font)
        th = text_size + 7
        ty = px[1] - th if px[1] - th > 0 else px[1]
        draw.rectangle((px[0], ty, px[0] + tw + 12, ty + th), fill=(*colour, 235))
        draw.text((px[0] + 6, ty + 3), text, font=font, fill=(255, 255, 255))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    encoded = base64.b64encode(out.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def boxes_for(reading, audit) -> dict[int, list[dict]]:
    """Group boxes by which uploaded photograph they belong to.

    Status comes from the audit rather than the reading: whether a product was
    actually usable is something only the engine knows, after resolution.
    """
    by_name = {p.product.name: p for p in audit.products}
    grouped: dict[int, list[dict]] = {}

    for product in reading.products:
        if not product.region or not product.region.bbox:
            continue
        resolved = by_name.get(product.name)
        if resolved is None:
            continue
        if resolved.matched_from_catalogue:
            status = "catalogue"
        elif resolved.actives:
            status = "read"
        else:
            status = "missed"
        grouped.setdefault(product.region.image_index, []).append(
            {"bbox": product.region.bbox, "status": status, "label": product.name}
        )

    for region in reading.unreadable_regions:
        if region.bbox:
            grouped.setdefault(region.image_index, []).append(
                {"bbox": region.bbox, "status": "missed", "label": region.label}
            )

    return grouped

"""Bounds on what one audit may consume.

Nothing here existed until an upload form was on the horizon. A CLI reading a
JSON file you wrote yourself has no attacker; a page that accepts photographs
from strangers has one, and the cheapest attack on a system that calls a vision
model is simply to hand it more work than it can afford.

The three ceilings:

  products   a shelf is bounded by a bathroom cabinet. Forty is already an
             unusual number of skincare products to own, and the pairwise
             findings pass is O(n^2) in it.
  images     each photograph is a vision call. Eight covers a shelf
             photographed from several angles; fifty is someone probing.
  tokens     a per-run ceiling enforced by the model client itself, so a
             runaway loop stops at the library rather than at the invoice.

Every limit truncates and reports rather than failing. A user who owns 45
products should get an audit of 40 with a clear note, not an error page — and
the note matters, because an audit that silently ignored five products is
wrong in a way the user cannot see.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai.usage import UsageLimits

# Per audit.
MAX_PRODUCTS = 40
MAX_IMAGES = 8
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 20_000

# Per agent run. request_limit stops a tool-call loop; the token ceiling is
# the backstop for a single enormous request.
READER_LIMITS = UsageLimits(request_limit=6, total_tokens_limit=120_000)
AUDITOR_LIMITS = UsageLimits(request_limit=4, total_tokens_limit=80_000)

# What one audit should cost at the measured rate (~$0.0015). Twenty times
# that is generous for a large shelf and still catches a runaway.
COST_CEILING_USD = 0.03


@dataclass
class Trim:
    """What a limit removed, so it can be shown to the user."""

    kind: str
    kept: int
    dropped: int
    note: str


def cap_products(products: list, trims: list[Trim]) -> list:
    if len(products) <= MAX_PRODUCTS:
        return products
    dropped = len(products) - MAX_PRODUCTS
    trims.append(
        Trim(
            kind="products",
            kept=MAX_PRODUCTS,
            dropped=dropped,
            note=f"Only the first {MAX_PRODUCTS} products were audited. "
                 f"{dropped} more were left out, so this audit is incomplete.",
        )
    )
    return products[:MAX_PRODUCTS]


def cap_images(paths: list, trims: list[Trim]) -> list:
    kept, oversize = [], 0
    for path in paths[:MAX_IMAGES]:
        try:
            if path.stat().st_size > MAX_IMAGE_BYTES:
                oversize += 1
                continue
        except OSError:
            continue
        kept.append(path)

    if len(paths) > MAX_IMAGES:
        trims.append(
            Trim(
                kind="images",
                kept=MAX_IMAGES,
                dropped=len(paths) - MAX_IMAGES,
                note=f"Only the first {MAX_IMAGES} photographs were read.",
            )
        )
    if oversize:
        trims.append(
            Trim(
                kind="image_size",
                kept=len(kept),
                dropped=oversize,
                note=f"{oversize} photograph(s) were over "
                     f"{MAX_IMAGE_BYTES // (1024 * 1024)}MB and were skipped.",
            )
        )
    return kept


def cap_text(text: str | None, trims: list[Trim]) -> str | None:
    if not text or len(text) <= MAX_TEXT_CHARS:
        return text
    trims.append(
        Trim(
            kind="text",
            kept=MAX_TEXT_CHARS,
            dropped=len(text) - MAX_TEXT_CHARS,
            note="The product list was truncated; it was longer than this tool accepts.",
        )
    )
    return text[:MAX_TEXT_CHARS]

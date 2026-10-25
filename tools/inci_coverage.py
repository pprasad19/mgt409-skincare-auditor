"""Which real label terms does the resolver fail to recognise?

The sunscreen bug was not really about sunscreen. It was that an
ingredient's INCI list held five terms when labels use twenty-four, and
nothing would have revealed that short of someone noticing.

This generalises it: take every ingredient list in the lookup cache —
real published lists, fetched from brand and retailer pages — and find
the terms that resolve to nothing. Most will be water and emulsifiers the
table rightly ignores. The interesting ones are terms that look like an
active we already claim to know, under a name we do not have.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, "src")

import yaml

from rules import Rules

rules = Rules()

ing = yaml.safe_load(pathlib.Path("data/ingredients.yaml").read_text(encoding="utf-8"))
ing = ing["ingredients"] if isinstance(ing, dict) else ing

# Words that mark a term as plausibly an active we care about, rather than
# a solvent, emulsifier, preservative, fragrance or plant extract.
SIGNALS = [
    ("retino", "retinoid"), ("retinal", "retinoid"), ("tretinoin", "retinoid"),
    ("adapalene", "retinoid"), ("ascorb", "vitamin C"), ("niacinamid", "niacinamide"),
    ("nicotinamid", "niacinamide"), ("salicyl", "BHA"), ("glycolic", "AHA"),
    ("lactic", "AHA"), ("mandelic", "AHA"), ("malic", "AHA"), ("tartaric", "AHA"),
    ("citric", "AHA"), ("gluconolactone", "PHA"), ("lactobionic", "PHA"),
    ("azelaic", "azelaic"), ("azeloyl", "azelaic"), ("benzoyl peroxide", "BPO"),
    ("hydroquinone", "hydroquinone"), ("arbutin", "arbutin"),
    ("tranexamic", "tranexamic"), ("kojic", "pigment"), ("cysteamine", "pigment"),
    ("thiamidol", "pigment"), ("ceramide", "ceramide"), ("peptide", "peptide"),
    ("tripeptide", "peptide"), ("copper", "copper"), ("urea", "urea"),
    ("panthenol", "soothing"), ("centella", "soothing"), ("madecass", "soothing"),
    ("asiatic", "soothing"), ("allantoin", "soothing"), ("bisabolol", "soothing"),
    ("squalane", "emollient"), ("sulfur", "sulfur"), ("sulphur", "sulfur"),
    ("zinc oxide", "uv"), ("titanium dioxide", "uv"), ("triazine", "uv"),
    ("triazone", "uv"), ("benzoate", "uv"), ("camphor", "uv"),
    ("benzophenone", "uv"), ("octocrylene", "uv"), ("homosalate", "uv"),
    ("salate", "uv"), ("cinnamate", "uv"), ("avobenzone", "uv"),
    ("hyaluron", "humectant"), ("glycerin", "humectant"),
]

cache = json.loads(pathlib.Path("data/learned_products.json").read_text(encoding="utf-8"))
lists = [(v.get("matched_name") or k, v["inci"]) for k, v in cache.items() if v.get("inci")]
print(f"  {len(lists)} real published ingredient lists in the cache\n")

unknown: dict[str, set] = {}
total_terms = 0
for name, inci in lists:
    for term in inci:
        t = " ".join(str(term).split())
        if not t:
            continue
        total_terms += 1
        if rules.resolve_text(t):
            continue
        low = t.lower()
        for needle, family in SIGNALS:
            if needle in low:
                unknown.setdefault(f"{family}: {t}", set()).add(name[:30])
                break

print(f"  {total_terms} terms across those lists")
print(f"  {len(unknown)} unrecognised terms that look like an active we claim to know\n")
for key in sorted(unknown):
    where = sorted(unknown[key])
    print(f"    {key}")
    print(f"        in: {', '.join(where[:3])}{' …' if len(where) > 3 else ''}")

# How many INCI terms does each ingredient carry? A short list is where the
# sunscreen bug lived.
print("\n  INCI terms per ingredient, thinnest first:")
rows = sorted(ing, key=lambda r: len(r.get("inci") or []))
for r in rows[:12]:
    print(f"    {len(r.get('inci') or []):>2}  {r['id']:24} {r.get('inci')}")

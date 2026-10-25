"""The ingredient-interaction engine, exposed over MCP.

    python mcp_server/server.py          # stdio, for an MCP client
    python mcp_server/server.py --demo   # print what each tool returns

Reads data/skincare.db, which build_db.py compiles from the YAML in data/.
Nothing here writes, and nothing here invents: every answer comes out of the
table, and a question about an ingredient the table does not know returns
"unknown" rather than a guess.

WHY THIS EXISTS SEPARATELY FROM THE APP

The useful thing in this project is not the web page, it is the rules —
32 ingredients, 34 interaction and contraindication rules, product names in
four languages. Behind MCP those become something any agent can query:
someone can point Claude Desktop at this server and ask whether their retinol
clashes with their acne wash, with no part of this app running.

The web app does not route through it. A spawned subprocess on the path
between an upload and an answer is a failure mode the app does not need, and
the engine it would be calling is in the same process already. The agents can
attach it when they want to look something up; the verdict is computed
directly either way. That is a deliberate split, not an omission — see
README.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastmcp import FastMCP  # noqa: E402

from rules import Rules  # noqa: E402

mcp = FastMCP("skincare-rules")

_rules: Rules | None = None


def engine() -> Rules:
    global _rules
    if _rules is None:
        _rules = Rules()
    return _rules


@mcp.tool
def resolve_ingredients(label_text: str) -> list[dict]:
    """Find known actives in a block of label text.

    Accepts an INCI list in any of the supported languages, or a messy
    paste. Matching is literal — it looks for strings, it does not interpret
    claims — so a label asserting that an ingredient is absent still resolves
    that ingredient. Use this when you have label text.
    """
    r = engine()
    out = []
    for ingredient_id in r.resolve_text(label_text):
        row = r.ingredients[ingredient_id]
        out.append({
            "id": ingredient_id,
            "name": row["name"],
            "class": row["class"],
            "time_of_day": row["time"],
            "photosensitising": bool(row["photosensitising"]),
            "pregnancy": row["pregnancy"],
            "prescription": bool(row["prescription"]),
        })
    return out


@mcp.tool
def lookup_ingredient(name: str) -> dict:
    """Everything the table holds about one ingredient, by name or alias."""
    r = engine()
    ids = r.resolve_text(name)
    if not ids:
        return {"found": False, "name": name,
                "note": "not in the ingredient table; no opinion is available"}
    row = dict(r.ingredients[ids[0]])
    row["found"] = True
    row["photosensitising"] = bool(row["photosensitising"])
    row["prescription"] = bool(row["prescription"])
    return row


def _as_ids(values: list[str]) -> list[str]:
    """Accept ingredient ids, display names, INCI terms or local-language names.

    An agent calling this has no way to know that the id is `benzoyl_peroxide`
    rather than "Benzoyl Peroxide". The first version required exact ids,
    silently dropped everything else, and cheerfully reported no interaction
    between a benzoyl peroxide wash and a retinol — a wrong answer delivered
    confidently, which is worse than an error.
    """
    r = engine()
    out: list[str] = []
    for value in values or []:
        text = (value or "").strip()
        if not text:
            continue
        if text in r.ingredients:
            out.append(text)
            continue
        out.extend(r.resolve_text(text))
    seen, unique = set(), []
    for i in out:
        if i not in seen:
            seen.add(i)
            unique.append(i)
    return unique


@mcp.tool
def check_interactions(ingredient_ids: list[str]) -> list[dict]:
    """Rules that fire for a set of ingredients used together.

    Pass ingredient ids, display names, INCI terms or local-language names —
    "benzoyl_peroxide", "Benzoyl Peroxide" and "과산화벤조일" all work.

    Returns conflicts, cautions, synergies, myths and redundancies, each with
    the rule id that produced it, the mechanism, what to do, and whether that
    rule has been checked against a source.
    """
    r = engine()
    known = _as_ids(ingredient_ids)

    def matches(selector: str) -> list[str]:
        if selector == "*":
            return known
        if selector.startswith("class:"):
            want = selector.removeprefix("class:")
            return [i for i in known if r.ingredients[i]["class"] == want]
        if selector.startswith("ing:"):
            want = selector.removeprefix("ing:")
            return [i for i in known if i == want]
        return []

    out = []
    for rule in r.interactions:
        excepted = set((rule["except_ingredients"] or "").split(",")) - {""}
        a = [i for i in matches(rule["a"]) if i not in excepted]
        if not a:
            continue
        if rule["b"] == "*":
            b = []
        else:
            b = [i for i in matches(rule["b"]) if i not in excepted]
            if not b or (rule["a"] == rule["b"] and len(set(a + b)) < 2):
                continue
        out.append({
            "rule_id": rule["rule_id"],
            "type": rule["type"],
            "severity": rule["severity"],
            "ingredients": sorted(set(a + b)),
            "mechanism": rule["mechanism"],
            "guidance": rule["guidance"],
            "resolution": rule["resolution"],
            "verified": rule["review"] == "verified",
        })
    return out


@mcp.tool
def check_contraindications(ingredient_ids: list[str], conditions: list[str]) -> list[dict]:
    """Gates that route to a clinician. Never advice — always a handoff.

    Conditions understood: pregnancy, prescription_product, declined_to_say.
    """
    r = engine()
    known = _as_ids(ingredient_ids)
    active = set(conditions)
    out = []

    for rule in r.contraindications:
        if rule["condition"] not in active:
            continue
        sel = rule["matches"]
        if sel.startswith("class:"):
            hit = [i for i in known if r.ingredients[i]["class"] == sel.removeprefix("class:")]
        elif sel.startswith("ing:"):
            hit = [i for i in known if i == sel.removeprefix("ing:")]
        elif sel == "prescription:true":
            hit = [i for i in known if r.ingredients[i]["prescription"]]
        else:
            hit = []
        if hit:
            out.append({
                "rule_id": rule["rule_id"],
                "condition": rule["condition"],
                "severity": rule["severity"],
                "ingredients": hit,
                "message": rule["message"],
                "action": rule["action"],
            })
    return out


@mcp.tool
def find_product(name: str) -> dict:
    """Look a product up by name, for when no ingredient list is available.

    Returns the actives the product is known to be formulated around. This is
    a claim about a product, not a reading of a particular bottle —
    formulations change, and a label beats this whenever one exists.
    """
    from models import InputProduct

    hit = engine().match_catalogue(InputProduct(name=name))
    if not hit:
        return {"found": False, "name": name}
    return {
        "found": True,
        "brand": hit["brand"],
        "name": hit["name"],
        "form": hit["form"],
        "actives": [a for a in hit["actives"].split(",") if a],
        "typical_price_usd": hit["typical_price_usd"],
        "caveat": "catalogue entry, not a reading of this bottle",
    }


@mcp.tool
def layering_order() -> list[dict]:
    """The canonical order products go on, thinnest to thickest."""
    r = engine()
    return [
        {"form": f["id"], "name": f["name"], "order": f["rank"],
         "times": f["times"].split(","), "note": f["note"]}
        for f in sorted(r.forms.values(), key=lambda x: x["rank"])
    ]


@mcp.tool
def coverage() -> dict:
    """What this server knows, and how much of it has been verified."""
    r = engine()
    return {
        "ingredients": len(r.ingredients),
        "interaction_rules": len(r.interactions),
        "contraindication_rules": len(r.contraindications),
        "catalogue_products": len(r.catalogue),
        "rules_verified": r.rules_verified,
        "rules_total": r.rules_total,
        "caveat": "rules not yet verified against primary sources are marked per rule",
    }


def _demo() -> None:
    label = "Aqua, Benzoyl Peroxide, Glycerin"
    found = resolve_ingredients(label)
    ids = [f["id"] for f in found] + ["retinol"]
    print(f"resolve_ingredients({label!r})")
    for f in found:
        print("   ", f["id"], "-", f["class"])
    print(f"\ncheck_interactions({ids})")
    for row in check_interactions(ids):
        print("   ", row["rule_id"], row["severity"], "-", row["guidance"][:60])
    print("\ncheck_contraindications(['retinol'], ['pregnancy'])")
    for row in check_contraindications(["retinol"], ["pregnancy"]):
        print("   ", row["rule_id"], "-", row["message"][:70])
    print("\nfind_product('Hydrating Facial Cleanser')")
    print("   ", find_product("Hydrating Facial Cleanser"))
    print("\ncoverage()")
    print("   ", coverage())


if __name__ == "__main__":
    if "--demo" in sys.argv:
        _demo()
    else:
        mcp.run()

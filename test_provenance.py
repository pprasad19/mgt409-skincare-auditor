"""The aliases are unverified, so a product that rests on one says so.

232 of the resolver's search terms are non-English ingredient names that
were machine-generated and have never been read by a speaker of any of
those languages. They cannot be verified here — that needs four speakers
this project does not have — so the question is what to do instead.

The risk is one-sided. A *missing* translation costs a finding: fewer
actives are recognised, fewer conflicts are reported, and the user is no
worse off than with no translation at all. A *wrong* one invents an
ingredient, and the warning it produces is indistinguishable on the page
from a real one.

So the unchecked half is made to declare itself. When a product's actives
were found only through an `intl:*` term, that product carries the fact
and the page names it — that product, that ingredient, that language —
instead of a disclaimer over every audit, which would be ignored.

This file pins both directions, because only one of them is a defence.
Flagging everything is as useless as flagging nothing.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from models import AuditNarrative, InputProduct  # noqa: E402
from render import render  # noqa: E402
from rules import Rules  # noqa: E402

R = Rules()
failures: list[str] = []
checks = 0


def check(label: str, got, want) -> None:
    global checks
    checks += 1
    if got != want:
        failures.append(f"{label}\n      got:  {got!r}\n      want: {want!r}")


def check_true(label: str, cond: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not cond:
        failures.append(f"{label}{': ' + detail if detail else ''}")


def resolve(name: str, *ingredients: str):
    return R.resolve(InputProduct(name=name, listed_ingredients=list(ingredients)))


# --- the table these terms come from ----------------------------------
kinds: dict[str, int] = {}
for _term, _id, kind in R.terms:
    kinds[kind] = kinds.get(kind, 0) + 1
unchecked = sum(n for k, n in kinds.items() if k.startswith("intl:"))
check_true("the term table records where each term came from",
           set(kinds) >= {"inci", "name", "alias"}, str(sorted(kinds)))
check_true("and there really is an unchecked population to defend against",
           unchecked > 100, f"{unchecked} intl terms of {len(R.terms)}")


# --- not flagged: the ordinary case -----------------------------------
# Almost every real audit. If this fires, the warning appears on shelves
# it has nothing to say about and stops meaning anything.
plain = resolve("Plain Serum", "Water", "Niacinamide", "Glycerin")
check_true("an English label finds its active", "niacinamide" in plain.actives,
           str(plain.actives))
check("and is not flagged", plain.translated_only, {})

inci = resolve("INCI Serum", "Aqua", "Retinol", "Tocopherol")
check_true("an INCI label finds its active", "retinol" in inci.actives)
check("and is not flagged", inci.translated_only, {})

# INCI is international: a Korean or French label still mostly resolves
# through terms a human has checked, which is why this mitigation is
# narrow rather than a blanket warning on every non-English shelf.
mixed = resolve("K-Beauty Serum", "정제수", "Niacinamide", "부틸렌글라이콜")
check_true("a Korean label listing INCI still finds the active",
           "niacinamide" in mixed.actives)
check("and is not flagged, because the checked term carried the match",
      mixed.translated_only, {})

# The same label, both names present. Which one the matcher happens to
# reach first is an accident of string length, so the flag must not
# depend on it.
both = resolve("Bilingual Serum", "Water", "Niacinamide (나이아신아마이드)")
check_true("both names present still finds the active",
           "niacinamide" in both.actives)
check("and the checked name clears the flag", both.translated_only, {})


# Every checked term in the table, one product each. This is the check
# that caught the real bug: "avobenzone" is both an INCI name and a word
# the French list repeats, the build stored one kind per term from an
# unordered set, and an English sunscreen label was warned about as an
# unchecked French translation. Three terms were affected and eyeballing
# the French list would have found two of them. Sweeping every term finds
# all of them, and keeps finding them.
wrongly_flagged: list[str] = []
for term, ingredient_id, kind in R.terms:
    if kind.startswith("intl:"):
        continue
    got = resolve(f"{ingredient_id} test", "Water", term)
    if got.translated_only:
        wrongly_flagged.append(f"{term!r} ({kind}) -> {got.translated_only}")
check("no checked term is reported as an unchecked translation",
      wrongly_flagged, [])

# An English word misfiled under French is possible — avobenzone was —
# because the scripts are the same. Under a CJK language it would stand
# out, so require at least one non-Latin character. Not "no Latin
# characters": アスコルビルリン酸Na and 維A酸 are real terms whose Latin
# letter is a chemical symbol.
all_latin = [
    f"{kind} {term!r}"
    for term, _id, kind in R.terms
    if kind in ("intl:zh", "intl:ko", "intl:ja") and term.isascii()
]
check("no Chinese, Korean or Japanese term is written entirely in Latin script",
      all_latin, [])


# --- flagged: the case the mitigation exists for ----------------------
ko = resolve("한국 세럼", "정제수", "나이아신아마이드")
check("a Korean-only label still finds the active", ko.actives, ["niacinamide"])
check("and is flagged, naming ingredient and language",
      ko.translated_only, {"Niacinamide": "Korean"})

ja = resolve("日本の美容液", "水", "レチノール")
check_true("a Japanese-only label finds its active", "retinol" in ja.actives)
check("and names Japanese", ja.translated_only.get("Retinol"), "Japanese")

fr = resolve("Sérum Français", "Eau", "rétinol")
check_true("a French-only label finds its active", "retinol" in fr.actives)
check("and names French", fr.translated_only.get("Retinol"), "French")

zh = resolve("中文精华", "水", "烟酰胺")
check_true("a Chinese-only label finds its active", "niacinamide" in zh.actives)
check("and names Chinese", zh.translated_only.get("Niacinamide"), "Chinese")

# Every language in the file is covered by the warning, so adding one
# later cannot slip through unnamed.
langs = {k.removeprefix("intl:") for k in kinds if k.startswith("intl:")}
check("all four languages are flagged by name",
      sorted({next(iter(p.translated_only.values()))
              for p in (ko, ja, fr, zh)}),
      ["Chinese", "French", "Japanese", "Korean"])
check_true("and the file holds no fifth language this test would miss",
           langs == {"ko", "ja", "fr", "zh"}, str(sorted(langs)))


# --- the finding is still made ----------------------------------------
# The flag is a caveat, not a veto. A Korean shelf with a real conflict
# must still be told about the conflict — warning and finding together.
audit = R.audit([
    InputProduct(name="한국 레티놀", listed_ingredients=["정제수", "레티놀"]),
    InputProduct(name="한국 BHA", listed_ingredients=["정제수", "살리실산"]),
], concerns=[])
check_true("a Korean shelf still produces findings",
           len(audit.findings) >= 1, str([f.rule_id for f in audit.findings]))
flagged = [p for p in audit.products if p.translated_only]
check_true("and the products carrying them are flagged",
           len(flagged) >= 1, str([p.product.name for p in audit.products]))


# --- and it reaches the reader ----------------------------------------
page = render(audit, AuditNarrative(summary="x", explanations=[], steps=[]))
text = re.sub("<[^>]+>", " ", page)
check_true("the page says a term was unchecked",
           "no speaker of that language has checked" in text)
check_true("it names the product it applies to", "한국 레티놀" in page)
check_true("it names the language", "Korean name" in text)
check_true("and it tells the reader what to do",
           "confirming against the bottle" in text)

# An all-English audit must not carry the block at all.
clean_page = render(
    R.audit([InputProduct(name="Retinol Serum", listed_ingredients=["Retinol"]),
             InputProduct(name="BHA", listed_ingredients=["Salicylic Acid"])],
            concerns=[]),
    AuditNarrative(summary="x", explanations=[], steps=[]),
)
check_true("an English audit carries no such block",
           "no speaker of that language has checked" not in clean_page)


if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)

print(f"ok  {checks} checks passed")
print(f"    {unchecked} of {len(R.terms)} search terms are unverified translations;")
print("    a product resting on one says so, naming the ingredient and the")
print("    language, and an English or INCI label is left alone")

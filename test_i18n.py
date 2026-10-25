"""Regression check for non-English support. No API key, no pytest.

    python test_i18n.py

Covers the two things that broke silently before:

  1. Ingredient resolution from local-language labels. The original
     normalise() deleted every non-ASCII character, so a Korean or Japanese
     label matched nothing and the audit came back clean and empty — a
     confident wrong answer, which is worse than an error.
  2. Form inference from non-English product names. An English-only keyword
     list classified everything else as a serum, which then placed it wrongly
     in the routine.

Neither failure raises anything. Both produce plausible output. That is the
argument for checking them here rather than by eye.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from models import InputProduct  # noqa: E402
from rules import Rules  # noqa: E402

# (language, product name, expected form)
FORMS = [
    ("ko", "토리든 다이브인 세럼", "serum"),
    ("ko", "라운드랩 약산성 클렌징폼", "cleanser"),
    ("ko", "에스트라 아토베리어 수분크림", "moisturiser"),
    ("ko", "닥터지 레드블레미쉬 선크림", "spf"),
    ("ko", "조선미녀 무기자차 선스틱", "spf"),
    ("ko", "아누아 어성초 토너", "toner"),
    ("ko", "메디힐 시트마스크", "mask"),
    ("ko", "이니스프리 아이크림", "eye"),
    ("fr", "La Roche-Posay Eau Micellaire", "cleanser"),
    ("fr", "Avène Lait Démaquillant", "cleanser"),
    ("fr", "Nuxe Crème Hydratante", "moisturiser"),
    ("fr", "Vichy Fluide Solaire SPF50", "spf"),
    ("fr", "Caudalie Sérum Vinoperfect", "serum"),
    ("fr", "Bioderma Masque Hydratant", "mask"),
    ("fr", "Clarins Contour des Yeux", "eye"),
    ("fr", "Nuxe Huile Prodigieuse", "oil"),
    ("ja", "資生堂 化粧水", "toner"),
    ("ja", "無印良品 乳液", "moisturiser"),
    ("ja", "アネッサ 日焼け止め", "spf"),
    ("ja", "オバジ 美容液", "serum"),
    ("zh", "薇诺娜 舒敏面霜", "moisturiser"),
    ("zh", "珀莱雅 精华液", "serum"),
    ("zh", "理肤泉 防晒霜", "spf"),
    ("zh", "玉泽 洁面乳", "cleanser"),
]

# (language, label terms, ingredient ids that must resolve)
INGREDIENTS = [
    ("ko", ["정제수", "레티놀", "스쿠알란"], {"retinol", "squalane"}),
    ("ko", ["나이아신아마이드", "히알루론산"], {"niacinamide", "hyaluronic_acid"}),
    ("ko", ["살리실산", "병풀"], {"salicylic_acid", "centella"}),
    ("ja", ["アスコルビン酸", "トコフェロール"], {"l_ascorbic_acid"}),
    ("ja", ["酸化亜鉛", "グリセリン"], {"zinc_oxide", "glycerin"}),
    ("ja", ["サリチル酸", "セラミド"], {"salicylic_acid", "ceramides"}),
    ("zh", ["积雪草", "神经酰胺", "甘油"], {"centella", "ceramides", "glycerin"}),
    ("zh", ["水杨酸", "烟酰胺"], {"salicylic_acid", "niacinamide"}),
    ("fr", ["Aqua", "Niacinamide", "Acide salicylique"], {"niacinamide", "salicylic_acid"}),
    ("fr", ["Glycérine", "Céramides", "Panthénol"], {"glycerin", "ceramides", "panthenol"}),
    # INCI unchanged on a non-English label: the common case, needing no aliases.
    ("ko", ["Water", "Niacinamide", "Adenosine"], {"niacinamide"}),
]

# Things that must NOT resolve. A false positive invents a conflict, which is
# worse than missing one, so the absence cases are worth asserting too.
NEGATIVES = [
    ("ko", ["정제수", "향료", "부틸렌글라이콜"], {"retinol", "niacinamide", "salicylic_acid"}),
    ("ja", ["水", "香料", "エタノール"], {"retinol", "l_ascorbic_acid"}),
]



# One alias inside another. The audit of the table found seven of these —
# "retinol" inside "retinyl palmitate" in Japanese, "ascorbic acid" inside
# two of its own derivatives in Chinese, "peptide" inside "copper peptide"
# in three languages. The matcher survives them by taking the longest term
# first and consuming the span, so the shorter one cannot also match. That
# is a property of the matcher, not of the table, and nothing else checks
# it: a change to the matching order would silently start reporting
# retinol in every moisturiser containing retinyl palmitate.
EXACT = [
    ("ja", "パルミチン酸レチノール", {"retinyl_palmitate"}),
    ("ja", "レチノール", {"retinol"}),
    ("zh", "抗坏血酸磷酸酯钠", {"sodium_ascorbyl_phosphate"}),
    ("zh", "四己基癸醇抗坏血酸酯", {"thd_ascorbate"}),
    ("zh", "抗坏血酸", {"l_ascorbic_acid"}),
    ("ko", "구리펩타이드", {"copper_peptides"}),
    ("ko", "펩타이드", {"peptides"}),
    ("zh", "銅胜肽", {"copper_peptides"}),
    # China's regulatory ingredient catalogue names hydroquinone 对苯二酚.
    # The table had only the common chemical name 氢醌, so a compliant
    # Chinese label would not have matched — on an ingredient that
    # escalates a pregnant user to a clinician.
    # Added 25 Oct with ascorbyl palmitate: the Chinese name contains the
    # Chinese name for ascorbic acid, the same trap as the other two
    # derivatives.
    ("zh", "抗坏血酸棕榈酸酯", {"ascorbyl_palmitate"}),
    ("ja", "パルミチン酸アスコルビル", {"ascorbyl_palmitate"}),
    ("zh", "对苯二酚", {"hydroquinone"}),
    ("zh", "對苯二酚", {"hydroquinone"}),
]

def _aliases() -> dict:
    import yaml

    path = Path(__file__).resolve().parent / "data" / "ingredient_aliases.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))["aliases"]


ALIASES = _aliases()


def main() -> int:
    rules = Rules()
    failures: list[str] = []

    for lang, name, want in FORMS:
        got = rules.infer_form(InputProduct(name=name))
        if got != want:
            failures.append(f"form  {lang}  {name!r} -> {got}, expected {want}")

    for lang, terms, want in INGREDIENTS:
        got = set(rules.resolve(InputProduct(name="x", listed_ingredients=terms)).actives)
        missing = want - got
        if missing:
            failures.append(f"match {lang}  {terms} missed {sorted(missing)}")

    for lang, term, want in EXACT:
        got = set(rules.resolve_text(term))
        if got != want:
            failures.append(
                f"exact {lang}  {term!r} -> {sorted(got)}, expected {sorted(want)}"
            )

    # No two ingredients may claim the same alias. A collision means the
    # matcher picks one arbitrarily and the other is unreachable.
    owner: dict[tuple[str, str], set[str]] = {}
    for ident, langs in (ALIASES or {}).items():
        for lang, terms in (langs or {}).items():
            for t in terms if isinstance(terms, list) else [terms]:
                owner.setdefault((lang, str(t).strip().lower()), set()).add(ident)
    for (lang, term), ids in sorted(owner.items()):
        if len(ids) > 1:
            failures.append(f"collision {lang}  {term!r} claimed by {sorted(ids)}")

    for lang, terms, forbidden in NEGATIVES:
        got = set(rules.resolve(InputProduct(name="x", listed_ingredients=terms)).actives)
        wrong = forbidden & got
        if wrong:
            failures.append(f"false positive {lang}  {terms} matched {sorted(wrong)}")

    checks = (len(FORMS) + len(INGREDIENTS) + len(NEGATIVES)
              + len(EXACT) + len(owner))
    if failures:
        print(f"FAILED {len(failures)} of {checks} checks\n")
        for f in failures:
            print(f"  {f}")
        return 1

    print(f"ok  {checks} checks passed")
    print(f"    {len(FORMS)} form inferences across ko/fr/ja/zh")
    print(f"    {len(INGREDIENTS)} ingredient resolutions")
    print(f"    {len(NEGATIVES)} false-positive guards")
    print(f"    {len(EXACT)} exact resolutions where one alias contains another")
    print(f"    {len(owner)} aliases checked for collisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

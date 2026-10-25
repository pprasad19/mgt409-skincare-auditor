"""Malformed and hostile input, without an API key.

    python test_robustness.py

The rubric names agent malfunction alongside attacks and overspending, and
until now nothing here had ever been handed anything but a well-formed shelf.
Everything below is a shape a real upload form will receive within a week of
existing: an empty list, one product, a product with no ingredient list, a
shelf far past the cap, absurd prices, duplicate names, text where a number
belongs.

The bar is that the engine returns something coherent, or raises something
intelligible. A crash is a failure; so is a confident wrong answer.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from limits import MAX_PRODUCTS, Trim, cap_images, cap_products, cap_text  # noqa: E402
from models import Observation, SkinReading, InputProduct  # noqa: E402
from render import render  # noqa: E402
from rules import Rules  # noqa: E402

failures: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  ok    {name}")
    except Exception as exc:  # noqa: BLE001 - this is the point of the test
        failures.append(f"{name}: {type(exc).__name__}: {exc}")
        print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")


def main() -> int:
    rules = Rules()
    print("robustness\n")

    def empty_shelf():
        r = rules.audit([])
        assert r.findings == [] and r.waste.products_owned == 0
        assert render(r, None)

    def single_product():
        r = rules.audit([InputProduct(name="Only Thing", listed_ingredients=["Aqua"])])
        assert r.findings == []
        assert render(r, None)

    def no_ingredients():
        r = rules.audit([InputProduct(name="Mystery Jar")])
        assert r.products[0].actives == []
        assert r.products[0].confidence == 0.0
        assert render(r, None)

    def nothing_recognised():
        r = rules.audit([
            InputProduct(name="A", listed_ingredients=["Aqua", "Parfum"]),
            InputProduct(name="B", listed_ingredients=["Alcohol Denat."]),
        ])
        assert all(p.actives == [] for p in r.products)
        assert render(r, None)

    def over_the_cap():
        trims: list[Trim] = []
        many = [
            InputProduct(name=f"Product {i}", listed_ingredients=["Retinol"])
            for i in range(MAX_PRODUCTS + 25)
        ]
        r = rules.audit(many, trims=trims)
        assert len(r.products) == MAX_PRODUCTS, len(r.products)
        assert trims and trims[0].dropped == 25
        assert render(r, None)

    def duplicate_names():
        same = [InputProduct(name="Same Name", listed_ingredients=["Retinol"])] * 3
        r = rules.audit(same)
        assert render(r, None)

    def absurd_prices():
        r = rules.audit([
            InputProduct(name="Free", listed_ingredients=["Retinol"], price_usd=0.0),
            InputProduct(name="Silly", listed_ingredients=["Glycolic Acid"], price_usd=1e9),
            InputProduct(name="Negative", listed_ingredients=["Niacinamide"], price_usd=-5.0),
        ])
        assert render(r, None)

    def hostile_strings():
        """Markup in a product name must not escape either context it lands in.

        Two different contexts, two different rules, and the first version of
        this test checked the wrong one. In the page body the fix is HTML
        escaping. Inside the <script> element it is not: an opening "<script>"
        there is inert, because an HTML parser in script data only looks for
        "</script". So the assertion is about closing sequences and tag count,
        not about the substring "<script>" appearing at all.
        """
        r = rules.audit([
            InputProduct(
                name="</script><script>alert(1)</script>",
                listed_ingredients=["Retinol", "<img src=x onerror=alert(1)>"],
            ),
            InputProduct(name="Benzoyl Peroxide Wash", listed_ingredients=["Benzoyl Peroxide"]),
        ])
        html = render(r, None)

        # Body: escaped, not live markup.
        assert "&lt;script&gt;" in html, "name not HTML-escaped in the body"
        assert "onerror=alert" not in html, "attribute payload survived unescaped"

        # Script element: exactly one real tag pair, so nothing broke out.
        assert html.count("<script>") == 1 or html.count("</script>") == 1, (
            f"script element terminated early: "
            f"{html.count('</script>')} closing tags"
        )
        assert "<\\/script>" in html, "closing sequence was not neutralised"

    def enormous_ingredient_list():
        r = rules.audit([
            InputProduct(name="Everything", listed_ingredients=["Aqua"] * 5000 + ["Retinol"])
        ])
        assert "retinol" in r.products[0].actives
        assert render(r, None)

    def unknown_condition():
        r = rules.audit(
            [InputProduct(name="Retinol Thing", listed_ingredients=["Retinol"])],
            ["not_a_real_condition"],
        )
        assert r.escalations == []

    def unknown_form():
        r = rules.audit([
            InputProduct(name="Thing", form="not_a_form", listed_ingredients=["Retinol"])
        ])
        assert r.products[0].form in rules.forms

    def caps_are_safe_on_junk():
        trims: list[Trim] = []
        assert cap_products([], trims) == []
        assert cap_images([Path("does/not/exist.png")], trims) == []
        assert cap_text(None, trims) is None
        assert len(cap_text("x" * 99_999, trims)) == 20_000

    def caveat_is_stripped():
        """The verification clause, in every phrasing it has arrived in.

        Three rounds of prompting failed to stop the auditor appending this,
        and each fix caught the previous phrasing and missed the next:
        "findings are unverified", then "have not been verified against a
        source", then "one finding is not yet verified". The rule is now the
        broad one — any trailing clause mentioning verification at all — and
        these cases exist so the next variant fails loudly here rather than
        quietly on the page.
        """
        from agents import strip_verification_caveat

        strip = [
            "Use the wash in the morning; one finding is not yet verified.",
            "Keep the stronger one. 30 findings have not been verified against a source.",
            "Separate them by time of day, though these rules are unverified.",
            "Drop the weaker retinol, but note the rules are unverified.",
        ]
        keep = [
            "Use them on alternate nights rather than together.",
            "Your acne wash is breaking down the retinol; separate them by time of day.",
            "Keep the stronger Retinol 1% in Squalane and drop the other.",
        ]
        for text in strip:
            out = strip_verification_caveat(text)
            assert "verif" not in out.lower(), f"not stripped: {out}"
            assert len(out) > 20, f"stripped too much: {out}"
        for text in keep:
            assert strip_verification_caveat(text) == text, f"wrongly altered: {text}"

    def sunscreen_is_recognised_from_its_label():
        """A shelf holding a sunscreen must never be told it has none.

        This fired for real. The gap check keyed on the product's *form*,
        which is guessed from its name, and "Beauty of Joseon Relief Sun"
        contains no word the keyword list knows. Meanwhile the ingredient
        table listed five UV filters, two of them trade names no label
        prints, and omitted Ethylhexyl Triazone — which appears in three
        of the products in our own lookup cache. So a real sunscreen, read
        from a real label, resolved to no filters, was filed as a serum,
        and the shelf was told at high severity that it had no sun
        protection.
        """
        labels = {
            "korean": ["Water", "Diethylamino Hydroxybenzoyl Hexyl Benzoate",
                       "Ethylhexyl Triazone", "Diethylhexyl Butamido Triazone"],
            "us drugstore": ["Avobenzone", "Octocrylene", "Homosalate", "Octisalate"],
            "european": ["Bis-Ethylhexyloxyphenol Methoxyphenyl Triazine",
                         "Methylene Bis-Benzotriazolyl Tetramethylbutylphenol"],
            "mineral zinc": ["Zinc Oxide"],
            "mineral titanium": ["Titanium Dioxide"],
            "mexoryl": ["Terephthalylidene Dicamphor Sulfonic Acid"],
        }
        for label, inci in labels.items():
            p = rules.resolve(InputProduct(name="Untitled Product", listed_ingredients=inci))
            assert p.actives, f"{label}: no filter resolved from {inci}"
            assert p.form == "spf", f"{label}: filed as {p.form}, not spf"

            r = rules.audit([
                InputProduct(name="Untitled Product", listed_ingredients=inci),
                InputProduct(name="Retinol Serum", listed_ingredients=["Retinol"]),
            ])
            wrong = [g for g in r.gaps if g.kind == "no_sun_protection"]
            assert not wrong, f"{label}: told it has no sunscreen while holding one"

    def no_diagnosis_reaches_the_page():
        """The observer must not name a condition, structurally.

        Observation.concern is a Literal over six observable concerns, so
        a diagnosis cannot be expressed there. `seen`, `where` and
        `lighting_note` are free text and are rendered verbatim, so "the
        classic butterfly pattern of rosacea" reached the reader as a
        diagnosis from an app whose entire escalation design exists to
        avoid making one. The prompt forbids it in three places; this is
        the code that does not depend on the prompt.
        """
        from agents import scrub_diagnosis

        hostile = SkinReading(
            observations=[Observation(
                concern="redness", where="cheeks", confidence="clear",
                seen="the classic butterfly pattern of rosacea, papules typical "
                     "of subtype 2 — consistent with seborrheic dermatitis too",
            )],
            lighting_note="even light, no sign of actinic keratosis",
            needs_a_clinician=False,
        )
        cleaned, removed = scrub_diagnosis(hostile)
        assert removed, "named conditions were not detected"
        # A model reaching for a diagnosis is a referral signal, not only a bug.
        assert cleaned.needs_a_clinician, "diagnosis found but not escalated"

        page = render(rules.audit([]), None, skin=cleaned)
        for word in ("rosacea", "papule", "dermatitis", "keratosis", "subtype"):
            assert word not in page.lower(), f"{word!r} reached the page"

        # And it must leave an honest observation alone, or the guard costs
        # more than it saves.
        fine = SkinReading(
            observations=[Observation(
                concern="dryness", where="forehead and cheeks", confidence="possible",
                seen="small flakes catching the light along the brow",
            )],
            lighting_note="bright and even",
            needs_a_clinician=False,
        )
        same, hits = scrub_diagnosis(fine)
        assert not hits, f"false positive on an innocent reading: {hits}"
        assert same.observations[0].seen == fine.observations[0].seen
        assert not same.needs_a_clinician, "innocent reading wrongly escalated"

    for name, fn in [
        ("verification caveat stripped", caveat_is_stripped),
        ("empty shelf", empty_shelf),
        ("single product", single_product),
        ("product with no ingredients", no_ingredients),
        ("nothing recognised", nothing_recognised),
        (f"more than {MAX_PRODUCTS} products", over_the_cap),
        ("duplicate product names", duplicate_names),
        ("zero, huge and negative prices", absurd_prices),
        ("html injection in names", hostile_strings),
        ("5000-line ingredient list", enormous_ingredient_list),
        ("unknown condition", unknown_condition),
        ("unknown product form", unknown_form),
        ("caps handle junk", caps_are_safe_on_junk),
        ("sunscreen recognised from its label", sunscreen_is_recognised_from_its_label),
        ("no diagnosis reaches the page", no_diagnosis_reaches_the_page),
    ]:
        check(name, fn)

    print()
    if failures:
        print(f"{len(failures)} failed")
        return 1
    print("all robustness checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

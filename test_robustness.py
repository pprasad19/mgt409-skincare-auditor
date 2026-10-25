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
from models import InputProduct  # noqa: E402
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

    for name, fn in [
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

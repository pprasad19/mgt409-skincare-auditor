"""The deterministic core.

No model is involved in anything below. Products come in, the table decides what
is true about them, and a routine comes out. The agents that sit on top of this
read labels and write explanations; they do not get a vote on the findings.

That split is the point of the project. It is also why this module is testable
without an API key.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from limits import Trim, cap_products
from models import (
    Suggestion,
    Unresolved,
    display_name,
    ApplicationSpec,
    AuditResult,
    Escalation,
    Finding,
    Gap,
    InputProduct,
    ResolvedProduct,
    Routine,
    RoutineStep,
    WasteSummary,
)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "skincare.db"

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Used only when the user did not say what a product is, and only for typed
# input — the Shelf Reader sets the form itself from packaging, in whatever
# language the packaging is in.
#
# Keywords cover English, French, Spanish, Portuguese, German, Italian, Korean,
# Japanese and Chinese. An English-only list quietly classified every non-English
# product as a serum, which then placed it wrongly in the routine. Order matters:
# the first match wins, so the more specific forms are listed first.
FORM_KEYWORDS = [
    ("spf", ["spf", "sunscreen", "sun cream", "uv ", "fps", "protector solar", "écran solaire",
             "protection solaire", "crème solaire", "fluide solaire", "sonnenschutz",
             "protezione solare", "선크림", "선스틱", "선쿠션", "자외선 차단", "무기자차",
             "유기자차", "日焼け止め", "サンスクリーン", "防曬", "防晒", "防晒霜"]),
    # Before `cleanser`, because "cleansing oil" and "cleansing balm" both
    # contain "cleansing" and first match wins. They were being filed as
    # ordinary cleansers, which put an oil cleanser in the morning routine
    # and let it stand in for a face wash. It is the first half of a double
    # cleanse: evening only, and the water-based cleanser still follows.
    ("oil_cleanser", ["cleansing oil", "cleanse oil", "oil cleanser", "oil to foam",
                      "oil-to-foam", "cleansing balm", "balm cleanser", "cleansing sherbet",
                      "makeup melting", "melting cleanser", "huile démaquillante",
                      "huile nettoyante", "baume démaquillant", "baume nettoyant",
                      "aceite limpiador", "bálsamo limpiador", "reinigungsöl",
                      "클렌징오일", "클렌징 오일", "클렌징밤", "클렌징 밤", "오일클렌저",
                      "クレンジングオイル", "クレンジングバーム", "オイルクレンジング",
                      "卸妆油", "卸妝油", "卸妆膏", "卸妝膏", "潔顏油", "洁颜油"]),
    ("cleanser", ["cleanser", "face wash", "cleansing", "wash", "nettoyant", "limpiador",
                  "limpeza", "reinigung", "detergente", "eau micellaire", "démaquillant",
                  "lait démaquillant", "gel moussant", "mousse nettoyante",
                  "클렌저", "클렌징", "폼클렌징", "세안", "클렌징폼",
                  "洗顔", "クレンジング", "洗顔料", "洁面", "潔面", "洗面奶", "卸妆"]),
    ("exfoliant", ["scrub", "peel", "exfoliat", "gommage", "exfoliante", "peeling",
                   "스크럽", "필링", "角質", "スクラブ", "去角质", "去角質"]),
    ("toner", ["toner", "tonic", "tonique", "lotion tonique", "tónico", "토너", "스킨",
               "스킨토너", "토닝", "화장수", "化粧水", "爽膚水", "爽肤水", "化妆水"]),
    ("essence", ["essence", "에센스", "精華水", "精华水"]),
    ("mask", ["mask", "masque", "mascarilla", "maske", "마스크", "팩", "시트마스크",
              "マスク", "パック", "面膜"]),
    ("eye", ["eye cream", "eye serum", "under eye", "contour des yeux", "soin yeux",
             "contorno de ojos", "augencreme", "아이크림", "눈가", "目元", "アイクリーム",
             "眼霜", "眼部精华"]),
    ("oil", ["face oil", " oil", "huile", "aceite", "öl", "olio", "오일", "オイル", "精油", "面油"]),
    ("occlusive", ["sleeping mask", "petrolatum", "vaseline", "balm", "baume", "bálsamo",
                   "슬리핑", "수면팩", "ワセリン", "睡眠面膜"]),
    ("serum", ["serum", "ampoule", "booster", "sérum", "suero", "soin concentré",
               "세럼", "앰플", "세람", "セラム", "アンプル", "美容液",
               "精华", "精華", "精华液", "安瓶"]),
    ("treatment", ["treatment", "spot", "retinol", "retinoid", "acid", "bha", "aha",
                   "traitement", "tratamiento", "behandlung", "트리트먼트", "레티놀",
                   "治療", "治疗"]),
    ("moisturiser", ["moisturis", "moisturiz", "cream", "lotion", "gel-cream", "emulsion",
                     "crème", "creme", "crema", "hidratante", "feuchtigkeits", "emulsión",
                     "fluide", "lait hydratant", "soin hydratant", "baume hydratant",
                     "크림", "로션", "수분", "에멀전", "에멀젼", "수분크림", "영양크림",
                     "クリーム", "乳液", "保湿", "保濕", "面霜", "乳霜"]),
]


def normalise(text: str) -> str:
    """Must stay identical to build_db.normalise — see the note there."""
    folded = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", folded).strip()


def term_pattern(term: str) -> str:
    r"""Build the search pattern for one term.

    \b is defined by a transition between word and non-word characters, which
    works for "retinol" sitting between spaces but is unreliable in scripts
    written without them: CJK text is all word characters, so \b never fires
    inside a run of it. Latin terms keep word boundaries to avoid matching
    inside a longer word; non-Latin terms fall back to a plain substring match,
    where that risk does not arise the same way.
    """
    if term.isascii():
        return rf"\b{re.escape(term)}\b"
    return re.escape(term)


# The steps a routine is incomplete without, and what to say when one is
# absent. Deliberately three short of the twelve forms in
# product_forms.yaml: these are the ones the AAD order names and the only
# rows in that file marked `verified`. Toner, essence, eye cream and the
# rest are the industry layering convention — real, near-universal, and
# not a need. Telling someone they are "missing" a toner would invent a
# purchase, which is the failure this whole project is built to avoid.
#
# Sunscreen is handled separately below, because what to say about it
# depends on whether anything on the shelf raises sun sensitivity.
# Worth having, not required. These produce a `recommended` gap: named,
# explained, and visibly a rung below the essentials — a routine without
# a serum is a routine, and a routine without a cleanser is not.
RECOMMENDED_STEPS: list[tuple[str, str, str, str]] = [
    (
        "serum",
        "low",
        "There is no serum in either routine.",
        "Cleanser, moisturiser and sunscreen keep skin well. A serum is where "
        "a routine does something — it is the step carrying the active "
        "ingredient, at a concentration the other steps are not formulated "
        "for. Without one this shelf maintains rather than treats.",
    ),
    (
        "oil_cleanser",
        "low",
        "Nothing here breaks down sunscreen or makeup.",
        "An oil or balm cleanser is the first of two evening steps: it lifts "
        "sunscreen and makeup, which are designed not to rinse off, and the "
        "water-based cleanser then takes it and the day's oil away. If you "
        "wear either, one wash is usually doing half the job.",
    ),
]

# Offered, never missing. A toner and an eye cream are reasonable things
# to own and reasonable things not to own; there is no published finding
# that a routine needs either. They appear as a short "if you want to go
# further" list rather than as a gap, because the difference between
# "you are missing this" and "this exists" is the difference between
# advice and a shopping list.
OPTIONAL_STEPS: list[tuple[str, str]] = [
    ("toner",
     "A hydrating layer straight after cleansing. Worth it if your skin feels "
     "tight after washing; skip it otherwise — a toner is not a step a routine "
     "is incomplete without, whatever the shelf at the shop implies."),
    ("eye",
     "The skin around the eye is thinner and a face cream is often too heavy "
     "for it. An eye cream is a gentler version of what you already use, not a "
     "different kind of treatment, and published routines disagree about "
     "whether it is needed at all."),
]

ESSENTIAL_STEPS: list[tuple[str, str, str, str]] = [
    (
        "cleanser",
        "medium",
        "There is nothing here to wash your face with.",
        "Cleansing is the first step in the published order, and the one every "
        "routine agrees on. Actives also work better on skin that has had the "
        "day taken off it — so without a cleanser, the products you do own are "
        "doing less than they could.",
    ),
    (
        "moisturiser",
        "medium",
        "There is no moisturiser on this shelf.",
        "Moisturiser is where a routine holds on to what the other steps did, "
        "and it is the usual answer to the irritation that actives cause. "
        "Skipping it tends to be why people conclude an active 'did not agree' "
        "with them.",
    ),
]

LANGUAGE_NAMES = {
    "intl:zh": "Chinese",
    "intl:ko": "Korean",
    "intl:ja": "Japanese",
    "intl:fr": "French",
}


class Rules:
    """Everything loaded from the compiled database."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        if not db_path.is_file():
            raise FileNotFoundError(f"{db_path} not found. Run: python build_db.py")
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row

        self.ingredients = {r["id"]: dict(r) for r in con.execute("SELECT * FROM ingredients")}
        # (term, ingredient_id, kind). The kind says where the term came
        # from — inci, name, alias, or intl:<lang> — which is what lets a
        # match report that it rests on a translation nobody has checked.
        self.terms = sorted(
            ((r["term"], r["ingredient_id"], r["kind"])
             for r in con.execute("SELECT * FROM ingredient_terms")),
            key=lambda t: -len(t[0]),
        )
        self.interactions = [dict(r) for r in con.execute("SELECT * FROM interactions")]
        self.contraindications = [dict(r) for r in con.execute("SELECT * FROM contraindications")]
        self.forms = {r["id"]: dict(r) for r in con.execute("SELECT * FROM product_forms")}
        self.concerns = {r["id"]: dict(r) for r in con.execute("SELECT * FROM concerns")}
        self.catalogue = {r["id"]: dict(r) for r in con.execute("SELECT * FROM catalogue")}
        self.catalogue_terms = sorted(
            ((r["term"], r["catalogue_id"]) for r in con.execute("SELECT * FROM catalogue_terms")),
            key=lambda t: -len(t[0]),
        )
        con.close()

        self.rules_total = len(self.interactions) + len(self.contraindications)
        self.rules_verified = sum(
            1 for r in self.interactions + self.contraindications if r["review"] == "verified"
        )

    # -- resolution --------------------------------------------------------

    def infer_form(
        self,
        product: InputProduct,
        catalogue_form: str | None = None,
        actives: list[str] | None = None,
    ) -> str:
        """What kind of product this is, best source first.

        The catalogue sits above the keyword guess because it is a statement
        about a specific product, while the keywords are a guess from a name.
        Leaving it out was not a near miss: "La Roche-Posay Anthelios UVMune
        400" contains no word resembling sunscreen, so it fell all the way
        through to the default and was treated as a serum. The shelf then got
        told it had no sunscreen on it while its sunscreen sat in the routine,
        ordered as a serum rather than last in the morning.
        """
        # "Cleansing oil" and "cleansing balm" in the name beat whatever the
        # reader called it. Sits above product.form for the same reason the
        # UV-filter check below does: the reader's category is "cleanser",
        # which cannot express the difference, and the difference decides
        # both the time of day and whether a face wash is still needed.
        # A tester's cleansing balm was read as a cleanser, placed in the
        # morning routine, and counted as satisfying the shelf's need for
        # one — three wrong answers from a single missing distinction.
        # These phrases are specific enough to be safe: a product named
        # "cleansing oil" is one.
        name = normalise(product.name or "")
        if any(k in name for k in dict(FORM_KEYWORDS)["oil_cleanser"]):
            return "oil_cleanser"
        if product.form and product.form in self.forms:
            return product.form
        # A product whose label lists UV filters is a sunscreen, whatever it
        # is called. This sits above the catalogue and the name keywords
        # because it is read off the bottle: "Beauty of Joseon Relief Sun"
        # contains no word the keyword list recognises, and its ingredient
        # list contains three UV filters. Getting this wrong told a shelf
        # holding a sunscreen that it had none.
        if any(self.ingredients[a]["class"] == "uv_filter" for a in (actives or [])):
            return "spf"
        if catalogue_form and catalogue_form in self.forms:
            return catalogue_form
        haystack = f"{product.brand or ''} {product.name}".lower()
        for form_id, keywords in FORM_KEYWORDS:
            if any(k in haystack for k in keywords):
                return form_id
        return "serum"

    def ingredients_in_rules(self) -> set[str]:
        """Ingredient ids that any rule can fire on.

        An ingredient no rule mentions cannot change an audit, so its absence
        from a reading is not worth warning anyone about.
        """
        out: set[str] = set()
        selectors = [r["a"] for r in self.interactions] + [r["b"] for r in self.interactions]
        selectors += [r["matches"] for r in self.contraindications]

        for selector in selectors:
            if selector.startswith("ing:"):
                out.add(selector.removeprefix("ing:"))
            elif selector.startswith("class:"):
                wanted = selector.removeprefix("class:")
                out |= {i for i, row in self.ingredients.items() if row["class"] == wanted}
        return out

    def resolve_text(self, text: str) -> list[str]:
        """Ingredient ids mentioned anywhere in a blob of text.

        The matching core, usable on raw input rather than a structured
        product. safety.detect_suppression re-reads the user's own words with
        this to catch ingredients a reader was talked out of recording — it
        works precisely because it does not understand anything and so cannot
        be told that an ingredient is not there.
        """
        label = normalise(text)
        consumed: list[tuple[int, int]] = []
        found: list[str] = []

        for term, ingredient_id, kind in self.terms:
            if ingredient_id in found:
                continue
            for match in re.finditer(term_pattern(term), label):
                span = match.span()
                if any(span[0] < end and start < span[1] for start, end in consumed):
                    continue
                consumed.append(span)
                found.append(ingredient_id)
                break
        return found

    def match_catalogue(self, product: InputProduct) -> dict | None:
        """Find a known product by name, longest phrase first.

        Only consulted when no ingredients could be read. A label always wins:
        what is printed on the bottle in front of someone beats what this file
        believes about a product with a similar name.
        """
        haystack = normalise(f"{product.brand or ''} {product.name}")
        if not haystack:
            return None

        for term, cat_id in self.catalogue_terms:
            if not term or term not in haystack:
                continue
            hit = self.catalogue[cat_id]
            # Refuse the match if the input names a different brand we know
            # about. "Glytone Hydrating Facial Cleanser" matching CeraVe's
            # product would attach CeraVe's ingredients and price to someone
            # else's bottle — a wrong answer that looks authoritative.
            stated = {
                normalise(row["brand"])
                for row in self.catalogue.values()
                if normalise(row["brand"]) in haystack
            }
            if stated and normalise(hit["brand"]) not in stated:
                continue
            return hit
        return None

    def _stated_in_checked_terms(self, ingredient_id: str, label: str) -> bool:
        """Does the label name this ingredient in a term a human has checked?

        Only asked about an ingredient that matched a machine translation,
        to decide whether that translation actually carried the match or
        merely happened to be the longer string.
        """
        return any(
            re.search(term_pattern(term), label)
            for term, other, kind in self.terms
            if other == ingredient_id and not kind.startswith("intl:")
        )

    def resolve(self, product: InputProduct) -> ResolvedProduct:
        """Match label terms to known ingredients, longest term first.

        Longest-first with span consumption stops 'ascorbic acid' from also
        matching inside 'sodium ascorbyl phosphate'-style entries, which would
        silently attribute a low-pH conflict to a product that does not have one.
        """
        label = normalise(" , ".join(product.listed_ingredients))
        consumed: list[tuple[int, int]] = []
        actives: list[str] = []

        found_via: dict[str, str] = {}
        for term, ingredient_id, kind in self.terms:
            if ingredient_id in actives:
                continue
            for match in re.finditer(term_pattern(term), label):
                span = match.span()
                if any(span[0] < end and start < span[1] for start, end in consumed):
                    continue
                consumed.append(span)
                actives.append(ingredient_id)
                found_via[ingredient_id] = kind
                break

        matched_text = {label[s:e].strip() for s, e in consumed}
        listed = {normalise(t) for t in product.listed_ingredients if t.strip()}
        unmatched = sorted(t for t in listed if t and not any(m and m in t for m in matched_text))

        # Nothing readable on the label — fall back to the catalogue, and
        # record that we did, so the page can tell the user to check the bottle.
        from_catalogue = None
        catalogue_form: str | None = None
        # Carried in when the price arrived from the web lookup; set below
        # when it comes from the catalogue. Either way it is not the user's.
        typical_price = product.price_is_typical
        if not actives:
            hit = self.match_catalogue(product)
            if hit:
                actives = [a for a in hit["actives"].split(",") if a]
                from_catalogue = f"{hit['brand']} {hit['name']}"
                catalogue_form = hit["form"]
                # The catalogue knows the brand the photograph did not show.
                # Renaming here means every later mention is unambiguous.
                # Use the catalogue's own name, not the reader's with a brand
                # bolted on. Prepending produced "CeraVe Glytone Hydrating
                # Facial Cleanser" when the reader had run two shelf items
                # together — a product that does not exist, stated confidently.
                updates = {"name": f"{hit['brand']} {hit['name']}"}
                # Only when the user said nothing. What someone actually paid
                # always wins over what a product usually costs.
                if product.price_usd is None and hit["typical_price_usd"]:
                    updates["price_usd"] = float(hit["typical_price_usd"])
                    typical_price = True
                product = product.model_copy(update=updates)

        classes = sorted({self.ingredients[a]["class"] for a in actives})

        # Confidence is about actives, not about recognising every INCI line.
        # A label is mostly water, solvents and emulsifiers the table has no
        # opinion on, so scoring by share-of-terms-matched would mark every
        # real product as low confidence and the warning would mean nothing.
        # What matters is whether we found anything to reason about at all.
        confidence = 1.0 if actives else 0.0

        return ResolvedProduct(
            product=product,
            form=self.infer_form(product, catalogue_form, actives),
            actives=actives,
            classes=classes,
            unmatched_terms=unmatched,
            confidence=confidence,
            matched_from_catalogue=from_catalogue,
            price_is_typical=typical_price,
            dwell_seconds=int(product.dwell_seconds or 0),
            dwell_source=product.dwell_source or "",
            # Actives found only through a machine-translated term. INCI is
            # international, so most non-English labels still resolve through
            # verified terms and this stays empty; when it does not, the page
            # says which product rested on an unchecked translation rather
            # than tainting every audit equally.
            # The matching loop takes the longest term first, so whether a
            # label carrying both "Niacinamide" and the Korean name matches
            # the checked term or the unchecked one is an accident of which
            # string is longer. Before flagging, look again: if any checked
            # term for that ingredient is also on the label, the translation
            # was not load-bearing and there is nothing to warn about.
            # Runs only over ingredients already flagged, which is normally
            # none.
            translated_only={
                self.ingredients[a]["name"]:
                    LANGUAGE_NAMES.get(found_via[a], found_via[a].removeprefix("intl:"))
                for a in sorted(actives)
                if found_via.get(a, "").startswith("intl:")
                and not self._stated_in_checked_terms(a, label)
            },
        )

    # -- selectors ---------------------------------------------------------

    def matches(self, selector: str, product: ResolvedProduct) -> list[str]:
        """Return the ingredient ids that make this product satisfy the selector."""
        if selector == "*":
            return list(product.actives)
        if selector.startswith("class:"):
            wanted = selector.removeprefix("class:")
            return [a for a in product.actives if self.ingredients[a]["class"] == wanted]
        if selector.startswith("ing:"):
            wanted = selector.removeprefix("ing:")
            return [a for a in product.actives if a == wanted]
        if selector == "prescription:true":
            return [a for a in product.actives if self.ingredients[a]["prescription"]]
        return []

    # -- findings ----------------------------------------------------------

    def _form_ok(self, rule: dict, product: ResolvedProduct) -> bool:
        """Some rules only make sense for certain product forms.

        Ceramides in a rinse-off cleanser do not rebuild a barrier, so the
        ceramide/retinoid synergy should not fire for one. The constraint
        applies to the `a` side, which is the side the guidance talks about.
        """
        allowed = rule.get("forms")
        return not allowed or product.form in allowed.split(",")

    def find(self, products: list[ResolvedProduct]) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[tuple[str, frozenset[str]]] = set()

        for rule in self.interactions:
            excepted = set((rule["except_ingredients"] or "").split(",")) - {""}

            # Single-product rules: ordering and timing, written with b == "*".
            if rule["b"] == "*":
                for product in products:
                    if not self._form_ok(rule, product):
                        continue
                    hits = [h for h in self.matches(rule["a"], product) if h not in excepted]
                    if hits:
                        findings.append(self._finding(rule, [product], hits))
                continue

            for i, left in enumerate(products):
                for right in products[i + 1:]:
                    for p1, p2 in ((left, right), (right, left)):
                        if not self._form_ok(rule, p1):
                            continue
                        a_hits = [h for h in self.matches(rule["a"], p1) if h not in excepted]
                        b_hits = [h for h in self.matches(rule["b"], p2) if h not in excepted]
                        if not (a_hits and b_hits):
                            continue
                        key = (rule["rule_id"], frozenset({p1.product.name, p2.product.name}))
                        if key in seen:
                            continue
                        seen.add(key)
                        findings.append(self._finding(rule, [p1, p2], a_hits + b_hits))
                        break

        findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.rule_id))
        return findings

    def _finding(self, rule: dict, products: list[ResolvedProduct], hits: list[str]) -> Finding:
        return Finding(
            rule_id=rule["rule_id"],
            type=rule["type"],
            severity=rule["severity"],
            products=[p.product.name for p in products],
            ingredients=sorted(set(hits)),
            mechanism=rule["mechanism"],
            guidance=rule["guidance"],
            resolution=rule["resolution"],
            verified=rule["review"] == "verified",
        )

    def escalate(self, products: list[ResolvedProduct], conditions: list[str]) -> list[Escalation]:
        """Contraindication gates. A declined answer routes to the cautious path."""
        out: list[Escalation] = []
        active_conditions = set(conditions)

        for rule in self.contraindications:
            if rule["condition"] not in active_conditions:
                continue
            hit_products = [p.product.name for p in products if self.matches(rule["matches"], p)]
            if hit_products:
                out.append(
                    Escalation(
                        rule_id=rule["rule_id"],
                        condition=rule["condition"],
                        severity=rule["severity"],
                        message=rule["message"],
                        products=hit_products,
                    )
                )
        return out

    # -- routine -----------------------------------------------------------

    def build_routine(self, products: list[ResolvedProduct], findings: list[Finding]) -> Routine:
        placement: dict[str, str] = {}
        because: dict[str, list[str]] = {p.product.name: [] for p in products}

        # Which timing rule moved each product, by id.
        #
        # This used to record the bare word "photosensitising". The result
        # page deliberately keeps timing findings out of the findings list,
        # on the stated grounds that "every step carries the rule id that
        # placed it" — and it did not. SKA-082 and SKA-083 fired at high
        # severity, moved products to the evening, and appeared nowhere on
        # the page at all, under a footer promising that every claim cites
        # the rule that produced it.
        timing_rules: dict[str, list[str]] = {}
        for finding in findings:
            if finding.type in ("timing", "ordering"):
                for name in finding.products:
                    timing_rules.setdefault(name, []).append(finding.rule_id)

        for product in products:
            name = product.product.name
            allowed = self.forms[product.form]["times"].split(",")
            times = {self.ingredients[a]["time"] for a in product.actives}
            photo = any(self.ingredients[a]["photosensitising"] for a in product.actives)

            if "am" in allowed and "pm" not in allowed:
                placement[name] = "am"
            elif "pm" in allowed and "am" not in allowed:
                placement[name] = "pm"
            elif photo:
                placement[name] = "pm"
                because[name].extend(
                    timing_rules.get(name) or ["photosensitising"]
                )
            elif "pm" in times:
                placement[name] = "pm"
                because[name].append("evening-only ingredient")
            elif "am" in times:
                placement[name] = "am"
            else:
                placement[name] = "both"

        # Conflicts that want the two products in different halves of the day.
        #
        # Findings arrive sorted by severity, so the most important separation is
        # decided first and then locked. Without locking, a later medium-severity
        # rule could undo a high-severity one and quietly reintroduce the worse
        # conflict. Where a shelf cannot satisfy every rule at once, say so
        # rather than emitting a routine that looks fine and is not.
        locked: dict[str, str] = {}
        tensions: list[str] = []

        for finding in findings:
            if finding.resolution != "separate_am_pm" or len(finding.products) != 2:
                continue
            first, second = finding.products
            first_slot, second_slot = locked.get(first), locked.get(second)

            if first_slot and second_slot:
                if first_slot == second_slot:
                    tensions.append(
                        f"{first} and {second} conflict ({finding.rule_id}), but higher-priority "
                        f"rules have already pinned both to the "
                        f"{'morning' if first_slot == 'am' else 'evening'}. No arrangement of "
                        f"this shelf satisfies every rule — dropping one of these two is the "
                        f"real fix, not reordering."
                    )
                continue

            if first_slot or second_slot:
                anchored, free = (first, second) if first_slot else (second, first)
                slot = locked[anchored]
                other = "pm" if slot == "am" else "am"
                placement[free] = other
                locked[free] = other
                because[free].append(finding.rule_id)

                score = self._pm_score(products, free)
                if (other == "pm" and score <= -2) or (other == "am" and score >= 2):
                    wanted = "morning" if other == "pm" else "evening"
                    tensions.append(
                        f"{free} would work best in the {wanted}, but {anchored} has that "
                        f"slot and {finding.rule_id} keeps them apart. If you want {free} "
                        f"back where it belongs, {anchored} is the product to reconsider."
                    )
                continue

            first_score, second_score = self._pm_score(products, first), self._pm_score(products, second)
            first_pm = first_score >= second_score
            placement[first] = "pm" if first_pm else "am"
            placement[second] = "am" if first_pm else "pm"
            locked[first], locked[second] = placement[first], placement[second]
            because[first].append(finding.rule_id)
            because[second].append(finding.rule_id)

        alternating = {
            name
            for f in findings
            if f.resolution == "alternate_nights"
            for name in f.products
        }
        for f in findings:
            if f.resolution == "alternate_nights":
                for name in f.products:
                    because[name].append(f.rule_id)

        routine = Routine()
        for slot in ("am", "pm"):
            steps = [
                p for p in products
                if placement[p.product.name] in (slot, "both")
                and slot in self.forms[p.form]["times"].split(",")
            ]
            steps.sort(key=lambda p: self.forms[p.form]["rank"])
            target = routine.am if slot == "am" else routine.pm
            for order, product in enumerate(steps, start=1):
                name = product.product.name
                target.append(
                    RoutineStep(
                        product_name=name,
                        form=self.forms[product.form]["name"],
                        form_id=product.form,
                        order=order,
                        frequency="alternate nights" if (slot == "pm" and name in alternating) else "daily",
                        because=sorted(set(because[name])),
                        # The product's own looked-up time, or nothing —
                        # never a figure for "this kind of mask". If the
                        # form is worn and no time was found, the step
                        # says so rather than counting down a guess.
                        dwell_seconds=product.dwell_seconds,
                        dwell_unknown=bool(
                            self.forms[product.form].get("dwell_required")
                            and not product.dwell_seconds
                        ),
                        dwell_source=product.dwell_source,
                        dwell_note=self.forms[product.form].get("dwell_note") or "",
                        application=ApplicationSpec(),
                    )
                )

        if alternating:
            routine.notes.append(
                "Some evening products alternate rather than stack. Using them on "
                "different nights keeps the benefit and removes the irritation."
            )
        routine.notes.extend(dict.fromkeys(tensions))
        return routine

    def _pm_score(self, products: list[ResolvedProduct], name: str) -> int:
        """How strongly a product wants the evening. Negative means morning.

        A magnitude of 2 or more is a real preference rooted in the ingredient
        table — photosensitivity, or an ingredient whose time is fixed. Zero
        means the product is happy either way.
        """
        for p in products:
            if p.product.name != name:
                continue
            score = 0
            if any(self.ingredients[a]["photosensitising"] for a in p.actives):
                score += 2
            if any(self.ingredients[a]["time"] == "pm" for a in p.actives):
                score += 2
            if any(self.ingredients[a]["time"] == "am" for a in p.actives):
                score -= 2
            return score
        return 0

    # -- money -------------------------------------------------------------

    def waste(self, products: list[ResolvedProduct], findings: list[Finding]) -> WasteSummary:
        by_name = {p.product.name: p for p in products}
        price = lambda n: (by_name[n].product.price_usd or 0.0) if n in by_name else 0.0

        redundant: set[str] = set()
        for f in findings:
            if f.type == "redundancy" and len(f.products) == 2:
                # Count the cheaper one as the avoidable spend.
                redundant.add(min(f.products, key=price))

        conflicted = {
            n for f in findings if f.type == "conflict" and f.severity in ("critical", "high")
            for n in f.products
        }

        return WasteSummary(
            shelf_value_usd=round(sum(p.product.price_usd or 0.0 for p in products), 2),
            products_owned=len(products),
            products_unused=sum(1 for p in products if p.product.unused),
            unused_value_usd=round(sum(p.product.price_usd or 0.0 for p in products if p.product.unused), 2),
            redundant_value_usd=round(sum(price(n) for n in redundant), 2),
            conflicted_value_usd=round(sum(price(n) for n in conflicted), 2),
        )

    # -- top level ---------------------------------------------------------

    def suggest(self, products: list[ResolvedProduct], concerns: list[str]) -> list[Suggestion]:
        """What to consider adding, for concerns the shelf does not address.

        A lookup, not a judgement. The concern came from the user, the
        actives that address it come from concerns.yaml, and what is already
        owned comes from the resolved products. Nothing here is the model's
        opinion about anyone's face.

        Where a concern is already covered, that is the answer — telling
        someone they need nothing is more useful than finding them something
        to buy.
        """
        owned = {a for p in products for a in p.actives}
        out: list[Suggestion] = []

        for concern_id in concerns:
            row = self.concerns.get(concern_id)
            if not row:
                continue
            addressed = [a for a in row["addressed_by"].split(",") if a]
            covered = [a for a in addressed if a in owned]
            missing = [a for a in addressed if a not in owned]

            products_for = []
            if not covered:
                for entry in self.catalogue.values():
                    actives = set(entry["actives"].split(","))
                    if actives & set(missing):
                        products_for.append(f"{entry['brand']} {entry['name']}")
                    if len(products_for) >= 3:
                        break

            out.append(
                Suggestion(
                    concern=concern_id,
                    concern_label=row["label"],
                    why=row["note"] or "",
                    missing_actives=[self.ingredients[a]["name"] for a in missing],
                    already_covered_by=[
                        p.product.name for p in products
                        if set(p.actives) & set(covered)
                    ],
                    products=products_for,
                )
            )
        return out

    def _when_phrase(self, form_id: str) -> str:
        """When this step belongs, in words, from the form's own `times`.

        Derived rather than written out beside each message, so a gap can
        never tell the user a different time of day from the one the
        routine builder would place the product in — both read this
        column.
        """
        times = (self.forms[form_id]["times"] or "").split(",")
        if "am" in times and "pm" in times:
            return "It belongs in both routines, morning and evening."
        if "am" in times:
            return "It belongs in the morning routine."
        return "It belongs in the evening routine."

    def gaps(self, products: list[ResolvedProduct]) -> list[Gap]:
        """What this shelf needs and does not have.

        Pairwise rules can only compare things the user owns, so they are blind
        to an absence. The sun-protection case is the one that matters: several
        of the strongest actives increase UV sensitivity, and using them without
        sunscreen does more harm than not using them at all.
        """
        out: list[Gap] = []

        held = {p.form for p in products}

        # A shelf can be missing a whole step, not just sun protection. A
        # tester gave us five products with no cleanser and no moisturiser
        # and was told only that there was no sunscreen — the routine was
        # built from what they owned and never mentioned what was absent,
        # which is the question someone buying skincare actually has.
        #
        # Only these three. They are the steps the AAD order names, and the
        # three product_forms rows marked `verified` rather than
        # `reasoned`; every other form here is the layering convention,
        # where "you are missing a toner" would be an invented need. Not
        # flagging the optional ones is as much the point as flagging
        # these, and the page says so rather than leaving the reader to
        # wonder whether we simply did not check.
        for form_id, severity, headline, why in ESSENTIAL_STEPS:
            if form_id in held:
                continue
            # Telling someone a step is missing without saying when to use
            # it leaves them to guess the one thing the routine would have
            # told them. Taken from the form's own `times`, so it cannot
            # drift from where the routine would actually place it.
            why = f"{why} {self._when_phrase(form_id)}"
            # An oil cleanser is the first half of a double cleanse, not a
            # face wash, so a shelf holding one still needs a cleanser —
            # but saying "there is nothing here to wash your face with" to
            # someone looking at their cleansing balm reads as a bug.
            if form_id == "cleanser" and "oil_cleanser" in held:
                headline = "A cleansing balm or oil is only half of a cleanse."
                why = (
                    "An oil cleanser dissolves sunscreen and makeup, and is then "
                    "rinsed away by a water-based cleanser — that second step is "
                    "the one missing here. On its own it tends to leave a film, "
                    "which is usually what people mean when they say a balm broke "
                    "them out. " + self._when_phrase("cleanser")
                )
            out.append(
                Gap(
                    kind=f"no_{form_id}",
                    severity=severity,
                    label=self.forms[form_id]["name"],
                    headline=headline,
                    message=why,
                )
            )

        # The mirror of a missing step: several products doing one job.
        # The redundancy rules in interactions.yaml are ingredient pairs —
        # two retinoids, two AHAs — so four cleansers produced nothing at
        # all. The routine only ever places one product per step, so the
        # rest are sitting unused, which is a money question rather than
        # a safety one.
        #
        # Three, not two. Two cleansers is an ordinary shelf — a wash and
        # a balm, or a gentle one for mornings — and calling that a
        # problem would be the invented-need failure again, pointing the
        # other way.
        by_form: dict[str, list[str]] = {}
        for p in products:
            by_form.setdefault(p.form, []).append(p.product.name)
        for form_id, names in sorted(by_form.items()):
            if len(names) < 3 or form_id not in self.forms:
                continue
            label = self.forms[form_id]["name"]
            out.append(
                Gap(
                    kind=f"several_{form_id}",
                    severity="low",
                    label=label,
                    headline=f"You have {len(names)} products doing the job of one.",
                    message=(
                        f"All {len(names)} of these are filed as {label.lower()}, and a "
                        f"routine uses one at a time — so the others are not in the "
                        f"plan below. That is fine if you are rotating them or using "
                        f"up old stock. If you are not, it is the clearest thing on "
                        f"this shelf to stop re-buying. {self._when_phrase(form_id)}"
                    ),
                    because=sorted(names),
                )
            )

        # A rung below. Same shape, different kind: `recommended` so the
        # page can show it as a suggestion rather than something wrong.
        for form_id, severity, headline, why in RECOMMENDED_STEPS:
            if form_id in held:
                continue
            out.append(
                Gap(
                    kind=f"consider_{form_id}",
                    severity=severity,
                    label=self.forms[form_id]["name"],
                    headline=headline,
                    message=f"{why} {self._when_phrase(form_id)}",
                    suggestion=True,
                )
            )

        # And the ones that are purely a matter of taste. One entry, so a
        # list of optional extras cannot read as a list of failures.
        absent = [(f, why) for f, why in OPTIONAL_STEPS if f not in held]
        if absent:
            out.append(
                Gap(
                    kind="optional_steps",
                    severity="low",
                    label="Optional",
                    headline="Two steps you could add, and do not have to.",
                    # Plain prose: gap.message is escaped on the way out,
                    # so markdown here would reach the reader as asterisks.
                    message=" ".join(
                        f"{self.forms[f]['name']}: {why} "
                        f"{self._when_phrase(f)}" for f, why in absent
                    ),
                    because=[self.forms[f]["name"] for f, _ in absent],
                    suggestion=True,
                )
            )

        photo = [
            p.product.name
            for p in products
            if any(self.ingredients[a]["photosensitising"] for a in p.actives)
        ]
        # Belt and braces with infer_form: a product is sun protection if it
        # is filed as one or if it actually contains a filter.
        has_spf = any(
            p.form == "spf"
            or any(self.ingredients[a]["class"] == "uv_filter" for a in p.actives)
            for p in products
        )
        if photo and not has_spf:
            out.append(
                Gap(
                    kind="no_sun_protection",
                    severity="high",
                    label="Sun protection",
                    headline="There is no sunscreen on this shelf, and you need one.",
                    message=(
                        f"{len(photo)} of your products increase sun sensitivity. Without "
                        "daily SPF they work against the thing most of them were bought "
                        "to fix. It belongs in the morning routine, as the last step "
                        "before makeup — and on overcast days too."
                    ),
                    because=photo,
                )
            )
        elif photo:
            out.append(
                Gap(
                    kind="spf_is_load_bearing",
                    severity="medium",
                    label="Sun protection",
                    headline="Wear your sunscreen every day, not just sunny ones.",
                    message=(
                        f"{len(photo)} of your products increase sun sensitivity. Sunscreen "
                        "is the step that makes the rest of them safe to use, so skipping "
                        "it costs you more than it would with a gentler routine. Every "
                        "morning, as the last step — not only on sunny ones."
                    ),
                    because=photo,
                )
            )
        elif not has_spf:
            # No sunscreen and nothing that raises sun sensitivity. The
            # branch above does not fire, so this shelf used to be told
            # nothing about sunscreen at all — the most-recommended product
            # in skincare, unmentioned because the user owned nothing
            # dangerous. Lower severity than the photosensitising case,
            # because here it is a general recommendation rather than
            # something the rest of the shelf depends on.
            out.append(
                Gap(
                    kind="no_spf",
                    severity="medium",
                    label="Sun protection",
                    headline="There is no sunscreen on this shelf.",
                    message=(
                        "Nothing you own raises sun sensitivity, so this is not urgent "
                        "the way it would be with a retinoid or an acid. It is still the "
                        "step with the most evidence behind it, and the one that decides "
                        "whether the rest of a routine compounds or just maintains. It "
                        "belongs in the morning routine, as the last step."
                    ),
                )
            )

        return out

    def audit(
        self,
        raw: list[InputProduct],
        conditions: list[str] | None = None,
        trims: list[Trim] | None = None,
        concerns: list[str] | None = None,
    ) -> AuditResult:
        # The findings pass is O(n^2) in products, so the cap is a cost control
        # as much as a sanity one. Truncate and say so; never drop silently.
        raw = cap_products(raw, trims if trims is not None else [])
        products = [self.resolve(p) for p in raw]
        findings = self.find(products)
        # Products we read a name for and nothing else. The audit cannot say
        # anything about them, and must say so rather than leave them out.
        unresolved = [
            Unresolved(
                name=p.product.name,
                reason="no ingredients were readable for this product",
            )
            for p in products
            if not p.actives and not p.matched_from_catalogue
        ]

        return AuditResult(
            products=products,
            unresolved=unresolved,
            findings=findings,
            escalations=self.escalate(products, conditions or []),
            routine=self.build_routine(products, findings),
            waste=self.waste(products, findings),
            gaps=self.gaps(products),
            suggestions=self.suggest(products, concerns or []),
            rules_verified=self.rules_verified,
            rules_total=self.rules_total,
        )

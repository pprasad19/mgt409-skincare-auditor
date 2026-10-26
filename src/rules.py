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
    # "mist" is here rather than in its own form. A facial mist is a
    # watery hydrating step applied at the toner's position, and giving
    # it a form of its own would mean inventing a rank, a dose and a
    # technique with nothing to base them on. Filed as a toner it gets
    # the right position and the right dose.
    #
    # Added after a tester expected her toner and her mist to be called
    # duplicates and was told nothing was duplicated. They were not
    # being compared: with no keyword and no known actives the mist
    # fell through to the default and was filed as a serum, which is a
    # different step, so the engine was right about the shelf it
    # thought it had and wrong about the shelf she owned.
    #
    # English only. The translated terms for this were in the 232 that
    # were withdrawn for being machine-generated, and one unverified
    # string is how that whole surface started.
    ("toner", ["toner", "tonic", "tonique", "lotion tonique", "tónico", "토너", "스킨",
               "스킨토너", "토닝", "화장수", "化粧水", "爽膚水", "爽肤水", "化妆水",
               "mist", "face mist", "facial mist"]),
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


def _a(noun: str) -> str:
    """"a cleanser", but "an eye cream" and "an exfoliant"."""
    return f"{'an' if noun[:1] in 'aeiou' else 'a'} {noun}"


def normalise(text: str) -> str:
    """Must stay identical to build_db.normalise — see the note there."""
    folded = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", folded).strip()


# Units a container is labelled in, folded to one spelling each. Only the
# three that appear on skincare packaging; a size this cannot parse falls
# back to string comparison rather than guessing.
_UNITS = {
    "ml": "ml", "mls": "ml", "millilitre": "ml", "millilitres": "ml",
    "milliliter": "ml", "milliliters": "ml", "cc": "ml",
    "oz": "oz", "ozs": "oz", "ounce": "oz", "ounces": "oz",
    "g": "g", "gr": "g", "gram": "g", "grams": "g", "gm": "g",
}
_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(fl\.?\s*oz|[a-z]+)", re.I)


def size_measures(text: str) -> set[tuple[float, str]]:
    """Every (amount, unit) a size string states.

    A container is routinely labelled in two units at once — "4 fl oz /
    120 mL" is one bottle, not two — so a size is a *set* of measures
    rather than a string.
    """
    out: set[tuple[float, str]] = set()
    for amount, unit in _SIZE_RE.findall(text or ""):
        u = re.sub(r"[^a-z]", "", unit.lower())
        u = "oz" if u in ("floz", "fl") else u
        if u in _UNITS:
            try:
                out.add((round(float(amount), 3), _UNITS[u]))
            except ValueError:
                continue
    return out


def same_size(a: str, b: str) -> bool:
    """Do two size strings describe the same container?

    Compared by measure, not by text. A lookup came back with "4 fl oz /
    120 mL" for a bottle the user had called "4 fl oz"; string equality
    called that a mismatch, and a correct $18 price was dropped from the
    money section as though it belonged to a different bottle. One
    shared measure is agreement — the dual-unit label means both refer
    to the same thing.

    Falls back to normalised text when neither side parses, so an
    unparseable size is still compared rather than silently treated as
    a mismatch.
    """
    ma, mb = size_measures(a), size_measures(b)
    if ma and mb:
        return bool(ma & mb)
    return normalise(a or "") == normalise(b or "")


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

# Any mention of the eye at all, in the languages the form keywords
# cover. Deliberately looser than FORM_KEYWORDS["eye"], which lists whole
# phrases like "eye cream": this is only used to decide whether to
# believe the reader when it says a product is an eye product, and the
# first version — reusing those phrases — threw away "Youth Dose Eye
# Treatment" and "Eye Repair Cream", which are plainly eye products.
# Refusing a real one is worse than the bug this guards against.
EYE_WORDS = ("eye", "yeux", "ojos", "augen", "occhi", "olhos",
             "아이", "눈", "目", "眼")

ESSENTIAL_STEPS: list[tuple[str, str, str, str]] = [
    (
        "oil_cleanser",
        "medium",
        "Nothing here breaks down sunscreen or makeup.",
        # The reason this is a requirement rather than a suggestion —
        # the app recommends daily sunscreen, and sunscreen is built not
        # to rinse off — belongs in the comment, not on the page. The
        # first version opened with "Promoted from a suggestion to a
        # requirement on 26 Oct 2026, after a tester pointed out...",
        # which is a changelog entry. A tester read it and said she did
        # not need a history lesson. She was right: the user wants the
        # advice, and how the advice came to exist is our business.
        "This app recommends sunscreen every morning, and sunscreen is built "
        "not to come off with water alone. An oil or balm cleanser lifts it, "
        "along with makeup; the water-based cleanser then takes that and the "
        "day's oil away. One wash on its own tends to leave a film.",
    ),
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
        # An eye cream says so on the box. The reader called a Kiehl's
        # retinol serum an eye cream, which moved it to the eye step and
        # — because the shelf then appeared to have one — withheld the
        # suggestion that the user get an eye cream at all. One misread
        # word, two wrong answers, and the second invisible.
        #
        # Narrower than it looks: this only refuses `eye`, only when the
        # name carries no eye word in any of the languages the keyword
        # table covers, and then falls through to the ordinary inference
        # rather than asserting a form of its own.
        if product.form == "eye" and not any(w in name for w in EYE_WORDS):
            product = product.model_copy(update={"form": None})

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
        # A label listing a prescription-only active is a treatment,
        # whatever the tub is called. "Tretinoin 0.05% cream" matches no
        # keyword in the form table and ends in "cream", so it was filed
        # as a moisturiser: placed at the moisturiser's position in the
        # routine, and — once two of a form began to count — named as a
        # duplicate of the user's actual face cream. The ingredient table
        # already knew tretinoin is prescription-only; the form inference
        # was not asking it.
        #
        # Same shape and same justification as the UV-filter rule above:
        # read off the bottle, so it outranks a guess from the name. The
        # two actives this covers, tretinoin and hydroquinone, are both
        # leave-on treatments.
        if any(self.ingredients[a]["prescription"] for a in (actives or [])):
            return "treatment"
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
                if hit["typical_price_usd"]:
                    found = float(hit["typical_price_usd"])
                    # Recorded whether or not she has given us a figure,
                    # so the Found online column still has something to
                    # show beside a price she typed herself.
                    updates["price_found_usd"] = (
                        product.price_found_usd or found)
                    if product.price_usd is None:
                        updates["price_usd"] = found
                        # On the product too, not only on the
                        # resolution. The same fact lived in two places:
                        # the page read the copy on ResolvedProduct and
                        # said "retail, looked up", while the money
                        # rules read the copy on InputProduct, which
                        # this branch left False — so a catalogue price
                        # was summed into "on the shelf" as though the
                        # user had stated it. Six products, no price
                        # typed, and a $96 total with every row labelled
                        # as a guess.
                        updates["price_is_typical"] = True
                        typical_price = True
                product = product.model_copy(update=updates)

        elif product.price_found_usd is None:
            # A readable label answers the question this branch exists
            # for, so the catalogue is not consulted for actives. It was
            # not consulted for a PRICE either, which is a separate
            # question it can often answer — so a product whose
            # ingredients we could read came back with nothing in Found
            # online and no tick beside it: "when I add an item, the use
            # retail price checkbox does not immediately appear".
            #
            # Price only. No renaming, no actives, no catalogue
            # attribution: the label won those on merit and a name match
            # is weaker evidence than a printed ingredient list.
            hit = self.match_catalogue(product)
            if hit and hit["typical_price_usd"]:
                product = product.model_copy(update={
                    "price_found_usd": float(hit["typical_price_usd"])})

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
            price_off_page=product.price_off_page or "",
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

    @staticmethod
    def in_use(products: list[ResolvedProduct]) -> list[ResolvedProduct]:
        """The shelf she actually uses, which is not the shelf she owns.

        Ticking "I never use this" has to reach every piece of reasoning
        about what to DO — the routine, the clashes, the gaps, the
        suggestions — and must not reach what she OWNS: the product
        list, the unused tile, the correction table.

        This exists because that line was redrawn four times, once per
        caller, each after a tester found the one that had been missed.
        The routine builder learned it first, then the finder, then
        gaps(), and then suggest() was still answering "already covered"
        with a product she had told us she never uses. Each fix was
        correct and none of them was the fix.
        """
        return [p for p in products if not p.product.unused]

    def find(self, products: list[ResolvedProduct]) -> list[Finding]:
        """Every interaction the table fires on, for the shelf in use.

        Products the user has said she never uses are excluded. Two
        tester reports turned out to be this one omission: "when I say
        that I dont use something, it is still being reflected in the
        what clashes what section", and a duplicate-function figure
        that did not move when she marked one of the pair unused.

        Both are the same mistake. A clash is between two things you
        put on your face; a product sitting in a drawer cannot clash
        with anything, and calling it a duplicate as well as unused is
        two findings for one fact — the unused tile already says you
        own it and do not use it.
        """
        products = self.in_use(products)
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
                        # A prescribed product is not something you
                        # stop re-buying to save money, so it is not
                        # half of a duplicate. Conflicts still fire on
                        # it — a clash with a prescription is exactly
                        # what its clinician should hear about — but
                        # "you are paying twice for one effect" is not
                        # a thing this tool gets to say about a
                        # prescription.
                        if rule["type"] == "redundancy" and (
                                p1.product.prescribed or p2.product.prescribed):
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
                    source=rule.get("source") or "",
        )

    def escalate(self, products: list[ResolvedProduct], conditions: list[str]) -> list[Escalation]:
        """Contraindication gates. A declined answer routes to the cautious path."""
        out: list[Escalation] = []
        active_conditions = set(conditions)

        # Named by the user rather than inferred from the label. Her
        # statement is better evidence than the ingredient table: she is
        # reading a box a pharmacist handed her, and the table only knows
        # the handful of actives that are prescription-only everywhere.
        # Declaring a prescription used to do nothing at all unless the
        # app had independently guessed the same product.
        named = {p.product.name for p in products if p.product.prescribed}
        for name in sorted(named):
            out.append(
                Escalation(
                    rule_id="SKC-010",
                    condition="prescription_product",
                    severity="critical",
                    message=("You told us this was prescribed for you. Any "
                             "change to how it is used belongs with the "
                             "clinician who prescribed it, not with this tool."),
                    products=[name],
                )
            )

        for rule in self.contraindications:
            if rule["condition"] not in active_conditions:
                continue

            if rule["condition"] == "prescription_product":
                # Asked, never inferred. A tester: "do not assume what
                # has been prescribed to me, let me specifically tell
                # you." The ingredient table knows which actives are
                # prescription-only in general; it does not know which
                # box on this shelf came from a pharmacist. Telling
                # somebody "this product was prescribed for you" about
                # a product they never named is this tool putting words
                # in their mouth, and it was wrong on her shelf: she
                # has an over-the-counter retinol the table flagged and
                # a compounded cream it could not see.
                #
                # Named products are already escalated above. If the
                # box is ticked and nothing is named, the honest move
                # is to ask rather than to guess.
                if not named:
                    out.append(
                        Escalation(
                            rule_id=rule["rule_id"],
                            condition=rule["condition"],
                            severity="high",
                            message=(
                                "You told us something here was prescribed, "
                                "but not which one, and this tool will not "
                                "guess. Tick Prescribed beside it in the "
                                "table at the bottom of this page and that "
                                "product is left to the clinician who "
                                "prescribed it."),
                            products=[],
                        )
                    )
                continue

            hit_products = [p.product.name for p in products
                            if self.matches(rule["matches"], p)]
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

    def build_routine(self, products: list[ResolvedProduct], findings: list[Finding],
        wanted: set[str] | None = None) -> Routine:
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
        held_forms = {p.form for p in products}
        # Essentials are never optional; the rest only if asked for.
        include_missing = {f for f, *_ in ESSENTIAL_STEPS} | {"spf"}
        include_missing |= set(wanted or ())
        include_missing = {f for f in include_missing if f in self.forms}

        for slot in ("am", "pm"):
            steps = [
                p for p in products
                if placement[p.product.name] in (slot, "both")
                and slot in self.forms[p.form]["times"].split(",")
                # "if I say that I do not use something, why is it
                # included in any of the steps". I had kept them in and
                # marked them, reasoning that "you own this and it
                # would help" is useful. The tester's answer is
                # simpler: she told the app she does not use it, and a
                # routine is a list of what to do. It stays on the
                # shelf, in the money section, and out of the steps.
                and not p.product.unused
            ]
            steps.sort(key=lambda p: self.forms[p.form]["rank"])

            # Collapse the forms you pick one of. Two toners are a choice
            # between two products, not two things to put on your face,
            # and the routine had no way to say so — it listed them as
            # consecutive steps and a tester reasonably read that as an
            # instruction to use both.
            #
            # The first of each such form keeps the step and names the
            # others; the others leave the routine. Which one is "first"
            # is arbitrary, so the step presents them as equals rather
            # than recommending one.
            alternatives: dict[str, list[str]] = {}
            collapsed = []
            for product in steps:
                form = product.form
                # A prescription keeps its own step and is never offered
                # as the one to drop, nor collapsed into another
                # product's "or use this instead".
                if product.product.prescribed:
                    collapsed.append(product)
                    continue
                if not self.forms[form].get("one_at_a_time"):
                    collapsed.append(product)
                    continue
                if form in alternatives:
                    alternatives[form].append(product.product.name)
                    continue
                alternatives[form] = []
                collapsed.append(product)
            steps = collapsed
            target = routine.am if slot == "am" else routine.pm
            # Steps for what is not on the shelf. A missing essential is
            # always shown — the page already says you need one, and
            # leaving it out of the routine was the page disagreeing
            # with itself. An optional form appears only if asked for.
            ghosts = []
            for form_id in sorted(include_missing,
                                  key=lambda f: self.forms[f]["rank"]):
                if form_id in held_forms:
                    continue
                if slot not in self.forms[form_id]["times"].split(","):
                    continue
                ghosts.append(form_id)

            # The list holds both resolved products and bare form ids, so
            # the rank lookup has to cope with either — inserting a
            # placeholder made the next insertion trip over it.
            def _rank(entry) -> int:
                form_id = entry if isinstance(entry, str) else entry.form
                return self.forms[form_id]["rank"]

            ordered: list = list(steps)
            for form_id in ghosts:
                rank = self.forms[form_id]["rank"]
                at = next((n for n, entry in enumerate(ordered)
                           if _rank(entry) > rank), len(ordered))
                ordered.insert(at, form_id)

            for order, product in enumerate(ordered, start=1):
                if isinstance(product, str):
                    form = self.forms[product]
                    target.append(
                        RoutineStep(
                            product_name=_a(form["name"].lower()),
                            form=form["name"],
                            form_id=product,
                            order=order,
                            placeholder=True,
                            typical_seconds=int(form.get("typical_seconds") or 0),
                            typical_how=form.get("typical_how") or "",

                            because=[],
                        )
                    )
                    continue
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
                        unused=bool(product.product.unused),
                        prescribed=bool(product.product.prescribed),
                        instead_of=alternatives.get(product.form) or [],
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

    def waste(self, products: list[ResolvedProduct], findings: list[Finding],
              routine: Routine | None = None) -> WasteSummary:
        """What the shelf is wasting, in the prices the user confirmed.

        `routine` is optional only so older callers keep working; pass
        it. The routine knows about a kind of duplication the findings
        do not: the interaction rules pair INGREDIENTS, so two retinols
        are a duplicate and two toners are invisible to them. The
        routine places one product per step and marks the rest
        `instead_of` — "one of these, not both" — and the money section
        was ignoring that and reporting "nothing duplicated" on the same
        page. A tester with a toner and a mist read both and asked which
        one to believe.
        """
        by_name = {p.product.name: p for p in products}
        # A price for the wrong size is reference, not arithmetic. It is
        # shown beside its product with the size named; adding it to
        # "on the shelf" would put a 10 oz figure behind a 4 oz bottle
        # and quietly make every total wrong.
        def _countable(p) -> float:
            """A price counts only if the user confirmed it.

            Every money complaint from three testers was a figure this
            app had guessed — a full-size price against a sample, an
            Amazon listing it cannot read, an original where the page
            showed a sale. The inputs are structurally weak and will
            stay weak, so the totals do not rest on them.

            Two things count. A figure she typed, and a figure we found
            that she read and ticked. Everything else is shown beside
            its product, labelled with where it came from, and left out
            of the arithmetic.

            Written as three questions in order rather than a chain of
            exclusions, because the chain is what let a catalogue price
            through: each clause was individually right and the one
            that mattered was reading the wrong copy of a flag.
            """
            prod = p.product
            if getattr(prod, "price_size_mismatch", ""):
                # For a different bottle. No tick makes it this one's.
                return 0.0
            if not p.price_is_typical and prod.price_usd:
                # Hers. p.price_is_typical is the flag the page renders,
                # so the label and the total cannot disagree about which
                # figures these are.
                return float(prod.price_usd)
            if getattr(prod, "price_confirmed", False):
                # Ours, read and accepted. A tester asked for this
                # directly: retyping a number already on the screen is a
                # bad way to spend somebody's attention.
                return float(getattr(prod, "price_found_usd", None)
                             or prod.price_usd or 0.0)
            return 0.0

        price = lambda n: _countable(by_name[n]) if n in by_name else 0.0

        redundant: set[str] = set()

        # The routine's own verdict first. Each `instead_of` is a step
        # saying it and these others do one job; the cheapest of that
        # group is the avoidable spend, on the same reasoning the
        # ingredient rules use.
        for step in list(getattr(routine, "am", []) or []) + list(
                getattr(routine, "pm", []) or []):
            if not step.instead_of:
                continue
            group = [step.product_name, *step.instead_of]
            priced = [n for n in group if price(n) > 0]
            if len(priced) > 1:
                redundant.add(min(priced, key=price))

        for f in findings:
            if f.type == "redundancy" and len(f.products) == 2:
                # The cheaper of the two is the avoidable spend — but
                # only among the ones we can actually price. Since
                # totals count confirmed prices only, an unpriced
                # product scores 0 here, so min() picked it every time
                # and the figure stayed at zero no matter what the user
                # typed. A tester entered what she had paid and watched
                # the duplicate total not move.
                priced = [n for n in f.products if price(n) > 0]
                if priced:
                    redundant.add(min(priced, key=price))

        conflicted = {
            n for f in findings if f.type == "conflict" and f.severity in ("critical", "high")
            for n in f.products
        }

        return WasteSummary(
            shelf_value_usd=round(sum(_countable(p) for p in products), 2),
            products_owned=len(products),
            products_unused=sum(1 for p in products if p.product.unused),
            unused_value_usd=round(sum(_countable(p) for p in products if p.product.unused), 2),
            redundant_value_usd=round(sum(price(n) for n in redundant), 2),
            redundant_counted={n: round(price(n), 2) for n in sorted(redundant)},
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

        "Covered" means covered by something she uses. A tester read
        "Already covered — ..." naming a product she had just told us
        she never uses, which is the section answering with the one
        fact she had corrected.
        """
        # Filtered once, at the top, so the set of actives and the names
        # printed beside "Already covered" cannot come from different
        # shelves. They did: `owned` was corrected and the name list a
        # few lines below still walked everything.
        products = self.in_use(products)
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

    def gaps(self, products: list[ResolvedProduct],
             wanted: set[str] | None = None) -> list[Gap]:
        """What this shelf needs and does not have.

        Pairwise rules can only compare things the user owns, so they are blind
        to an absence. The sun-protection case is the one that matters: several
        of the strongest actives increase UV sensitivity, and using them without
        sunscreen does more harm than not using them at all.
        """
        out: list[Gap] = []

        # What she actually uses, not what she owns. A tester marked her
        # only cleanser as one she never uses and the section still had
        # nothing to suggest: "the what you might add section is not
        # updated when I say I never use the item". She is right — a
        # cleanser in a drawer leaves the same hole in a routine as no
        # cleanser at all, and this section exists to name holes.
        #
        products = self.in_use(products)

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
        # Two, not three.
        #
        # The threshold was three, on the reasoning that two cleansers is
        # an ordinary shelf — a wash and a balm, or a gentle one for
        # mornings. That reasoning has since been overtaken twice. An oil
        # cleanser is its own form now, so the balm-plus-wash case is not
        # two of anything. And the routine already places one product per
        # step and marks the rest "one of these, not both", while the
        # money section counts the cheaper as duplicate spend — both at
        # two.
        #
        # So three surfaces called two products interchangeable and this
        # one stayed silent until there were three. A tester saw the
        # mismatch immediately: "why does the what to do section not also
        # reflect that the toner and mist are interchangeable if it lists
        # that the moisturizers are interchangeable". The hedge that made
        # three feel safer belongs in the wording, where it now is, not in
        # a threshold that makes the page disagree with itself.
        by_form: dict[str, list[str]] = {}
        for p in products:
            # Same reason as the money figure: "stop re-buying one of
            # these" is not advice this tool gives about a prescription.
            if p.product.prescribed:
                continue
            by_form.setdefault(p.form, []).append(p.product.name)
        for form_id, names in sorted(by_form.items()):
            if len(names) < 2 or form_id not in self.forms:
                continue
            label = self.forms[form_id]["name"]
            headline = (f"Your {len(names)} {label.lower()}s do the same job."
                        if len(names) == 2
                        else f"You have {len(names)} products doing the job of one.")
            out.append(
                Gap(
                    kind=f"several_{form_id}",
                    severity="low",
                    label=label,
                    headline=headline,
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
        # A form the user has asked for is no longer something to offer
        # them; it is in the routine as a step they intend to buy.
        absent = [(f, why) for f, why in OPTIONAL_STEPS
                  if f not in held and f not in (wanted or ())]
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
        wanted: set[str] | None = None,
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
            routine=(routine := self.build_routine(products, findings, wanted)),
            waste=self.waste(products, findings, routine),
            gaps=self.gaps(products, wanted),
            suggestions=self.suggest(products, concerns or []),
            rules_verified=self.rules_verified,
            rules_total=self.rules_total,
        )

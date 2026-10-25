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
    ("cleanser", ["cleanser", "face wash", "cleansing", "wash", "nettoyant", "limpiador",
                  "limpeza", "reinigung", "detergente", "eau micellaire", "démaquillant",
                  "lait démaquillant", "gel moussant", "mousse nettoyante",
                  "클렌저", "클렌징", "폼클렌징", "세안", "클렌징폼", "클렌징오일",
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


class Rules:
    """Everything loaded from the compiled database."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        if not db_path.is_file():
            raise FileNotFoundError(f"{db_path} not found. Run: python build_db.py")
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row

        self.ingredients = {r["id"]: dict(r) for r in con.execute("SELECT * FROM ingredients")}
        self.terms = sorted(
            ((r["term"], r["ingredient_id"]) for r in con.execute("SELECT * FROM ingredient_terms")),
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

    def infer_form(self, product: InputProduct, catalogue_form: str | None = None) -> str:
        """What kind of product this is, best source first.

        The catalogue sits above the keyword guess because it is a statement
        about a specific product, while the keywords are a guess from a name.
        Leaving it out was not a near miss: "La Roche-Posay Anthelios UVMune
        400" contains no word resembling sunscreen, so it fell all the way
        through to the default and was treated as a serum. The shelf then got
        told it had no sunscreen on it while its sunscreen sat in the routine,
        ordered as a serum rather than last in the morning.
        """
        if product.form and product.form in self.forms:
            return product.form
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

        for term, ingredient_id in self.terms:
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

    def resolve(self, product: InputProduct) -> ResolvedProduct:
        """Match label terms to known ingredients, longest term first.

        Longest-first with span consumption stops 'ascorbic acid' from also
        matching inside 'sodium ascorbyl phosphate'-style entries, which would
        silently attribute a low-pH conflict to a product that does not have one.
        """
        label = normalise(" , ".join(product.listed_ingredients))
        consumed: list[tuple[int, int]] = []
        actives: list[str] = []

        for term, ingredient_id in self.terms:
            if ingredient_id in actives:
                continue
            for match in re.finditer(term_pattern(term), label):
                span = match.span()
                if any(span[0] < end and start < span[1] for start, end in consumed):
                    continue
                consumed.append(span)
                actives.append(ingredient_id)
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
            form=self.infer_form(product, catalogue_form),
            actives=actives,
            classes=classes,
            unmatched_terms=unmatched,
            confidence=confidence,
            matched_from_catalogue=from_catalogue,
            price_is_typical=typical_price,
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
                because[name].append("photosensitising")
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
                        order=order,
                        frequency="alternate nights" if (slot == "pm" and name in alternating) else "daily",
                        because=sorted(set(because[name])),
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

    def gaps(self, products: list[ResolvedProduct]) -> list[Gap]:
        """What this shelf needs and does not have.

        Pairwise rules can only compare things the user owns, so they are blind
        to an absence. The sun-protection case is the one that matters: several
        of the strongest actives increase UV sensitivity, and using them without
        sunscreen does more harm than not using them at all.
        """
        out: list[Gap] = []

        photo = [
            p.product.name
            for p in products
            if any(self.ingredients[a]["photosensitising"] for a in p.actives)
        ]
        has_spf = any(p.form == "spf" for p in products)
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
                        "to fix."
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
                        "it costs you more than it would with a gentler routine."
                    ),
                    because=photo,
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

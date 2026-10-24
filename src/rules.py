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

from models import (
    ApplicationSpec,
    AuditResult,
    Escalation,
    Finding,
    InputProduct,
    ResolvedProduct,
    Routine,
    RoutineStep,
    WasteSummary,
)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "skincare.db"

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Used only when the user did not say what a product is.
FORM_KEYWORDS = [
    ("spf", ["spf", "sunscreen", "sun cream", "uv "]),
    ("cleanser", ["cleanser", "face wash", "cleansing", "wash"]),
    ("exfoliant", ["scrub", "peel", "exfoliat"]),
    ("toner", ["toner", "tonic"]),
    ("essence", ["essence"]),
    ("mask", ["mask"]),
    ("eye", ["eye cream", "eye serum", "under eye"]),
    ("oil", ["face oil", " oil"]),
    ("occlusive", ["sleeping mask", "petrolatum", "vaseline", "balm"]),
    ("serum", ["serum", "ampoule", "booster"]),
    ("treatment", ["treatment", "spot", "retinol", "retinoid", "acid", "bha", "aha"]),
    ("moisturiser", ["moisturis", "moisturiz", "cream", "lotion", "gel-cream", "emulsion"]),
]


def normalise(text: str) -> str:
    """Must stay identical to build_db.normalise — see the note there."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


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
        con.close()

        self.rules_total = len(self.interactions) + len(self.contraindications)
        self.rules_verified = sum(
            1 for r in self.interactions + self.contraindications if r["review"] == "verified"
        )

    # -- resolution --------------------------------------------------------

    def infer_form(self, product: InputProduct) -> str:
        if product.form and product.form in self.forms:
            return product.form
        haystack = f"{product.brand or ''} {product.name}".lower()
        for form_id, keywords in FORM_KEYWORDS:
            if any(k in haystack for k in keywords):
                return form_id
        return "serum"

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
            for match in re.finditer(rf"\b{re.escape(term)}\b", label):
                span = match.span()
                if any(span[0] < end and start < span[1] for start, end in consumed):
                    continue
                consumed.append(span)
                actives.append(ingredient_id)
                break

        matched_text = {label[s:e].strip() for s, e in consumed}
        listed = {normalise(t) for t in product.listed_ingredients if t.strip()}
        unmatched = sorted(t for t in listed if t and not any(m and m in t for m in matched_text))

        classes = sorted({self.ingredients[a]["class"] for a in actives})

        # Confidence is about actives, not about recognising every INCI line.
        # A label is mostly water, solvents and emulsifiers the table has no
        # opinion on, so scoring by share-of-terms-matched would mark every
        # real product as low confidence and the warning would mean nothing.
        # What matters is whether we found anything to reason about at all.
        confidence = 1.0 if actives else 0.0

        return ResolvedProduct(
            product=product,
            form=self.infer_form(product),
            actives=actives,
            classes=classes,
            unmatched_terms=unmatched,
            confidence=confidence,
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

    def audit(self, raw: list[InputProduct], conditions: list[str] | None = None) -> AuditResult:
        products = [self.resolve(p) for p in raw]
        findings = self.find(products)
        return AuditResult(
            products=products,
            findings=findings,
            escalations=self.escalate(products, conditions or []),
            routine=self.build_routine(products, findings),
            waste=self.waste(products, findings),
            rules_verified=self.rules_verified,
            rules_total=self.rules_total,
        )

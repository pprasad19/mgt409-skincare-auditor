"""Build data/skincare.db from the YAML source files.

The YAML is the source of truth and lives in git, so the rules the auditor
applies are reviewable in a diff. The database is a derived artifact and is
gitignored — rebuild it with:

    python build_db.py

Every selector in interactions.yaml is checked against ingredients.yaml before
anything is written. A typo in a rule would otherwise mean the rule silently
never fires, which is the worst possible failure for a table whose whole purpose
is to be trustworthy.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
import sys
from pathlib import Path

import yaml


def normalise(text: str) -> str:
    """Fold punctuation to spaces, in any script.

    Applied to search terms here and to label text at match time. Both sides
    must go through the same function: otherwise an INCI name like
    "Copper Tripeptide-1" is stored with a hyphen, the label is normalised to a
    space, and the ingredient silently never matches.

    The character class is Unicode-aware on purpose. An earlier [^a-z0-9 ]
    version deleted every non-ASCII character, which meant a Korean or Japanese
    label reduced to punctuation before anything could match it — the system
    did not fail on non-English input, it silently found nothing.
    """
    folded = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", folded).strip()

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DB_PATH = DATA / "skincare.db"

SCHEMA = """
DROP TABLE IF EXISTS ingredients;
DROP TABLE IF EXISTS ingredient_terms;
DROP TABLE IF EXISTS interactions;
DROP TABLE IF EXISTS contraindications;
DROP TABLE IF EXISTS product_forms;

CREATE TABLE ingredients (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    class            TEXT NOT NULL,
    ph_min           REAL,
    ph_max           REAL,
    photosensitising INTEGER NOT NULL,
    time             TEXT NOT NULL,
    pregnancy        TEXT NOT NULL,
    prescription     INTEGER NOT NULL,
    potency          INTEGER NOT NULL,
    note             TEXT,
    source           TEXT,
    review           TEXT NOT NULL
);

-- One row per searchable term, so label parsing can match INCI names,
-- common names and colloquial aliases through a single index.
CREATE TABLE ingredient_terms (
    term          TEXT NOT NULL,
    ingredient_id TEXT NOT NULL REFERENCES ingredients(id),
    kind          TEXT NOT NULL,
    PRIMARY KEY (term, ingredient_id)
);
CREATE INDEX idx_terms ON ingredient_terms(term);

CREATE TABLE interactions (
    rule_id            TEXT PRIMARY KEY,
    a                  TEXT NOT NULL,
    b                  TEXT NOT NULL,
    type               TEXT NOT NULL,
    severity           TEXT NOT NULL,
    mechanism          TEXT NOT NULL,
    guidance           TEXT NOT NULL,
    resolution         TEXT NOT NULL,
    except_ingredients TEXT,
    forms              TEXT,
    source             TEXT,
    review             TEXT NOT NULL
);

CREATE TABLE contraindications (
    rule_id   TEXT PRIMARY KEY,
    condition TEXT NOT NULL,
    matches   TEXT NOT NULL,
    severity  TEXT NOT NULL,
    message   TEXT NOT NULL,
    action    TEXT NOT NULL,
    source    TEXT,
    review    TEXT NOT NULL
);

CREATE TABLE concerns (
    id               TEXT PRIMARY KEY,
    label            TEXT NOT NULL,
    observable       INTEGER NOT NULL,
    observation_hint TEXT,
    addressed_by     TEXT NOT NULL,
    note             TEXT
);

CREATE TABLE catalogue (
    id      INTEGER PRIMARY KEY,
    brand   TEXT NOT NULL,
    name    TEXT NOT NULL,
    form    TEXT,
    actives TEXT NOT NULL,
    typical_price_usd REAL,
    review  TEXT NOT NULL
);

-- One row per phrase that should match a catalogue product, so lookup is a
-- single indexed query rather than a scan with fuzzy matching.
CREATE TABLE catalogue_terms (
    term         TEXT NOT NULL,
    catalogue_id INTEGER NOT NULL REFERENCES catalogue(id),
    PRIMARY KEY (term, catalogue_id)
);
CREATE INDEX idx_cat_terms ON catalogue_terms(term);

CREATE TABLE product_forms (
    id     TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    rank   INTEGER NOT NULL,
    times  TEXT NOT NULL,
    note   TEXT,
    -- How long the product stays on the face after it is applied, for the
    -- forms where that is most of the step. A mask is applied in half a
    -- minute and worn for fifteen, and nothing in the schema could say so.
    dwell_seconds INTEGER NOT NULL DEFAULT 0,
    dwell_note    TEXT,
    -- These numbers decide the order of every routine the app
    -- produces, so they carry provenance like the rules table. The YAML
    -- always had it; the table did not load it, which made the claim
    -- true of the file and not of anything that could check it.
    source TEXT,
    review TEXT NOT NULL
);
"""

VALID_TYPES = {"conflict", "caution", "synergy", "myth", "redundancy", "ordering", "timing"}
VALID_SEVERITY = {"critical", "high", "medium", "low"}
VALID_PREGNANCY = {"ok", "caution", "avoid"}

# Three states, not two.
#
#   verified  a human checked this against a published source, and the
#             source is named in the row
#   reasoned  a human reviewed it, found no published source for this
#             specific claim, and kept it on recorded mechanism
#   pending   nobody has looked
#
# `reasoned` exists because most of the interaction rules are claims about
# two ingredients together, and almost nothing in the literature tests
# pairs. Marking those `verified` would be false; leaving them `pending`
# implies nobody examined them. Only `verified` sets the flag the result
# page uses to present a claim as settled.
VALID_REVIEW = {"verified", "reasoned", "pending"}


def load(name: str) -> dict:
    path = DATA / name
    if not path.is_file():
        sys.exit(f"Missing {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def check_selector(selector: str, ids: set[str], classes: set[str], where: str, errors: list[str]) -> None:
    """A selector is '*', 'class:<name>', 'ing:<id>' or 'prescription:true'."""
    if selector == "*" or selector.startswith("prescription:"):
        return
    if selector.startswith("class:"):
        if selector.removeprefix("class:") not in classes:
            errors.append(f"{where}: unknown class in {selector!r}")
    elif selector.startswith("ing:"):
        if selector.removeprefix("ing:") not in ids:
            errors.append(f"{where}: unknown ingredient in {selector!r}")
    else:
        errors.append(f"{where}: malformed selector {selector!r}")


def main() -> None:
    ingredients = load("ingredients.yaml")["ingredients"]
    intl = (load("ingredient_aliases.yaml") or {}).get("aliases") or {}
    rules_doc = load("interactions.yaml")
    interactions = rules_doc["interactions"]
    contraindications = rules_doc.get("contraindications", [])
    forms = load("product_forms.yaml")["forms"]
    catalogue = (load("products.yaml") or {}).get("products") or []
    concerns = (load("concerns.yaml") or {}).get("concerns") or []

    ids = {row["id"] for row in ingredients}
    classes = {row["class"] for row in ingredients}
    errors: list[str] = []

    for ingredient_id in intl:
        if ingredient_id not in ids:
            errors.append(f"ingredient_aliases.yaml: unknown ingredient {ingredient_id!r}")

    if len(ids) != len(ingredients):
        errors.append("duplicate ingredient id")

    for row in ingredients:
        if row["pregnancy"] not in VALID_PREGNANCY:
            errors.append(f"{row['id']}: bad pregnancy value {row['pregnancy']!r}")
        if row.get("review") not in VALID_REVIEW:
            errors.append(f"{row['id']}: bad review value {row.get('review')!r}")
        if row.get("review") in ("verified", "reasoned") and not row.get("source"):
            errors.append(f"{row['id']}: {row['review']} with no source recorded")
        if not 1 <= row["potency"] <= 5:
            errors.append(f"{row['id']}: potency out of range")

    seen_rules: set[str] = set()
    for rule in interactions:
        rid = rule["rule_id"]
        where = f"interaction {rid}"
        if rid in seen_rules:
            errors.append(f"{where}: duplicate rule_id")
        seen_rules.add(rid)
        if rule["type"] not in VALID_TYPES:
            errors.append(f"{where}: bad type {rule['type']!r}")
        if rule["severity"] not in VALID_SEVERITY:
            errors.append(f"{where}: bad severity {rule['severity']!r}")
        check_selector(rule["a"], ids, classes, where, errors)
        check_selector(rule["b"], ids, classes, where, errors)
        for exc in rule.get("except_ingredients") or []:
            if exc not in ids:
                errors.append(f"{where}: unknown ingredient in except_ingredients: {exc!r}")

    for rule in contraindications:
        where = f"contraindication {rule['rule_id']}"
        if rule["rule_id"] in seen_rules:
            errors.append(f"{where}: duplicate rule_id")
        seen_rules.add(rule["rule_id"])
        check_selector(rule["matches"], ids, classes, where, errors)

    if errors:
        print("Validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)

    for row in ingredients:
        ph = row.get("ph_range") or [None, None]
        con.execute(
            "INSERT INTO ingredients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                row["id"], row["name"], row["class"], ph[0], ph[1],
                int(row["photosensitising"]), row["time"], row["pregnancy"],
                int(row["prescription"]), row["potency"],
                row.get("note"), row.get("source"), row["review"],
            ),
        )
        # One row per term, and the kind decides how far it is trusted — a
        # term found only through an `intl:*` kind makes the result page warn
        # that no speaker has checked it. So a term that is both an INCI name
        # and an entry in a translation list has to be recorded as the INCI
        # name, not the translation.
        #
        # This was a set of (term, kind) pairs with INSERT OR IGNORE, which
        # kept whichever pair the set happened to yield first. Set iteration
        # order over strings is randomised per process, so the kind of every
        # duplicated term varied between builds. One run filed "avobenzone"
        # — a word that is identical in both lists — as French, and an
        # English sunscreen label was then warned about as an unchecked
        # translation. Precedence, applied in order, makes it deterministic.
        kinds: dict[str, str] = {}
        for term, kind in (
            [(normalise(t), "inci") for t in row.get("inci") or []]
            + [(normalise(row["name"]), "name")]
            + [(normalise(t), "alias") for t in row.get("aliases") or []]
            + [(normalise(t), f"intl:{lang}")
               for lang, words in (intl.get(row["id"]) or {}).items()
               for t in words]
        ):
            kinds.setdefault(term, kind)
        for term, kind in sorted(kinds.items()):
            con.execute(
                "INSERT OR IGNORE INTO ingredient_terms VALUES (?,?,?)",
                (term, row["id"], kind),
            )

    for rule in interactions:
        con.execute(
            "INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rule["rule_id"], rule["a"], rule["b"], rule["type"], rule["severity"],
                " ".join(rule["mechanism"].split()), rule["guidance"], rule["resolution"],
                ",".join(rule.get("except_ingredients") or []) or None,
                ",".join(rule.get("forms") or []) or None,
                rule.get("source"), rule["review"],
            ),
        )

    for rule in contraindications:
        con.execute(
            "INSERT INTO contraindications VALUES (?,?,?,?,?,?,?,?)",
            (
                rule["rule_id"], rule["condition"], rule["matches"], rule["severity"],
                " ".join(rule["message"].split()), rule["action"],
                rule.get("source"), rule["review"],
            ),
        )

    for row in concerns:
        bad = [a for a in row["addressed_by"] if a not in ids]
        if bad:
            errors.append(f"concerns.yaml: {row['id']}: unknown ingredients {bad}")
            continue
        con.execute(
            "INSERT INTO concerns VALUES (?,?,?,?,?,?)",
            (row["id"], row["label"], int(row.get("observable", False)),
             row.get("observation_hint"), ",".join(row["addressed_by"]),
             row.get("note")),
        )

    for n, row in enumerate(catalogue):
        bad = [a for a in row["actives"] if a not in ids]
        if bad:
            errors.append(f"products.yaml: {row['brand']} {row['name']}: unknown {bad}")
            continue
        con.execute(
            "INSERT INTO catalogue VALUES (?,?,?,?,?,?,?)",
            (n, row["brand"], row["name"], row.get("form"),
             ",".join(row["actives"]), row.get("typical_price_usd"),
             row.get("review", "pending")),
        )
        phrases = {f"{row['brand']} {row['name']}", row["name"]}
        phrases |= {a for a in row.get("aliases", [])}
        phrases |= {f"{row['brand']} {a}" for a in row.get("aliases", [])}
        for phrase in phrases:
            con.execute(
                "INSERT OR IGNORE INTO catalogue_terms VALUES (?,?)",
                (normalise(phrase), n),
            )

    for form in forms:
        con.execute(
            "INSERT INTO product_forms VALUES (?,?,?,?,?,?,?,?,?)",
            (form["id"], form["name"], form["rank"], ",".join(form["times"]),
             form.get("note"), int(form.get("dwell_seconds") or 0),
             form.get("dwell_note"),
             form.get("source"), form.get("review", "pending")),
        )

    con.commit()

    counts = {
        "ingredients": len(ingredients),
        "search terms": con.execute("SELECT COUNT(*) FROM ingredient_terms").fetchone()[0],
        "interactions": len(interactions),
        "contraindications": len(contraindications),
        "product forms": len(forms),
        "concerns": len(concerns),
        "catalogue products": len(catalogue),
        "catalogue phrases": con.execute("SELECT COUNT(*) FROM catalogue_terms").fetchone()[0],
    }
    rows = list(ingredients) + list(interactions) + list(contraindications)
    states = Counter(r["review"] for r in rows)

    con.close()

    print(f"Built {DB_PATH.relative_to(ROOT)}")
    for k, v in counts.items():
        print(f"  {v:>4}  {k}")

    # Per-language coverage, printed rather than asserted. A language that
    # looks supported but covers half the actives will silently under-report
    # findings on products in that language, and nothing else in the pipeline
    # would reveal it.
    languages = sorted({lang for entry in intl.values() for lang in entry})
    if languages:
        total = len(ingredients)
        print("\n  alias coverage by language")
        for lang in languages:
            have = sum(1 for row in ingredients if lang in (intl.get(row["id"]) or {}))
            gaps = [row["id"] for row in ingredients if lang not in (intl.get(row["id"]) or {})]
            bar = "#" * round(have / total * 20)
            print(f"    {lang}  {have:>2}/{total}  {bar:<20}")
            if gaps and len(gaps) <= 8:
                print(f"         missing: {', '.join(gaps)}")

    # Printed every build, because the moment this stops being visible is
    # the moment a drafted row starts being treated as a checked one.
    print("\n  provenance")
    print(f"    {states['verified']:>4}  verified   checked against a published source")
    print(f"    {states['reasoned']:>4}  reasoned   reviewed, no source for this specific")
    print(f"    {'':>4}             claim, kept on a recorded mechanism")
    if states["pending"]:
        print(f"    {states['pending']:>4}  pending    nobody has looked yet")
    print("\n  Only verified rows are presented to the user as settled.")
    print("  Translations in ingredient_aliases.yaml remain unchecked.")


if __name__ == "__main__":
    main()

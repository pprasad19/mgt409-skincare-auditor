"""Internal consistency of the rules table.

Different question from "is this claim true". These are the faults that
make a table wrong against itself: a rule no pair of ingredients can
satisfy, two rules giving opposite advice on the same pair, an ingredient
no rule can reach, a resolution that contradicts the severity.

build_db already checks that every selector names something real. It does
not check that anything can actually satisfy it.
"""
import itertools
import sys
from collections import defaultdict

sys.path.insert(0, "src")

from rules import Rules

r = Rules()
ING = r.ingredients
print(f"  {len(ING)} ingredients, {len(r.interactions)} rules, "
      f"{len(r.contraindications)} gates\n")


def members(selector: str) -> set[str]:
    if selector == "*":
        return set(ING)
    if selector.startswith("class:"):
        want = selector.removeprefix("class:")
        return {i for i, row in ING.items() if row["class"] == want}
    if selector.startswith("ing:"):
        want = selector.removeprefix("ing:")
        return {want} if want in ING else set()
    if selector.startswith("prescription:"):
        want = selector.removeprefix("prescription:") == "true"
        return {i for i, row in ING.items() if bool(row["prescription"]) == want}
    return set()


# --- 1. rules nothing can satisfy -------------------------------------
print("  rules that no pair of ingredients can satisfy:")
dead = []
for rule in r.interactions:
    a, b = members(rule["a"]), members(rule["b"])
    if not a or not b:
        dead.append((rule["rule_id"], rule["a"], rule["b"], "empty selector"))
        continue
    # a == b rules need two DIFFERENT products of the same kind, which is
    # satisfiable with one member; cross rules need a disjoint pair.
    if rule["a"] != rule["b"] and not {(x, y) for x in a for y in b if x != y}:
        dead.append((rule["rule_id"], rule["a"], rule["b"], "no distinct pair"))
print("    " + ("none" if not dead else ""))
for rid, sa, sb, why in dead:
    print(f"    {rid}  {sa} + {sb}  — {why}")

# --- 2. ingredients no rule and no gate can reach ---------------------
reachable = set()
for rule in r.interactions:
    reachable |= members(rule["a"]) | members(rule["b"])
gated = set()
for c in r.contraindications:
    gated |= members(c["matches"])
inert = sorted(set(ING) - reachable - gated)
print(f"\n  ingredients no rule and no gate can reach: {len(inert)}")
for i in inert:
    print(f"    {i:24} class={ING[i]['class']}")

# --- 3. the same pair, two rules, different advice --------------------
print("\n  ingredient pairs matched by more than one rule:")
pairs = defaultdict(list)
for rule in r.interactions:
    a, b = members(rule["a"]), members(rule["b"])
    for x, y in itertools.product(sorted(a), sorted(b)):
        if x == y and rule["a"] != rule["b"]:
            continue
        pairs[tuple(sorted((x, y)))].append(rule)
conflicting = 0
for pair, rules_hit in sorted(pairs.items()):
    if len(rules_hit) < 2:
        continue
    resolutions = {ru["resolution"] for ru in rules_hit if ru["resolution"] != "none"}
    types = {ru["type"] for ru in rules_hit}
    # Synergy sitting on top of a conflict is the interesting case: the
    # page would tell someone these work well together and clash.
    if len(resolutions) > 1 or ("synergy" in types and types & {"conflict", "caution"}):
        conflicting += 1
        print(f"    {pair[0]} + {pair[1]}")
        for ru in rules_hit:
            print(f"        {ru['rule_id']}  {ru['type']:10} {ru['severity']:7} "
                  f"{ru['resolution']}")
if not conflicting:
    print("    none")

# --- 4. severity against resolution -----------------------------------
print("\n  high-severity rules that do nothing about it:")
lazy = [ru for ru in r.interactions
        if ru["severity"] in ("critical", "high") and ru["resolution"] == "none"
        and ru["type"] in ("conflict", "caution")]
print("    " + ("none" if not lazy else ""))
for ru in lazy:
    print(f"    {ru['rule_id']}  {ru['type']} {ru['severity']}  resolution=none")

"""Rule-based DRAFT allergen tags for IFCT foods.

IFCT foods are single raw ingredients, so an allergen is PRESENT when the food IS (or is made from)
the allergen source, ABSENT otherwise, and UNKNOWN where identity does not settle it (processed/dried
fruit for sulphites, coconut for tree nuts). Cross-reactivity (e.g. peanut-legume) and cross-contact are
NOT modelled. These tags are a starting point for review, not a clinical statement.
"""
import re
import sqlite3

SOURCE_SLUG = "draft-allergen-rules"
NOTE = "RULE_BASED_DRAFT: identity-based tag from food group/name; not reviewed by a dietitian"

_GLUTEN = re.compile(r"\b(wheat|barley|oats?|rye|triticale|spelt)\b", re.I)
_TREE_NUT = re.compile(r"\b(almond|cashew|walnut|pistachio|pine seed|hazelnut|pecan|macadamia|brazil nut)\b", re.I)
_CRUSTACEAN = re.compile(r"\b(prawns?|shrimps?|crabs?|lobster)\b", re.I)
_MOLLUSC = re.compile(r"\b(oyster|clam|mussel|squid|octopus|cuttlefish)\b", re.I)
_SULPHITE_RISK = re.compile(r"\b(dried|dry|processed|raisins?)\b", re.I)


def classify(name: str, group: str) -> tuple[set[str], set[str]]:
    """Return (PRESENT codes, UNKNOWN codes) for one food."""
    present: set[str] = set()
    unknown: set[str] = set()
    n = name or ""
    if group == "L": present.add("milk")
    if group == "M": present.add("eggs")
    if group == "P": present.add("fish")
    if group == "Q": present.add("molluscs" if _MOLLUSC.search(n) else "crustaceans")
    if group == "R": present.add("molluscs")
    if group == "S":
        present.add("crustaceans" if _CRUSTACEAN.search(n) else ("molluscs" if _MOLLUSC.search(n) else "fish"))
    if group in ("A", "F", "G") and _GLUTEN.search(n): present.add("gluten_cereals")
    if re.search(r"\bsoya?\b|\bsoyabean\b", n, re.I): present.add("soybeans")
    if re.search(r"ground ?nut|peanut", n, re.I): present.add("peanuts")
    if _TREE_NUT.search(n): present.add("tree_nuts")
    if re.search(r"coconut", n, re.I): unknown.add("tree_nuts")
    if re.search(r"gingelly|sesame", n, re.I): present.add("sesame")
    if re.search(r"mustard", n, re.I): present.add("mustard")
    if re.search(r"celery", n, re.I): present.add("celery")
    if re.search(r"lupin", n, re.I): present.add("lupin")
    if group in ("E", "H", "J") and _SULPHITE_RISK.search(n): unknown.add("sulphites")
    return present, unknown


def tag_allergens(conn: sqlite3.Connection) -> int:
    """Insert one row per (food, allergen). Deterministic order. Returns rows written."""
    codes = {r[1]: r[0] for r in conn.execute("SELECT id, code FROM allergens ORDER BY code")}
    if not codes:
        raise RuntimeError("allergens table is empty; seed reference data first")
    conn.execute(
        "INSERT OR IGNORE INTO sources(slug, name, description, version, publisher, verification_status, notes) VALUES (?,?,?,?,?,?,?)",
        (SOURCE_SLUG, "Rule-based allergen tags (draft)", "Identity-based allergen tags for IFCT foods", "1",
         "DietDB project", "UNVERIFIED", NOTE),
    )
    source_id = conn.execute("SELECT id FROM sources WHERE slug = ?", (SOURCE_SLUG,)).fetchone()[0]
    foods = conn.execute(
        "SELECT f.id, f.english_name, g.code FROM foods f JOIN food_groups g ON g.id = f.food_group_id ORDER BY f.id"
    ).fetchall()
    rows = []
    for food_id, name, group in foods:
        present, unknown = classify(name, group)
        for code in sorted(codes):
            if code in present: presence, note = "PRESENT", NOTE
            elif code in unknown: presence, note = "UNKNOWN", NOTE
            else: presence, note = "ABSENT", None
            rows.append((food_id, codes[code], presence, source_id, None, note))
    conn.executemany(
        "INSERT OR REPLACE INTO food_allergens(food_id, allergen_id, presence, source_id, assessed_at, notes) VALUES (?,?,?,?,?,?)",
        rows,
    )
    return len(rows)

#!/usr/bin/env python3
"""DietDB CLI - python -m dietdb build"""
import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def get_db_hash(db_path: str) -> str:
    """Deterministic hash excluding rowid, FTS tables, timestamps."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'food_aliases_fts%'
        AND name != 'build_metadata'
        AND name != 'schema_version'
        ORDER BY name
    """)
    tables = [r[0] for r in cur.fetchall()]

    h = hashlib.sha256()
    for tbl in tables:
        cur.execute(f"PRAGMA table_info({tbl})")
        info = cur.fetchall()
        cols = [r['name'] for r in info if r['name'] not in ('rowid','created_at','updated_at')]
        if not cols:
            continue
        col_list = ', '.join(f'"{c}"' for c in cols)
        primary = [r['name'] for r in sorted(info, key=lambda r: r['pk']) if r['pk']]
        order = ', '.join(f'"{c}"' for c in primary or cols)
        cur.execute(f"SELECT {col_list} FROM {tbl} ORDER BY {order}")
        h.update((tbl + '\0').encode())
        for row in cur:
            for c in cols:
                v = row[c]
                h.update(('<NULL>' if v is None else str(v) + '\0').encode())
    conn.close()
    return h.hexdigest()


def build_database(db_path: str, csv_path: str = None, output_hash: bool = False):
    """Build database from IFCT 2017 CSV with YAML mapping."""
    if tuple(map(int, sqlite3.sqlite_version.split('.'))) < (3, 37, 0):
        raise RuntimeError(f"SQLite 3.37+ is required, found {sqlite3.sqlite_version}")
    from dietdb.ingest.ifct_loader import IFCTLoader

    repo = Path(__file__).parent.parent.parent
    csv_path = csv_path or str(repo / 'data/raw/ifct2017/2.0.0/index.csv')
    mapping_path = str(repo / 'data/mappings/ifct_columns.yaml')
    sha256 = '22bb9d5072d3907af389cb77deab37a164ba5f84bf2a3eaf1a3fb274f6567ba9'

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    output_path = Path(db_path)
    if output_path.exists() and output_path.stat().st_size:
        raise FileExistsError(
            f"Refusing to rebuild existing database {db_path}; remove it first"
        )

    # Apply migrations
    conn = sqlite3.connect(str(db_path))
    for m in sorted((repo / 'migrations').glob('*.sql')):
        conn.executescript(open(m).read())
    conn.close()

    # Load IFCT data
    IFCTLoader(csv_path, mapping_path, str(db_path), sha256).load()
    from dietdb.rules import seed_reference_data
    conn = sqlite3.connect(str(db_path))
    seed_reference_data(conn, repo / 'data/seed')
    conn.commit()
    conn.close()

    # Record build metadata
    conn = sqlite3.connect(str(db_path))
    db_hash = get_db_hash(str(db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS build_metadata (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO build_metadata VALUES ('build_hash',?)", (db_hash,))
    conn.execute("INSERT OR REPLACE INTO build_metadata VALUES ('build_time',?)",
                 (datetime.utcnow().isoformat(),))
    conn.commit()
    conn.close()

    if output_hash:
        return db_hash
    print(f"Built: {db_path}\nHash: {db_hash}")


def main():
    p = argparse.ArgumentParser(description='DietDB CLI')
    sp = p.add_subparsers(dest='cmd', required=True)

    bp = sp.add_parser('build', help='Build database from IFCT 2017')
    bp.add_argument('--db', required=True, help='Output database path')
    bp.add_argument('--csv', help='Path to IFCT CSV (optional)')
    bp.add_argument('--output-hash', action='store_true', help='Output only hash')

    hp = sp.add_parser('hash', help='Compute database hash')
    hp.add_argument('--db', required=True)

    rp = sp.add_parser('load-rules', help='Load validated declarative rules')
    rp.add_argument('--db', required=True)
    rp.add_argument('--rules-dir', default=None)
    rp.add_argument('--mode', choices=('production', 'test', 'draft-review'), default='production')

    pp = sp.add_parser('plan', help='Resolve, optimize, verify, and write a plan')
    pp.add_argument('--db', required=True)
    pp.add_argument('--patient', required=True)
    pp.add_argument('--rules-mode', choices=('production', 'test', 'draft-review'), default='production')
    pp.add_argument('--out', required=True)
    pp.add_argument('--added-salt-g-per-day', type=float, default=5.0)
    pp.add_argument('--max-food-grams-per-day', type=float, default=500.0)

    a = p.parse_args()
    if a.cmd == 'build':
        r = build_database(a.db, getattr(a, 'csv', None), a.output_hash)
        if a.output_hash:
            print(r)
    elif a.cmd == 'hash':
        print(get_db_hash(a.db))
    elif a.cmd == 'load-rules':
        from dietdb.rules import load_rules
        rules_dir = a.rules_dir or ('data/rules/draft' if a.mode == 'draft-review' else 'data/rules')
        if a.mode == 'draft-review':
            if Path(a.db).resolve() == (Path('data/diet.db').resolve()):
                raise SystemExit('draft-review requires a separate database path')
            from dietdb.rules import load_conditions
            count = load_rules(a.db, rules_dir, a.mode)
            condition_file = Path('data/conditions/draft_conditions.json')
            conditions = load_conditions(a.db, condition_file) if condition_file.exists() else 0
            print(f"RULES ARE UNREVIEWED DRAFTS: loaded {count} rules and {conditions} conditions")
        else:
            print(f"Loaded {load_rules(a.db, rules_dir, a.mode)} rules")
    elif a.cmd == 'plan':
        import json
        from dietdb.engine.constraints import Patient, resolve
        from dietdb.engine.optimizer import optimize
        from dietdb.engine.verifier import verify
        from dietdb.engine.db import connect_readonly
        from dietdb.rules import load_rules
        patient_values = json.loads(Path(a.patient).read_text())
        rules_dir = 'data/rules/draft' if a.rules_mode == 'draft-review' else 'data/rules'
        load_rules(a.db, rules_dir, a.rules_mode)
        patient = Patient.from_database(patient_values, a.db)
        resolved = resolve(patient, a.db, a.rules_mode)
        output = {"status": resolved.status, "needs_info": resolved.needs_info,
                  "advisories": resolved.advisories, "nutrients": resolved.nutrients}
        if resolved.status not in {"INCOMPLETE", "CLINICIAN_REQUIRED", "INFEASIBLE_RULES"}:
            output["plan"] = optimize(a.db, patient.values, resolved, a.added_salt_g_per_day,
                                       max_food_grams_per_day=a.max_food_grams_per_day)
            if output["plan"]["status"] != "OK":
                output["status"] = output["plan"]["status"]
            else:
                output["plan"]["foods"] = [f for f in output["plan"]["foods"] if f["grams"] >= 5]
                checked = verify(output["plan"], a.db, resolved, patient.values)
                output["verification"] = checked
                if not checked["ok"]: output["status"] = "VERIFIER_REJECTED"
                with connect_readonly(a.db) as conn:
                    units = {r[0]: r[1] for r in conn.execute("SELECT canonical_name, canonical_unit FROM nutrients")}
                nutrient_report = {}
                for name, bounds in resolved.nutrients.items():
                    total = checked["totals"].get(name, 0.0)
                    if name == "sodium": total += a.added_salt_g_per_day * 393.0
                    nutrient_report[name] = {"total": round(total, 3), "min": bounds.get("min"),
                        "max": bounds.get("max"), "unit": units.get(name),
                        "met": (bounds.get("min") is None or total >= bounds["min"]) and
                               (bounds.get("max") is None or total <= bounds["max"])}
                energy_total = checked["totals"].get("energy_kcal", 0.0)
                output["plan"]["nutrients"] = nutrient_report
                output["plan"]["energy_total_kcal"] = round(energy_total, 3)
                output["plan"]["pct_of_target"] = round(100 * energy_total / resolved.energy_target_kcal, 3) if resolved.energy_target_kcal else None
        output["applied_rules"] = resolved.applied_rules
        Path(a.out).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": output["status"], "out": a.out}, sort_keys=True))
        raise SystemExit(2 if output["status"] in {"INFEASIBLE_RULES", "INFEASIBLE_PLAN", "VERIFIER_REJECTED"} else 0)


if __name__ == '__main__':
    main()

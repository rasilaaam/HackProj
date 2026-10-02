#!/usr/bin/env python3
"""Check database integrity after IFCT loading."""
import sqlite3, sys
from pathlib import Path

def check_integrity(db_path):
    """Run integrity checks."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print("Database Integrity Check")
    print("=" * 50)
    
    # Check foreign keys
    cur.execute("PRAGMA foreign_keys")
    fk_status = cur.fetchone()[0]
    print(f"Foreign keys: {'ENABLED' if fk_status else 'DISABLED'}")
    
    # Table counts
    tables = ['sources', 'nutrients', 'food_groups', 'foods', 'food_nutrients']
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"{table}: {count}")
    
    # Check critical issues
    issues = []
    
    # 1. Foods without food groups
    cur.execute("""SELECT COUNT(*) FROM foods f 
        LEFT JOIN food_groups g ON f.food_group_id = g.id
        WHERE g.id IS NULL AND f.food_group_id IS NOT NULL""")
    orphaned = cur.fetchone()[0]
    if orphaned:
        issues.append(f"{orphaned} foods have invalid food_group_id")
    
    # 2. Duplicate food_nutrients
    cur.execute("""SELECT food_id, nutrient_id, COUNT(*) FROM food_nutrients 
        GROUP BY food_id, nutrient_id HAVING COUNT(*) > 1""")
    dups = cur.fetchall()
    if dups:
        issues.append(f"{len(dups)} duplicate food_nutrient entries")
    
    # 3. Measured with NULL values
    cur.execute("""SELECT COUNT(*) FROM food_nutrients
        WHERE value_status = 'MEASURED' AND value_canonical IS NULL""")
    null_measured = cur.fetchone()[0]
    if null_measured:
        issues.append(f"{null_measured} MEASURED nutrients with NULL value")
    
    # 4. Check IFCT source
    cur.execute("SELECT * FROM sources WHERE slug = 'ifct2017'")
    if not cur.fetchone():
        issues.append("IFCT 2017 source missing")
    
    conn.close()
    
    if issues:
        print("\nISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("\nAll checks passed!")
        return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 check_integrity.py <database.db>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    if not Path(db_path).exists():
        print(f"Database {db_path} not found")
        sys.exit(1)
    
    success = check_integrity(db_path)
    sys.exit(0 if success else 1)
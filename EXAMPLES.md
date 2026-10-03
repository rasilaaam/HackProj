# DietDB - Usage Examples

Quick examples of what you can do with DietDB.

## Database Stats

```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('data/diet.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM foods')
print(f"Foods: {cursor.fetchone()[0]}")

cursor.execute('SELECT COUNT(*) FROM nutrients')
print(f"Nutrients: {cursor.fetchone()[0]}")

cursor.execute('SELECT COUNT(*) FROM food_nutrients')
print(f"Measurements: {cursor.fetchone()[0]}")

conn.close()
EOF
```

## Search Foods

```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('data/diet.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT english_name FROM foods WHERE english_name LIKE ? LIMIT 5", ('%rice%',))
for row in cursor.fetchall():
    print(row['english_name'])
conn.close()
EOF
```

## List Nutrients

```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('data/diet.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT canonical_name, category FROM nutrients ORDER BY category")
for row in cursor.fetchall():
    print(f"{row['canonical_name']:20} ({row['category']})")
conn.close()
EOF
```

## Get Food Nutrition

```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('data/diet.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT f.english_name, n.canonical_name, fn.value_canonical, n.canonical_unit
    FROM foods f
    JOIN food_nutrients fn ON f.id = fn.food_id
    JOIN nutrients n ON fn.nutrient_id = n.id
    WHERE f.id = 1
""")

rows = cursor.fetchall()
if rows:
    print(f"Nutrients in {rows[0]['english_name']}:")
    for row in rows:
        print(f"  {row['canonical_name']}: {row['value_canonical']} {row['canonical_unit']}")
conn.close()
EOF
```

## Top Protein Foods

```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('data/diet.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT f.english_name, fn.value_canonical
    FROM foods f
    JOIN food_nutrients fn ON f.id = fn.food_id
    JOIN nutrients n ON fn.nutrient_id = n.id
    WHERE n.canonical_name = 'protein' AND fn.value_status = 'MEASURED'
    ORDER BY fn.value_canonical DESC
    LIMIT 10
""")

print("Top 10 protein sources (per 100g):")
for i, row in enumerate(cursor.fetchall(), 1):
    print(f"{i:2}. {row['english_name']:30} {row['value_canonical']:>6}g")
conn.close()
EOF
```

## Data Quality

```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('data/diet.db')
cursor = conn.cursor()

cursor.execute("SELECT value_status, COUNT(*) as count FROM food_nutrients GROUP BY value_status ORDER BY count DESC")
total = sum(row[1] for row in cursor.fetchall())
cursor.execute("SELECT value_status, COUNT(*) as count FROM food_nutrients GROUP BY value_status ORDER BY count DESC")

for status, count in cursor.fetchall():
    pct = (count / total * 100) if total > 0 else 0
    print(f"{status:15} {count:>5} ({pct:>5.1f}%)")
conn.close()
EOF
```

## High Calorie Foods

```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('data/diet.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT f.english_name, fn.value_canonical
    FROM foods f
    JOIN food_nutrients fn ON f.id = fn.food_id
    JOIN nutrients n ON fn.nutrient_id = n.id
    WHERE n.canonical_name = 'energy_kcal' AND fn.value_status = 'MEASURED'
    ORDER BY fn.value_canonical DESC
    LIMIT 5
""")

print("Highest calorie foods:")
for row in cursor.fetchall():
    print(f"  {row['english_name']:30} {row['value_canonical']:>6} kcal")
conn.close()
EOF
```

## Iron Rich Foods

```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('data/diet.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT f.english_name, fn.value_canonical
    FROM foods f
    JOIN food_nutrients fn ON f.id = fn.food_id
    JOIN nutrients n ON fn.nutrient_id = n.id
    WHERE n.canonical_name = 'iron' AND fn.value_status = 'MEASURED'
    ORDER BY fn.value_canonical DESC
    LIMIT 5
""")

print("Top iron sources (mg per 100g):")
for row in cursor.fetchall():
    print(f"  {row['english_name']:30} {row['value_canonical']:>6}mg")
conn.close()
EOF
```

## Export to CSV

```bash
python3 << 'EOF'
import sqlite3, csv
conn = sqlite3.connect('data/diet.db')
cursor = conn.cursor()

cursor.execute("SELECT english_name, food_state FROM foods LIMIT 50")
with open('foods.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Food Name', 'State'])
    writer.writerows(cursor.fetchall())

print("Exported to foods.csv")
conn.close()
EOF
```

## Run Tests

```bash
pytest tests/ -v                    # All tests
pytest tests/test_parsing.py -v     # Specific file
pytest tests/ --cov=dietdb          # With coverage
```

## Rebuild Database

```bash
rm data/diet.db
python3 -m dietdb build --db data/diet.db
```

## Features

- 542 Indian foods from IFCT 2017
- 166 mapped nutrients tracked
- 89,972 nutrient measurements
- Data quality status tracking
- Tests are run with `python -m pytest -q`
- Deterministic builds
- Full SQL database access

#!/usr/bin/env python3
"""Generate ifct_columns.yaml from unit_verification.csv"""
import csv
import yaml
from collections import defaultdict

# Load unit_verification.csv
verification = {}
with open('data/mappings/unit_verification.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        verification[row['csv_col']] = row

# Build mapping
mapping = {}
status_count = defaultdict(int)

for csv_col in sorted(verification.keys()):
    info = verification[csv_col]
    book_table = info['book_table']
    csv_to_printed = info['csv_to_printed_factor']
    status = info['status']
    
    # Skip UNVERIFIED
    if status.startswith('UNVERIFIED'):
        status_count[status] += 1
        continue
    
    # Special handling for energy: CSV is kJ, book is kJ, canonical is kcal
    if csv_col == 'enerc':
        entry = {
            "book_table": 1,
            "csv_to_printed": 1.0,  # CSV kJ to printed kJ
            "printed_unit": "kJ",
            "printed_to_canonical": 0.2388,  # kJ to kcal
            "canonical_unit": "kcal",
            "status": status
        }
        mapping[csv_col] = entry
        status_count[status] += 1
        continue
    
    # Parse factor
    if csv_to_printed == '':
        factor = None
        printed_unit = 'UNKNOWN'
        printed_to_canonical = 1.0
    elif csv_to_printed == 'per_protein':
        factor = 'per_protein'
        printed_unit = 'g_per_100g_protein'
        printed_to_canonical = 'per_protein'
    else:
        factor = float(csv_to_printed)
        printed_to_canonical = factor
        
        # Infer printed unit
        if factor == 1.0:
            printed_unit = "g"
        elif factor == 1000.0:
            printed_unit = "mg"
        elif factor == 1000000.0:
            printed_unit = "ug"
        elif factor == 0.2388:
            printed_unit = "kcal"
        else:
            printed_unit = "UNKNOWN"
    
    # Canonical unit
    if printed_to_canonical == "per_protein":
        canonical_unit = "g_per_100g_protein"
    elif printed_unit == "g":
        canonical_unit = "g"
    elif printed_unit == "mg":
        canonical_unit = "mg"
    elif printed_unit == "ug":
        canonical_unit = "ug"
    elif printed_unit == "kcal":
        canonical_unit = "kcal"
    else:
        canonical_unit = "UNKNOWN"
    
    # Build entry
    entry = {
        "book_table": int(book_table) if book_table and book_table.isdigit() else book_table,
        "csv_to_printed": printed_to_canonical,
        "printed_unit": printed_unit,
        "canonical_unit": canonical_unit,
        "status": status
    }
    
    mapping[csv_col] = entry
    status_count[status] += 1

with open('data/mappings/ifct_columns.yaml', 'w') as f:
    yaml.dump(mapping, f, default_flow_style=False, sort_keys=True)

print(f"Created mapping with {len(mapping)} VERIFIED/WEAK columns")
for s in sorted(status_count.keys()):
    print(f"  {s}: {status_count[s]}")


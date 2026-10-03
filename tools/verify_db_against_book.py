#!/usr/bin/env python3
"""End-to-end check: every MEASURED value in the built SQLite DB vs the book's printed values.

  pdftotext -layout IFCT2017.pdf local/ifct_text/ifct_full.txt     # local only, never commit
  python tools/verify_db_against_book.py --db data/diet.db --text local/ifct_text/ifct_full.txt

Needs tools/verify_units.py next to it. Expected DB layout: foods(source_code), nutrients(ifct_column_code),
food_nutrients(value_native, value_canonical, canonical_unit, value_status).
- canonical kcal  -> compared as value_canonical * 4.18 against the printed kJ
- canonical g_per_100g_protein -> compared against book Table 8
- everything else -> value_canonical (in the book's printed unit) against any book table
Exit code 1 if the match rate is below --min-rate (default 0.99). Prints the worst columns and examples.
Writes no book values to disk.
"""
import argparse, collections, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_units import table_regions, tokens, hit

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True); ap.add_argument('--text', required=True)
    ap.add_argument('--min-rate', type=float, default=0.99)
    a = ap.parse_args()
    lines = open(a.text, encoding='utf-8').read().split('\n')
    regions = table_regions(lines); tok = tokens(lines, regions)
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    q = """SELECT f.source_code code, n.ifct_column_code col, fn.value_canonical vc, fn.canonical_unit u
           FROM food_nutrients fn JOIN nutrients n ON n.id=fn.nutrient_id JOIN foods f ON f.id=fn.food_id
           WHERE fn.value_status='MEASURED' AND fn.value_canonical IS NOT NULL"""
    tot = ok = 0; bad = collections.Counter(); ex = []
    for r in c.execute(q):
        if r['u'] == 'kcal': val, tabs = r['vc'] * 4.18, [1]
        elif r['u'] == 'g_per_100g_protein': val, tabs = r['vc'], [8]
        else: val, tabs = r['vc'], list(regions)
        toks = [t for n in tabs for t in tok[n].get(r['code'], [])]
        tot += 1
        if hit(val, toks): ok += 1
        else:
            bad[r['col']] += 1
            if len(ex) < 10: ex.append((r['code'], r['col'], round(val, 6), r['u']))
    rate = ok / tot if tot else 0
    print(f'MEASURED rows checked: {tot}; matched: {ok} ({rate:.2%}); mismatches: {tot-ok}')
    print('worst columns:', bad.most_common(12)); print('examples:', ex)
    sys.exit(0 if rate >= a.min_rate else 1)

if __name__ == '__main__':
    main()

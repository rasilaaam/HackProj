#!/usr/bin/env python3
"""Independently verify IFCT 2017 CSV column units/factors against the official book text.

Usage:
  pdftotext -layout IFCT2017.pdf local/ifct_full.txt      # keep this file OUT of git
  python tools/verify_units.py --text local/ifct_full.txt \
      --csv data/raw/ifct2017/2.0.0/index.csv --out data/mappings/unit_verification.csv \
      [--mapping data/mappings/ifct_columns.yaml]          # optional: fail if mapping disagrees

For every CSV value column it finds which book table and which scale factor reproduces the
book's printed values. csv_to_printed is the number to multiply the CSV value by to get the
unit printed in the book (1 = g, 1000 = mg, 1000000 = ug). Amino acids are checked as
csv / protein * 100 (the book prints g per 100 g protein; the CSV is g per 100 g food).
Only column codes, factors and match counts are written (no book values), so the output is safe to commit.
"""
import argparse, collections, csv, re, sys

META = {'code', 'name', 'scie', 'lang', 'grup', 'regn', 'tags'}
AMINO = 'his ile leu lys met cys phe thr trp val ala arg asp glu gly pro ser tyr'.split()
CANDIDATES = [1, 1e3, 1e6, 1e-3]
NUM = re.compile(r'(?<![\w.±])(\d+(?:\.\d+)?)(?:±\d+(?:\.\d+)?)?')
CODE = re.compile(r'(?<![A-Z0-9])([A-T]\d{3})(?![0-9])')

def table_regions(lines):
    starts = {}
    for i, l in enumerate(lines):
        s = l.strip()
        m = re.match(r'Table (\d+)\.\s+([A-Z][A-Z ,\-()/&]+)$', s)
        if m and i > 1900 and int(m.group(1)) not in starts:
            starts[int(m.group(1))] = i
    order = sorted(starts.items(), key=lambda x: x[1])
    return {n: (s, order[k + 1][1] if k + 1 < len(order) else len(lines)) for k, (n, s) in enumerate(order)}

def tokens(lines, regions):
    tok = {n: collections.defaultdict(list) for n in regions}
    for n, (s, e) in regions.items():
        for i in range(s, e):
            m = CODE.search(lines[i])
            if not m:
                continue
            for mm in NUM.finditer(lines[i][m.end():]):
                t = mm.group(1)
                tok[n][m.group(1)].append((float(t), len(t.split('.')[1]) if '.' in t else 0))
    return tok

def hit(v, toks):
    return any(abs(v - t) <= 0.5 * 10 ** (-d) + 1e-9 for t, d in toks)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--text', required=True); ap.add_argument('--csv', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--mapping')
    a = ap.parse_args()
    lines = open(a.text, encoding='utf-8').read().split('\n')
    regions = table_regions(lines)
    if len(regions) < 12:
        sys.exit(f'Could only locate {len(regions)} of 12 book tables; check the text file')
    tok = tokens(lines, regions)
    rows = list(csv.DictReader(open(a.csv, encoding='utf-8')))
    cols = [c for c in rows[0] if not c.endswith('_e') and c not in META]
    out = []
    for c in cols:
        best = None
        if c in AMINO:
            ok = tot = 0
            for r in rows:
                v, p = float(r[c]), float(r['protcnt'])
                toks = tok[8].get(r['code'])
                if v == 0 or p == 0 or not toks:
                    continue
                tot += 1; ok += hit(v / p * 100, toks)
            best = (ok / tot if tot else 0, 8, 'per_protein', ok, tot)
        else:
            for n in regions:
                for f in CANDIDATES:
                    ok = tot = 0
                    for r in rows:
                        v = float(r[c])
                        toks = tok[n].get(r['code'])
                        if v == 0 or not toks:
                            continue
                        tot += 1; ok += hit(v * f, toks)
                    if tot >= 5 and (best is None or ok / tot > best[0] + 1e-9):
                        best = (ok / tot, n, f, ok, tot)
        if best is None:
            out.append((c, '', '', '', 0, 'UNVERIFIED_TOO_FEW_VALUES'))
        else:
            rate, n, f, ok, tot = best
            out.append((c, n, f, ok, tot, 'VERIFIED' if rate >= 0.95 else 'WEAK_MATCH_REVIEW_MANUALLY'))
    with open(a.out, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['csv_col', 'book_table', 'csv_to_printed_factor', 'matches', 'tested', 'status'])
        w.writerows(out)
    print(collections.Counter(o[5] for o in out))
    if a.mapping:
        import yaml
        mp = yaml.safe_load(open(a.mapping))
        bad = []
        v = {o[0]: o for o in out if o[5] == 'VERIFIED'}
        for col, spec in mp.items():
            if col not in v:
                continue
            factor = spec.get('csv_to_printed') if isinstance(spec, dict) else None
            if factor is None or (v[col][2] != 'per_protein' and abs(float(factor) - float(v[col][2])) > 1e-9):
                bad.append((col, factor, v[col][2]))
        print('mapping disagreements:', len(bad)); [print('  ', b) for b in bad[:40]]
        sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()

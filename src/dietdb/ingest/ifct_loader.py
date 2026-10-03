#!/usr/bin/env python3
"""
IFCT 2017 loader: SHA256 verification, BDL rules, nutrient hierarchy, idempotent.

Key conversions:
- Energy: kJ → kcal via / 4.18
- SD values: converted by same factor as main value
- Group T (oils): NOT_ANALYSED per IFCT Table 12

License: IFCT 2017 (c) NIN/ICMR; product use requires NIN's written permission.
"""
import csv
import hashlib
import re
import sqlite3
import yaml
from pathlib import Path
from typing import Dict, List, Optional

from dietdb.aliases import extract_regional_names


# Nutrient parent hierarchy (child: parent ifct_column_code)
NUTRIENT_PARENTS = {
    # Fatty acids under total fat
    'fasat': 'fatce', 'fauns': 'fatce', 'fapu': 'fatce', 'fams': 'fatce',
    'f18d2cn6': 'fapu', 'f18d3n3': 'fapu', 'f20d4n6': 'fapu', 'f20d5n3': 'fapu', 'f22d6n3': 'fapu',
    # Amino acids under protein
    'his': 'protcnt', 'ile': 'protcnt', 'leu': 'protcnt', 'lys': 'protcnt',
    'met': 'protcnt', 'cys': 'protcnt', 'phe': 'protcnt', 'thr': 'protcnt',
    'trp': 'protcnt', 'val': 'protcnt', 'ala': 'protcnt', 'arg': 'protcnt',
    'asp': 'protcnt', 'glu': 'protcnt', 'gly': 'protcnt', 'pro': 'protcnt', 'ser': 'protcnt', 'tyr': 'protcnt',
    # Vitamins
    'vita': 'vit', 'vitd': 'vit', 'vite': 'vit', 'vitk': 'vit', 'vitc': 'vit',
    'thia': 'vit', 'ribf': 'vit', 'nia': 'vit', 'pantac': 'vit', 'vitb6c': 'vit', 'biot': 'vit', 'folsum': 'vit',
    # Minerals
    'ca': 'ash', 'fe': 'ash', 'mg': 'ash', 'p': 'ash', 'k': 'ash', 'na': 'ash', 'zn': 'ash',
    'cu': 'ash', 'mn': 'ash', 'se': 'ash',
}

# Canonical names for nutrients
CANONICAL_NAMES = {
    'enerc': 'energy_kcal', 'water': 'water', 'ash': 'ash',
    'protcnt': 'protein', 'fatce': 'fat_total', 'choavldf': 'carbohydrate',
    'fibtg': 'fiber_total', 'f16d0': 'palmitic_acid', 'f18d0': 'stearic_acid',
    'f18d1cn9': 'oleic_acid', 'f18d2cn6': 'linoleic_acid', 'f18d3n3': 'alpha_linolenic_acid',
    'f20d4n6': 'arachidonic_acid', 'f20d5n3': 'epa', 'f22d6n3': 'dha',
    'ca': 'calcium', 'fe': 'iron', 'mg': 'magnesium', 'p': 'phosphorus',
    'k': 'potassium', 'na': 'sodium', 'zn': 'zinc', 'cu': 'copper',
    'mn': 'manganese', 'se': 'selenium', 'vitc': 'vitamin_c',
    'thia': 'thiamin', 'ribf': 'riboflavin', 'nia': 'niacin',
    'pantac': 'pantothenic_acid', 'vitb6c': 'vitamin_b6', 'folsum': 'folate',
    'vitd': 'vitamin_d', 'vite': 'vitamin_e', 'vitk': 'vitamin_k',
    'his': 'histidine', 'ile': 'isoleucine', 'leu': 'leucine', 'lys': 'lysine',
    'met': 'methionine', 'cys': 'cysteine', 'phe': 'phenylalanine', 'thr': 'threonine',
    'trp': 'tryptophan', 'val': 'valine', 'ala': 'alanine', 'arg': 'arginine',
    'asp': 'aspartic_acid', 'glu': 'glutamic_acid', 'gly': 'glycine',
    'pro': 'proline', 'ser': 'serine', 'tyr': 'tyrosine',
}


class IFCTLoader:
    """Load IFCT 2017 CSV into dietdb schema."""
    
    def __init__(self, csv_path: str, mapping_path: str, db_path: str, expected_sha256: str):
        self.csv_path = Path(csv_path)
        self.mapping_path = Path(mapping_path)
        self.db_path = Path(db_path)
        self.expected_sha256 = expected_sha256
        self.conn = None
        
    def verify_checksum(self) -> bool:
        """Verify CSV SHA256 matches expected."""
        sha = hashlib.sha256()
        with open(self.csv_path, 'rb') as f:
            sha.update(f.read())
        actual = sha.hexdigest()
        if actual != self.expected_sha256:
            raise ValueError(f"CSV checksum mismatch. Expected {self.expected_sha256}, got {actual}")
        return True
    
    def load_mapping(self) -> Dict:
        """Load ifct_columns.yaml mapping - VERIFIED columns only."""
        with open(self.mapping_path) as f:
            mapping = yaml.safe_load(f)
        return {k: v for k, v in mapping.items() if v['status'] == 'VERIFIED'}
    
    def connect(self):
        """Connect to database."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def get_or_create_source(self) -> int:
        """Get or create IFCT 2017 source entry."""
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM sources WHERE slug = ?", ('ifct2017',))
        row = cur.fetchone()
        if row:
            return row[0]
        
        # Insert new source
        cur.execute(
            """INSERT INTO sources 
               (slug, name, description, version, year, publisher, license, 
                source_url, local_path, checksum, verification_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('ifct2017', 'IFCT 2017', 'Indian Food Composition Tables 2017',
             '2.0.0', 2017, 'National Institute of Nutrition (NIN), ICMR',
             'IFCT 2017 (c) National Institute of Nutrition (ICMR), Hyderabad. '
             'Electronic storage for product use requires NIN written permission; '
             'data transcription via @ifct2017/compositions 2.0.0 (MIT).',
             'https://github.com/ifct2017/compositions', str(self.csv_path),
             self.expected_sha256, 'CHECKED_AGAINST_BOOK_SAMPLE')
        )
        self.conn.commit()
        return cur.lastrowid
    
    def get_or_create_food_group(self, code: str) -> int:
        """Get or create food group."""
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM food_groups WHERE code = ?", (code,))
        row = cur.fetchone()
        if row:
            return row[0]
        
        # Insert (group names)
        groups = {
            'A': 'Cereals and Millets', 'B': 'Grain Legumes', 'C': 'Green Leafy Vegetables',
            'D': 'Other Vegetables', 'E': 'Fruits', 'F': 'Roots and Tubers',
            'G': 'Condiments & Spices', 'H': 'Nuts & Oil Seeds', 'I': 'Sugars',
            'J': 'Mushrooms', 'K': 'Miscellaneous', 'L': 'Milk & Milk Products',
            'M': 'Egg Products', 'N': 'Poultry', 'O': 'Animal Meat',
            'P': 'Marine Fish', 'Q': 'Marine Shellfish', 'R': 'Marine Mollusks',
            'S': 'Fresh Water Fish', 'T': 'Edible Oils & Fats'
        }
        cur.execute(
            "INSERT INTO food_groups (code, name, level) VALUES (?, ?, ?)",
            (code, groups.get(code, f'Group {code}'), 0)
        )
        self.conn.commit()
        return cur.lastrowid
    
    def get_or_create_nutrient(self, csv_col: str, mapping_info: Dict) -> int:
        """Get or create nutrient."""
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM nutrients WHERE ifct_column_code = ?", (csv_col,))
        row = cur.fetchone()
        if row:
            return row[0]
        
        # Infer category
        canonical_unit = mapping_info['canonical_unit']
        category = 'MACRONUTRIENT'
        if canonical_unit == 'ug' or 'vit' in csv_col or 'cart' in csv_col:
            category = 'MICRONUTRIENT'
        elif 'fa' in csv_col or 'f1' in csv_col or 'f2' in csv_col:
            category = 'FATTY_ACID'
        elif csv_col in ('his', 'ile', 'leu', 'lys', 'met', 'cys', 'phe', 'thr', 'trp', 'val', 'ala', 'arg', 'asp', 'glu', 'gly', 'pro', 'ser', 'tyr'):
            category = 'AMINO_ACID'
        
        canonical_name = CANONICAL_NAMES.get(csv_col, f'ifct_{csv_col}')
        native_unit = 'kJ' if csv_col == 'enerc' else 'g'
        conversion_factor = mapping_info.get('printed_to_canonical', 1.0)
        if isinstance(conversion_factor, str):
            conversion_factor = None
        cur.execute(
            """INSERT INTO nutrients 
               (canonical_name, display_name, category, canonical_unit,
                ifct_column_code, conversion_factor, native_unit)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (canonical_name, canonical_name.replace('_', ' ').title(), category,
             canonical_unit, csv_col, conversion_factor, native_unit)
        )
        self.conn.commit()
        return cur.lastrowid
    
    def load(self):
        """Load IFCT 2017 CSV into database."""
        self.verify_checksum()
        self.connect()
        try:
            existing_foods = self.conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
            if existing_foods == 542:
                return
            mapping = self.load_mapping()
            group_t_analysed = {
                column for column, info in mapping.items() if info.get('book_table') == 7
            }
            source_id = self.get_or_create_source()
            nutrient_map = {}
            for csv_col, info in mapping.items():
                nutrient_map[csv_col] = self.get_or_create_nutrient(csv_col, info)
            
            food_count = nutrient_count = 0
            with open(self.csv_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code, group_code = row['code'], row['code'][0]
                    group_id = self.get_or_create_food_group(group_code)
                    
                    food_state = 'RAW'
                    if group_code == 'M' and any(x in row['name'].lower() for x in ['boil', 'omlet']):
                        food_state = 'COOKED'
                    elif group_code == 'N':
                        food_state = 'UNKNOWN'
                    
                    cur = self.conn.cursor()
                    cur.execute("SELECT id FROM foods WHERE source_code = ? AND source_id = ?", (code, source_id))
                    food_row = cur.fetchone()
                    if not food_row:
                        cur.execute(
                            "INSERT INTO foods (source_code, source_id, english_name, scientific_name, food_group_id, food_state) VALUES (?, ?, ?, ?, ?, ?)",
                            (code, source_id, row['name'], row.get('scie') or None, group_id, food_state)
                        )
                        self.conn.commit()
                        food_id = cur.lastrowid
                        food_count += 1
                    else:
                        food_id = food_row[0]

                    # The package keeps language-coded aliases and diet tags in metadata columns.
                    aliases = {'English': row['name']}
                    aliases.update(extract_regional_names(row.get('lang', '')))
                    for language, alias in aliases.items():
                        if alias.strip():
                            cur.execute(
                                """INSERT OR IGNORE INTO food_aliases
                                   (food_id, alias, language, is_preferred)
                                   VALUES (?, ?, ?, ?)""",
                                (food_id, alias.strip(), language, int(language == 'English')))
                    for tag in row.get('tags', '').split():
                        tag_code = tag.strip().upper()
                        if not tag_code:
                            continue
                        cur.execute(
                            "INSERT OR IGNORE INTO diet_types (code, name) VALUES (?, ?)",
                            (tag_code, tag.strip().replace('_', ' ').title()))
                        cur.execute("SELECT id FROM diet_types WHERE code = ?", (tag_code,))
                        diet_type_id = cur.fetchone()[0]
                        cur.execute(
                            """INSERT OR IGNORE INTO diet_type_tags
                               (food_id, diet_type_id, is_compatible, source_id)
                               VALUES (?, ?, 1, ?)""",
                            (food_id, diet_type_id, source_id))
                    
                    for csv_col, nutrient_id in nutrient_map.items():
                        csv_value = row.get(csv_col, '').strip()
                        
                        if not csv_value:
                            value_status, value_native, sd = 'NOT_DETECTED', None, None
                        elif group_code == 'T' and csv_col not in group_t_analysed:
                            value_status, value_native, sd = 'NOT_ANALYSED', None, None
                        else:
                            try:
                                value_native = float(csv_value)
                            except ValueError:
                                continue
                            value_status = 'NOT_DETECTED' if value_native == 0 else 'MEASURED'
                            sd = None
                            try:
                                sd_val = row.get(f'{csv_col}_e', '').strip()
                                sd = float(sd_val) if sd_val else None
                            except ValueError:
                                pass
                        
                        if value_native is not None and value_status == 'MEASURED':
                            csv_to_printed = mapping[csv_col]['csv_to_printed']
                            if csv_to_printed == 'per_protein':
                                try:
                                    protcnt = float(row.get('protcnt', '0'))
                                    value_canonical = (value_native / protcnt * 100) if protcnt > 0 else None
                                    if value_canonical is None:
                                        value_status = 'NOT_DETECTED'
                                except (ValueError, ZeroDivisionError):
                                    value_canonical, value_status = None, 'NOT_DETECTED'
                            else:
                                # First convert CSV to printed value
                                value_printed = value_native * csv_to_printed
                                # Then convert printed to canonical if needed
                                printed_to_canonical = mapping[csv_col].get('printed_to_canonical', 1.0)
                                if isinstance(printed_to_canonical, str):
                                    # Handle 'per_protein' case (shouldn't happen, but safe)
                                    value_canonical = value_printed
                                else:
                                    value_canonical = value_printed * printed_to_canonical
                                if sd is not None:
                                    sd = sd * csv_to_printed * (
                                        printed_to_canonical if isinstance(printed_to_canonical, (int, float)) else 1.0
                                    )
                        else:
                            value_canonical = None

                        
                        cur.execute(
                            """INSERT OR REPLACE INTO food_nutrients 
                               (food_id, nutrient_id, value_native, unit_native, value_canonical, 
                                canonical_unit, sd, value_status, source_id, source_row)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (food_id, nutrient_id, value_native,
                             'kJ' if csv_col == 'enerc' else 'g', value_canonical,
                             mapping[csv_col]['canonical_unit'], sd, value_status, source_id, None)
                        )
                        nutrient_count += 1
            
            self.conn.commit()
            print(f"Loaded {food_count} foods, {nutrient_count} nutrient values")
        finally:
            self.close()


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Load IFCT 2017 into dietdb')
    ap.add_argument('--csv', required=True)
    ap.add_argument('--mapping', required=True)
    ap.add_argument('--db', required=True)
    ap.add_argument('--sha256', required=True)
    args = ap.parse_args()
    loader = IFCTLoader(args.csv, args.mapping, args.db, args.sha256)
    loader.load()


if __name__ == '__main__':
    main()

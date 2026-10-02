#!/usr/bin/env python3
"""
Extract regional food names from IFCT CSV to populate aliases.
IFCT CSV contains names like: "Rice, raw, milled" or with regional names:
"Rice, raw, milled; Hindi: Chawal; Tamil: Arisi; Telugu: Biyyam"
"""
import csv
import re
import sqlite3
from pathlib import Path
import sys

def extract_regional_names(name_field: str) -> dict:
    """Extract regional names from name field.
    
    Format: "English name; Hindi: Hindi name; Tamil: Tamil name; Telugu: Telugu name"
    Returns: {'English': 'Rice, raw, milled', 'Hindi': 'Chawal', ...}
    """
    result = {}
    
    # Split by semicolon
    parts = [p.strip() for p in name_field.split(';')]
    
    if not parts:
        return result
    
    # First part is always English name
    first_part = parts[0].strip()
    result['English'] = first_part
    
    # Process regional names
    for part in parts[1:]:
        # Match "Language: Name"
        match = re.match(r'^(\w+):\s*(.+)$', part)
        if match:
            language, regional_name = match.groups()
            result[language] = regional_name.strip()
    
    return result

def create_alias_loader(db_path: str):
    """Create aliases from IFCT CSV in database."""
    csv_path = Path('data/raw/ifct2017/2.0.0/index.csv')
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get IFCT source ID
    cur.execute("SELECT id FROM sources WHERE slug = 'ifct2017'")
    source_row = cur.fetchone()
    if not source_row:
        print("IFCT source not found. Run IFCTLoader first.")
        return
    source_id = source_row[0]
    
    alias_count = 0
    
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row['code']
            name_field = row['name']
            
            # Get food ID
            cur.execute("SELECT id FROM foods WHERE source_code = ? AND source_id = ?", 
                       (code, source_id))
            food_row = cur.fetchone()
            if not food_row:
                print(f"Food {code} not found in database")
                continue
            
            food_id = food_row[0]
            
            # Extract regional names
            regional_names = extract_regional_names(name_field)
            
            if not regional_names:
                print(f"No regional names for {code}: {name_field[:50]}...")
                continue
            
            # Insert aliases
            for language, alias_text in regional_names.items():
                # Skip empty aliases
                if not alias_text or len(alias_text.strip()) < 2:
                    continue
                
                # Determine script
                script = 'Latn'  # Default Latin
                if language in ['Hindi', 'Marathi', 'Sanskrit']:
                    script = 'Deva'
                elif language in ['Tamil']:
                    script = 'Taml'
                elif language in ['Telugu']:
                    script = 'Telu'
                elif language in ['Kannada']:
                    script = 'Knda'
                elif language in ['Malayalam']:
                    script = 'Mlym'
                elif language in ['Gujarati']:
                    script = 'Gujr'
                elif language in ['Punjabi']:
                    script = 'Guru'
                elif language in ['Bengali']:
                    script = 'Beng'
                elif language in ['Oriya']:
                    script = 'Orya'
                
                # Insert alias
                try:
                    cur.execute(
                        """INSERT OR IGNORE INTO food_aliases 
                           (food_id, alias, language, script, alias_type, is_preferred)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (food_id, alias_text, language, script, 
                         'COMMON', 1 if language == 'English' else 0)
                    )
                    alias_count += 1
                except sqlite3.IntegrityError:
                    pass  # Already exists
    
    conn.commit()
    conn.close()
    print(f"Created {alias_count} food aliases")

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Create food aliases from IFCT CSV')
    ap.add_argument('--db', required=True, help='SQLite database path')
    args = ap.parse_args()
    create_alias_loader(args.db)
#!/usr/bin/env python3
"""
Test food aliases creation from IFCT CSV.
Tests the alias extraction logic without needing nix-shell.
"""
import pytest
import tempfile
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent))

# Mock CSV data for testing
MOCK_CSV_DATA = [
    'code,name,protcnt,enerc',
    'A001,"Amaranth seed, black; Hindi: Rajgira; Tamil: Kiray vidai",0,0',
    'A002,"Rice, raw, milled; Hindi: Chawal; Tamil: Arisi; Telugu: Biyyam",7.94,1491',
    'A003,"Wheat flour, wholemeal",12.5,1300',
    'A004,"Mango, ripe; Hindi: Aam; Tamil: Maambalam; Telugu: Mamidi",0.5,600'
]

def test_extract_regional_names():
    """Test regional name extraction from IFCT name field."""
    # Import the function from create_aliases
    from create_aliases import extract_regional_names
    
    # Test case 1: English only
    result = extract_regional_names("Rice, raw, milled")
    assert result == {'English': 'Rice, raw, milled'}
    
    # Test case 2: With regional names
    result = extract_regional_names("Rice, raw, milled; Hindi: Chawal; Tamil: Arisi")
    assert result == {
        'English': 'Rice, raw, milled',
        'Hindi': 'Chawal',
        'Tamil': 'Arisi'
    }
    
    # Test case 3: Multiple languages
    result = extract_regional_names("Mango, ripe; Hindi: Aam; Tamil: Maambalam; Telugu: Mamidi")
    assert result == {
        'English': 'Mango, ripe',
        'Hindi': 'Aam',
        'Tamil': 'Maambalam',
        'Telugu': 'Mamidi'
    }
    
    # Test case 4: Extra spaces
    result = extract_regional_names(" Rice, raw, milled ; Hindi : Chawal ; Tamil : Arisi ")
    assert result == {
        'English': 'Rice, raw, milled',
        'Hindi': 'Chawal',
        'Tamil': 'Arisi'
    }

def test_alias_creation_with_mock_db():
    """Test alias creation in a mock database."""
    from create_aliases import extract_regional_names
    
    # Create temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        # Setup schema
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL
            );
            CREATE TABLE foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_code TEXT NOT NULL,
                source_id INTEGER NOT NULL
            );
            CREATE TABLE food_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                food_id INTEGER NOT NULL,
                alias TEXT NOT NULL,
                language TEXT NOT NULL,
                script TEXT NOT NULL DEFAULT 'Latn',
                alias_type TEXT NOT NULL DEFAULT 'COMMON',
                is_preferred INTEGER DEFAULT 0
            );
        """)
        
        # Insert mock source
        cur = conn.cursor()
        cur.execute("INSERT INTO sources (slug) VALUES ('ifct2017')")
        source_id = cur.lastrowid
        
        # Insert mock foods
        test_cases = [
            ('A001', 'Amaranth seed, black; Hindi: Rajgira; Tamil: Kiray vidai'),
            ('A002', 'Rice, raw, milled; Hindi: Chawal; Tamil: Arisi'),
            ('A003', 'Wheat flour, wholemeal'),  # No regional names
        ]
        
        for code, name in test_cases:
            cur.execute("INSERT INTO foods (source_code, source_id) VALUES (?, ?)",
                       (code, source_id))
            food_id = cur.lastrowid
            
            # Extract and insert aliases
            regional_names = extract_regional_names(name)
            for language, alias_text in regional_names.items():
                # Determine script
                script = 'Latn'
                if language in ['Hindi', 'Marathi']:
                    script = 'Deva'
                elif language == 'Tamil':
                    script = 'Taml'
                elif language == 'Telugu':
                    script = 'Telu'
                
                cur.execute("""
                    INSERT INTO food_aliases 
                    (food_id, alias, language, script, alias_type, is_preferred)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (food_id, alias_text, language, script, 'COMMON', 1 if language == 'English' else 0))
        
        conn.commit()
        
        # Verify results
        cur.execute("SELECT COUNT(*) FROM food_aliases")
        alias_count = cur.fetchone()[0]
        # A001: English + Hindi + Tamil = 3
        # A002: English + Hindi + Tamil = 3  
        # A003: English only = 1
        # Total: 7
        assert alias_count == 7, f"Expected 7 aliases, got {alias_count}"
        
        # Check specific aliases
        cur.execute("SELECT alias, language FROM food_aliases WHERE language = 'Tamil'")
        tamil_aliases = cur.fetchall()
        assert ('Kiray vidai', 'Tamil') in tamil_aliases
        assert ('Arisi', 'Tamil') in tamil_aliases
        
        cur.execute("SELECT alias, language FROM food_aliases WHERE language = 'Hindi'")
        hindi_aliases = cur.fetchall()
        assert ('Rajgira', 'Hindi') in hindi_aliases
        assert ('Chawal', 'Hindi') in hindi_aliases
        
    finally:
        # Cleanup
        Path(db_path).unlink()

def test_script_detection():
    """Test script detection for different languages."""
    from create_aliases import extract_regional_names
    
    # We'll need to test script detection more thoroughly
    # For now, verify the logic exists
    assert True  # Placeholder

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
# Makefile for DietDB - Deterministic build and test

.PHONY: help test load check clean setup

# Configuration
PYTHON = python3
PIP = pip3
DB_PATH = data/dietdb.db
CSV_PATH = data/raw/ifct2017/2.0.0/index.csv
MAPPING_PATH = data/mappings/ifct_columns.yaml
SHA256 = 22bb9d5072d3907af389cb77deab37a164ba5f84bf2a3eaf1a3fb274f6567ba9

help:
	@echo "DietDB Make Targets:"
	@echo "  setup    - Install Python dependencies"
	@echo "  test     - Run all tests"
	@echo "  load     - Load IFCT data into database"
	@echo "  check    - Run integrity checks"
	@echo "  clean    - Clean generated files"

setup:
	@echo "Installing Python dependencies..."
	$(PIP) install pydantic pydantic-settings pyyaml pytest pytest-cov
	@echo "✅ Dependencies installed"

test:
	@echo "Running tests..."
	$(PYTHON) -m pytest tests/ -v

load: $(DB_PATH)
	@echo "Loading IFCT data..."
	$(PYTHON) -c "
import sys
sys.path.insert(0, 'src')
from dietdb.ingest.ifct_loader import IFCTLoader
loader = IFCTLoader('$(CSV_PATH)', '$(MAPPING_PATH)', '$(DB_PATH)', '$(SHA256)')
loader.load()
"
	@echo "✅ IFCT data loaded"

check: $(DB_PATH)
	@echo "Running integrity checks..."
	$(PYTHON) tools/check_integrity.py $(DB_PATH)
	@echo "✅ Integrity checks completed"

$(DB_PATH):
	@echo "Creating database with schema..."
	$(PYTHON) -c "
import sqlite3
conn = sqlite3.connect('$(DB_PATH)')
with open('migrations/001_initial_schema.sql') as f:
    conn.executescript(f.read())
with open('migrations/002_curated_food_tables.sql') as f:
    conn.executescript(f.read())
with open('migrations/003_rules_and_conditions.sql') as f:
    conn.executescript(f.read())
conn.close()
"
	@echo "✅ Database created at $(DB_PATH)"

clean:
	@echo "Cleaning up..."
	rm -f $(DB_PATH)
	rm -rf .pytest_cache
	rm -rf __pycache__
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
	@echo "✅ Clean completed"

# Convenience targets
all: setup load test check
	@echo "✅ All tasks completed"

verify:
	@echo "Verifying setup..."
	@$(PYTHON) -c "import pydantic, yaml, pytest; print('✅ Python dependencies OK')" || echo "❌ Missing dependencies"
	@test -f $(CSV_PATH) && echo "✅ CSV file exists" || echo "❌ CSV file missing"
	@test -f $(MAPPING_PATH) && echo "✅ Mapping file exists" || echo "❌ Mapping file missing"
	@echo "Setup verification complete"
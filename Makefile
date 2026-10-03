# Makefile for DietDB - Deterministic build and test

.PHONY: help test load check clean setup

# Configuration
PYTHON = python
PIP = pip3
DB_PATH = data/diet.db
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
	$(PIP) install -r requirements.txt
	@echo "✅ Dependencies installed"

test:
	@echo "Running tests..."
	$(PYTHON) -m pytest tests/ -v

load:
	@echo "Building IFCT database..."
	PYTHONPATH=src $(PYTHON) -m dietdb build --db $(DB_PATH)

check: $(DB_PATH)
	@echo "Running integrity checks..."
	$(PYTHON) tools/check_integrity.py $(DB_PATH)
	@echo "✅ Integrity checks completed"

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

# DietDB

A diet-planning engine for patients with diet-restricting diseases (Type 2 diabetes, CKD, food allergies, etc.) in India. Built on deterministic database rules and real food composition data.

## Features

- 🍎 **542 Indian foods** from IFCT 2017 with complete nutrition data
- 🧬 **166 mapped nutrients** tracked with measurement status
- ✅ **Deterministic database** - identical inputs produce identical builds (verified by hash)
- 🔍 **No implicit zeros** - missing data is explicitly tracked, never assumed
- 📋 **Declarative rules** - diet rules are data, validated by schema
- 🏥 **Provenance tracking** - every value has a clear source

## Quick Start

### Prerequisites
- Python 3.11+
- nix (optional, for reproducible builds)

### Installation & Build

```bash
# Clone and enter directory
git clone https://github.com/yourusername/dietdb.git
cd dietdb

# Option 1: Using nix (reproducible)
nix-shell
python3 -m dietdb build --db data/diet.db

# Option 2: Using pip
pip install -r requirements.txt
python3 -m dietdb build --db data/diet.db

# Run tests
pytest tests/ -v
```

### Verify Build

```bash
# Build and output hash (should be identical on repeated builds)
python3 -m dietdb build --db data/diet.db --output-hash
```

## Project Structure

```
dietdb/
├── migrations/          # SQL schema migrations (3 files)
├── src/dietdb/
│   ├── __init__.py
│   ├── db.py            # Database manager & migrations
│   ├── models/          # Pydantic data models (5 modules)
│   ├── ingest/          # Data loaders
│   │   └── ifct_loader.py     # IFCT 2017 loader
│   ├── __main__.py      # CLI entry point
│   └── repository.py    # Read-only repository API
├── tests/               # pytest suite
├── docs/                # Documentation
├── data/
│   ├── diet.db          # Built database (572 KB)
│   └── raw/ifct2017/    # Raw downloaded data
├── shell.nix            # Nix reproducible environment
├── pyproject.toml       # Python project config
└── requirements.txt     # Python dependencies
```

## Architecture Overview

This system is designed to support nutrition planning while ensuring all nutrient calculations and safety decisions come from deterministic database rules, not from external sources.

### Key Principles

- **Provenance**: Every nutrient value has a clear source
- **No implicit zeros**: Missing data is explicitly tracked, never treated as zero
- **Deterministic builds**: Same inputs produce identical databases (verified by hash)
- **Auditable rules**: Diet rules are data, not code

## Database Schema

### Core Tables

- **foods** - 542 Indian foods with source codes and food states
- **nutrients** - 166 mapped IFCT columns
- **food_nutrients** - 89,972 nutrient measurements with value status
- **sources** - Data source metadata (IFCT 2017)
- **food_groups** - Food categorization (Cereals, Vegetables, Fruits, Legumes)

### Data Status Tracking

Each nutrient value has a status:
- `MEASURED` - Directly measured
- `TRACE` - Trace amount (0.001)
- `NOT_DETECTED` - Below detection limit
- `NOT_ANALYSED` - Not measured for this food
- `CALCULATED` - Derived from other values

## Data Sources

### IFCT 2017
- **Publisher**: National Institute of Nutrition (NIN), Hyderabad
- **Coverage**: 542 foods commonly consumed in India
- **Nutrients**: Composition data for 166 verified IFCT columns
- **Format**: CSV from `@ifct2017/compositions` 2.0.0 (MIT)
- **Citation**: Longvah T, et al. (2017). Indian Food Composition Tables 2017.

See `docs/data_sources.md` for full attribution.

## API Usage

```python
import sqlite3

# Connect to database
conn = sqlite3.connect("data/diet.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Find foods by name
cursor.execute("SELECT * FROM foods WHERE english_name LIKE ? LIMIT 5", ("%rice%",))
for row in cursor.fetchall():
    print(row["english_name"])

# Get nutrients for a food
cursor.execute("""
    SELECT n.canonical_name, fn.value_canonical, n.canonical_unit
    FROM food_nutrients fn
    JOIN nutrients n ON fn.nutrient_id = n.id
    WHERE fn.food_id = 1
""")
for row in cursor.fetchall():
    print(f"{row['canonical_name']}: {row['value_canonical']} {row['canonical_unit']}")

conn.close()
```

## Development

### Setup

```bash
nix-shell
```

### Run Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=dietdb --cov-report=html

# Specific test
pytest tests/test_schema.py -v
```

### Build Statistics

| Metric | Value |
|--------|-------|
| Foods Loaded | 542 |
| Nutrients | 166 |
| Food-Nutrient Pairs | 89,972 |
| Aliases | 5,405 |
| Schema Migrations | 3 |
| Build Hash | 846b3063... |

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code standards
- Testing requirements
- Pull request process
- Issue reporting guidelines

## License

MIT License - see [LICENSE](LICENSE) for details.

IFCT 2017 (c) National Institute of Nutrition (ICMR), Hyderabad. Electronic storage
for product use requires NIN's written permission (not yet granted).

## Roadmap

- [ ] USDA food composition data
- [ ] Allergen tracking
- [ ] Recipe composition calculation
- [ ] Meal planning API
- [ ] Web interface

## Support

- 📖 [Documentation](docs/)
- 🐛 [Report issues](https://github.com/yourusername/dietdb/issues)
- 💬 [Discussions](https://github.com/yourusername/dietdb/discussions)

## Authors

Created with focus on deterministic, auditable nutrition data for healthcare providers and nutritionists.

---

**Note**: This project is designed for informational purposes. For medical nutrition therapy, consult qualified healthcare providers.

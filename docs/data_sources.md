# Data Sources Documentation

## Primary: IFCT 2017

**Source**: Indian Food Composition Tables 2017, National Institute of Nutrition, Hyderabad

**Machine-Readable**: `@ifct2017/compositions` npm package (nodef/ifct2017)

**Verification Status**: UNVERIFIED_AGAINST_OFFICIAL_SOURCE (IFCT PDF not provided)

**Raw Data Location**: `data/raw/ifct2017/<version>/`

## Parsing Rules

| Source Format | Parsed Value | Status |
|--------------|--------------|--------|
| "12.5" | 12.5 | MEASURED |
| "12.5 ± 1.2" | 12.5, sd=1.2 | MEASURED |
| "Tr" | 0.001 | TRACE |
| "BD" | null | NOT_DETECTED |
| "-" | null | NOT_ANALYSED |

## Curated Data (Empty, To Be Populated)
- Allergen information
- Diet type tags (vegetarian, vegan, Jain)
- Glycemic Index values
- Household measures (katori, roti, glass, tsp)
- Regional prices (INR/kg)
- Preparation effects (nutrient retention)

## Baseline Reference Intakes
ICMR-NIN Recommended Dietary Allowances as BASELINE_DEFAULT rules.

## Open Questions
1. IFCT data license from NIN
2. Official verification against book PDF
3. Allergen assessment methodology
4. Regional price data sources
# CivicLedger

**Sixteen years of the City of Chicago's budget, migrated from 31 inconsistent public files into
one chart-of-accounts warehouse — and reconciled to the cent.**

| | |
|---|---|
| Source files | 31 (adopted ordinance 2011–2026, Mayor's recommendation 2012–2026) |
| Source lines | 119,135 → 243,349 amounts (one per line × measure) |
| Loaded | 243,327 amounts · 1,945 funds · 44 departments · 420 accounts · 18,451 COA keys |
| Control totals (R1) | **61 / 61 file × measure checks reconciled, variance $0.00** |
| Publisher subtotals (R4) | **15 / 15 match the loaded detail to the dollar** |
| Tests | 24, all run on the real data in CI |

Data: [City of Chicago Data Portal](https://data.cityofchicago.org) (Budget – Appropriations and
Budget – Budget Recommendations). Files are stored unchanged in `data/raw/` with a SHA-256 manifest.

---

## The problem

Chicago publishes one file per year and budget stage, and the layout drifts:

- the adopted amount column is called `amount`, `appropriation_ordinance` or `_ordinance_amount_`
  depending on the year;
- the prior-year column is misspelled `appropration` for eight years;
- 2012's recommendation file renames departments and authorities (`org`, `org_description`);
- codes lose their leading zeros (`100` vs `0100`), descriptions change case;
- one file has the publisher's own subtotal rows inside the detail, with "Grand Total" twice.

Load that naively and the 2013 file counts its $8.48 bn prior-year total four times, columns
silently drop to null, and one fund splits into two.

## What CivicLedger does

```
data/raw/*.csv.gz ──► mapping.yaml ──► validation rules ──► DuckDB warehouse ──► reconciliations ──► reports/
 (31 files, as        (source → target,  (VR-01..VR-09,      (dim_fund, dim_department,  (R1 control totals,
  published)           per year)          REJECT/WARN/INFO)    dim_account, dim_coa,       R2 prior-year restatement,
                                                               fact_appropriation)         R3 council changes,
                                                                                           R4 publisher subtotals)
```

1. **Data-gap analysis** — `reports/data_gap_matrix.csv` shows, for every file, which source
   column fed each target field. 14 gaps are documented in [DATA_MAPPING_SPEC.md](docs/DATA_MAPPING_SPEC.md).
2. **Mapping** — all column variants live in [`config/mapping.yaml`](config/mapping.yaml), not in code.
3. **Validation** — 9 rules ([VALIDATION_RULES.md](docs/VALIDATION_RULES.md)); every exception
   names the source file and row.
4. **Reconciliation** — [`sql/reconciliation.sql`](sql/reconciliation.sql):

| Check | Question | Result |
|---|---|---|
| R1 Control totals | Source = loaded + rejected, rows and dollars, per file and measure? | 61/61 reconciled, $0.00 |
| R4 Publisher subtotals | Do the file's own subtotals equal the detail we loaded? | 15/15 match |
| R2 Prior-year restatement | Does year Y+1's "prior appropriation" equal what council adopted for Y? | Local funds: 11/15 years exact. 16 fund-level differences flagged, 12 of them in 2015 (Corporate Fund −$96.8 M). Grant funds never match — grant codes are reissued each year |
| R3 Council changes | Adopted ordinance vs Mayor's recommendation, by department | Council added $317.8 M in 2026; largest single change: Finance General +$163.6 M in 2025 |

## Run it

```bash
pip install -r requirements.txt
python -m civicledger.warehouse      # full run, ~15 s; rewrites reports/
python -m pytest                     # 24 tests
python scripts/fetch_chicago.py      # (optional) re-download the source files
```

## Reports

| File | For |
|---|---|
| `reports/summary.json` | Headline numbers |
| `reports/reconciliation_control.csv` | R1, per file × measure |
| `reports/embedded_totals_check.csv` | R4 |
| `reports/prior_year_by_fund_type.csv`, `prior_year_check.csv` | R2, summary and per fund |
| `reports/council_changes.csv` | R3 |
| `reports/exceptions.csv` | Every rule hit, with source file and row |
| `reports/data_gap_matrix.csv` | Source column used for each target field, per file |

## Documents

- [Functional specification](docs/FUNCTIONAL_SPEC.md) — scope, stakeholders, requirements FR-01..FR-11
- [Data mapping specification](docs/DATA_MAPPING_SPEC.md) — gap analysis and field mapping
- [Validation rules](docs/VALIDATION_RULES.md)
- [UAT test cases](docs/UAT_TEST_CASES.md) — 22 cases traced to requirements and tests

## Stack

Python · pandas · DuckDB (SQL) · YAML · pytest · GitHub Actions

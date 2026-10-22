# Functional Specification — CivicLedger

## 1. Purpose

The City of Chicago publishes its annual budget appropriations as 31 separate files (adopted
ordinance 2011–2026, Mayor's recommendation 2012–2026). The layout changes over the years:
columns are renamed, misspelled, added and dropped; codes lose their leading zeros; descriptions
change case; and some files carry the publisher's own subtotal rows in the detail.

CivicLedger migrates all 31 files into one chart-of-accounts warehouse **without losing or
inventing a dollar**, and proves it with reconciliations a reviewer can re-run.

## 2. Scope

| In scope | Out of scope |
|---|---|
| Appropriations (budgeted amounts), all funds, all departments | Actual spending, revenue, positions/salaries files |
| Adopted ordinance and Mayor's recommendation | Mid-year amendments |
| Data-gap analysis, mapping, validation, reconciliation | Dashboards (reports are CSV for Excel / BI tools) |

## 3. Stakeholders and their questions

| Stakeholder | Question the system answers | Report |
|---|---|---|
| Data migration lead | Did every source dollar land in the warehouse? | `reconciliation_control.csv` |
| Budget analyst | Does next year's "prior appropriation" restate what council adopted? | `prior_year_by_fund_type.csv`, `prior_year_check.csv` |
| Policy analyst | What did City Council change from the Mayor's recommendation? | `council_changes.csv` |
| Data steward | Which rows broke a rule, and where are they in the raw file? | `exceptions.csv` |
| Business analyst | Which source column fed each target field, per year? | `data_gap_matrix.csv` |

## 4. Functional requirements

| ID | Requirement | Verified by |
|---|---|---|
| FR-01 | Fetch every file in `config/sources.json` from the official API, store it unchanged, and record row count and SHA-256 in a manifest | `scripts/fetch_chicago.py`, UT-17 |
| FR-02 | Map each file's columns to the canonical model using `config/mapping.yaml`; no column names hard-coded in code | UT-01..UT-03 |
| FR-03 | Normalise codes (zero-pad, keep alphanumeric grant codes) and descriptions (case, spacing, "2005 - " prefixes) | UT-04..UT-07 |
| FR-04 | Parse amounts in every format present; never coerce an unparseable value to zero | UT-08, VR-03 |
| FR-05 | Apply validation rules VR-01..VR-09; REJECT rows are kept out of the warehouse, WARN/INFO rows are loaded; every exception names the source file and row | UT-09..UT-16 |
| FR-06 | Build a dimensional model: `dim_fund`, `dim_department`, `dim_account`, `dim_coa`, `fact_appropriation` | `sql/warehouse.sql` |
| FR-07 | R1: per file and measure, source = loaded + rejected, rows and dollars, zero variance | UT-18 |
| FR-08 | R4: every publisher subtotal row equals the sum of the loaded detail it covers | UT-19 |
| FR-09 | R2: compare each year's adopted ordinance with the next year's restated prior appropriation, by fund type and by fund | `prior_year_*.csv` |
| FR-10 | R3: Mayor's recommendation vs adopted ordinance, by year and department | `council_changes.csv` |
| FR-11 | One command re-runs everything and rewrites every report; CI runs it on every change | `python -m civicledger.warehouse`, `.github/workflows/ci.yml` |

## 5. Canonical data model

One row per **source line × measure**, so a proposed-budget line (which carries three amounts)
becomes three facts and every fact keeps `source_file` + `source_row`.

| Field | Type | Notes |
|---|---|---|
| fiscal_year | int | from `config/sources.json` |
| stage | adopted / proposed | |
| measure | ordinance / recommendation / prior_appropriation / prior_revised | |
| fund_type | LOCAL / GRANTS / CDBG | |
| fund_code | char(4) | alphanumeric, e.g. `0100`, `0K38` |
| department_code | char(3) | |
| authority_code | char(4) | `0000` in the COA key where absent |
| account_code | char(4) | alphanumeric, e.g. `0005`, `909A` |
| amount | decimal | USD |
| coa_key | text | `fund-department-authority-account` |

See [DATA_MAPPING_SPEC.md](DATA_MAPPING_SPEC.md) for the field-by-field, year-by-year mapping and
[VALIDATION_RULES.md](VALIDATION_RULES.md) for the rules.

# Data Mapping Specification

Source: City of Chicago Data Portal, "Budget – Appropriations" (adopted ordinance) and
"Budget – Budget Recommendations" (proposed) datasets, 2011–2026. Dataset IDs are in
`config/sources.json`; the machine-readable mapping is `config/mapping.yaml`; the per-file result
of applying it is `reports/data_gap_matrix.csv`.

## 1. Data-gap analysis — what changes between years

| # | Gap found in the source | Years | Treatment |
|---|---|---|---|
| G1 | The adopted amount column has three names: `amount`, `appropriation_ordinance`, `_ordinance_amount_` | 2011 / 2013 / 2012, 2014–2026 | All mapped to measure `ordinance` |
| G2 | Prior-year column spelled `appropration` (typo) | proposed 2013–2020 | Mapped to `prior_appropriation` |
| G3 | Underscore-prefixed names `_appropriation`, `_revised_appropriation`, `_recommendation` | proposed 2012 | Mapped to the same measures |
| G4 | `department_code` instead of `department_number`; `org` / `org_description` instead of `appropriation_authority*` | proposed 2012 | Mapped to `department_code`, `authority_code`, `authority_description` |
| G5 | Extra 2-letter `department` abbreviation column | adopted 2011 | Not mapped (no later year carries it); listed as unmapped |
| G6 | Codes without leading zeros: fund `100` vs `0100`, account `5` vs `0005` | varies | Compared numerically, stored zero-padded (4/3/4/4) |
| G7 | Alphanumeric codes: grant funds (`0K38`, `925F`), sub-accounts (`909A`) | all | Kept as-is; format rule VR-06 accepts `[0-9A-Z]` |
| G8 | Description case and spacing differ ("Corporate Fund" / "CORPORATE FUND") | varies | Upper-cased, whitespace collapsed |
| G9 | Authority descriptions sometimes prefixed with their code ("2005 - POLICE BOARD") | varies | Prefix stripped |
| G10 | `fund_type` case differs (`Local` / `LOCAL`) | varies | Upper-cased |
| G11 | Publisher subtotal rows inside the detail ("LOCAL Total", "Grand Total" twice) | proposed 2013 | Rejected (VR-09), reused as a control total (R4) |
| G12 | Fully blank rows | proposed 2012 (2 rows) | Rejected (VR-01) |
| G13 | One line with no recommendation amount | proposed 2025 | Loaded without that measure, flagged (VR-04) |
| G14 | Amounts as `145000.00` and as integers | varies | Parsed to decimal; unparseable values rejected (VR-03), never zeroed |

## 2. Field mapping

| Target field | Source column(s), first present wins | Transformation |
|---|---|---|
| fund_type | `fund_type` | upper-case |
| fund_code | `fund_code` | zero-pad to 4 |
| fund_description | `fund_description` | upper-case, collapse spaces |
| department_code | `department_number`, `department_code` | zero-pad to 3 |
| department_description | `department_description` | upper-case |
| authority_code | `appropriation_authority`, `org` | zero-pad to 4 |
| authority_description | `appropriation_authority_description`, `org_description` | upper-case, strip "NNNN - " |
| account_code | `appropriation_account` | zero-pad to 4 |
| account_description | `appropriation_account_description` | upper-case |
| **ordinance** (adopted) | `amount`, `_ordinance_amount_`, `appropriation_ordinance` | decimal |
| **recommendation** (proposed) | `recommendation`, `_recommendation` | decimal |
| **prior_appropriation** (proposed) | `appropriation`, `appropration`, `_appropriation` | decimal |
| **prior_revised** (proposed) | `revised_appropriation`, `_revised_appropriation` | decimal |

## 3. Chart-of-accounts key

`coa_key = fund_code-department_code-authority_code-account_code`, e.g. `0100-057-2005-0005`
(Corporate Fund · Police · authority 2005 · salaries). 18,451 distinct keys across 2011–2026.

## 4. Dimensions

When a code's description changed over the years, the dimension keeps the **latest** name and
VR-08 lists every historical name (398 codes), so nothing is silently overwritten.

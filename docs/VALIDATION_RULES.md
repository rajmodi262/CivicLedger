# Validation Rules

Implemented in `civicledger/rules.py`. Each exception in `reports/exceptions.csv` carries the rule,
severity, source file and 1-based source row, so a reviewer can open the raw file and check it.

| Severity | Action |
|---|---|
| REJECT | Kept out of the warehouse; its dollars are counted in the R1 "rejected" column so the file still balances |
| WARN | Loaded; listed for review |
| INFO | Loaded; documents a mapping decision |

| Rule | Check | Severity | Result on the 2011–2026 data |
|---|---|---|---|
| VR-01 | Every column of the source row is empty | REJECT | 2 rows (6 measure values), proposed 2012 |
| VR-02 | Fund, department or account code missing | REJECT | 0 |
| VR-03 | Amount present but not numeric | REJECT | 0 |
| VR-04 | Amount missing for a measure the file should carry | WARN | 1 (proposed 2025, recommendation) |
| VR-05 | Negative amount | WARN | 1,111 values, mostly 2011–2012 and 2025–2026; listed for review |
| VR-06 | Code not in the COA format (fund 4, department 3 digits, authority 4, account 4; alphanumeric) | WARN | 0 after normalisation |
| VR-07 | Same COA key twice within one file and measure | WARN | 0 |
| VR-08 | Same fund/department code, different description across years | INFO | 398 codes |
| VR-09 | Publisher subtotal row ("LOCAL Total", "Grand Total") in the detail | REJECT | 5 rows (15 values), proposed 2013 — reused as control totals in R4 |

## How a rule was found, not assumed

VR-09 did not exist in the first design. The first run rejected 5 rows of the 2013 proposed file
under VR-02 (codes missing). Opening those rows showed they were the publisher's own subtotals,
with "Grand Total" printed twice. Loading them would have counted the file's $8.48 bn
prior-year total four times (detail + fund-type subtotals + two grand totals); rejecting
them as generic bad rows would have thrown away a free control. They now have their own rule and
are checked against the detail in R4 — all 15 match to the dollar.

Likewise VR-06 first flagged 79,058 values as "non-numeric codes". Profiling showed these were
real Chicago grant-fund and sub-account codes (`0K38`, `925F`, `909A`), so the rule was changed to
a format check and the finding went into the mapping spec (G7).

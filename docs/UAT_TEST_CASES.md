# UAT Test Cases

All cases are automated (`python -m pytest`, 24 tests) and run in CI on every change.

| ID | Requirement | Given / When / Then | Test |
|---|---|---|---|
| UT-01 | FR-02 | Given an adopted file with `amount`, `_ordinance_amount_` or `appropriation_ordinance`, the column maps to `ordinance` | `test_amount_column_resolved_per_year` |
| UT-02 | FR-02 | Given the misspelled `appropration`, it maps to `prior_appropriation` | `test_misspelled_prior_year_column_is_mapped` |
| UT-03 | FR-02 | Given 2012's `org` / `org_description`, they map to the authority fields | `test_2012_proposed_org_columns_feed_authority` |
| UT-04 | FR-03 | `100`, `0100` and `100.0` normalise to the same fund `0100` | `test_codes_zero_padded_and_compared_numerically` |
| UT-05 | FR-03 | Alphanumeric codes `0K38`, `909A` are kept | `test_alphanumeric_codes_kept` |
| UT-06 | FR-03 | "Corporate Fund" and "CORPORATE  FUND" normalise to the same text | `test_text_normalised_for_case_and_spacing` |
| UT-07 | FR-03 | "2005 - Police Board" becomes "POLICE BOARD" | `test_authority_description_prefix_stripped` |
| UT-08 | FR-04 | `145000.00`, `$1,234.50`, `-500` parse; blank is missing; `N/A` is flagged, not zero | `test_amount_parsing` |
| UT-09 | FR-05 | A clean line loads with no exceptions | `test_clean_row_loads_with_no_exceptions` |
| UT-10..15 | FR-05 | A planted bad line fires VR-01, 02, 03, 04, 05, 06, 09 and is rejected or loaded per severity | `test_rule_fires_and_routes` (7 cases) |
| UT-16 | FR-05 | The same COA key twice in one file fires VR-07; a renamed fund fires VR-08 as INFO | `test_duplicate_key_…`, `test_description_drift_…` |
| UT-17 | FR-01 | All 31 manifest files load; source lines = manifest row total (119,135) | `test_every_file_in_manifest_is_loaded` |
| UT-18 | FR-07 | Every file × measure reconciles: 61/61, variance $0.00 | `test_control_totals_reconcile_to_the_cent` |
| UT-19 | FR-08 | Every publisher subtotal equals the loaded detail: 15/15 | `test_publisher_subtotals_match_loaded_detail` |
| UT-20 | FR-04/05 | No unparseable amounts and no missing codes in the real data | `test_no_unparseable_amounts_or_missing_codes` |
| UT-21 | FR-03 | Every code conforms to the COA format after normalisation | `test_codes_conform_to_chart_of_accounts_format` |
| UT-22 | FR-11 | Every report is written and non-empty | `test_reports_written` |

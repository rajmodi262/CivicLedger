"""End-to-end on the committed City of Chicago files (UAT cases UT-17..UT-22).

These assert the acceptance criteria in docs/UAT_TEST_CASES.md against the real data.
"""

import json

import pytest

from civicledger import RAW
from civicledger.warehouse import run


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp("reports")
    summary = run(out, db_path=":memory:")
    return summary, out


def test_every_file_in_manifest_is_loaded(result):
    summary, _ = result
    manifest = json.loads((RAW / "MANIFEST.json").read_text(encoding="utf-8"))
    assert summary["files"] == len(manifest["files"]) == 31
    assert summary["source_lines"] == sum(f["rows"] for f in manifest["files"])


def test_control_totals_reconcile_to_the_cent(result):
    summary, _ = result
    assert summary["control_reconciled"] == summary["control_checks"]
    assert summary["max_abs_variance"] == 0.0


def test_publisher_subtotals_match_loaded_detail(result):
    summary, _ = result
    assert summary["embedded_total_checks"] > 0
    assert summary["embedded_total_matches"] == summary["embedded_total_checks"]


def test_no_unparseable_amounts_or_missing_codes(result):
    summary, _ = result
    assert not any(k.startswith(("VR-02", "VR-03")) for k in summary["exceptions_by_rule"])


def test_codes_conform_to_chart_of_accounts_format(result):
    summary, _ = result
    assert not any(k.startswith("VR-06") for k in summary["exceptions_by_rule"])


def test_reports_written(result):
    _, out = result
    for name in ["reconciliation_control.csv", "prior_year_by_fund_type.csv", "prior_year_check.csv",
                 "embedded_totals_check.csv", "council_changes.csv", "exceptions.csv",
                 "data_gap_matrix.csv", "summary.json"]:
        assert (out / name).stat().st_size > 0, name

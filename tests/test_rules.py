"""Each validation rule fires on a planted bad row and stays silent on a clean one (UAT cases UT-09..UT-16)."""

import pandas as pd
import pytest

from civicledger.ingest import parse_amount
from civicledger.rules import validate


def row(**overrides):
    base = {
        "fiscal_year": 2025, "stage": "adopted", "source_file": "t.csv", "source_row": 1, "measure": "ordinance",
        "fund_type": "LOCAL", "fund_code": "0100", "fund_description": "CORPORATE FUND",
        "department_code": "057", "department_description": "CHICAGO POLICE DEPARTMENT",
        "authority_code": "2005", "authority_description": "POLICE", "account_code": "0005",
        "account_description": "SALARIES", "raw_amount": "1000", "blank_row": False,
    }
    base.update(overrides)
    base["amount"] = parse_amount(base["raw_amount"])
    return base


def run(*rows):
    df = pd.DataFrame([{**r, "source_row": i} for i, r in enumerate(rows, start=1)])
    return validate(df)


def rules_fired(exceptions):
    return set(exceptions["rule_id"]) if not exceptions.empty else set()


def test_clean_row_loads_with_no_exceptions():
    loaded, exc = run(row())
    assert len(loaded) == 1 and exc.empty


@pytest.mark.parametrize("bad, rule, rejected", [
    (row(blank_row=True, fund_code=None, department_code=None, account_code=None, raw_amount=""), "VR-01", True),
    (row(department_code=None), "VR-02", True),
    (row(raw_amount="twelve"), "VR-03", True),
    (row(raw_amount=""), "VR-04", False),
    (row(raw_amount="-250"), "VR-05", False),
    (row(fund_code="01-0"), "VR-06", False),
    (row(fund_type="GRAND TOTAL", fund_code=None, department_code=None, account_code=None), "VR-09", True),
])
def test_rule_fires_and_routes(bad, rule, rejected):
    loaded, exc = run(row(), bad)
    assert rule in rules_fired(exc)
    assert len(loaded) == (1 if rejected else 2)


def test_duplicate_key_in_one_file_is_flagged():
    _, exc = run(row(), row())
    assert "VR-07" in rules_fired(exc)


def test_description_drift_across_years_is_info():
    _, exc = run(row(), row(fiscal_year=2024, fund_description="GENERAL FUND", department_code="058"))
    drift = exc[exc["rule_id"] == "VR-08"]
    assert len(drift) == 1 and drift.iloc[0]["severity"] == "INFO"

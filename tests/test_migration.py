"""
Unit and Integration Tests for CivicLedger Municipal Migration Engine
Tests COA parsing, schema bounds, and trial balance reconciliation fidelity.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.coa_mapper import ChartOfAccountsMapper, COASegmentError
from src.etl_pipeline import MunicipalMigrationEngine

def test_coa_valid_parsing():
    raw = "100-20-2010-52100-000"
    res = ChartOfAccountsMapper.parse_legacy_string(raw)
    assert res["fund_code"] == "100"
    assert res["fund_name"] == "General Fund"
    assert res["department_code"] == "20"
    assert res["account_type"] == "EXPENDITURE"
    assert res["project_code"] is None

def test_coa_dot_delimited():
    raw = "500.30.3020.41000.PRJ01"
    res = ChartOfAccountsMapper.parse_legacy_string(raw)
    assert res["fund_code"] == "500"
    assert res["fund_name"] == "Water & Sewer Utility Enterprise Fund"
    assert res["account_type"] == "REVENUE"
    assert res["project_code"] == "PRJ01"

def test_coa_invalid_length_raises():
    with pytest.raises(COASegmentError):
        ChartOfAccountsMapper.parse_legacy_string("100-20-30")

def test_municipal_migration_and_reconciliation():
    engine = MunicipalMigrationEngine()
    
    sample_records = [
        {"account_string": "100-10-1010-51000-000", "department_name": "Police Dept", "fiscal_year": 2025, "budget_amount": 1500000.0, "actual_amount": 1420000.0},
        {"account_string": "100-20-2010-51000-000", "department_name": "Fire & Rescue", "fiscal_year": 2025, "budget_amount": 950000.0, "actual_amount": 935000.0},
        {"account_string": "200-40-4010-53000-GRT01", "department_name": "Parks & Recreation", "fiscal_year": 2025, "budget_amount": 350000.0, "actual_amount": 310000.0},
        {"account_string": "500-30-3010-41000-000", "department_name": "Water Utilities", "fiscal_year": 2025, "budget_amount": 2800000.0, "actual_amount": 2850000.0},
    ]

    summary = engine.ingest_records(sample_records)
    assert summary["migrated_records"] == 4
    assert summary["total_budget_staged"] == 5600000.0
    assert summary["distinct_funds"] == 3
    assert summary["distinct_departments"] == 4

    df = engine.execute_reconciliation()
    assert len(df) == 3
    assert df[df["fund_code"] == "100"]["total_budget"].iloc[0] == 2450000.0
    assert df[df["fund_code"] == "500"]["total_budget"].iloc[0] == 2800000.0

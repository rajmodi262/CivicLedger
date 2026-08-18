"""
CivicLedger - Municipal Budget ETL & Automated Reconciliation Pipeline
Ingests municipal budget datasets (e.g. City of Austin / Chicago open data),
normalizes COA schemas into DuckDB/PostgreSQL, and executes trial balance reconciliation.
"""

import os
import csv
import json
import duckdb
import pandas as pd
from typing import Dict, Any, List, Tuple
from .coa_mapper import ChartOfAccountsMapper

class MunicipalMigrationEngine:
    def __init__(self, db_path: str = ":memory:"):
        self.con = duckdb.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        """Initializes normalized municipal staging schema."""
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS dim_fund (
                id INTEGER PRIMARY KEY,
                fund_code VARCHAR(10) UNIQUE,
                fund_name VARCHAR(100),
                fund_category VARCHAR(50)
            );

            CREATE TABLE IF NOT EXISTS dim_department (
                id INTEGER PRIMARY KEY,
                department_code VARCHAR(10) UNIQUE,
                department_name VARCHAR(100)
            );

            CREATE TABLE IF NOT EXISTS dim_chart_of_accounts (
                id INTEGER PRIMARY KEY,
                account_key VARCHAR(50) UNIQUE,
                fund_id INTEGER,
                department_id INTEGER,
                division_code VARCHAR(20),
                object_code VARCHAR(20),
                account_type VARCHAR(30)
            );

            CREATE TABLE IF NOT EXISTS gl_entry_staging (
                entry_id INTEGER PRIMARY KEY,
                batch_id VARCHAR(50),
                coa_id INTEGER,
                fiscal_year INTEGER,
                budget_amount DOUBLE,
                revised_amount DOUBLE,
                actual_amount DOUBLE
            );
        """)

    def ingest_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Processes and stages raw municipal budget rows.
        Enforces validation rules, maps COA dimensions, and records totals.
        """
        migrated_count = 0
        total_budget = 0.0
        total_actual = 0.0
        fund_map = {}
        dept_map = {}
        coa_map = {}

        for i, rec in enumerate(records, start=1):
            coa = ChartOfAccountsMapper.parse_legacy_string(rec["account_string"])
            
            # Upsert Fund
            f_code = coa["fund_code"]
            if f_code not in fund_map:
                f_id = len(fund_map) + 1
                fund_map[f_code] = f_id
                self.con.execute(
                    "INSERT INTO dim_fund VALUES (?, ?, ?, ?)",
                    [f_id, f_code, coa["fund_name"], coa["fund_category"]]
                )
            f_id = fund_map[f_code]

            # Upsert Dept
            d_code = coa["department_code"]
            if d_code not in dept_map:
                d_id = len(dept_map) + 1
                dept_map[d_code] = d_id
                d_name = rec.get("department_name", f"Department {d_code}")
                self.con.execute(
                    "INSERT INTO dim_department VALUES (?, ?, ?)",
                    [d_id, d_code, d_name]
                )
            d_id = dept_map[d_code]

            # Upsert COA
            acc_key = coa["raw_account_string"]
            if acc_key not in coa_map:
                c_id = len(coa_map) + 1
                coa_map[acc_key] = c_id
                self.con.execute(
                    "INSERT INTO dim_chart_of_accounts VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [c_id, acc_key, f_id, d_id, coa["division_code"], coa["object_code"], coa["account_type"]]
                )
            c_id = coa_map[acc_key]

            # Insert GL Entry
            b_amt = float(rec.get("budget_amount", 0.0))
            r_amt = float(rec.get("revised_amount", b_amt))
            a_amt = float(rec.get("actual_amount", 0.0))

            self.con.execute(
                "INSERT INTO gl_entry_staging VALUES (?, ?, ?, ?, ?, ?, ?)",
                [i, rec.get("batch_id", "MIG_2025_BATCH_1"), c_id, int(rec.get("fiscal_year", 2025)), b_amt, r_amt, a_amt]
            )
            migrated_count += 1
            total_budget += b_amt
            total_actual += a_amt

        return {
            "migrated_records": migrated_count,
            "total_budget_staged": round(total_budget, 2),
            "total_actual_staged": round(total_actual, 2),
            "distinct_funds": len(fund_map),
            "distinct_departments": len(dept_map),
            "distinct_accounts": len(coa_map),
            "status": "SUCCESS"
        }

    def execute_reconciliation(self) -> pd.DataFrame:
        """Runs the trial balance reconciliation query comparing staged entries."""
        query = """
            SELECT 
                f.fund_code,
                f.fund_name,
                f.fund_category,
                gl.fiscal_year,
                COUNT(*) AS line_items,
                ROUND(SUM(gl.budget_amount), 2) AS total_budget,
                ROUND(SUM(gl.actual_amount), 2) AS total_actual
            FROM gl_entry_staging gl
            JOIN dim_chart_of_accounts coa ON gl.coa_id = coa.id
            JOIN dim_fund f ON coa.fund_id = f.id
            GROUP BY f.fund_code, f.fund_name, f.fund_category, gl.fiscal_year
            ORDER BY total_budget DESC
        """
        return self.con.execute(query).df()

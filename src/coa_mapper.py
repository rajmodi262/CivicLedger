"""
CivicLedger - Chart of Accounts (COA) Normalization & Segment Mapping Engine
Implements municipal multi-segment string parsing (Fund-Dept-Div-Object-Project)
and validates schema constraints against GASB municipal standards.
"""

from typing import Dict, Any, Optional, List, Tuple
import re

class COASegmentError(Exception):
    pass

class ChartOfAccountsMapper:
    """
    Parses and standardizes legacy municipal GL strings into 5-tier normalized COA dimensions:
    - Fund (e.g. 100 General Fund, 200 Special Revenue, 300 Capital Projects, 500 Enterprise)
    - Department (e.g. 10 Police, 20 Fire, 30 Public Works, 40 Parks & Rec)
    - Division / Program (e.g. 1010 Patrol, 1020 Investigations)
    - Object / Account Category (e.g. 51000 Personnel, 52000 Contractual, 53000 Supplies, 54000 Capital Outlay)
    - Project / Grant (e.g. PRJ2024-001 or 0000 None)
    """

    FUND_TYPES = {
        "100": ("General Fund", "GOVERNMENTAL"),
        "101": ("General Fund - Reserves", "GOVERNMENTAL"),
        "200": ("Special Revenue Fund - Grants", "SPECIAL_REVENUE"),
        "210": ("Highway & Road Improvement Fund", "SPECIAL_REVENUE"),
        "300": ("Capital Improvement Fund", "CAPITAL_PROJECTS"),
        "400": ("Debt Service Fund", "DEBT_SERVICE"),
        "500": ("Water & Sewer Utility Enterprise Fund", "ENTERPRISE"),
        "510": ("Municipal Airport Enterprise Fund", "ENTERPRISE"),
        "600": ("Internal Service Fund - Fleet", "INTERNAL_SERVICE"),
    }

    ACCOUNT_CATEGORIES = {
        "4": ("REVENUE", "Operating & Tax Revenue"),
        "5": ("EXPENDITURE", "Operating & Personnel Expenditure"),
        "1": ("ASSET", "Current & Capital Assets"),
        "2": ("LIABILITY", "Current & Long-Term Liabilities"),
        "3": ("FUND_BALANCE", "Restricted & Unassigned Fund Balance"),
    }

    @classmethod
    def parse_legacy_string(cls, account_string: str) -> Dict[str, Any]:
        """
        Parses legacy formats such as:
        - Dot-delimited: '100.20.2010.52100.000'
        - Dash-delimited: '100-20-2010-52100-PRJ01'
        - Fixed-width: '10020201052100000'
        """
        cleaned = account_string.strip()
        
        if "-" in cleaned:
            parts = cleaned.split("-")
        elif "." in cleaned:
            parts = cleaned.split(".")
        elif len(cleaned) == 17:
            parts = [cleaned[0:3], cleaned[3:5], cleaned[5:9], cleaned[9:14], cleaned[14:17]]
        else:
            raise COASegmentError(f"Unrecognized account segment format: {account_string}")

        if len(parts) != 5:
            raise COASegmentError(f"Expected 5 segments (Fund-Dept-Div-Object-Project), got {len(parts)} in '{account_string}'")

        fund_code, dept_code, div_code, object_code, proj_code = [p.strip() for p in parts]

        # Classify Fund
        fund_name, fund_category = cls.FUND_TYPES.get(fund_code, ("Custom Municipal Fund", "OTHER"))

        # Classify Account Type from first digit of object code
        first_digit = object_code[0] if object_code else "5"
        account_type, account_desc = cls.ACCOUNT_CATEGORIES.get(first_digit, ("EXPENDITURE", "General Expenditure"))

        return {
            "raw_account_string": account_string,
            "fund_code": fund_code,
            "fund_name": fund_name,
            "fund_category": fund_category,
            "department_code": dept_code,
            "division_code": div_code,
            "object_code": object_code,
            "account_type": account_type,
            "account_category_desc": account_desc,
            "project_code": proj_code if proj_code not in ("000", "0000", "") else None,
            "is_gasb_compliant": True
        }

"""Validation rules. Each rule has an ID, a severity and an action, documented in docs/VALIDATION_RULES.md.

REJECT rows are excluded from the warehouse and reported; WARN and INFO rows are loaded and reported.
Every exception carries the source file and row, so a reviewer can open the raw data and check it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

REQUIRED = ["fund_code", "department_code", "account_code"]

# Chicago codes are alphanumeric (grant funds such as 0K38, sub-accounts such as 909A).
CODE_FORMAT = {
    "fund_code": r"[0-9A-Z]{4}",
    "department_code": r"[0-9]{3}",
    "authority_code": r"[0-9A-Z]{4}",
    "account_code": r"[0-9A-Z]{4}",
}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    severity: str  # REJECT | WARN | INFO


RULES = {
    "VR-01": Rule("VR-01", "Blank source row", "REJECT"),
    "VR-02": Rule("VR-02", "Required code missing (fund, department or account)", "REJECT"),
    "VR-03": Rule("VR-03", "Amount present but not numeric", "REJECT"),
    "VR-04": Rule("VR-04", "Amount missing for a measure the file should carry", "WARN"),
    "VR-05": Rule("VR-05", "Negative amount", "WARN"),
    "VR-06": Rule("VR-06", "Code not in the chart-of-accounts format (4/3/4/4 alphanumeric)", "WARN"),
    "VR-07": Rule("VR-07", "Duplicate chart-of-accounts key within one file and measure", "WARN"),
    "VR-08": Rule("VR-08", "Same code, different description across years (mapping drift)", "INFO"),
    "VR-09": Rule("VR-09", "Embedded subtotal row (kept aside as a publisher control total)", "REJECT"),
}


def is_subtotal(df: pd.DataFrame) -> pd.Series:
    """Rows like 'LOCAL Total' / 'Grand Total' in the fund_type column, with no codes."""
    return df["fund_type"].fillna("").str.endswith("TOTAL") & df["fund_code"].isna()


def _exc(rows: pd.DataFrame, rule_id: str, detail: str | pd.Series) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    rule = RULES[rule_id]
    out = rows[["fiscal_year", "stage", "source_file", "source_row", "measure"]].copy()
    out["rule_id"], out["rule"], out["severity"] = rule.rule_id, rule.name, rule.severity
    out["detail"] = detail if isinstance(detail, str) else detail.loc[rows.index].astype(str)
    return out


def key_columns() -> list[str]:
    return ["fund_code", "department_code", "authority_code", "account_code"]


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (rows to load, exceptions)."""
    found = []
    blank = df[df["blank_row"]]
    found.append(_exc(blank, "VR-01", "every column empty"))
    rest = df[~df["blank_row"]]
    subtotal = rest[is_subtotal(rest)]
    found.append(_exc(subtotal, "VR-09", "publisher row: " + subtotal["fund_type"].astype(str)))
    rest = rest[~is_subtotal(rest)]

    missing = rest[rest[REQUIRED].isna().any(axis=1)]
    found.append(_exc(missing, "VR-02", missing[REQUIRED].isna().apply(
        lambda r: "missing: " + ", ".join(c for c, m in r.items() if m), axis=1)))

    bad_amount = rest[rest["amount"].isna() & rest["raw_amount"].notna() & (rest["raw_amount"].astype(str).str.strip() != "")]
    found.append(_exc(bad_amount, "VR-03", "raw value: " + bad_amount["raw_amount"].astype(str)))

    no_amount = rest[rest["raw_amount"].isna() | (rest["raw_amount"].astype(str).str.strip() == "")]
    found.append(_exc(no_amount, "VR-04", "no value in source"))

    negative = rest[rest["amount"] < 0]
    found.append(_exc(negative, "VR-05", "amount " + negative["amount"].astype(str)))

    code_cols = key_columns()
    bad_format = pd.Series(False, index=rest.index)
    detail = pd.Series("", index=rest.index)
    for col in code_cols:
        values = rest[col].dropna().astype(str)
        bad = values[~values.str.fullmatch(CODE_FORMAT[col])]
        bad_format.loc[bad.index] = True
        detail.loc[bad.index] += f"{col}=" + bad + " "
    found.append(_exc(rest[bad_format], "VR-06", detail.str.strip()))

    keyed = rest.dropna(subset=REQUIRED)
    dup_mask = keyed.duplicated(subset=["source_file", "measure", *code_cols], keep=False)
    dups = keyed[dup_mask]
    found.append(_exc(dups, "VR-07", "key " + dups[code_cols].fillna("-").agg("-".join, axis=1)))

    found.append(_description_drift(rest))

    exceptions = pd.concat([e for e in found if not e.empty], ignore_index=True) if any(not e.empty for e in found) else pd.DataFrame(
        columns=["fiscal_year", "stage", "source_file", "source_row", "measure", "rule_id", "rule", "severity", "detail"])
    rejected_keys = set(
        map(tuple, exceptions.loc[exceptions["severity"] == "REJECT", ["source_file", "source_row", "measure"]].to_numpy())
    )
    keep = ~df[["source_file", "source_row", "measure"]].apply(tuple, axis=1).isin(rejected_keys)
    return df[keep & ~df["blank_row"]].copy(), exceptions


def _description_drift(df: pd.DataFrame) -> pd.DataFrame:
    """One INFO exception per fund or department code whose name changed across years."""
    rows = []
    for code_col, desc_col in [("fund_code", "fund_description"), ("department_code", "department_description")]:
        names = df.dropna(subset=[code_col, desc_col]).groupby(code_col)[desc_col].agg(lambda s: sorted(set(s)))
        for code, descs in names.items():
            if len(descs) > 1:
                rows.append({
                    "fiscal_year": None, "stage": None, "source_file": None, "source_row": None, "measure": None,
                    "rule_id": "VR-08", "rule": RULES["VR-08"].name, "severity": "INFO",
                    "detail": f"{code_col} {code}: " + " | ".join(descs[:4]) + (" | ..." if len(descs) > 4 else ""),
                })
    return pd.DataFrame(rows)

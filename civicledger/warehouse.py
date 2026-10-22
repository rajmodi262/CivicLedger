"""Load validated rows into DuckDB, run the reconciliations, and write every report.

    python -m civicledger.warehouse          # full run over data/raw -> reports/
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

from civicledger import REPORTS, ROOT
from civicledger.ingest import Mapping, gap_matrix, load_all
from civicledger.rules import RULES, validate

SQL = ROOT / "sql"


def named_queries(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^-- name: (\w+)\s*$", text, flags=re.MULTILINE)
    return {parts[i]: parts[i + 1].strip().rstrip(";") for i in range(1, len(parts), 2)}


def build(df: pd.DataFrame, db_path: str = ":memory:") -> tuple[duckdb.DuckDBPyConnection, pd.DataFrame]:
    loaded, exceptions = validate(df)
    rejected_keys = exceptions.loc[exceptions["severity"] == "REJECT", ["source_file", "source_row", "measure"]].drop_duplicates()
    rejected = df.merge(rejected_keys, on=["source_file", "source_row", "measure"])
    con = duckdb.connect(db_path)
    con.register("canonical_df", loaded)
    con.register("source_df", df)
    con.register("rejected_df", rejected)
    con.execute("CREATE OR REPLACE TABLE canonical AS SELECT * FROM canonical_df")
    con.execute("CREATE OR REPLACE TABLE source_all AS SELECT * FROM source_df")
    con.execute("CREATE OR REPLACE TABLE rejected_rows AS SELECT * FROM rejected_df")
    con.execute((SQL / "warehouse.sql").read_text(encoding="utf-8"))
    return con, exceptions


def run(out: Path = REPORTS, db_path: str = str(ROOT / "data" / "warehouse.duckdb")) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    df = load_all(Mapping.load())
    con, exceptions = build(df, db_path)
    q = named_queries(SQL / "reconciliation.sql")
    control = con.execute(q["control_totals"]).df()
    prior_by_type = con.execute(q["prior_year_by_type"]).df()
    prior = con.execute(q["prior_year_check"]).df()
    council = con.execute(q["council_changes"]).df()
    embedded = con.execute(q["embedded_totals"]).df()

    reports = {
        "reconciliation_control.csv": control,
        "embedded_totals_check.csv": embedded,
        "prior_year_by_fund_type.csv": prior_by_type,
        "prior_year_check.csv": prior,
        "council_changes.csv": council,
        "exceptions.csv": exceptions,
        "data_gap_matrix.csv": gap_matrix().fillna("n/a"),
    }
    for name, frame in reports.items():
        frame.to_csv(out / name, index=False, lineterminator="\n")

    source_lines = int(df.drop_duplicates(["source_file", "source_row"]).shape[0])
    by_rule = exceptions.groupby(["rule_id", "severity"]).size().reset_index(name="count")
    summary = {
        "files": int(df["source_file"].nunique()),
        "years": [int(df["fiscal_year"].min()), int(df["fiscal_year"].max())],
        "source_lines": source_lines,
        "measure_values": int(len(df)),
        "loaded_values": int(con.execute("SELECT count(*) FROM fact_appropriation").fetchone()[0]),
        "funds": int(con.execute("SELECT count(*) FROM dim_fund").fetchone()[0]),
        "departments": int(con.execute("SELECT count(*) FROM dim_department").fetchone()[0]),
        "accounts": int(con.execute("SELECT count(*) FROM dim_account").fetchone()[0]),
        "coa_keys": int(con.execute("SELECT count(*) FROM dim_coa").fetchone()[0]),
        "control_checks": int(len(control)),
        "control_reconciled": int((control["status"] == "RECONCILED").sum()),
        "max_abs_variance": float(control["variance"].abs().max()),
        "prior_year_by_type": {
            t: f"{int((g['status'] == 'MATCH').sum())}/{len(g)} years match"
            for t, g in prior_by_type.groupby("fund_type")
        },
        "prior_year_local_fund_checks": int((prior["fund_type"] == "LOCAL").sum()),
        "prior_year_local_fund_differences": int(((prior["fund_type"] == "LOCAL") & (prior["status"] != "MATCH")).sum()),
        "embedded_total_checks": int(len(embedded)),
        "embedded_total_matches": int((embedded["status"] == "MATCH").sum()),
        "exceptions_by_rule": {f"{r.rule_id} ({r.severity})": int(r.count) for r in by_rule.itertuples()},
        "rules": {k: v.name for k, v in RULES.items()},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
    sys.exit(0)

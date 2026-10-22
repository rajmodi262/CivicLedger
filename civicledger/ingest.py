"""Read each raw file, apply the source-to-target mapping, and emit canonical long-format rows.

One output row per (source row, measure): an adopted file yields one "ordinance" amount per line;
a proposed file yields "recommendation", "prior_appropriation" and "prior_revised". Every row keeps
its source file and 1-based source row number, so any figure can be traced back to the raw data.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from civicledger import CONFIG, RAW

DIMENSIONS = [
    "fund_type", "fund_code", "fund_description", "department_code", "department_description",
    "authority_code", "authority_description", "account_code", "account_description",
]


@dataclass(frozen=True)
class Mapping:
    dimensions: dict[str, list[str]]
    measures: dict[str, dict[str, list[str]]]
    code_widths: dict[str, int]
    ignored: list[str]

    @classmethod
    def load(cls, path: Path = CONFIG / "mapping.yaml") -> Mapping:
        m = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(m["dimensions"], m["measures"], m["code_widths"], m.get("ignored_columns", []))


def resolve(columns: list[str], candidates: list[str]) -> str | None:
    """The first candidate source column present in this file, or None."""
    return next((c for c in candidates if c in columns), None)


def column_map(columns: list[str], stage: str, mapping: Mapping) -> tuple[dict[str, str | None], dict[str, str | None]]:
    dims = {field: resolve(columns, cands) for field, cands in mapping.dimensions.items()}
    meas = {field: resolve(columns, cands) for field, cands in mapping.measures[stage].items()}
    return dims, meas


_PREFIX = re.compile(r"^\s*\d+\s*-\s*")  # "2005 - POLICE BOARD" -> "POLICE BOARD"


def norm_code(value: object, width: int) -> str | None:
    """Codes arrive as '100', '0100' or '100.0'; compare numerically, store zero-padded."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(\.0+)?", text):
        return str(int(float(text))).zfill(width)
    return text.upper()  # non-numeric codes are kept (and flagged by VR-06)


def norm_text(value: object, strip_prefix: bool = False) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = " ".join(str(value).split()).upper()
    if strip_prefix:
        text = _PREFIX.sub("", text)
    return text or None


def parse_amount(value: object) -> float | None:
    """'$1,234.50', '1234.5' or '1,234' -> 1234.5; blank -> None; anything else -> NaN (flagged)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return float("nan")


def read_file(path: Path, year: int, stage: str, mapping: Mapping) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    dims, meas = column_map(list(raw.columns), stage, mapping)
    out_rows = []
    for i, row in enumerate(raw.to_dict("records"), start=1):
        base = {"fiscal_year": year, "stage": stage, "source_file": path.name, "source_row": i}
        blank = all(not str(v).strip() for v in row.values())
        for field in DIMENSIONS:
            col = dims.get(field)
            value = row.get(col) if col else None
            if field in mapping.code_widths:
                base[field] = norm_code(value, mapping.code_widths[field])
            else:
                base[field] = norm_text(value, strip_prefix=field == "authority_description")
        for measure, col in meas.items():
            raw_value = row.get(col) if col else None
            out_rows.append({
                **base, "measure": measure, "raw_amount": raw_value,
                "amount": parse_amount(raw_value), "blank_row": blank,
            })
    return pd.DataFrame(out_rows)


def sources() -> list[dict]:
    return json.loads((RAW / "MANIFEST.json").read_text(encoding="utf-8"))["files"]


def load_all(mapping: Mapping | None = None) -> pd.DataFrame:
    mapping = mapping or Mapping.load()
    frames = [read_file(RAW / s["file"], s["year"], s["stage"], mapping) for s in sources()]
    return pd.concat(frames, ignore_index=True)


def gap_matrix(mapping: Mapping | None = None) -> pd.DataFrame:
    """Which source column fed each canonical field, per file (the data-gap analysis)."""
    mapping = mapping or Mapping.load()
    rows = []
    for s in sources():
        columns = list(pd.read_csv(RAW / s["file"], nrows=0).columns)
        dims, meas = column_map(columns, s["stage"], mapping)
        used = {c for c in list(dims.values()) + list(meas.values()) if c}
        rows.append({
            "file": s["file"], **{k: v or "MISSING" for k, v in {**dims, **meas}.items()},
            "unmapped_source_columns": ", ".join(c for c in columns if c not in used) or "",
        })
    return pd.DataFrame(rows)

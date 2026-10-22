"""CivicLedger: municipal budget data migration, chart-of-accounts mapping, validation and reconciliation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
CONFIG = ROOT / "config"

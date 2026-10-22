"""Download the City of Chicago budget appropriation files listed in config/sources.json.

    python scripts/fetch_chicago.py

Each dataset is fetched once from the official Socrata API (data.cityofchicago.org) and saved
gzipped, unchanged, as data/raw/<year>_<stage>.csv.gz. A manifest records the dataset id, row
count and SHA-256 of every file, so later runs can prove the inputs did not change.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
API = "https://data.cityofchicago.org/resource/{id}.csv?$limit=200000"


def fetch(dataset_id: str) -> bytes:
    with urllib.request.urlopen(API.format(id=dataset_id), timeout=120) as resp:  # noqa: S310 - fixed host
        return resp.read()


def main() -> int:
    sources = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []
    for src in sources:
        name = f"{src['year']}_{src['stage']}.csv.gz"
        target = RAW / name
        if not target.exists():
            body = fetch(src["id"])
            target.write_bytes(gzip.compress(body, mtime=0))
        body = gzip.decompress(target.read_bytes())
        rows = sum(1 for _ in csv.reader(io.StringIO(body.decode("utf-8")))) - 1
        manifest.append({
            "file": name, "dataset_id": src["id"], "year": src["year"], "stage": src["stage"],
            "title": src["name"], "rows": rows, "sha256": hashlib.sha256(body).hexdigest(),
            "source": f"https://data.cityofchicago.org/d/{src['id']}",
        })
        print(f"{name}: {rows:,} rows")
    (RAW / "MANIFEST.json").write_text(
        json.dumps({"fetched": date.today().isoformat(), "files": manifest}, indent=1), encoding="utf-8"
    )
    print(f"{len(manifest)} files, {sum(m['rows'] for m in manifest):,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())

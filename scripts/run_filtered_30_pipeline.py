#!/usr/bin/env python3
"""Run the filtered 30-opportunity workflow and verify the final workbook."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DATA_DIR = Path("data/amazon_3c/filtered_30_opportunities")


def run_step(command: list[str], allow_failure: bool = False) -> int:
    print(f"\n$ {' '.join(command)}", flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode and not allow_failure:
        raise SystemExit(completed.returncode)
    return completed.returncode


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def selected_count() -> int:
    rows = load_json(DATA_DIR / "selected_30.json", [])
    return len({row.get("asin") for row in rows if row.get("asin")})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=30)
    parser.add_argument("--retry-passes", type=int, default=2)
    parser.add_argument("--skip-crawl", action="store_true", help="Reuse existing candidate_asins/selected JSON files.")
    parser.add_argument("--skip-retry", action="store_true", help="Build and verify without slow retry.")
    args = parser.parse_args()

    py = sys.executable
    if not args.skip_crawl:
        run_step([py, "scripts/crawl_3c_filtered_opportunities_fast.py"], allow_failure=True)

    if not args.skip_retry:
        for retry_idx in range(args.retry_passes):
            if selected_count() >= args.target:
                break
            print(f"\nRetry pass {retry_idx + 1}/{args.retry_passes}: selected={selected_count()}", flush=True)
            run_step([py, "scripts/retry_filtered_opportunity_details.py"], allow_failure=True)

    run_step([py, "scripts/build_filtered_30_opportunity_excel.py"])
    return run_step([py, "scripts/verify_crawl_outputs.py", "--target", str(args.target), "--filtered-only"])


if __name__ == "__main__":
    raise SystemExit(main())

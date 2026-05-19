#!/usr/bin/env python3
"""Merge distributed retry shard results into selected_30.json."""

from __future__ import annotations

import argparse
import csv
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATA_DIR = Path("data/amazon_3c/filtered_30_opportunities")
DEFAULT_RESULTS_GLOB = str(DATA_DIR / "retry_shards" / "results" / "shard_*.json")

FIELDS = [
    "final_rank",
    "source",
    "department",
    "category_path",
    "category_name",
    "asin",
    "title",
    "brand",
    "price",
    "price_num",
    "rating",
    "review_count",
    "review_count_num",
    "profit_score",
    "feasibility_score",
    "recommendation_score",
    "china_seller_suitability",
    "opportunity_point",
    "risk_point",
    "feasibility_analysis",
    "bullet_1",
    "bullet_2",
    "bullet_3",
    "bullet_4",
    "bullet_5",
    "image_url",
    "local_image",
    "product_url",
    "category_url",
    "preferred_hits",
    "risk_hits",
    "commodity_hits",
    "exclude_reasons",
]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-glob", default=DEFAULT_RESULTS_GLOB)
    parser.add_argument("--target", type=int, default=30)
    args = parser.parse_args()

    rows_by_asin = {}
    for row in load_json(DATA_DIR / "selected_30.json", []):
        asin = row.get("asin")
        if asin:
            rows_by_asin[asin] = row

    result_paths = [Path(path) for path in sorted(glob.glob(args.results_glob))]
    shard_rows = 0
    for path in result_paths:
        for row in load_json(path, []):
            asin = row.get("asin")
            if asin:
                rows_by_asin[asin] = row
                shard_rows += 1

    selected_rows = sorted(
        rows_by_asin.values(),
        key=lambda row: (row.get("recommendation_score", 0), row.get("profit_score", 0), row.get("feasibility_score", 0)),
        reverse=True,
    )[: args.target]
    for idx, row in enumerate(selected_rows, start=1):
        row["final_rank"] = idx

    write_json(DATA_DIR / "selected_30.json", selected_rows)
    write_csv(DATA_DIR / "selected_30.csv", selected_rows)
    summary = load_json(DATA_DIR / "summary.json", {})
    summary.update(
        {
            "merge_run_at": datetime.now(timezone.utc).isoformat(),
            "retry_shard_files": len(result_paths),
            "retry_shard_rows": shard_rows,
            "selected_after_shard_merge": len(selected_rows),
            "final_status": "target_met" if len(selected_rows) >= args.target else "target_not_met",
        }
    )
    write_json(DATA_DIR / "summary.json", summary)
    write_json(DATA_DIR / "summary_with_retry.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if len(selected_rows) >= args.target else 2


if __name__ == "__main__":
    raise SystemExit(main())

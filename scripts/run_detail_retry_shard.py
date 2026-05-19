#!/usr/bin/env python3
"""Run detail-page retries for one candidate shard without mutating shared outputs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_SCRIPT = Path("scripts/crawl_amazon_3c_bsr_new_releases.py")
FILTER_SCRIPT = Path("scripts/crawl_3c_filtered_opportunities.py")
IMAGE_DIR = Path("data/amazon_3c/filtered_30_opportunities/images")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_row(base, filt, crawler, candidate: dict[str, Any]) -> dict[str, Any]:
    detail = crawler.extract_product_detail(candidate["asin"])
    bullets = detail.get("bullet_points") or []
    row = {
        **candidate,
        **detail,
        "bullet_1": bullets[0] if len(bullets) > 0 else "",
        "bullet_2": bullets[1] if len(bullets) > 1 else "",
        "bullet_3": bullets[2] if len(bullets) > 2 else "",
        "bullet_4": bullets[3] if len(bullets) > 3 else "",
        "bullet_5": bullets[4] if len(bullets) > 4 else "",
        "bullet_points_joined": " | ".join(bullets),
    }
    row.update(filt.analyze_candidate(row))
    return row


def acceptable(row: dict[str, Any]) -> bool:
    if not row.get("title") or not row.get("image_url"):
        return False
    reasons = [part for part in str(row.get("exclude_reasons", "")).split("；") if part]
    hard = [part for part in reasons if part != "卖点信息不足"]
    if hard:
        return False
    return row.get("recommendation_score", 0) >= 50


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-attempts", type=int, default=350)
    parser.add_argument("--max-accepted", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=0.75)
    args = parser.parse_args()

    base = load_module(BASE_SCRIPT, "shard_base")
    filt = load_module(FILTER_SCRIPT, "shard_filter")
    crawler = base.Amazon3CBsrCrawler(timeout=15, sleep=args.sleep)

    candidates = load_json(args.input)
    accepted_rows = []
    attempted = 0
    for candidate in candidates:
        if attempted >= args.max_attempts or len(accepted_rows) >= args.max_accepted:
            break
        asin = candidate.get("asin")
        if not asin:
            continue
        attempted += 1
        row = make_row(base, filt, crawler, candidate)
        if acceptable(row):
            row["local_image"] = crawler.download_image(row["asin"], row.get("image_url", ""), IMAGE_DIR)
            if "卖点信息不足" in str(row.get("exclude_reasons", "")):
                note = row.get("feasibility_analysis", "")
                row["feasibility_analysis"] = f"{note}；页面五点不足，需人工复核Listing" if note else "页面五点不足，需人工复核Listing"
            accepted_rows.append(row)
            print(f"[accepted {len(accepted_rows):02d}] {asin} score={row.get('recommendation_score')}", flush=True)

    write_json(args.output, accepted_rows)
    write_json(
        args.output.with_suffix(".summary.json"),
        {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "input": str(args.input),
            "output": str(args.output),
            "candidates": len(candidates),
            "attempted": attempted,
            "accepted": len(accepted_rows),
        },
    )
    print(json.dumps({"attempted": attempted, "accepted": len(accepted_rows), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Slow retry for filtered opportunity candidates with missing detail fields."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


BASE_SCRIPT = Path("scripts/crawl_amazon_3c_bsr_new_releases.py")
FILTER_SCRIPT = Path("scripts/crawl_3c_filtered_opportunities.py")
OUTPUT_DIR = Path("data/amazon_3c/filtered_30_opportunities")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


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
    base = load_module(BASE_SCRIPT, "retry_base")
    filt = load_module(FILTER_SCRIPT, "retry_filter")
    crawler = base.Amazon3CBsrCrawler(timeout=15, sleep=0.35)

    selected = load_json(OUTPUT_DIR / "selected_30.json", [])
    accepted_pool = load_json(OUTPUT_DIR / "accepted_pool.json", [])
    candidates = load_json(OUTPUT_DIR / "candidate_asins.json", [])
    summary = load_json(OUTPUT_DIR / "summary.json", {})
    previous_retry_attempted = int(summary.get("retry_attempted", 0) or 0)

    selected_by_asin = {row["asin"]: row for row in selected if row.get("asin")}
    attempted = set(selected_by_asin)
    for row in accepted_pool:
        if row.get("asin"):
            attempted.add(row["asin"])

    print(f"Starting selected={len(selected_by_asin)} candidates={len(candidates)}", flush=True)
    eligible_seen = 0
    retried = 0
    for candidate in candidates:
        if len(selected_by_asin) >= 30:
            break
        asin = candidate.get("asin")
        if not asin or asin in attempted:
            continue
        eligible_seen += 1
        if eligible_seen <= previous_retry_attempted:
            continue
        attempted.add(asin)
        retried += 1
        row = make_row(base, filt, crawler, candidate)
        if acceptable(row):
            row["local_image"] = crawler.download_image(row["asin"], row.get("image_url", ""), OUTPUT_DIR / "images")
            if "卖点信息不足" in str(row.get("exclude_reasons", "")):
                row["feasibility_analysis"] = row.get("feasibility_analysis", "") + "；页面五点不足，需人工复核Listing"
            selected_by_asin[asin] = row
            print(f"[add {len(selected_by_asin):02d}] {asin} score={row.get('recommendation_score')} {row.get('title','')[:80]}", flush=True)
        if retried >= 900:
            break

    selected_rows = sorted(
        selected_by_asin.values(),
        key=lambda row: (row.get("recommendation_score", 0), row.get("profit_score", 0), row.get("feasibility_score", 0)),
        reverse=True,
    )[:30]
    for idx, row in enumerate(selected_rows, start=1):
        row["final_rank"] = idx

    fields = [
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
    write_json(OUTPUT_DIR / "selected_30.json", selected_rows)
    write_csv(OUTPUT_DIR / "selected_30.csv", selected_rows, fields)
    summary["selected_after_retry"] = len(selected_rows)
    summary["retry_attempted"] = previous_retry_attempted + retried
    write_json(OUTPUT_DIR / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if len(selected_rows) >= 30 else 2


if __name__ == "__main__":
    raise SystemExit(main())

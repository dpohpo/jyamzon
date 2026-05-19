#!/usr/bin/env python3
"""Run the local Claude Amazon crawler against the 3C report targets.

This script intentionally imports the existing Claude crawler instead of
reimplementing scraping logic. It only constrains scope, caps request timeouts,
and saves incremental audit artifacts.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CLAUDE_CRAWLER = Path(
    os.environ.get("CLAUDE_AMAZON_CRAWLER", "~/.claude/skills/amazon/scripts/amazon_crawler.py")
).expanduser()

KEYWORDS = [
    "dual monitor stand riser",
    "monitor riser",
    "monitor stand",
    "dual monitor stand",
    "monitor riser for desk",
    "desk monitor riser",
    "portable monitor stand",
    "cable organizer box",
]

TARGET_ASINS = [
    "B0855QBHTZ",
    "B082N9PL4B",
    "B0C4SZ286V",
    "B09712RBWB",
    "B0DJKSMV2T",
]


def load_crawler_class(crawler_path: Path) -> type:
    spec = importlib.util.spec_from_file_location("claude_amazon_crawler", crawler_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load crawler script: {crawler_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.AmazonCrawler


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return True


def summarize_product(product: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "title",
        "brand",
        "price",
        "rating",
        "review_count",
        "bullet_points",
        "description",
        "image_url",
        "bsr",
        "url",
    ]
    present = [field for field in fields if has_value(product.get(field))]
    missing = [field for field in fields if field not in present]
    return {
        "asin": product.get("asin", ""),
        "present_fields": present,
        "missing_fields": missing,
        "field_coverage": round(len(present) / len(fields), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local Claude Amazon crawler coverage.")
    parser.add_argument("--output", default="data/amazon_3c/crawler_audit")
    parser.add_argument("--marketplace", default="com")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--max-reviews", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--skip-reviews", action="store_true")
    parser.add_argument(
        "--crawler-script",
        default=str(DEFAULT_CLAUDE_CRAWLER),
        help="Path to Claude Amazon crawler. Defaults to CLAUDE_AMAZON_CRAWLER or ~/.claude/skills/amazon/scripts/amazon_crawler.py.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    crawler_path = Path(args.crawler_script).expanduser()
    crawler_cls = load_crawler_class(crawler_path)
    crawler = crawler_cls(args.marketplace)

    original_request = crawler.session.request

    def capped_request(method: str, url: str, **kwargs: Any):
        timeout = kwargs.get("timeout", args.timeout)
        if timeout is None or timeout > args.timeout:
            kwargs["timeout"] = args.timeout
        return original_request(method, url, **kwargs)

    crawler.session.request = capped_request
    crawler._delay = lambda min_sec=0, max_sec=0: None

    audit: dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "crawler_script": str(crawler_path),
        "marketplace": args.marketplace,
        "request_timeout_seconds": args.timeout,
        "search_pages_per_keyword": args.pages,
        "max_reviews_per_asin": args.max_reviews,
        "keywords": KEYWORDS,
        "target_asins": TARGET_ASINS,
    }

    search_rows: list[dict[str, Any]] = []
    search_results: dict[str, list[str]] = {}
    print("[1/3] Searching keywords", flush=True)
    for keyword in KEYWORDS:
        try:
            asins = crawler.search(keyword, pages=args.pages)
            search_results[keyword] = asins
            search_rows.append(
                {
                    "keyword": keyword,
                    "asin_count": len(asins),
                    "asins": " | ".join(asins),
                    "error": "",
                }
            )
        except Exception as exc:  # noqa: BLE001 - audit should keep going.
            search_results[keyword] = []
            search_rows.append(
                {
                    "keyword": keyword,
                    "asin_count": 0,
                    "asins": "",
                    "error": repr(exc),
                }
            )
        write_json(output_dir / "search_results.json", search_results)
        write_csv(output_dir / "search_results.csv", search_rows, ["keyword", "asin_count", "asins", "error"])

    products: list[dict[str, Any]] = []
    reviews: dict[str, list[dict[str, Any]]] = {}
    product_summaries: list[dict[str, Any]] = []
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    print("[2/3] Fetching target ASIN product pages", flush=True)
    for asin in TARGET_ASINS:
        try:
            product = crawler.get_product_detail(asin)
            if not product:
                product = {"asin": asin, "error": "no product detail returned"}
            if product.get("image_url"):
                product["local_image"] = crawler.download_image(asin, product["image_url"], str(image_dir))
        except Exception as exc:  # noqa: BLE001
            product = {"asin": asin, "error": repr(exc)}
        products.append(product)
        product_summaries.append(summarize_product(product))
        write_json(output_dir / "products.json", products)
        write_csv(
            output_dir / "products.csv",
            [
                {
                    **product,
                    "bullet_points": " | ".join(product.get("bullet_points", []))
                    if isinstance(product.get("bullet_points"), list)
                    else product.get("bullet_points", ""),
                }
                for product in products
            ],
            [
                "asin",
                "title",
                "brand",
                "price",
                "rating",
                "review_count",
                "bsr",
                "bullet_points",
                "description",
                "image_url",
                "local_image",
                "url",
                "error",
            ],
        )
        write_json(output_dir / "product_field_coverage.json", product_summaries)

    if args.skip_reviews:
        print("[3/3] Skipping negative reviews", flush=True)
    else:
        print("[3/3] Fetching target ASIN negative reviews", flush=True)
        for product in products:
            asin = product.get("asin", "")
            if not asin:
                continue
            try:
                reviews[asin] = crawler.get_negative_reviews(asin, max_reviews=args.max_reviews)
            except Exception as exc:  # noqa: BLE001
                reviews[asin] = [{"asin": asin, "error": repr(exc)}]
            write_json(output_dir / "negative_reviews.json", reviews)

    review_rows: list[dict[str, Any]] = []
    for asin, review_list in reviews.items():
        for review in review_list:
            review_rows.append(review)
    write_csv(
        output_dir / "negative_reviews.csv",
        review_rows,
        ["asin", "rating", "title", "body", "date", "verified", "helpful", "error"],
    )

    audit["search_keyword_count"] = len(search_rows)
    audit["search_total_asin_mentions"] = sum(row["asin_count"] for row in search_rows)
    audit["products_attempted"] = len(TARGET_ASINS)
    audit["products_with_title"] = sum(1 for product in products if has_value(product.get("title")))
    audit["reviews_attempted_asins"] = len(reviews)
    audit["reviews_collected"] = sum(len(items) for items in reviews.values())
    audit["outputs"] = {
        "search_results_json": str(output_dir / "search_results.json"),
        "products_json": str(output_dir / "products.json"),
        "negative_reviews_json": str(output_dir / "negative_reviews.json"),
        "product_field_coverage_json": str(output_dir / "product_field_coverage.json"),
    }
    write_json(output_dir / "audit_summary.json", audit)

    print(json.dumps(audit, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

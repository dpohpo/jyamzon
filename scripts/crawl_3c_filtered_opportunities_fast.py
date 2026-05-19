#!/usr/bin/env python3
"""Fast concurrent crawl for 30 filtered 3C BSR opportunities."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from collections import deque
from typing import Any


BASE_SCRIPT = Path("scripts/crawl_amazon_3c_bsr_new_releases.py")
FILTER_SCRIPT = Path("scripts/crawl_3c_filtered_opportunities.py")
OUTPUT_DIR = Path("data/amazon_3c/filtered_30_opportunities")
# Stable-by-default detail fetching.
#
# The broad crawl previously achieved near-complete detail coverage by fetching
# details serially with a small delay. High-concurrency detail fetching can get
# HTTP 200 pages that parse as missing title/image, so the production default
# favors success rate over speed. Override from CLI when doing exploratory runs.
DETAIL_TIMEOUT = 15
DETAIL_SLEEP = 0.35
DETAIL_RETRIES = 2


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def load_seed_tasks(base, filt) -> list[Any]:
    tasks = filt.load_known_category_tasks(base)
    if tasks:
        return tasks
    return list(base.ROOTS) + list(base.FALLBACK_ROOTS)


def collect_candidate_asins(base, filt, output_dir: Path, max_pages: int = 120, max_per_category: int = 24) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    crawler = base.Amazon3CBsrCrawler(timeout=10, sleep=0.03)
    existing = filt.load_existing_asins()
    tasks = deque(load_seed_tasks(base, filt))
    rows: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    seen_asins = set(existing)
    seen_urls: set[str] = set()

    while tasks and len(seen_urls) < max_pages:
        task = tasks.popleft()
        url = crawler.canonical_url(task.url)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        pre_reject = filt.category_pre_reject(task.path)
        if pre_reject:
            logs.append({"url": url, "path": task.path, "status": "pre_reject", "note": pre_reject})
            continue
        html, status = crawler.fetch(url)
        if not html:
            logs.append({"url": url, "path": task.path, "status": status, "asins": 0})
            continue
        asins, children = crawler.parse_category_page(task, html)
        logs.append({"url": url, "path": task.path, "status": status, "asins": len(asins)})
        for child in children:
            child_url = crawler.canonical_url(child.url)
            if child_url and child_url not in seen_urls and not filt.category_pre_reject(child.path):
                tasks.append(child)
        added = 0
        for rank, asin in enumerate(asins, start=1):
            if added >= max_per_category:
                break
            if asin in seen_asins:
                continue
            seen_asins.add(asin)
            added += 1
            rows.append(
                {
                    "source": task.source,
                    "department": task.department,
                    "category_path": task.path,
                    "category_name": task.path.split(" > ")[-1],
                    "category_url": url,
                    "category_node": crawler.category_node(url),
                    "rank_on_page": rank,
                    "page_asin_count": len(asins),
                    "asin": asin,
                }
            )

    write_json(output_dir / "candidate_asins.json", rows)
    write_json(output_dir / "category_logs.json", logs)
    return rows, logs


thread_local = threading.local()


def get_worker_crawler(base):
    crawler = getattr(thread_local, "crawler", None)
    if crawler is None:
        crawler = base.Amazon3CBsrCrawler(timeout=DETAIL_TIMEOUT, sleep=DETAIL_SLEEP)
        thread_local.crawler = crawler
    return crawler


def enrich_candidate(base, filt, candidate: dict[str, Any]) -> dict[str, Any]:
    crawler = get_worker_crawler(base)
    detail = crawler.extract_product_detail(candidate["asin"], retries=DETAIL_RETRIES, retry_sleep=max(DETAIL_SLEEP, 0.8))
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


def download_selected_images(base, rows: list[dict[str, Any]]) -> None:
    crawler = base.Amazon3CBsrCrawler(timeout=12, sleep=0)
    for row in rows:
        row["local_image"] = crawler.download_image(row["asin"], row.get("image_url", ""), OUTPUT_DIR / "images")


def main() -> int:
    global DETAIL_TIMEOUT, DETAIL_SLEEP, DETAIL_RETRIES
    parser = argparse.ArgumentParser(description="Fast concurrent crawl for filtered 3C BSR opportunities.")
    parser.add_argument("--max-pages", type=int, default=220)
    parser.add_argument("--max-per-category", type=int, default=24)
    parser.add_argument("--max-details", type=int, default=1500)
    parser.add_argument("--detail-workers", type=int, default=1)
    parser.add_argument("--detail-timeout", type=int, default=15)
    parser.add_argument("--detail-sleep", type=float, default=0.35)
    parser.add_argument("--detail-retries", type=int, default=2)
    args = parser.parse_args()

    DETAIL_TIMEOUT = args.detail_timeout
    DETAIL_SLEEP = args.detail_sleep
    DETAIL_RETRIES = args.detail_retries

    base = load_module(BASE_SCRIPT, "bsr_base_fast")
    filt = load_module(FILTER_SCRIPT, "filter_rules_fast")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates, logs = collect_candidate_asins(base, filt, OUTPUT_DIR, max_pages=args.max_pages, max_per_category=args.max_per_category)
    print(f"Candidate ASINs after dedupe: {len(candidates)}", flush=True)

    enriched: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    max_details = min(args.max_details, len(candidates))
    print(
        f"Detail fetch params: workers={args.detail_workers}, sleep={DETAIL_SLEEP}, retries={DETAIL_RETRIES}, timeout={DETAIL_TIMEOUT}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=args.detail_workers) as executor:
        future_map = {executor.submit(enrich_candidate, base, filt, candidate): candidate for candidate in candidates[:max_details]}
        done = 0
        for future in as_completed(future_map):
            done += 1
            candidate = future_map[future]
            try:
                row = future.result()
            except Exception as exc:  # noqa: BLE001
                rejected.append({**candidate, "exclude_reasons": f"详情抓取异常:{type(exc).__name__}:{exc}"})
                continue
            if row.get("exclude_reasons"):
                rejected.append(row)
            elif row.get("recommendation_score", 0) >= 50:
                enriched.append(row)
            else:
                rejected.append({**row, "exclude_reasons": "综合分低于50"})
            if done % 25 == 0:
                print(f"Details done {done}/{max_details}; pool={len(enriched)}; rejected={len(rejected)}", flush=True)
                write_json(OUTPUT_DIR / "accepted_pool.partial.json", enriched)
                write_json(OUTPUT_DIR / "rejected.partial.json", rejected)

    selected = sorted(
        enriched,
        key=lambda row: (row.get("recommendation_score", 0), row.get("profit_score", 0), row.get("feasibility_score", 0)),
        reverse=True,
    )[:30]
    download_selected_images(base, selected)
    for idx, row in enumerate(selected, start=1):
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
    ]
    write_json(OUTPUT_DIR / "accepted_pool.json", enriched)
    write_json(OUTPUT_DIR / "selected_30.json", selected)
    write_json(OUTPUT_DIR / "rejected.json", rejected)
    write_csv(OUTPUT_DIR / "accepted_pool.csv", enriched, fields)
    write_csv(OUTPUT_DIR / "selected_30.csv", selected, fields)
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "candidate_asins": len(candidates),
        "detail_pages_attempted": max_details,
        "accepted_pool": len(enriched),
        "selected": len(selected),
        "rejected": len(rejected),
        "category_pages": len(logs),
        "detail_workers": args.detail_workers,
        "detail_sleep": DETAIL_SLEEP,
        "detail_retries": DETAIL_RETRIES,
        "detail_timeout": DETAIL_TIMEOUT,
    }
    write_json(OUTPUT_DIR / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if len(selected) >= 30 else 2


if __name__ == "__main__":
    raise SystemExit(main())

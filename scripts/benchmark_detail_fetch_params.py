#!/usr/bin/env python3
"""Benchmark Amazon detail-page fetch workers/sleep settings.

The fast opportunity crawler used to run many detail requests with high
concurrency and no delay. Amazon can return HTTP 200 pages that are still
missing product content, so this benchmark measures parsed field success, not
only request status.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_SCRIPT = Path("scripts/crawl_amazon_3c_bsr_new_releases.py")
OUTPUT_DIR = Path("data/amazon_3c/detail_fetch_benchmark")


def load_base_module():
    spec = importlib.util.spec_from_file_location("benchmark_bsr_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_paths() -> list[Path]:
    return [
        Path("data/amazon_3c/filtered_30_opportunities/selected_30_curated.json"),
        Path("data/amazon_3c/filtered_30_opportunities/rejected.json"),
        Path("data/amazon_3c/filtered_30_opportunities/candidate_asins.json"),
        Path("data/amazon_3c/bsr_new_releases/products.json"),
        Path("examples/raw/filtered_30_opportunities/selected_30_curated.json"),
        Path("examples/raw/filtered_30_opportunities/rejected.json"),
        Path("examples/raw/filtered_30_opportunities/candidate_asins.json"),
        Path("examples/raw/bsr_new_releases/products.json"),
    ]


def row_score_hint(row: dict[str, Any]) -> tuple[int, str]:
    title_missing = not row.get("title")
    image_missing = not row.get("image_url")
    if title_missing or image_missing:
        return (0, "previous_missing_core")
    if row.get("asin"):
        return (1, "previous_ok")
    return (2, "candidate_only")


def load_asin_sample(sample_size: int, asin_file: str | None) -> list[str]:
    if asin_file:
        rows = load_json(Path(asin_file), [])
        if isinstance(rows, list):
            asins = [row.get("asin", row) if isinstance(row, dict) else row for row in rows]
        else:
            asins = []
        return [str(asin) for asin in asins if asin][:sample_size]

    seen: set[str] = set()
    ranked_rows: list[tuple[int, int, str]] = []
    order = 0
    for path in candidate_paths():
        rows = load_json(path, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            asin = row.get("asin")
            if not asin or asin in seen:
                continue
            seen.add(asin)
            rank, _ = row_score_hint(row)
            ranked_rows.append((rank, order, str(asin)))
            order += 1

    ranked_rows.sort(key=lambda item: (item[0], item[1]))
    return [asin for _, _, asin in ranked_rows[:sample_size]]


def parse_combo(value: str) -> tuple[int, float]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("combo must be workers:sleep, e.g. 6:0.25")
    workers_text, sleep_text = value.split(":", 1)
    return int(workers_text), float(sleep_text)


def field_stats(row: dict[str, Any]) -> dict[str, Any]:
    bullets = row.get("bullet_points") or []
    return {
        "title_ok": bool(row.get("title")),
        "price_ok": bool(row.get("price")),
        "rating_ok": bool(row.get("rating")),
        "review_ok": bool(row.get("review_count")),
        "image_ok": bool(row.get("image_url")),
        "bullets5_ok": len(bullets) >= 5,
        "core_ok": bool(row.get("title")) and bool(row.get("image_url")),
    }


def fetch_one(base, asin: str, timeout: int, sleep: float, retries: int, retry_sleep: float) -> dict[str, Any]:
    crawler = base.Amazon3CBsrCrawler(timeout=timeout, sleep=sleep)
    started = time.perf_counter()
    detail = crawler.extract_product_detail(asin, retries=retries, retry_sleep=retry_sleep)
    elapsed = time.perf_counter() - started
    stats = field_stats(detail)
    return {
        "asin": asin,
        "elapsed_seconds": round(elapsed, 3),
        "detail_status": detail.get("detail_status", ""),
        "detail_error": detail.get("detail_error", ""),
        "detail_attempts": detail.get("detail_attempts", 1),
        **stats,
    }


def summarize(combo: str, workers: int, sleep: float, rows: list[dict[str, Any]], elapsed: float) -> dict[str, Any]:
    total = len(rows)
    def count(key: str) -> int:
        return sum(1 for row in rows if row.get(key))

    core_ok = count("core_ok")
    return {
        "combo": combo,
        "workers": workers,
        "sleep": sleep,
        "sample_size": total,
        "elapsed_seconds": round(elapsed, 2),
        "pages_per_minute": round(total / elapsed * 60, 2) if elapsed else 0,
        "core_success": core_ok,
        "core_success_rate": round(core_ok / total, 4) if total else 0,
        "title_success_rate": round(count("title_ok") / total, 4) if total else 0,
        "price_success_rate": round(count("price_ok") / total, 4) if total else 0,
        "rating_success_rate": round(count("rating_ok") / total, 4) if total else 0,
        "review_success_rate": round(count("review_ok") / total, 4) if total else 0,
        "image_success_rate": round(count("image_ok") / total, 4) if total else 0,
        "bullets5_success_rate": round(count("bullets5_ok") / total, 4) if total else 0,
        "avg_attempts": round(sum(float(row.get("detail_attempts", 1)) for row in rows) / total, 3) if total else 0,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark detail page workers/sleep settings.")
    parser.add_argument("--sample-size", type=int, default=80)
    parser.add_argument("--asin-file")
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-sleep", type=float, default=0.8)
    parser.add_argument(
        "--combo",
        action="append",
        type=parse_combo,
        help="workers:sleep. Can be passed multiple times.",
    )
    args = parser.parse_args()

    combos = args.combo or [(14, 0.0), (10, 0.1), (8, 0.2), (6, 0.25), (4, 0.35), (3, 0.5)]
    asins = load_asin_sample(args.sample_size, args.asin_file)
    if not asins:
        raise SystemExit("No ASIN sample found. Run the crawler first or pass --asin-file.")

    base = load_base_module()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = OUTPUT_DIR / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sample_asins.json").write_text(json.dumps(asins, indent=2), encoding="utf-8")

    summaries: list[dict[str, Any]] = []
    for workers, sleep in combos:
        combo_label = f"{workers}w_{sleep:g}s"
        print(f"[combo] {combo_label} sample={len(asins)} retries={args.retries}", flush=True)
        started = time.perf_counter()
        rows: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(fetch_one, base, asin, args.timeout, sleep, args.retries, args.retry_sleep): asin
                for asin in asins
            }
            for future in as_completed(future_map):
                try:
                    rows.append(future.result())
                except Exception as exc:  # noqa: BLE001
                    rows.append(
                        {
                            "asin": future_map[future],
                            "elapsed_seconds": 0,
                            "detail_status": "exception",
                            "detail_error": f"{type(exc).__name__}:{exc}",
                            "detail_attempts": 0,
                            "title_ok": False,
                            "price_ok": False,
                            "rating_ok": False,
                            "review_ok": False,
                            "image_ok": False,
                            "bullets5_ok": False,
                            "core_ok": False,
                        }
                    )
        elapsed = time.perf_counter() - started
        rows.sort(key=lambda row: asins.index(row["asin"]) if row.get("asin") in asins else 999999)
        write_csv(output_dir / f"details_{combo_label}.csv", rows)
        summary = summarize(combo_label, workers, sleep, rows, elapsed)
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)

    summaries.sort(key=lambda row: (row["core_success_rate"], row["pages_per_minute"]), reverse=True)
    (output_dir / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(output_dir / "summary.csv", summaries)
    print(json.dumps({"output_dir": str(output_dir), "best": summaries[0]}, ensure_ascii=False, indent=2), flush=True)
    return 0 if summaries and summaries[0]["core_success_rate"] >= 0.95 else 2


if __name__ == "__main__":
    raise SystemExit(main())

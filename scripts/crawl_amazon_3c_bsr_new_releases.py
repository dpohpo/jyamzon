#!/usr/bin/env python3
"""Crawl Amazon 3C BSR/New Releases category pages without SellerSprite MCP.

The crawler uses public Amazon ranking pages as category discovery sources,
selects one unique ASIN per category, then fetches product detail fields.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE = "https://www.amazon.com"


@dataclass
class CategoryTask:
    source: str
    department: str
    path: str
    url: str
    depth: int


@dataclass
class CategoryPick:
    source: str
    department: str
    category_path: str
    category_name: str
    category_url: str
    category_node: str
    asin: str
    rank_on_page: int
    page_asin_count: int
    depth: int
    fetch_status: str
    fetch_note: str = ""


ROOTS = [
    CategoryTask("New Releases", "Electronics", "Electronics", f"{BASE}/gp/new-releases/electronics", 0),
    CategoryTask("New Releases", "Computers & Accessories", "Computers & Accessories", f"{BASE}/gp/new-releases/pc", 0),
    CategoryTask("New Releases", "Cell Phones & Accessories", "Cell Phones & Accessories", f"{BASE}/gp/new-releases/wireless", 0),
    CategoryTask("New Releases", "Camera & Photo", "Camera & Photo", f"{BASE}/gp/new-releases/photo", 0),
    CategoryTask("New Releases", "Video Games", "Video Games", f"{BASE}/gp/new-releases/videogames", 0),
]

FALLBACK_ROOTS = [
    CategoryTask("Best Sellers", "Electronics", "Electronics", f"{BASE}/Best-Sellers-Electronics/zgbs/electronics", 0),
    CategoryTask("Best Sellers", "Computers & Accessories", "Computers & Accessories", f"{BASE}/Best-Sellers-Computers-Accessories/zgbs/pc", 0),
    CategoryTask("Best Sellers", "Cell Phones & Accessories", "Cell Phones & Accessories", f"{BASE}/Best-Sellers-Cell-Phones-Accessories/zgbs/wireless", 0),
    CategoryTask("Best Sellers", "Camera & Photo", "Camera & Photo", f"{BASE}/Best-Sellers-Electronics-Camera-Photo-Products/zgbs/photo", 0),
    CategoryTask("Best Sellers", "Video Games", "Video Games", f"{BASE}/Best-Sellers-Video-Games/zgbs/videogames", 0),
]


class Amazon3CBsrCrawler:
    def __init__(self, timeout: int = 15, sleep: float = 0.25):
        self.timeout = timeout
        self.sleep = sleep
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "max-age=0",
            }
        )

    def fetch(self, url: str) -> tuple[str, str]:
        try:
            response = self.session.get(url, timeout=self.timeout)
            time.sleep(self.sleep)
            if response.status_code != 200:
                return "", f"http_{response.status_code}"
            text = response.text
            lower = text.lower()
            if "captcha" in lower and "enter the characters" in lower:
                return text, "captcha"
            if "robot check" in lower:
                return text, "robot_check"
            return text, "ok"
        except Exception as exc:  # noqa: BLE001
            return "", f"error:{type(exc).__name__}:{exc}"

    @staticmethod
    def clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    @staticmethod
    def canonical_url(href: str) -> str:
        full = urljoin(BASE, href)
        parsed = urlparse(full)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    @staticmethod
    def category_node(url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        match = re.search(r"/(\d+)$", path)
        return match.group(1) if match else path.split("/")[-1]

    @staticmethod
    def source_slug(task: CategoryTask) -> str:
        path = urlparse(task.url).path
        if task.source == "New Releases":
            parts = path.split("/")
            if "new-releases" in parts:
                idx = parts.index("new-releases")
                return parts[idx + 1] if idx + 1 < len(parts) else ""
        if "/zgbs/" in path:
            return path.split("/zgbs/", 1)[1].split("/", 1)[0]
        return ""

    def is_child_category(self, href: str, label: str, task: CategoryTask) -> bool:
        label = self.clean_text(label)
        if not label or label.lower() in {"new releases", "best sellers", "any department"}:
            return False
        if "next page" in label.lower() or "previous page" in label.lower():
            return False
        if label.isdigit():
            return False
        full = self.canonical_url(href)
        path = urlparse(full).path
        if "pg_" in href or "pg=" in href:
            return False
        current_path = urlparse(task.url).path.rstrip("/")
        if path.rstrip("/") == current_path:
            return False
        slug = self.source_slug(task)
        if task.source == "New Releases":
            return path.startswith(f"/gp/new-releases/{slug}/")
        return f"/zgbs/{slug}/" in path

    def parse_category_page(self, task: CategoryTask, html: str) -> tuple[list[str], list[CategoryTask]]:
        soup = BeautifulSoup(html, "html.parser")
        ordered_asins: list[str] = []
        seen_asins: set[str] = set()

        for asin in re.findall(r'data-asin=["\']([A-Z0-9]{10})["\']', html):
            if asin not in seen_asins:
                seen_asins.add(asin)
                ordered_asins.append(asin)

        for asin in re.findall(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", html):
            if asin not in seen_asins:
                seen_asins.add(asin)
                ordered_asins.append(asin)

        children: list[CategoryTask] = []
        seen_urls: set[str] = set()
        for link in soup.find_all("a", href=True):
            label = self.clean_text(link.get_text(" ", strip=True))
            href = link.get("href") or ""
            if not self.is_child_category(href, label, task):
                continue
            url = self.canonical_url(href)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            children.append(
                CategoryTask(
                    source=task.source,
                    department=task.department,
                    path=f"{task.path} > {label}",
                    url=url,
                    depth=task.depth + 1,
                )
            )

        return ordered_asins, children

    def discover_categories(self, target_count: int, min_count: int, max_pages: int) -> tuple[list[CategoryPick], list[dict[str, Any]]]:
        picks: list[CategoryPick] = []
        logs: list[dict[str, Any]] = []
        used_asins: set[str] = set()
        visited_urls: set[str] = set()
        queue: deque[CategoryTask] = deque(ROOTS)
        fallback_added = False

        while queue and len(picks) < target_count and len(visited_urls) < max_pages:
            task = queue.popleft()
            canonical = self.canonical_url(task.url)
            if canonical in visited_urls:
                continue
            visited_urls.add(canonical)

            html, status = self.fetch(canonical)
            log = {
                "url": canonical,
                "source": task.source,
                "department": task.department,
                "path": task.path,
                "depth": task.depth,
                "status": status,
                "asins": 0,
                "children": 0,
            }
            if not html or status not in {"ok", "captcha", "robot_check"}:
                logs.append(log)
                continue

            asins, children = self.parse_category_page(task, html)
            log["asins"] = len(asins)
            log["children"] = len(children)
            logs.append(log)

            chosen_asin = ""
            rank = 0
            for idx, asin in enumerate(asins, start=1):
                if asin not in used_asins:
                    chosen_asin = asin
                    rank = idx
                    break
            if chosen_asin:
                used_asins.add(chosen_asin)
                picks.append(
                    CategoryPick(
                        source=task.source,
                        department=task.department,
                        category_path=task.path,
                        category_name=task.path.split(" > ")[-1],
                        category_url=canonical,
                        category_node=self.category_node(canonical),
                        asin=chosen_asin,
                        rank_on_page=rank,
                        page_asin_count=len(asins),
                        depth=task.depth,
                        fetch_status=status,
                    )
                )
                print(f"[category {len(picks):03d}] {task.source} | {task.path} -> {chosen_asin}", flush=True)

            for child in children:
                child_url = self.canonical_url(child.url)
                if child_url not in visited_urls:
                    queue.append(child)

            if not fallback_added and not queue and len(picks) < min_count:
                queue.extend(FALLBACK_ROOTS)
                fallback_added = True

        return picks, logs

    def parse_jsonld_product(self, soup: BeautifulSoup) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            text = script.string or script.get_text()
            if not text:
                continue
            try:
                data = json.loads(text)
            except Exception:
                continue
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                graph = node.get("@graph")
                if isinstance(graph, list):
                    nodes.extend([x for x in graph if isinstance(x, dict)])
                node_type = node.get("@type")
                if isinstance(node_type, list):
                    is_product = "Product" in node_type
                else:
                    is_product = node_type == "Product"
                if not is_product:
                    continue
                result["jsonld_name"] = node.get("name", "")
                image = node.get("image", "")
                if isinstance(image, list):
                    image = image[0] if image else ""
                result["jsonld_image"] = image
                aggregate = node.get("aggregateRating") or {}
                if isinstance(aggregate, dict):
                    result["jsonld_rating"] = aggregate.get("ratingValue", "")
                    result["jsonld_review_count"] = aggregate.get("reviewCount", "")
                offers = node.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if isinstance(offers, dict):
                    result["jsonld_price"] = offers.get("price", "")
                    result["jsonld_currency"] = offers.get("priceCurrency", "")
        return result

    def extract_product_detail(self, asin: str) -> dict[str, Any]:
        url = f"{BASE}/dp/{asin}"
        html, status = self.fetch(url)
        product: dict[str, Any] = {
            "asin": asin,
            "product_url": url,
            "detail_status": status,
        }
        if not html:
            product["detail_error"] = status
            return product

        soup = BeautifulSoup(html, "html.parser")
        jsonld = self.parse_jsonld_product(soup)

        title_el = soup.select_one("#productTitle")
        title = self.clean_text(title_el.get_text(" ", strip=True)) if title_el else ""
        product["title"] = title or jsonld.get("jsonld_name", "")

        brand_el = soup.select_one("#bylineInfo")
        product["brand"] = self.clean_text(brand_el.get_text(" ", strip=True)) if brand_el else ""

        product["price"] = self.extract_price(soup, html, jsonld)
        product["rating"] = self.extract_rating(soup, jsonld)
        product["review_count"] = self.extract_review_count(soup, jsonld)
        product["bullet_points"] = self.extract_bullets(soup)
        product["image_url"] = self.extract_image(soup, jsonld)
        product["bsr_text"] = self.extract_bsr_text(soup)
        product["detail_error"] = "" if product.get("title") else "missing_title"
        return product

    def extract_price(self, soup: BeautifulSoup, html: str, jsonld: dict[str, Any]) -> str:
        json_price = self.clean_text(str(jsonld.get("jsonld_price", "")))
        if json_price:
            currency = self.clean_text(str(jsonld.get("jsonld_currency", "")))
            return f"{currency} {json_price}".strip()

        selectors = [
            "#corePriceDisplay_desktop_feature_div .a-offscreen",
            ".a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#priceblock_saleprice",
            "#sns-base-price",
        ]
        for selector in selectors:
            el = soup.select_one(selector)
            if el:
                text = self.clean_text(el.get_text(" ", strip=True))
                if re.search(r"\d", text):
                    return text

        whole = soup.select_one(".a-price-whole")
        fraction = soup.select_one(".a-price-fraction")
        if whole:
            whole_text = re.sub(r"[^\d,]", "", whole.get_text())
            fraction_text = re.sub(r"\D", "", fraction.get_text()) if fraction else ""
            return f"${whole_text}.{fraction_text or '00'}"

        match = re.search(r"\$[\d,]+\.\d{2}", html)
        return match.group(0) if match else ""

    def extract_rating(self, soup: BeautifulSoup, jsonld: dict[str, Any]) -> str:
        json_rating = self.clean_text(str(jsonld.get("jsonld_rating", "")))
        if json_rating:
            return json_rating
        selectors = [
            "#acrPopover .a-icon-alt",
            "span[data-hook='rating-out-of-text']",
            "i.a-icon-star span.a-icon-alt",
            ".a-icon-alt",
        ]
        for selector in selectors:
            el = soup.select_one(selector)
            if not el:
                continue
            text = self.clean_text(el.get_text(" ", strip=True) or el.get("title", ""))
            match = re.search(r"([\d.]+)", text)
            if match:
                return match.group(1)
        return ""

    def extract_review_count(self, soup: BeautifulSoup, jsonld: dict[str, Any]) -> str:
        json_count = self.clean_text(str(jsonld.get("jsonld_review_count", "")))
        if json_count and json_count != "0":
            return json_count
        el = soup.select_one("#acrCustomerReviewText")
        if el:
            match = re.search(r"([\d,]+)", el.get_text())
            if match:
                return match.group(1)
        return ""

    def extract_bullets(self, soup: BeautifulSoup) -> list[str]:
        bullets: list[str] = []
        for li in soup.select("#feature-bullets li"):
            text = self.clean_text(li.get_text(" ", strip=True))
            if text and len(text) > 8 and "make sure this fits" not in text.lower():
                bullets.append(text)
        return bullets[:8]

    def extract_image(self, soup: BeautifulSoup, jsonld: dict[str, Any]) -> str:
        image = self.clean_text(str(jsonld.get("jsonld_image", "")))
        if image:
            return image
        img = soup.select_one("#landingImage")
        if img:
            dynamic = img.get("data-a-dynamic-image")
            if dynamic:
                try:
                    data = json.loads(dynamic)
                    if isinstance(data, dict) and data:
                        return next(iter(data.keys()))
                except Exception:
                    pass
            return img.get("data-old-hires") or img.get("src") or ""
        return ""

    def extract_bsr_text(self, soup: BeautifulSoup) -> str:
        text_blocks: list[str] = []
        for selector in ["#SalesRank", "#detailBulletsWrapper_feature_div", "#productDetails_detailBullets_sections1"]:
            el = soup.select_one(selector)
            if el:
                text_blocks.append(self.clean_text(el.get_text(" ", strip=True)))
        combined = " ".join(text_blocks)
        if "Best Sellers Rank" not in combined:
            return ""
        idx = combined.find("Best Sellers Rank")
        return combined[idx : idx + 500]

    def download_image(self, asin: str, image_url: str, image_dir: Path) -> str:
        if not image_url:
            return ""
        image_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".jpg"
        parsed = urlparse(image_url)
        if parsed.path.lower().endswith(".png"):
            suffix = ".png"
        path = image_dir / f"{asin}{suffix}"
        if path.exists() and path.stat().st_size > 0:
            return str(path)
        try:
            response = self.session.get(image_url, timeout=self.timeout)
            time.sleep(self.sleep)
            if response.status_code == 200 and response.content:
                path.write_bytes(response.content)
                return str(path)
        except Exception:
            return ""
        return ""


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl Amazon 3C New Releases/BSR categories.")
    parser.add_argument("--output", default="data/amazon_3c/bsr_new_releases")
    parser.add_argument("--target", type=int, default=90)
    parser.add_argument("--min", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=260)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--skip-details", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    crawler = Amazon3CBsrCrawler(timeout=args.timeout, sleep=args.sleep)

    run_summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "target_count": args.target,
        "min_count": args.min,
        "max_category_pages": args.max_pages,
        "roots": [asdict(root) for root in ROOTS],
        "fallback_roots": [asdict(root) for root in FALLBACK_ROOTS],
    }

    print("[1/2] Discovering 3C New Releases category ASINs", flush=True)
    picks, category_logs = crawler.discover_categories(args.target, args.min, args.max_pages)
    write_json(output_dir / "category_picks.json", [asdict(pick) for pick in picks])
    write_json(output_dir / "category_page_logs.json", category_logs)

    if len(picks) < args.min:
        print(f"WARNING: only collected {len(picks)} category picks (< {args.min})", flush=True)

    products: list[dict[str, Any]] = []
    if not args.skip_details:
        print("[2/2] Fetching product details and images", flush=True)
        for index, pick in enumerate(picks, start=1):
            print(f"[detail {index:03d}/{len(picks):03d}] {pick.asin} | {pick.category_path}", flush=True)
            detail = crawler.extract_product_detail(pick.asin)
            local_image = crawler.download_image(pick.asin, detail.get("image_url", ""), output_dir / "images")
            row = {
                **asdict(pick),
                **detail,
                "bullet_1": (detail.get("bullet_points") or [""])[0] if detail.get("bullet_points") else "",
                "bullet_2": (detail.get("bullet_points") or ["", ""])[1] if len(detail.get("bullet_points") or []) > 1 else "",
                "bullet_3": (detail.get("bullet_points") or ["", "", ""])[2] if len(detail.get("bullet_points") or []) > 2 else "",
                "bullet_4": (detail.get("bullet_points") or ["", "", "", ""])[3] if len(detail.get("bullet_points") or []) > 3 else "",
                "bullet_5": (detail.get("bullet_points") or ["", "", "", "", ""])[4] if len(detail.get("bullet_points") or []) > 4 else "",
                "bullet_points_joined": " | ".join(detail.get("bullet_points") or []),
                "local_image": local_image,
            }
            products.append(row)
            if index % 10 == 0:
                write_json(output_dir / "products.json", products)
    write_json(output_dir / "products.json", products)

    fields = [
        "source",
        "department",
        "category_path",
        "category_name",
        "category_node",
        "category_url",
        "asin",
        "rank_on_page",
        "page_asin_count",
        "title",
        "brand",
        "price",
        "rating",
        "review_count",
        "bullet_1",
        "bullet_2",
        "bullet_3",
        "bullet_4",
        "bullet_5",
        "image_url",
        "local_image",
        "product_url",
        "bsr_text",
        "fetch_status",
        "detail_status",
        "detail_error",
    ]
    write_csv(output_dir / "products.csv", products, fields)
    write_csv(output_dir / "category_picks.csv", [asdict(pick) for pick in picks], list(asdict(picks[0]).keys()) if picks else [])

    run_summary.update(
        {
            "category_picks": len(picks),
            "products_with_title": sum(1 for product in products if product.get("title")),
            "products_with_price": sum(1 for product in products if product.get("price")),
            "products_with_rating": sum(1 for product in products if product.get("rating")),
            "products_with_review_count": sum(1 for product in products if product.get("review_count")),
            "products_with_five_bullets": sum(1 for product in products if product.get("bullet_5")),
            "products_with_image": sum(1 for product in products if product.get("image_url")),
            "products_with_local_image": sum(1 for product in products if product.get("local_image")),
            "category_pages_attempted": len(category_logs),
            "output_dir": str(output_dir),
        }
    )
    write_json(output_dir / "run_summary.json", run_summary)
    print(json.dumps(run_summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

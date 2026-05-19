#!/usr/bin/env python3
"""Find additional non-duplicate 3C BSR products suitable for selection review."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import re
import sys
from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_SCRIPT = Path("scripts/crawl_amazon_3c_bsr_new_releases.py")
OUTPUT_DIR = Path("data/amazon_3c/filtered_30_opportunities")

BIG_BRAND_TERMS = {
    "apple",
    "samsung",
    "sony",
    "microsoft",
    "xbox",
    "nintendo",
    "playstation",
    "google",
    "fitbit",
    "meta",
    "oculus",
    "amazon",
    "kindle",
    "ring",
    "roku",
    "garmin",
    "gopro",
    "canon",
    "nikon",
    "fujifilm",
    "dji",
    "hp",
    "hewlett",
    "dell",
    "lenovo",
    "asus",
    "acer",
    "msi",
    "brother",
    "epson",
    "logitech",
    "anker",
    "belkin",
    "bose",
    "jbl",
    "beats",
    "razer",
    "corsair",
    "steelseries",
    "sonos",
    "disney",
    "ugreen",
    "torras",
    "mosiso",
    "sandisk",
    "seagate",
    "western digital",
    "wd_black",
    "tp-link",
    "netgear",
}

HARD_STANDARD_TERMS = {
    "service",
    "warranty",
    "warranties",
    "license",
    "installation service",
    "sim card",
    "prepaid",
    "cell phone",
    "smartphone",
    "server",
    "camera body",
    "dslr camera",
    "digital camera",
    "television",
    "ssd",
    "hard drive",
    "memory card",
    "ram",
    "graphics card",
    "cpu",
    "processor",
    "motherboard",
    "game card",
    "standard edition",
    "digital code",
    "screen protector",
    "tempered glass",
    "macbook",
    "magsafe",
    "ipad",
    "airtag",
    "bootable",
    "macos",
    "switch/switch",
    "ps5",
    "disney",
    "sonos",
}

LOW_RELEVANCE_TERMS = {
    "mac games",
    "pc games",
    "playstation",
    "xbox",
    "nintendo",
    "wii",
    "sony psp",
    "vita",
    "video games",
}

PREFERRED_TERMS = {
    "case",
    "cases",
    "cover",
    "holder",
    "stand",
    "mount",
    "bracket",
    "organizer",
    "cord management",
    "cable organizer",
    "bag",
    "bags",
    "sleeve",
    "protector",
    "screen protector",
    "microphone",
    "adapter",
    "hub",
    "dock",
    "keyboard",
    "mouse pad",
    "webcam",
    "tripod",
    "filter",
    "light",
    "remote",
    "strap",
    "charging stand",
}

COMPLIANCE_RISK_TERMS = {
    "charger",
    "charging",
    "power strip",
    "surge protector",
    "battery",
    "wireless",
    "bluetooth",
    "wifi",
    "wi-fi",
    "radio",
    "gps",
    "camera",
    "security",
    "smart",
    "led",
}

COMMODITY_TERMS = {
    "usb cable",
    "hdmi cable",
    "adapter",
    "screen protector",
    "phone case",
    "clear case",
    "tempered glass",
    "cables",
}


def load_base_module():
    spec = importlib.util.spec_from_file_location("bsr_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def text_blob(row: dict[str, Any]) -> str:
    parts = [
        row.get("title", ""),
        row.get("brand", ""),
        row.get("category_path", ""),
        row.get("category_name", ""),
        " ".join(row.get("bullet_points") or []),
    ]
    return clean_text(" ".join(str(part) for part in parts)).lower()


def brand_title_blob(row: dict[str, Any]) -> str:
    return clean_text(f"{row.get('brand', '')} {str(row.get('title', ''))[:90]}").lower()


def category_pre_reject(path: str) -> str:
    lower = path.lower()
    hard_category_terms = [
        "warranties & services",
        "service & replacement plans",
        "installation services",
        "sim cards",
        "cell phones",
        "laptops",
        "desktops",
        "printers",
        "scanners",
        "servers",
        "tablets",
        "dslr cameras",
        "digital cameras",
        "point & shoot digital cameras",
        "televisions",
        "video games > mac games",
        "video games > pc games",
        "video games > nintendo",
        "video games > playstation",
        "video games > xbox",
        "video games > wii",
        "video games > sony psp",
    ]
    accessory_exceptions = ["accessories", "cases", "mounts", "bags", "controllers", "headsets"]
    if any(term in lower for term in hard_category_terms):
        if any(exception in lower for exception in accessory_exceptions) and "video games >" not in lower:
            return ""
        return "类目预过滤：整机/服务/软件/平台内容"
    return ""


def has_any(blob: str, terms: set[str]) -> list[str]:
    return sorted(term for term in terms if term in blob)


def parse_price(value: str) -> float | None:
    if not value:
        return None
    match = re.search(r"[\d,]+(?:\.\d+)?", value)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def parse_int(value: str) -> int | None:
    if value is None or value == "":
        return None
    match = re.search(r"[\d,]+", str(value))
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def parse_float(value: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def load_existing_asins() -> set[str]:
    paths = [
        Path("data/amazon_3c/bsr_new_releases/products.json"),
        Path("data/amazon_3c/crawler_audit/products.json"),
    ]
    asins: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in rows:
            asin = row.get("asin") if isinstance(row, dict) else None
            if asin:
                asins.add(asin)
    return asins


def load_known_category_tasks(module) -> list[Any]:
    path = Path("data/amazon_3c/bsr_new_releases/category_picks.json")
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    tasks = []
    for row in rows:
        category_path = row.get("category_path", "")
        lower = category_path.lower()
        if category_pre_reject(category_path):
            continue
        preferred_category_terms = [
            "accessories",
            "cases",
            "bags",
            "cables",
            "cord management",
            "microphones",
            "mounts",
            "power strips",
            "telephone accessories",
            "vehicle electronics accessories",
            "tablet accessories",
            "laptop accessories",
            "camera & photo > accessories",
            "binoculars & scopes",
            "lenses",
            "surveillance cameras",
            "headphones",
            "portable audio",
            "office electronics",
        ]
        if not any(term in lower for term in preferred_category_terms):
            continue
        tasks.append(
            module.CategoryTask(
                source=row.get("source", "New Releases"),
                department=row.get("department", ""),
                path=category_path,
                url=row.get("category_url", ""),
                depth=int(row.get("depth") or 1),
            )
        )
    return tasks


def analyze_candidate(row: dict[str, Any]) -> dict[str, Any]:
    blob = text_blob(row)
    price = parse_price(row.get("price", ""))
    rating = parse_float(row.get("rating", ""))
    reviews = parse_int(row.get("review_count", ""))
    big_hits = has_any(brand_title_blob(row), BIG_BRAND_TERMS)
    hard_hits = has_any(blob, HARD_STANDARD_TERMS)
    low_rel_hits = has_any(blob, LOW_RELEVANCE_TERMS)
    preferred_hits = has_any(blob, PREFERRED_TERMS)
    risk_hits = has_any(blob, COMPLIANCE_RISK_TERMS)
    commodity_hits = has_any(blob, COMMODITY_TERMS)

    exclude_reasons: list[str] = []
    if big_hits:
        exclude_reasons.append("大牌/平台品牌：" + ", ".join(big_hits[:4]))
    if hard_hits:
        exclude_reasons.append("强标品/整机/服务：" + ", ".join(hard_hits[:4]))
    if low_rel_hits:
        exclude_reasons.append("低相关内容/游戏类：" + ", ".join(low_rel_hits[:4]))
    if not row.get("title"):
        exclude_reasons.append("详情页标题缺失")
    if not row.get("image_url"):
        exclude_reasons.append("图片缺失")
    if len(row.get("bullet_points") or []) < 3:
        exclude_reasons.append("卖点信息不足")

    profit = 45
    feasibility = 55

    if preferred_hits:
        profit += 18
        feasibility += 12
    if price is None:
        profit -= 10
        feasibility -= 5
    elif 15 <= price <= 49:
        profit += 18
        feasibility += 8
    elif 8 <= price < 15 or 49 < price <= 79:
        profit += 8
    elif price > 120:
        profit -= 15
        feasibility -= 12

    if reviews is None:
        profit += 2
        feasibility -= 5
    elif reviews <= 50:
        profit += 10
        feasibility += 3
    elif reviews <= 500:
        profit += 14
        feasibility += 7
    elif reviews <= 2000:
        profit += 4
        feasibility += 1
    else:
        profit -= 8
        feasibility -= 5

    if rating is not None:
        if rating < 4.2:
            profit += 5
            feasibility -= 8
        elif rating <= 4.7:
            profit += 4
            feasibility += 4
        else:
            feasibility += 2

    if commodity_hits:
        profit -= 10
        feasibility -= 4
    if risk_hits:
        feasibility -= 12
        profit -= 3
    if "battery" in risk_hits or "power strip" in risk_hits or "surge protector" in risk_hits:
        feasibility -= 12
    if "wireless" in risk_hits or "bluetooth" in risk_hits or "wifi" in risk_hits:
        feasibility -= 8

    if big_hits:
        profit -= 35
        feasibility -= 30
    if hard_hits:
        profit -= 35
        feasibility -= 35
    if low_rel_hits:
        profit -= 30
        feasibility -= 25

    profit = max(0, min(100, round(profit)))
    feasibility = max(0, min(100, round(feasibility)))
    recommendation = max(0, min(100, round(profit * 0.55 + feasibility * 0.45)))

    if recommendation >= 78:
        suitability = "适合优先研究"
    elif recommendation >= 65:
        suitability = "适合观察/二次验证"
    elif recommendation >= 50:
        suitability = "谨慎，需补数据验证"
    else:
        suitability = "不建议优先做"

    opportunity = build_opportunity(row, preferred_hits, reviews, price, rating)
    risks = build_risks(row, risk_hits, commodity_hits, reviews, rating)
    feasibility_note = build_feasibility_note(row, suitability, preferred_hits, risk_hits, commodity_hits)

    return {
        "exclude_reasons": "；".join(exclude_reasons),
        "big_brand_hits": ", ".join(big_hits),
        "standard_hits": ", ".join(hard_hits),
        "low_relevance_hits": ", ".join(low_rel_hits),
        "preferred_hits": ", ".join(preferred_hits),
        "risk_hits": ", ".join(risk_hits),
        "commodity_hits": ", ".join(commodity_hits),
        "price_num": price,
        "rating_num": rating,
        "review_count_num": reviews,
        "profit_score": profit,
        "feasibility_score": feasibility,
        "recommendation_score": recommendation,
        "china_seller_suitability": suitability,
        "opportunity_point": opportunity,
        "risk_point": risks,
        "feasibility_analysis": feasibility_note,
    }


def build_opportunity(row: dict[str, Any], preferred_hits: list[str], reviews: int | None, price: float | None, rating: float | None) -> str:
    path = row.get("category_path", "")
    ideas: list[str] = []
    if preferred_hits:
        ideas.append("轻小件/配件属性明显，可通过材质、套装、颜色、兼容型号、包装和说明书做差异化")
    if "mount" in " ".join(preferred_hits) or "stand" in " ".join(preferred_hits) or "holder" in " ".join(preferred_hits):
        ideas.append("结构件适合中国供应链开模或小改款，重点做稳定性、承重、安装体验")
    if "case" in " ".join(preferred_hits) or "bag" in " ".join(preferred_hits) or "protector" in " ".join(preferred_hits):
        ideas.append("可做细分型号适配和外观差异，但要避免纯价格战")
    if "microphone" in " ".join(preferred_hits) or "light" in " ".join(preferred_hits) or "webcam" in " ".join(preferred_hits):
        ideas.append("内容创作者场景可套装化，卖点能围绕直播/会议/拍摄效率展开")
    if reviews is not None and reviews <= 500:
        ideas.append("评论壁垒相对不高，新品仍可能切入")
    if price is not None and 15 <= price <= 49:
        ideas.append("价格带适合小件FBA和广告测试")
    if rating is not None and rating < 4.4:
        ideas.append("现有体验可能有改进空间，可从差评中找结构/兼容/说明痛点")
    if not ideas:
        ideas.append(f"{path} 有榜单曝光，但需要进一步验证真实需求和差异化空间")
    return "；".join(ideas[:3])


def build_risks(row: dict[str, Any], risk_hits: list[str], commodity_hits: list[str], reviews: int | None, rating: float | None) -> str:
    risks: list[str] = []
    if commodity_hits:
        risks.append("标品化/同质化明显，容易价格战")
    if risk_hits:
        risks.append("涉及" + "、".join(risk_hits[:5]) + "，需检查FCC/UL/电池/安全合规或售后责任")
    if reviews is not None and reviews > 2000:
        risks.append("评论壁垒偏高，冷启动广告和转化压力大")
    if rating is not None and rating < 4.2:
        risks.append("低评分说明质量/体验风险较高，需要先看差评原因")
    if not row.get("review_count"):
        risks.append("评论数为空，可能是新品也可能是页面字段未公开，需求强度不确定")
    if not risks:
        risks.append("主要风险是榜单热度不等于销量，仍需验证搜索量、购买率和头部集中度")
    return "；".join(risks[:3])


def build_feasibility_note(row: dict[str, Any], suitability: str, preferred_hits: list[str], risk_hits: list[str], commodity_hits: list[str]) -> str:
    parts = [suitability]
    if preferred_hits:
        parts.append("供应链侧可通过轻改款/组合装/配件化运营")
    if risk_hits:
        parts.append("上架前必须做合规和退货风险评估")
    if commodity_hits:
        parts.append("需要避开纯同款，优先找细分人群或场景")
    if not risk_hits and not commodity_hits:
        parts.append("更适合先做小批量测款")
    return "；".join(parts)


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


def main() -> int:
    module = load_base_module()
    crawler = module.Amazon3CBsrCrawler(timeout=10, sleep=0.05)
    existing_asins = load_existing_asins()

    roots = load_known_category_tasks(module) + list(module.ROOTS) + list(module.FALLBACK_ROOTS)
    queue = deque(roots)
    visited_urls: set[str] = set()
    probed_asins: set[str] = set(existing_asins)
    accepted_pool: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []

    max_pages = 320
    max_details = 260
    max_asins_per_category = 20
    detail_count = 0

    print(f"Existing ASINs excluded: {len(existing_asins)}", flush=True)
    while queue and len(visited_urls) < max_pages and detail_count < max_details and len(accepted_pool) < 80:
        task = queue.popleft()
        canonical = crawler.canonical_url(task.url)
        if canonical in visited_urls:
            continue
        visited_urls.add(canonical)
        html, status = crawler.fetch(canonical)
        if not html:
            logs.append({"url": canonical, "path": task.path, "source": task.source, "status": status, "asins": 0, "children": 0})
            continue
        asins, children = crawler.parse_category_page(task, html)
        logs.append({"url": canonical, "path": task.path, "source": task.source, "status": status, "asins": len(asins), "children": len(children)})

        for child in children:
            child_url = crawler.canonical_url(child.url)
            if child_url not in visited_urls:
                queue.append(child)

        if task.depth == 0:
            continue
        pre_reject = category_pre_reject(task.path)
        if pre_reject:
            rejected.append(
                {
                    "source": task.source,
                    "department": task.department,
                    "category_path": task.path,
                    "category_url": canonical,
                    "exclude_reasons": pre_reject,
                }
            )
            continue

        accepted_this_category = False
        for rank, asin in enumerate(asins[:max_asins_per_category], start=1):
            if asin in probed_asins:
                continue
            probed_asins.add(asin)
            detail_count += 1
            detail = crawler.extract_product_detail(asin)
            if detail.get("image_url"):
                detail["local_image"] = crawler.download_image(asin, detail.get("image_url", ""), OUTPUT_DIR / "images")
            bullets = detail.get("bullet_points") or []
            row = {
                "source": task.source,
                "department": task.department,
                "category_path": task.path,
                "category_name": task.path.split(" > ")[-1],
                "category_url": canonical,
                "category_node": crawler.category_node(canonical),
                "rank_on_page": rank,
                "page_asin_count": len(asins),
                **detail,
                "bullet_1": bullets[0] if len(bullets) > 0 else "",
                "bullet_2": bullets[1] if len(bullets) > 1 else "",
                "bullet_3": bullets[2] if len(bullets) > 2 else "",
                "bullet_4": bullets[3] if len(bullets) > 3 else "",
                "bullet_5": bullets[4] if len(bullets) > 4 else "",
                "bullet_points_joined": " | ".join(bullets),
            }
            analysis = analyze_candidate(row)
            row.update(analysis)
            hard_reject = bool(row["exclude_reasons"])
            if hard_reject:
                rejected.append(row)
                continue
            if row["recommendation_score"] < 50:
                rejected.append({**row, "exclude_reasons": "综合分低于50"})
                continue
            accepted_pool.append(row)
            accepted_this_category = True
            if len(accepted_pool) % 5 == 0:
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                write_json(OUTPUT_DIR / "accepted_pool.partial.json", accepted_pool)
                write_json(OUTPUT_DIR / "rejected.partial.json", rejected)
            print(
                f"[pool {len(accepted_pool):02d}] {task.source} | {task.path} -> {asin} score={row['recommendation_score']}",
                flush=True,
            )
            break

        if not accepted_this_category and len(asins) == 0:
            continue

    selected = sorted(
        accepted_pool,
        key=lambda row: (row.get("recommendation_score", 0), row.get("profit_score", 0), row.get("feasibility_score", 0)),
        reverse=True,
    )[:30]
    for idx, row in enumerate(selected, start=1):
        row["final_rank"] = idx

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_DIR / "accepted_pool.json", accepted_pool)
    write_json(OUTPUT_DIR / "selected_30.json", selected)
    write_json(OUTPUT_DIR / "rejected.json", rejected)
    write_json(OUTPUT_DIR / "crawl_logs.json", logs)
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "existing_asins_excluded": len(existing_asins),
        "category_pages_visited": len(visited_urls),
        "detail_pages_attempted": detail_count,
        "accepted_pool": len(accepted_pool),
        "selected": len(selected),
        "rejected": len(rejected),
        "output_dir": str(OUTPUT_DIR),
    }
    write_json(OUTPUT_DIR / "summary.json", summary)

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
    write_csv(OUTPUT_DIR / "selected_30.csv", selected, fields)
    write_csv(OUTPUT_DIR / "accepted_pool.csv", accepted_pool, fields)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if len(selected) >= 30 else 2


if __name__ == "__main__":
    raise SystemExit(main())

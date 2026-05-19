#!/usr/bin/env python3
"""Build Excel workbook for 30 filtered Amazon 3C BSR opportunities."""

from __future__ import annotations

import json
import re
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from PIL import Image as PILImage


DATA_DIR = Path("data/amazon_3c/filtered_30_opportunities")
OUTPUT_DIR = Path("outputs/amazon_3c_filtered_opportunities")
OUTPUT_XLSX = OUTPUT_DIR / "amazon_3c_bsr_filtered_30_opportunities.xlsx"
THUMB_DIR = DATA_DIR / "thumbs_final"

REMOVE_ASINS = {
    "B0GW6LKFV3",  # Starlink / SpaceX ecosystem
    "B0GL7W53X4",  # Bitcoin miner, high regulatory/commodity risk
    "B0G92PM3ZN",  # stickers, weak 3C relevance
}

REPLACEMENT_ASINS = [
    "B0GW87PLJH",
    "B0GLH1115J",
    "B0GCZ8F63H",
]

GLOBAL_BRAND_OR_IP_TERMS = [
    "apple",
    "samsung",
    "sonos",
    "disney",
    "starlink",
    "spacex",
    "nintendo",
    "playstation",
    "xbox",
    "google",
    "fitbit",
    "sony",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_price(value: str) -> float | None:
    if not value:
        return None
    match = re.search(r"[\d,]+(?:\.\d+)?", str(value))
    return float(match.group(0).replace(",", "")) if match else None


def parse_int(value: str) -> int | None:
    if value is None or value == "":
        return None
    match = re.search(r"[\d,]+", str(value))
    return int(match.group(0).replace(",", "")) if match else None


def parse_float(value: str) -> float | None:
    try:
        return float(str(value))
    except Exception:
        return None


def text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key, ""))
        for key in ["title", "brand", "category_path", "bullet_1", "bullet_2", "bullet_3", "bullet_4", "bullet_5"]
    ).lower()


def adjusted_analysis(row: dict[str, Any]) -> dict[str, Any]:
    blob = text(row)
    price = parse_price(row.get("price", ""))
    reviews = parse_int(row.get("review_count", ""))
    rating = parse_float(row.get("rating", ""))

    profit = int(row.get("profit_score") or 50)
    feasibility = int(row.get("feasibility_score") or 50)
    notes: list[str] = []

    if any(term in blob for term in GLOBAL_BRAND_OR_IP_TERMS):
        profit = min(profit, 35)
        feasibility = min(feasibility, 30)
        notes.append("依赖大品牌/IP生态，不能作为优先私标方向")

    if any(term in blob for term in ["power saver", "energy saving", "stopwatt", "voltage optimization", "remove surges"]):
        profit = min(profit, 35)
        feasibility = min(feasibility, 20)
        notes.append("节电器/省电宣称合规和投诉风险高，不建议优先做")

    if any(term in blob for term in ["power strip", "surge protector", "charger", "charging", "battery", "ac/dc"]):
        feasibility = min(feasibility, 55)
        notes.append("电源/充电/安规责任重，需UL/ETL/FCC等合规验证")

    if any(term in blob for term in ["bluetooth", "wireless", "wifi", "wi-fi", "2.4ghz", "5ghz"]):
        feasibility = min(feasibility, 58)
        notes.append("无线类需FCC/射频合规，售后和连接稳定性风险高")

    if any(term in blob for term in ["printer", "shredder", "dvd player", "cd player", "speaker", "headphones", "earbuds"]):
        feasibility = min(feasibility, 65)
        notes.append("功能件售后和质量一致性要求高，适合有工厂/质检能力再做")

    if any(term in blob for term in ["bag", "case", "strap", "mount", "stand", "cord", "organizer", "cable ties", "backdrop"]):
        profit = max(profit, min(82, profit + 4))
        feasibility = max(feasibility, min(82, feasibility + 6))
        notes.append("轻小配件可通过材质、套装、颜色、适配场景做差异化")

    if reviews is not None and reviews > 2000:
        profit = min(profit, 58)
        notes.append("评论壁垒偏高，广告冷启动压力大")
    elif reviews is not None and reviews <= 500:
        notes.append("评论壁垒相对低，适合小批量测款")
    elif reviews is None:
        notes.append("评论数为空，需复核是新品无评论还是页面字段缺失")

    if price is not None:
        if 15 <= price <= 60:
            notes.append("价格带适合轻量FBA和广告测试")
        elif price < 10:
            profit = min(profit, 55)
            notes.append("价格过低，利润空间和广告承受力弱")
        elif price > 100:
            feasibility = min(feasibility, 55)
            notes.append("客单价高，退货和资金占用压力更大")

    if rating is not None and rating < 4.2:
        feasibility = min(feasibility, 50)
        notes.append("评分偏低，需先拆差评确认是否可改进")

    profit = max(0, min(100, round(profit)))
    feasibility = max(0, min(100, round(feasibility)))
    recommendation = max(0, min(100, round(profit * 0.55 + feasibility * 0.45)))

    if recommendation >= 78:
        fit = "适合优先研究"
    elif recommendation >= 65:
        fit = "适合观察/二次验证"
    elif recommendation >= 50:
        fit = "谨慎，需补数据验证"
    else:
        fit = "不建议优先做"

    opportunity = row.get("opportunity_point", "")
    risk = row.get("risk_point", "")
    feasibility_note = row.get("feasibility_analysis", "")
    extra = "；".join(dict.fromkeys(notes))
    if extra:
        risk = f"{risk}；{extra}" if risk else extra
        feasibility_note = f"{feasibility_note}；{extra}" if feasibility_note else extra

    return {
        "adj_profit_score": profit,
        "adj_feasibility_score": feasibility,
        "adj_recommendation_score": recommendation,
        "final_suitability": fit,
        "final_opportunity": opportunity,
        "final_risk": risk,
        "final_feasibility": feasibility_note,
        "final_remark": extra,
    }


def curate_rows() -> list[dict[str, Any]]:
    selected = load_json(DATA_DIR / "selected_30.json")
    rejected = load_json(DATA_DIR / "rejected.json")
    rows_by_asin = {row["asin"]: row for row in selected if row.get("asin") and row.get("asin") not in REMOVE_ASINS}
    rejected_by_asin = {row.get("asin"): row for row in rejected if row.get("asin")}

    for asin in REPLACEMENT_ASINS:
        row = rejected_by_asin.get(asin)
        if not row:
            continue
        if not row.get("local_image"):
            row["local_image"] = download_image_stdlib(asin, row.get("image_url", ""), DATA_DIR / "images")
        rows_by_asin[asin] = row

    rows = list(rows_by_asin.values())
    for row in rows:
        row.update(adjusted_analysis(row))

    rows = sorted(
        rows,
        key=lambda row: (row.get("adj_recommendation_score", 0), row.get("adj_profit_score", 0), row.get("adj_feasibility_score", 0)),
        reverse=True,
    )[:30]
    for idx, row in enumerate(rows, start=1):
        row["final_rank"] = idx
    write_json(DATA_DIR / "selected_30_curated.json", rows)
    return rows


def download_image_stdlib(asin: str, image_url: str, image_dir: Path) -> str:
    if not image_url:
        return ""
    image_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".png" if ".png" in image_url.lower() else ".jpg"
    path = image_dir / f"{asin}{suffix}"
    if path.exists() and path.stat().st_size > 0:
        return str(path)
    try:
        request = urllib.request.Request(
            image_url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read()
        if data:
            path.write_bytes(data)
            return str(path)
    except Exception:
        return ""
    return ""


def make_thumb(image_path: str, asin: str) -> str:
    if not image_path:
        return ""
    src = Path(image_path)
    if not src.exists() or src.stat().st_size == 0:
        return ""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    out = THUMB_DIR / f"{asin}.png"
    try:
        with PILImage.open(src) as image:
            image = image.convert("RGB")
            image.thumbnail((96, 96))
            canvas = PILImage.new("RGB", (96, 96), "white")
            canvas.paste(image, ((96 - image.width) // 2, (96 - image.height) // 2))
            canvas.save(out, "PNG", optimize=True)
        return str(out)
    except Exception:
        return ""


def style_header(ws, row: int, fill: str) -> None:
    for cell in ws[row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def set_border(ws, min_row: int, max_row: int, min_col: int, max_col: int) -> None:
    side = Side(style="thin", color="D9E2F3")
    border = Border(left=side, right=side, top=side, bottom=side)
    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def build_workbook(rows: list[dict[str, Any]]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "30个筛选机会品"
    headers = [
        "排名",
        "图片",
        "ASIN",
        "标题",
        "类目路径",
        "榜单",
        "价格",
        "评分",
        "评论数",
        "是否适合中国卖家",
        "可赚钱性评分",
        "运营可行性评分",
        "综合推荐分",
        "机会点",
        "风险点",
        "多维度可行性分析",
        "Bullet 1",
        "Bullet 2",
        "Bullet 3",
        "Bullet 4",
        "Bullet 5",
        "商品链接",
        "榜单链接",
        "图片URL",
    ]
    ws.append(headers)
    style_header(ws, 1, "1F4E78")
    ws.freeze_panes = "D2"

    for row in rows:
        ws.append(
            [
                row.get("final_rank"),
                "",
                row.get("asin"),
                row.get("title"),
                row.get("category_path"),
                row.get("source"),
                row.get("price"),
                row.get("rating"),
                row.get("review_count"),
                row.get("final_suitability"),
                row.get("adj_profit_score"),
                row.get("adj_feasibility_score"),
                row.get("adj_recommendation_score"),
                row.get("final_opportunity"),
                row.get("final_risk"),
                row.get("final_feasibility"),
                row.get("bullet_1"),
                row.get("bullet_2"),
                row.get("bullet_3"),
                row.get("bullet_4"),
                row.get("bullet_5"),
                row.get("product_url"),
                row.get("category_url"),
                row.get("image_url"),
            ]
        )
        excel_row = ws.max_row
        ws.row_dimensions[excel_row].height = 78
        thumb = make_thumb(row.get("local_image", ""), row.get("asin", f"row{excel_row}"))
        if thumb:
            image = XLImage(thumb)
            image.width = 72
            image.height = 72
            ws.add_image(image, f"B{excel_row}")
        for col in [22, 23, 24]:
            cell = ws.cell(excel_row, col)
            if cell.value:
                cell.hyperlink = cell.value
                cell.style = "Hyperlink"
        score = row.get("adj_recommendation_score", 0)
        score_cell = ws.cell(excel_row, 13)
        if score >= 75:
            score_cell.fill = PatternFill("solid", fgColor="C6E0B4")
        elif score >= 60:
            score_cell.fill = PatternFill("solid", fgColor="FFF2CC")
        else:
            score_cell.fill = PatternFill("solid", fgColor="F4CCCC")

    widths = {
        "A": 8,
        "B": 14,
        "C": 14,
        "D": 55,
        "E": 42,
        "F": 14,
        "G": 12,
        "H": 9,
        "I": 10,
        "J": 22,
        "K": 12,
        "L": 14,
        "M": 12,
        "N": 48,
        "O": 55,
        "P": 55,
        "Q": 40,
        "R": 40,
        "S": 40,
        "T": 40,
        "U": 40,
        "V": 28,
        "W": 28,
        "X": 28,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.auto_filter.ref = f"A1:X{len(rows) + 1}"
    set_border(ws, 1, len(rows) + 1, 1, len(headers))
    table = Table(displayName="Filtered3COpportunities", ref=f"A1:X{len(rows) + 1}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
    ws.add_table(table)

    overview = wb.create_sheet("概览", 0)
    overview["A1"] = "3C BSR 非大牌/非强标品机会品筛选"
    overview["A1"].font = Font(size=18, bold=True, color="1F4E78")
    overview.merge_cells("A1:H1")
    overview["A2"] = f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}；数据源：Amazon BSR/New Releases公开榜单页 + 商品详情页；未调用MCP。"
    overview.merge_cells("A2:H2")
    metrics = [
        ("候选ASIN", load_json(DATA_DIR / "summary.json").get("candidate_asins", "")),
        ("详情尝试", load_json(DATA_DIR / "summary.json").get("detail_pages_attempted", "")),
        ("最终入表", len(rows)),
        ("推荐分>=70", sum(1 for row in rows if row.get("adj_recommendation_score", 0) >= 70)),
        ("不建议/谨慎", sum(1 for row in rows if row.get("adj_recommendation_score", 0) < 60)),
        ("图片嵌入", sum(1 for row in rows if row.get("local_image"))),
    ]
    for i, (label, value) in enumerate(metrics):
        row = 4 + (i // 3) * 3
        col = 1 + (i % 3) * 3
        overview.cell(row, col, label)
        overview.cell(row + 1, col, value)
        overview.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col + 1)
        overview.merge_cells(start_row=row + 1, start_column=col, end_row=row + 1, end_column=col + 1)
        overview.cell(row, col).fill = PatternFill("solid", fgColor="D9EAF7")
        overview.cell(row, col).font = Font(bold=True, color="1F4E78")
        overview.cell(row + 1, col).font = Font(size=16, bold=True)
        overview.cell(row + 1, col).alignment = Alignment(horizontal="center")

    overview["A11"] = "筛选口径"
    overview["A11"].font = Font(size=13, bold=True, color="1F4E78")
    rules = [
        "硬排除：Apple/Samsung/Sony/Microsoft/Nintendo/Google/Sonos/Disney/Starlink 等大牌或IP生态。",
        "硬排除：整机、服务/授权、游戏软件、手机/笔记本/服务器等强标品或非私标方向。",
        "保留但降分：无线、蓝牙、WiFi、电源、节电器、打印/播放器等合规或售后重的功能件。",
        "分数含义：综合推荐分=可赚钱性55%+运营可行性45%，100为极度推荐，0为完全不推荐。",
    ]
    for idx, rule in enumerate(rules, start=12):
        overview.cell(idx, 1, f"{idx - 11}. {rule}")
        overview.merge_cells(start_row=idx, start_column=1, end_row=idx, end_column=8)

    overview["A18"] = "推荐分分布"
    overview["A18"].font = Font(size=13, bold=True, color="1F4E78")
    buckets = Counter(
        "70+" if row.get("adj_recommendation_score", 0) >= 70 else "60-69" if row.get("adj_recommendation_score", 0) >= 60 else "<60"
        for row in rows
    )
    overview.append([])
    overview.append(["区间", "数量"])
    style_header(overview, 20, "5B9BD5")
    for bucket in ["70+", "60-69", "<60"]:
        overview.append([bucket, buckets.get(bucket, 0)])
    for col in range(1, 9):
        overview.column_dimensions[get_column_letter(col)].width = 18
    overview.column_dimensions["A"].width = 34
    set_border(overview, 20, 23, 1, 2)

    rules_ws = wb.create_sheet("评分规则")
    rules_ws.append(["维度", "加分/扣分逻辑"])
    style_header(rules_ws, 1, "8064A2")
    rule_rows = [
        ("可赚钱性", "价格带15-60、评论壁垒低、轻小配件、可套装/材质/适配差异化加分；大牌/IP依赖、价格过低、评论壁垒高扣分。"),
        ("运营可行性", "轻小件、非电源/非无线、售后简单加分；无线、蓝牙、WiFi、电源、充电、打印/播放器等功能件扣分。"),
        ("综合推荐分", "可赚钱性55% + 运营可行性45%；低分品不是推荐，只是保留作反例或观察样本。"),
        ("数据限制", "BSR/New Releases榜单不等于销量、搜索量或利润；未接入MCP，所以没有PPC、购买率、集中度、真实月销量。"),
    ]
    for item in rule_rows:
        rules_ws.append(list(item))
    rules_ws.column_dimensions["A"].width = 18
    rules_ws.column_dimensions["B"].width = 90
    set_border(rules_ws, 1, len(rule_rows) + 1, 1, 2)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wb.save(OUTPUT_XLSX)


def verify(path: Path) -> dict[str, Any]:
    wb = load_workbook(path)
    ws = wb["30个筛选机会品"]
    return {
        "sheets": wb.sheetnames,
        "rows": ws.max_row - 1,
        "cols": ws.max_column,
        "images": len(getattr(ws, "_images", [])),
        "required_ok": {"概览", "30个筛选机会品", "评分规则"}.issubset(set(wb.sheetnames)),
    }


def main() -> int:
    rows = curate_rows()
    build_workbook(rows)
    checks = verify(OUTPUT_XLSX)
    write_json(OUTPUT_DIR / "verification.json", checks)
    print(json.dumps({"output": str(OUTPUT_XLSX), **checks}, ensure_ascii=False, indent=2))
    return 0 if checks["rows"] == 30 and checks["required_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

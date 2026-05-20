#!/usr/bin/env python3
"""Parser checks for granular SellerSprite OpenCLI extraction."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "collect_sellersprite_opencli_asin_keywords.py"
spec = importlib.util.spec_from_file_location("sellersprite_opencli_granular", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_primary_traffic_keyword_parser() -> None:
    blocks = [
        {
            "name": "main_relation",
            "text": (
                "主要流量词 收起 流量词 流量占比 流量词类型 自然排名 广告排名 "
                "white sheets 白床单 19.80% 主要流量词 自然搜索词 24 第1页,24/70 昨日06:35排名 前3页无排名 "
                "white queen sheets 白色大号床单 7.45% 主要流量词 自然搜索词 品牌广告词 "
                "8 第1页,8/53 昨日06:34排名 62 第2页,6/52 05月15日排名 点击查看全部流量词"
            ),
        }
    ]
    rows = module.parse_primary_traffic_keywords("B0CT9R7WN5", blocks)
    assert len(rows) == 2
    assert rows[0]["keyword"] == "white sheets"
    assert rows[0]["keyword_translation"] == "白床单"
    assert rows[0]["traffic_share"] == 0.198
    assert rows[0]["organic_rank"] == 24
    assert rows[0]["ad_not_top_3_pages"] is True
    assert rows[1]["is_brand_ad_keyword"] is True
    assert rows[1]["ad_rank"] == 62


def test_traffic_source_product_parser() -> None:
    rows = [
        [
            "",
            "",
            "",
            (
                "Queen Size 4 Piece Sheet Set - White Oeko-Tex Bed Sheet Set "
                "变体数:362 Color: 01 - White | Size: Queen $21.24 4.5/438,993 B01M16WBW1"
            ),
            "自然搜索 亚马逊推荐 PPC广告",
            "3,758",
            "2,475",
            "177",
            "0",
            "0",
            "54",
            "809",
            "412",
            "1,293",
        ]
    ]
    parsed = module.parse_traffic_source_products("B0CT9R7WN5", rows)
    assert len(parsed) == 1
    first = parsed[0]
    assert first["related_asin"] == "B01M16WBW1"
    assert first["variation_count"] == 362
    assert first["price"] == 21.24
    assert first["rating_count"] == 438993
    assert first["all_traffic_keywords"] == 3758
    assert first["brand_ad_keywords"] == 1293
    assert first["has_ppc_ad_source"] is True


def test_keyword_miner_row_parser() -> None:
    row = [
        "1",
        "phone stand AC 手机支架",
        "",
        "Video Games Office Products",
        "",
        "100 177",
        "250,587 8,353",
        "9,322 3.72%",
        "7,175,246 114,996",
        "212",
        "13",
        "2.3 109,241",
        "391",
        "24.28% 19.44%",
        "$0.77 $1.03 $1.29",
        "$9.99 70,666 ( 4.5 )",
        "",
    ]
    parsed = module.parse_keyword_miner_rows("phone stand", [row])
    assert len(parsed) == 1
    first = parsed[0]
    assert first["keyword"] == "phone stand"
    assert first["keyword_translation"] == "手机支架"
    assert first["is_amazon_choice_recommended"] is True
    assert first["monthly_searches"] == 250587
    assert round(first["purchase_rate"], 4) == 0.0372
    assert first["ppc_bid_exact"] == 1.03


def test_keyword_reverse_row_parser() -> None:
    row = [
        "1",
        "white sheets 白床单",
        "16.68% 3,827 主要流量词 -",
        "自然搜索词",
        "* 自然: 100.00% * 广告: 0.00%",
        "24 第1页, 24 / 70 昨日06:35排名",
        "前3页无排名",
        "",
        "53,000",
        "30,700 1,023",
        "10",
        "1",
        "417 1.36%",
        "798,663 12,551",
        "0.3 95,138",
        "81",
        "39.69% 22.13%",
        "$1.88 $2.51 $3.14",
        "",
    ]
    parsed = module.parse_keyword_reverse_rows("B0CT9R7WN5", [row])
    assert len(parsed) == 1
    first = parsed[0]
    assert first["keyword"] == "white sheets"
    assert first["traffic_share"] == 0.1668
    assert first["traffic_value"] == 3827
    assert first["natural_traffic_share"] == 1.0
    assert first["organic_rank"] == 24
    assert first["ad_not_top_3_pages"] is True
    assert first["monthly_purchases"] == 417
    assert round(first["purchase_rate"], 4) == 0.0136


if __name__ == "__main__":
    test_primary_traffic_keyword_parser()
    test_traffic_source_product_parser()
    test_keyword_miner_row_parser()
    test_keyword_reverse_row_parser()
    print("parser tests passed")

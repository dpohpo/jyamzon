---
name: jyamzon
description: Crawl public Amazon US 3C BSR/New Releases pages, filter non-big-brand product-selection candidates, score China-seller feasibility, and export Excel workbooks. Use when the user asks for Amazon 3C product selection, BSR/new-release crawling, non-MCP Amazon research, ASIN discovery, China seller fit, opportunity/risk scoring, or reusable Amazon selection workflows.
---

# jyamzon

Use this skill to run a local, non-MCP Amazon 3C product-selection workflow.

## Core Boundary

- Uses public Amazon BSR/New Releases/category/detail pages only.
- Does not call SellerSprite MCP, SP-API, Keepa, or paid APIs.
- Good for discovery, triage, and building a shortlist.
- Not sufficient for final decisions on search volume, purchases, PPC, sales, market concentration, or conversion data.

## Quick Start

From the cloned `jyamzon` repo:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Broad New Releases crawl:

```bash
python scripts/crawl_amazon_3c_bsr_new_releases.py --target 90 --min 50
python scripts/build_3c_bsr_excel.py
```

Filtered opportunity crawl:

```bash
python scripts/crawl_3c_filtered_opportunities_fast.py
python scripts/retry_filtered_opportunity_details.py
python scripts/build_filtered_30_opportunity_excel.py
```

## Workflow

1. Start with `crawl_amazon_3c_bsr_new_releases.py` to map 50-100 visible 3C categories.
2. Build the broad workbook with `build_3c_bsr_excel.py`.
3. Run `crawl_3c_filtered_opportunities_fast.py` to collect non-duplicate candidates and apply hard filters.
4. Run `retry_filtered_opportunity_details.py` if selected count is below 30 or many detail pages are missing fields.
5. Build the final workbook with `build_filtered_30_opportunity_excel.py`.
6. In the final response, report:
   - workbook path
   - candidate count
   - detail pages attempted
   - final selected count
   - key data limitations
7. If the user asks what crawler-only data can replace MCP/API calls, run `scripts/run_claude_crawler_audit.py --skip-reviews` when a Claude Amazon crawler is available, then summarize field coverage and gaps.

## Hard Filters

Exclude:

- major brand/platform/IP ecosystems such as Apple, Samsung, Sony, Microsoft, Nintendo, Google, Sonos, Disney, Starlink
- phones, laptops, desktops, tablets, servers, printers as primary products
- service plans, warranties, licenses, software, game editions, digital codes
- products where public page data is too incomplete to inspect title/image

## Scoring

Score 0-100:

- `profit_score`: likely margin/ad headroom/differentiation potential
- `feasibility_score`: operational feasibility for China sellers
- `recommendation_score`: `profit_score * 0.55 + feasibility_score * 0.45`

High-risk categories such as wireless, Bluetooth, Wi-Fi, power strips, chargers, batteries, security cameras, and child-use products should be downgraded unless compliance and QA capability is proven.

## Evidence Standard

Be explicit that BSR/New Releases rank is not demand proof. It is only a discovery signal. Recommend paid-data validation only after the crawler creates a shortlist.

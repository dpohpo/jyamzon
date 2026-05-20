---
name: jyamzon
description: Crawl public Amazon US 3C pages and optionally enrich a known ASIN with granular SellerSprite web/extension data through OpenCLI, then export analyst-ready Excel workbooks. Use when the user says /jyamzon, $jyamzon, asks for Amazon 3C product selection, BSR/New Releases crawling, non-MCP Amazon research, ASIN discovery, SellerSprite OpenCLI scraping, related keyword extraction, China seller fit, opportunity scoring, or reusable Amazon selection workflows.
---

# jyamzon

Use this skill to run local Amazon 3C product-selection and ASIN enrichment workflows.

## Core Boundary

- The crawler workflow uses public Amazon BSR/New Releases/category/detail pages only.
- The OpenCLI enrichment workflow can read SellerSprite data already visible in the user's logged-in Chrome web page or SellerSprite extension overlay.
- Neither workflow calls SellerSprite MCP, SP-API, Keepa, or paid APIs.
- OpenCLI enrichment is not API parity. It is only as complete as the current page/plugin renders.
- Excel outputs must be granular: one metric, identifier, boolean, date, or numeric value per cell. Keep raw blobs in JSON audit files, not workbook business sheets.

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

Granular SellerSprite OpenCLI ASIN enrichment:

```bash
python scripts/collect_sellersprite_opencli_asin_keywords.py \
  --asin B0CT9R7WN5 \
  --keyword-miner-top 3
```

Prerequisites for OpenCLI enrichment:

- Chrome has the OpenCLI Browser Bridge extension installed and connected.
- The user is already logged in to SellerSprite web.
- The SellerSprite Chrome extension is installed and active on Amazon product pages.
- The OpenCLI session names are `amazonss` for Amazon pages and `sellersprite` for SellerSprite web pages.

Output:

```text
data/sellersprite_opencli/sellersprite_opencli_asin_keywords_<ASIN>_<timestamp>.xlsx
data/sellersprite_opencli/sellersprite_opencli_asin_keywords_<ASIN>_<timestamp>.json
```

Workbook sheets:

- `ASIN_Summary`: one row per product metric.
- `Keyword_Reverse_Rows`: one row per SellerSprite web keyword-reverse result for the ASIN.
- `Primary_Traffic_Keywords`: one row per extension-visible keyword with separate rank, share, type, and ad fields.
- `Inventory_Offers`: one row per visible inventory/offer.
- `Traffic_Source_Products`: one row per related ASIN from SellerSprite traffic source.
- `Keyword_Miner_Rows`: optional expansion for top visible traffic keywords.
- `Run_Metadata`: provenance and boundary notes.

The filtered crawler defaults to stable detail fetching: one detail worker, 0.35s sleep, 15s timeout, and 2 retries. Keep those defaults when the user prioritizes completeness. A measured speed option is `--detail-workers 2 --detail-sleep 0.35 --detail-retries 2`; avoid higher concurrency unless you re-run the benchmark.

## Workflow

1. Start with `crawl_amazon_3c_bsr_new_releases.py` to map 50-100 visible 3C categories.
2. Build the broad workbook with `build_3c_bsr_excel.py`.
3. Run `crawl_3c_filtered_opportunities_fast.py` to collect non-duplicate candidates and apply hard filters.
4. Run `retry_filtered_opportunity_details.py` if selected count is below 30 or many detail pages are missing fields.
5. Build the final workbook with `build_filtered_30_opportunity_excel.py`.
6. For OpenCLI ASIN enrichment, run `collect_sellersprite_opencli_asin_keywords.py` and inspect the workbook sheet counts before reporting success.
7. In the final response, report:
   - workbook path
   - candidate count
   - detail pages attempted
   - final selected count
   - key data limitations
8. If the user asks what crawler-only data can replace MCP/API calls, run `scripts/run_claude_crawler_audit.py --skip-reviews` when a Claude Amazon crawler is available, then summarize field coverage and gaps.
9. If detail-page success drops, run `scripts/benchmark_detail_fetch_params.py` and compare `core_success_rate` across workers/sleep settings before changing production defaults.

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

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
python scripts/run_filtered_30_pipeline.py --target 30 --retry-passes 2
```

## Workflow

1. Start with `crawl_amazon_3c_bsr_new_releases.py` to map 50-100 visible 3C categories.
2. Build the broad workbook with `build_3c_bsr_excel.py`.
3. Run `run_filtered_30_pipeline.py` for the filtered 30-product output. It runs fast crawl, retry, Excel rebuild, and consistency verification.
4. If the pipeline still misses target, use `plan_retry_shards.py`, `run_detail_retry_shard.py`, and `merge_retry_shards.py` to split slow retries across isolated workers, then rebuild and verify.
5. Always run `verify_crawl_outputs.py --target 30` before reporting success.
6. In the final response, report:
   - workbook path
   - candidate count
   - detail pages attempted
   - final selected count
   - JSON/Excel consistency status
   - key data limitations
7. If the user asks what crawler-only data can replace MCP/API calls, run `scripts/run_claude_crawler_audit.py --skip-reviews` when a Claude Amazon crawler is available, then summarize field coverage and gaps.

## Reliability Mode

Use reliability mode when Amazon pages are sparse, selected count is below target, or another agent reports inconsistent Excel/JSON counts:

```bash
python scripts/run_filtered_30_pipeline.py --target 30 --retry-passes 2
python scripts/verify_crawl_outputs.py --target 30
```

If standard retry cannot reach target:

```bash
python scripts/plan_retry_shards.py --shards 4 --max-candidates 1200
# run commands from data/amazon_3c/filtered_30_opportunities/retry_shards/commands.txt
python scripts/merge_retry_shards.py --target 30
python scripts/build_filtered_30_opportunity_excel.py
python scripts/verify_crawl_outputs.py --target 30
```

Do not claim "30 opportunities" unless the final Excel contains 30 unique ASINs and matches `selected_30_curated.json`.

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

When detail fields are missing, report `detail_error` categories such as `captcha`, `sign_in_page`, `not_found_or_unavailable`, or `missing_title_parse`. Do not collapse all missing titles into one cause without evidence.

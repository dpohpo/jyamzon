# Crawl Reliability Playbook

`jyamzon` should improve public-page coverage without depending on brittle anti-bot tricks. The goal is deterministic recovery: capture what failed, retry slowly, verify the workbook, and only then call the output accepted.

## Minimum Safe Workflow

Run the filtered workflow through the orchestrator instead of running the three scripts by hand:

```bash
python scripts/run_filtered_30_pipeline.py --target 30 --retry-passes 2
```

The orchestrator runs:

1. fast candidate crawl
2. slow retry if fewer than 30 selected products exist
3. Excel rebuild
4. JSON/Excel consistency verification

The final command fails if `selected_30.json`, `selected_30_curated.json`, and the Excel workbook do not agree on the final ASIN count.

## Verification

Use this after any manual rerun, copy, or employee handoff:

```bash
python scripts/verify_crawl_outputs.py --target 30
```

Treat the run as incomplete when:

- the filtered Excel has fewer than 30 unique ASINs
- `selected_30.json` and `selected_30_curated.json` disagree
- the Excel workbook was not rebuilt after retry
- broad crawl coverage is reported as product truth instead of scrape coverage

## Failure Classification

Detail-page failures should be classified by `detail_error`, not just counted as missing fields. Important values include:

- `captcha`
- `robot_check`
- `bot_block_message`
- `sign_in_page`
- `not_found_or_unavailable`
- `unavailable_or_sparse_page`
- `missing_title_parse`

This lets operators distinguish Amazon blocking, unavailable pages, and parser drift.

## Ranking-Card Fallback

When detail pages are sparse but ranking/category pages are readable, broad crawl uses the product card as a fallback source for:

- title
- image URL
- rating
- review count
- sometimes price

Rows populated this way include `fallback_source=category_card` and `fallback_fields`. Treat these as triage fields. They are strong enough to identify and filter products, but they do not replace bullets, BSR detail text, or product-page validation.

## Distributed Retry Strategy

Use distributed retry only after the fast crawler has produced `candidate_asins.json`. Do not run many high-concurrency workers against the same pages. Prefer slow, bounded, auditable shards.

Plan shards:

```bash
python scripts/plan_retry_shards.py --shards 4 --max-candidates 1200 --max-attempts-per-shard 350
```

Run the commands in `data/amazon_3c/filtered_30_opportunities/retry_shards/commands.txt` on separate terminals or machines. Each shard writes an isolated result file and does not mutate shared selected outputs.

Merge shard results:

```bash
python scripts/merge_retry_shards.py --target 30
python scripts/build_filtered_30_opportunity_excel.py
python scripts/verify_crawl_outputs.py --target 30
```

This improves coverage by spreading retries across time and workers while keeping merge behavior deterministic.

## What Not To Do

- Do not claim that missing title equals zero demand, zero reviews, or product failure.
- Do not call an output "30 opportunities" unless the final Excel actually contains 30 unique ASINs.
- Do not use proxy/captcha bypass instructions as the default employee workflow.
- Do not treat crawler-only BSR/New Releases output as final market truth.

## Paid Data Boundary

After a clean crawler shortlist exists, validate the remaining questions with SellerSprite, Keepa, SP-API, or another paid data source:

- search volume
- monthly purchases
- PPC bid
- purchase rate
- product and brand concentration
- review moat
- estimated monthly sales and revenue

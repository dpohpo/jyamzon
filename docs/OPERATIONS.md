# Operations Guide

## Full Run

```bash
source .venv/bin/activate

python scripts/crawl_amazon_3c_bsr_new_releases.py \
  --output data/amazon_3c/bsr_new_releases \
  --target 90 \
  --min 50 \
  --max-pages 260

python scripts/build_3c_bsr_excel.py

python scripts/crawl_3c_filtered_opportunities_fast.py
python scripts/retry_filtered_opportunity_details.py
python scripts/build_filtered_30_opportunity_excel.py
```

`crawl_3c_filtered_opportunities_fast.py` is stable-by-default for detail pages:

```text
--detail-workers 1
--detail-sleep 0.35
--detail-timeout 15
--detail-retries 2
```

This follows the broad crawl pattern that previously produced high detail-field coverage. Increase workers only when speed matters more than completeness.

Current measured speed option after the `Continue shopping` handling fix:

```text
--detail-workers 2
--detail-sleep 0.35
--detail-retries 2
```

On a 40-ASIN stress sample this reached 100% core success, where core success means both title and image parsed. Keep the one-worker default for production runs when completeness matters most.

## Expected Outputs

```text
outputs/amazon_3c_bsr_new_releases/amazon_3c_new_releases_bsr_crawl.xlsx
outputs/amazon_3c_filtered_opportunities/amazon_3c_bsr_filtered_30_opportunities.xlsx
```

## Optional Claude Crawler Audit

If the local machine has an existing Claude Amazon crawler, run:

```bash
python scripts/run_claude_crawler_audit.py --skip-reviews
```

Use `--crawler-script` or `CLAUDE_AMAZON_CRAWLER` when the crawler lives somewhere else:

```bash
CLAUDE_AMAZON_CRAWLER=~/.claude/skills/amazon/scripts/amazon_crawler.py \
  python scripts/run_claude_crawler_audit.py --skip-reviews
```

The audit output is useful for deciding which fields are reliably crawlable and which fields still need MCP/API validation.

## When Amazon Blocks Pages

Symptoms:

- many products missing title
- many products missing image
- category page ASIN count is zero
- page redirects to sign-in/captcha

Actions:

1. Re-run later with lower concurrency.
2. Run `retry_filtered_opportunity_details.py`.
3. Inspect the generated JSON logs.
4. Do not treat missing fields as product truth.

## Benchmark Detail Fetching

To test alternate detail-page settings:

```bash
python scripts/benchmark_detail_fetch_params.py \
  --sample-size 80 \
  --retries 1 \
  --combo 1:0.35 \
  --combo 2:0.35 \
  --combo 4:0.35
```

Use `core_success_rate` as the primary metric. It requires both title and image to parse, so HTTP 200 pages with missing product content count as failures.

## Employee Workflow

1. Clone repo.
2. Install dependencies.
3. Run broad crawl.
4. Run filtered crawl.
5. Open Excel.
6. Sort by recommendation score.
7. Treat low-score rows as rejection examples.

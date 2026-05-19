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

## Employee Workflow

1. Clone repo.
2. Install dependencies.
3. Run broad crawl.
4. Run filtered crawl.
5. Open Excel.
6. Sort by recommendation score.
7. Treat low-score rows as rejection examples.

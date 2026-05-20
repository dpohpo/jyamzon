# jyamzon

Reusable Amazon 3C product-selection crawler and agent skill.

`jyamzon` crawls public Amazon US BSR/New Releases pages, expands 3C category pages, extracts ASIN/product detail fields, filters out big-brand and hard-standardized products, scores China-seller fit, and exports analyst-ready Excel workbooks.

The core crawler does **not** use SellerSprite MCP, Keepa, paid APIs, or Amazon SP-API. It only uses public Amazon ranking/detail pages, so the output is best for discovery and triage, not final investment decisions.

There is also an optional OpenCLI enrichment path for a known ASIN. It reads SellerSprite data already visible in the user's logged-in Chrome web page and SellerSprite Chrome extension overlay, then normalizes it into granular Excel sheets. This is browser-visible data capture, not SellerSprite API/MCP parity.

## What It Produces

- ASIN
- title
- price
- rating
- review count
- bullet points
- product image URL and embedded Excel thumbnail
- category path and ranking source
- China-seller suitability
- opportunity/risk notes
- profit score, feasibility score, recommendation score

Optional SellerSprite OpenCLI ASIN enrichment:

- one ASIN summary metric per row
- ASIN keyword-reverse rows split into keyword, translation, traffic share, traffic type, organic rank, ad rank, search volume, purchases, PPC, and competition metrics
- extension primary traffic keywords split into keyword, translation, traffic share, keyword type flags, organic rank, and ad rank when the Amazon extension renders them
- visible inventory offers split into quantity, price, currency, and seller
- related ASIN traffic-source rows split into product, price, rating, source flags, and keyword counts
- optional Keyword Miner expansion for top visible traffic keywords

## Install

```bash
git clone https://github.com/dpohpo/jyamzon.git
cd jyamzon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install the bundled skill for local agents:

```bash
bash scripts/install_jyamzon_skill.sh --all
```

This installs `skills/jyamzon` to both `~/.codex/skills/jyamzon` and `~/.claude/skills/jyamzon`. After install, users can invoke the workflow with `/jyamzon` or `$jyamzon` in agents that load local skills.

## Quick Start

### 1. Crawl 50-100 New Releases category examples

```bash
python scripts/crawl_amazon_3c_bsr_new_releases.py \
  --output data/amazon_3c/bsr_new_releases \
  --target 90 \
  --min 50

python scripts/build_3c_bsr_excel.py
```

Output:

```text
outputs/amazon_3c_bsr_new_releases/amazon_3c_new_releases_bsr_crawl.xlsx
```

### 2. Find 30 filtered non-big-brand opportunities

```bash
python scripts/crawl_3c_filtered_opportunities_fast.py
python scripts/retry_filtered_opportunity_details.py
python scripts/build_filtered_30_opportunity_excel.py
```

The filtered crawler is stable-by-default: detail pages run with low concurrency, delay, and retry because Amazon can return HTTP 200 pages that still lack product content under aggressive request patterns. If you explicitly want speed over success rate, override:

```bash
python scripts/crawl_3c_filtered_opportunities_fast.py \
  --detail-workers 2 \
  --detail-sleep 0.35 \
  --detail-retries 2
```

Output:

```text
outputs/amazon_3c_filtered_opportunities/amazon_3c_bsr_filtered_30_opportunities.xlsx
```

### 3. Optional crawler coverage audit

Use this only when you have an existing Claude Amazon crawler installed and want to compare what public crawling can retrieve before paying for MCP/API data:

```bash
python scripts/run_claude_crawler_audit.py --skip-reviews
```

If your Claude crawler is not at the default path, pass it explicitly:

```bash
python scripts/run_claude_crawler_audit.py \
  --crawler-script ~/.claude/skills/amazon/scripts/amazon_crawler.py \
  --skip-reviews
```

### 4. Optional SellerSprite OpenCLI ASIN + keyword enrichment

Use this when Chrome is already logged in to SellerSprite and the SellerSprite Chrome extension is active on Amazon product pages.

```bash
python scripts/collect_sellersprite_opencli_asin_keywords.py \
  --asin B0CT9R7WN5 \
  --keyword-miner-top 3
```

By default, the script collects:

- Amazon product-page SellerSprite extension summary
- extension-visible primary traffic keywords
- extension-visible inventory offers
- SellerSprite `/v3/reversing` traffic-source related products
- SellerSprite `/v3/keyword-reverse` keyword-reverse rows for the ASIN

`--keyword-miner-top 3` additionally opens SellerSprite Keyword Miner for the top three visible traffic keywords and normalizes the visible table. Set it to `0` when you only want the ASIN-level workbook.

Output:

```text
data/sellersprite_opencli/sellersprite_opencli_asin_keywords_<ASIN>_<timestamp>.xlsx
data/sellersprite_opencli/sellersprite_opencli_asin_keywords_<ASIN>_<timestamp>.json
```

The workbook is designed so each cell contains one value. Raw browser text is kept only in the JSON audit file.

## Agent Skill Install

Clone this repo, then install the bundled skill:

```bash
bash scripts/install_jyamzon_skill.sh --all
```

After that, Codex and Claude Code can use the `jyamzon` skill when the user asks for `/jyamzon`, `$jyamzon`, Amazon 3C BSR product selection, non-MCP crawling, SellerSprite OpenCLI ASIN enrichment, China-seller feasibility scoring, or Excel output.

## Recommended Workflow

1. Run the broad New Releases crawl to understand visible 3C categories.
2. Run the filtered opportunity crawler to remove obvious big-brand, service, software, and hard-standardized products.
3. Open the Excel workbook and inspect high-score rows first.
4. Treat low-score rows as reject examples, not recommendations.
5. Use paid data sources only after the crawler creates a shortlist.

## Data Limitations

This tool cannot reliably provide:

- monthly search volume
- monthly sales/revenue
- PPC bid
- purchase rate
- click concentration
- true market concentration
- seller country distribution
- conversion keywords

Those require third-party datasets or Amazon-side data. `jyamzon` is designed to reduce paid-tool calls by doing cheap public-page discovery first.

## Repository Layout

```text
scripts/
  crawl_amazon_3c_bsr_new_releases.py      # broad BSR/New Releases crawl
  build_3c_bsr_excel.py                    # broad crawl Excel builder
  crawl_3c_filtered_opportunities.py       # filtering/scoring rules
  crawl_3c_filtered_opportunities_fast.py  # concurrent opportunity crawl
  retry_filtered_opportunity_details.py    # slow retry for blocked/missing detail pages
  build_filtered_30_opportunity_excel.py   # curated 30-opportunity Excel builder
  benchmark_detail_fetch_params.py         # tests detail-page workers/sleep success rate
  run_claude_crawler_audit.py              # optional crawler coverage audit
  collect_sellersprite_opencli_asin_keywords.py # granular SellerSprite browser-visible ASIN + keyword workbook
  install_jyamzon_skill.sh                 # installs skills/jyamzon into Codex and/or Claude skill dirs
  install_claude_skill.sh                  # backward-compatible Claude-only installer

skills/jyamzon/SKILL.md                    # Codex/Claude Code skill
docs/SCORING.md                            # scoring and filtering rules
docs/OPERATIONS.md                         # repeatable runbook
reports/                                   # prior crawler/MCP gap notes and HTML report
examples/outputs/                          # sample workbooks from a real run
examples/raw/                              # sample raw JSON/CSV artifacts from real runs
```

## Operational Notes

- Amazon pages can return empty/captcha/sign-in pages. The scripts keep status fields and retry paths because public scraping is not deterministic.
- Do not treat New Releases rank as proof of demand.
- Do not treat empty review count as zero reviews.
- Always manually review compliance risk for wireless, battery, power, charger, security camera, and child-use products.
- Treat OpenCLI SellerSprite data as browser-visible enrichment. If a field is not rendered by the current web page or extension, use MCP/API or the official export workflow instead of guessing it.

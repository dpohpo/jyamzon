# Detail Fetch Tuning

## Conclusion

Use stable defaults when completeness matters:

```text
--detail-workers 1
--detail-sleep 0.35
--detail-timeout 15
--detail-retries 2
```

Use this measured speed option when a faster exploratory run is acceptable:

```text
--detail-workers 2
--detail-sleep 0.35
--detail-timeout 15
--detail-retries 2
```

## Why

The broad BSR/New Releases crawl previously achieved high detail-field coverage because it fetched detail pages serially with a small delay:

- 90 products
- 89 titles
- 89 prices
- 90 ratings
- 82 review counts
- 86 products with five bullets
- 89 images

The filtered crawler originally used high-concurrency detail fetching with no delay. That created many HTTP 200 responses that were not real product pages. They were Amazon `Continue shopping` interstitial pages from `/errors/validateCaptcha`, so the parser recorded missing title and missing image.

The fix detects that page type and submits the hidden continue-shopping form once before parsing.

## Measurements

After the fix:

| Setting | Sample | Core success | Rating | Review count | Five bullets | Speed |
|---|---:|---:|---:|---:|---:|---:|
| 1 worker, 0.35s sleep, 2 retries | 20 ASIN | 100% | 95% | 95% | 95% | 16.06 pages/min |
| 2 workers, 0.35s sleep, 2 retries | 40 ASIN | 100% | 97.5% | 97.5% | 95% | 31.56 pages/min |

Core success means both `title` and `image_url` were parsed. HTTP 200 alone is not a success metric.

## Rule

Do not raise concurrency after a failure run and call that a fix. First check whether Amazon is returning `continue_shopping`, `captcha`, `robot_check`, sign-in, or empty pages. Missing fields are often a fetch-quality problem, not a selector problem.


# 3C 选品数据：本地爬虫 vs MCP 覆盖核验

生成时间：2026-05-18  
目标细分：Amazon US 双显示器增高架 / 桌面收纳型 monitor stand riser  
本次原则：未调用 SellerSprite MCP，只使用本机已有爬虫脚本和本地分析脚本。

## 1. 本次实际跑过的脚本

| 脚本 | 路径 | 结果 |
|---|---|---|
| Claude requests 爬虫 | `/Users/poincare/.claude/skills/amazon/scripts/amazon_crawler.py` | 可用，已抓搜索 ASIN、商品详情、图片；差评页返回 0 |
| Claude Selenium 反检测爬虫 | `/Users/poincare/.claude/skills/amazon/scripts/amazon_crawler_v2.py` | 单 ASIN 商品详情可用；差评页被重定向到 Amazon 登录页 |
| Claude 分析脚本 | `/Users/poincare/.claude/skills/amazon/scripts/amazon_analyze.py` | 可运行；因差评为空，评论洞察不可用 |
| amazon-crawler-v3 | `/Volumes/金阳/amazon-crawler-v3` | CLI 启动失败：`ProxyConfig()` 参数类型错误 |
| amazon-scraper-v3 | `/Volumes/金阳/amazon-scraper-v3` | CLI 启动失败：`browser.profiles` 缺少 `for_domain` 导入 |

## 2. 已落盘产物

| 文件 | 内容 |
|---|---|
| `data/amazon_3c/crawler_audit/audit_summary.json` | 本次爬虫运行概要 |
| `data/amazon_3c/crawler_audit/search_results.json` / `.csv` | 8 个关键词的搜索页 ASIN 列表 |
| `data/amazon_3c/crawler_audit/products.json` / `.csv` | 5 个竞品 ASIN 的商品页字段 |
| `data/amazon_3c/crawler_audit/product_field_coverage.json` | 每个 ASIN 的字段覆盖率 |
| `data/amazon_3c/crawler_audit/negative_reviews.json` / `.csv` | 差评抓取结果，本次为空 |
| `data/amazon_3c/crawler_audit/images/*.jpg` | 5 个竞品主图 |
| `data/amazon_3c/crawler_audit/v2_probe_B0C4SZ286V.json` | Selenium v2 单 ASIN 探针结果 |
| `reports/claude_crawler_analysis_dual_monitor_stand_riser.md` | Claude 分析脚本生成的报告，评论部分不可用 |

## 3. 关键词搜索页结果

最终有效运行中，requests 版搜索页能解析 ASIN，但稳定性一般：第一次运行 8 个关键词均为 0，第二次运行正常返回。

| 关键词 | 抓到 ASIN 数 | 说明 |
|---|---:|---|
| dual monitor stand riser | 33 | 包含 `B0DJKSMV2T`、`B0C4SZ286V` 等报告竞品 |
| monitor riser | 34 | 可做竞品发现 |
| monitor stand | 30 | 会混入支架臂、非增高架产品 |
| dual monitor stand | 27 | 会混入气压臂、夹具类产品 |
| monitor riser for desk | 34 | 相关性较好 |
| desk monitor riser | 33 | 相关性较好 |
| portable monitor stand | 58 | 偏向便携支架，不适合作为同一细分 |
| cable organizer box | 33 | 邻近 3C 桌面收纳品类，可用于横向对比 |

结论：搜索页 ASIN 发现可以先用爬虫，不必先用 MCP；但它只能得到“当前页有哪些 ASIN”，不能得到搜索量、购买量、转化率、PPC、供需比等经营指标。

## 4. 竞品 ASIN 商品页覆盖

| ASIN | 标题 | 品牌 | 价格 | 评分 | Review 数 | Bullet | 主图 | BSR |
|---|---|---|---|---|---|---:|---|---|
| B0855QBHTZ | 成功 | 成功 | `28.` | 失败 | `10,250` | 5 | 成功 | 失败 |
| B082N9PL4B | 成功 | 成功 | `29.` | 失败 | `8,317` | 5 | 成功 | 失败 |
| B0C4SZ286V | 成功 | 成功 | `24.` | `4.6` | `7,596` | 5 | 成功 | 失败 |
| B09712RBWB | 成功 | 成功 | `29.` | `4.6` | `4,043` | 5 | 成功 | 失败 |
| B0DJKSMV2T | 成功 | 成功 | `29.` | 失败 | `2,677` | 5 | 成功 | 失败 |

字段覆盖率：

| ASIN | 覆盖率 | 缺失字段 |
|---|---:|---|
| B0855QBHTZ | 70% | rating, description, bsr |
| B082N9PL4B | 70% | rating, description, bsr |
| B0C4SZ286V | 80% | description, bsr |
| B09712RBWB | 80% | description, bsr |
| B0DJKSMV2T | 70% | rating, description, bsr |

结论：商品标题、品牌、Review 数、Bullet Points、主图、链接可以先用爬虫。价格目前只抓到整数部分，解析器需要补小数位；评分只成功 2/5；BSR 和描述本次没有抓到。

## 5. 差评与评论洞察

| 爬虫 | 测试范围 | 结果 |
|---|---|---|
| requests 版 | 5 个竞品 ASIN，每个最多 3 条差评 | 0 条 |
| Selenium v2 | `B0C4SZ286V` 单 ASIN | 商品详情成功，差评页被重定向登录，0 条 |
| 分析脚本 | 基于空差评数据 | 可运行，但评论分类、痛点、机会缺口没有实际依据 |

结论：当前这套爬虫不能可靠替代 MCP 的评论/差评数据。以后如果要不用 MCP，需要先修评论页抓取：处理登录重定向、使用真实浏览器 profile/cookie、保存 raw HTML、更新 review selector。

## 6. 可以先不用 MCP 的数据

这些字段本次已经证明可以用本地爬虫拿到，或者小改解析器后能稳定拿到：

| 数据 | 当前状态 | 后续动作 |
|---|---|---|
| 关键词搜索页 ASIN 列表 | 可抓，但偶发 0 | 加重试、保存 raw HTML、识别 captcha/空页 |
| 商品标题 | 5/5 成功 | 可直接用 |
| 品牌 / 店铺 byline | 5/5 成功 | 清洗 `Visit the ... Store` |
| 当前页面价格 | 5/5 粗略成功 | 修复小数位和 `$` 解析 |
| Review 数 | 5/5 成功 | 转成整数 |
| Bullet Points | 5/5 成功 | 可用于卖点和差异化拆解 |
| 主图 | 5/5 成功 | 可用于视觉、材质、结构对比 |
| 当前搜索结果中的竞品发现 | 可用 | 后续可以抓前 2-3 页再去重 |

## 7. 爬虫可改造后再替代 MCP 的数据

| 数据 | 当前问题 | 改造建议 |
|---|---|---|
| 评分 | 只成功 2/5 | 增加 `#acrPopover`, JSON-LD, `aria-label` 等 selector |
| BSR / 类目排名 | 0/5 | 抓 `detailBulletsWrapper_feature_div`、`productDetails_detailBullets_sections1` 和页面文本正则 |
| 商品尺寸 / 重量 | 未抓 | 抓 Product Information 表格 |
| 变体 / 颜色 / 款式 | 未抓 | 抓 variation swatches 和 `twister` 数据 |
| 卖家 / 发货方式 | 未抓 | 抓 buy box 区域；需要考虑地区、登录状态和 Prime 展示差异 |
| Q&A 数 | 未抓 | 抓 `askATFLink` 或页面问答模块 |
| 评论列表 / 差评 | 当前 0 | 用 Selenium profile/cookie 或浏览器插件方式重构 |
| Review 痛点分类 | 下游脚本可运行 | 必须先有真实 review 数据 |

## 8. 仍建议用 MCP 的数据

这些不是普通 Amazon 页面稳定公开字段，或本地爬虫当前没有数据源，后续仍应优先 MCP：

| 数据类型 | 为什么爬虫不适合 |
|---|---|
| 月搜索量、月购买量、购买率 | Amazon 页面不直接公开 |
| ABA 排名、搜索增长率、三个月趋势、同比趋势 | 需要平台侧历史数据 |
| PPC 竞价、广告竞品数 | 普通页面不公开 |
| 供需比、标题密度、关键词商品数 | 需要结构化平台计算，爬虫只能近似 |
| 点击集中度、头部 ASIN 点击/转化占比 | 普通页面不公开 |
| ASIN 自然/广告流量词、流量占比、转化词 | 需要反查数据源 |
| 月销量、月销售额、利润、FBA 费用估算 | 普通页面无法可靠推断 |
| 市场容量、类目新品占比、商品集中度 | 需要类目级样本和估算模型 |
| 品牌集中度、卖家集中度、卖家国家分布 | 需要批量样本和结构化卖家数据 |
| Coupon 历史、价格历史、Keepa 类趋势 | 需要历史数据库 |
| Listing Quality Score | 第三方平台计算指标 |
| Google Trends 长周期趋势 | Claude Amazon 爬虫没有该能力；可另接 pytrends，但不是这套 Amazon 爬虫 |

## 9. 建议的数据调用策略

1. 先用本地爬虫做低成本 discovery：关键词搜索页 ASIN、竞品标题、图片、Bullet、Review 数。
2. 用爬虫清洗出候选 ASIN 池后，再只对候选池调用 MCP：关键词搜索量、购买率、PPC、流量词、销量销售额、市场集中度。
3. 评论数据当前不要依赖本地爬虫，除非先修复 review 抓取；否则 review 痛点仍用 MCP 或官方页面手动抽样。
4. v3 两个项目当前先不要纳入生产流程，先修 CLI 启动错误，再做同样的字段覆盖测试。


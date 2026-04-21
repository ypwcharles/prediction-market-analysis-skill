# CL HIGH $115 by End of June 分析记录

- 日期: 2026-04-13
- 市场: [Polymarket - Will Crude Oil (CL) hit (HIGH) $115 by end of June?](https://polymarket.com/event/cl-hit-jun-2026)
- 分析范围: 汇总 2026-04-10 至 2026-04-11 的几轮判断，并整理成一份可复用的 Markdown 记录
- 结论状态: 当前主结论不变

## 核心结论

1. 事件级别结论是 `NO TRADE`。
2. 在整条 `CL hit by end of June` 链里，若用户 thesis 是“停火不会持续，谈判破裂概率高”，最接近该 thesis 的表达不是更高的极端 strike，而是 `HIGH $115 Yes`，次选 `HIGH $120 Yes`。
3. `HIGH $115 Yes` 在 `57c` 直接吃 ask 时不值得买。
4. 如果要参与，这笔单只能用被动限价单来做，且仅在 `<= 50c` 成交时才满足 risk/reward 要求。
5. 在未提供完整组合暴露和 bankroll 的前提下，总仓位只建议做 `0.25%-0.5% bankroll` 的试探仓，未成交就放弃，不追价。

## 一、市场与规则摘要

### 基础信息

- 平台: Polymarket
- 事件页: [Will Crude Oil (CL) hit__ by end of June?](https://polymarket.com/event/cl-hit-jun-2026)
- 关注合约: `Will Crude Oil (CL) hit (HIGH) $115 by end of June?`
- 交易原型: `cross-bucket structure`

### 结算规则

该系列市场的共同规则是:

- 若 2026-06-30 之前任一交易日，CME 前月 CL 期货的官方 `settlement` 首次发布值达到或高于对应 strike，则该合约结算为 `Yes`
- 只看 `official settlement`
- 不看 intraday 高点、低点、最后成交价、mid 或 indicative 价格

这意味着:

- “油价曾盘中冲过 115” 对这张票没有直接结算意义
- 真正相关的是 “某天 official settlement 是否 >= 115”

## 二、这条链里哪个表达最干净

最初对整条事件链的判断是:

- 不应把这组市场当成单一方向盘
- 应把它视为一条 barrier / strike 曲线
- 关键不是 “看多油价” 本身，而是 “你是否拥有足够强的 timing 与幅度判断，去买某一个具体 strike”

在这个框架下:

- `HIGH $175` 和 `HIGH $200` 不是对“停火会破裂”这一 thesis 的直接表达
- 它们买的是更极端的尾部场景
- 如果 thesis 只是“停火破裂，风险溢价会抬升”，那么 `HIGH $115` 比 `HIGH $130/$140/$175/$200` 都更干净

因此，后续分析聚焦在 `HIGH $115 Yes`。

## 三、盘口快照

以下盘口来自对 Polymarket Gamma API 的抓取。可确认到的时间戳主要集中在 `2026-04-10 16:00 UTC` 左右。

| 合约 | Best Bid | Best Ask | Last | Spread |
| --- | ---: | ---: | ---: | ---: |
| HIGH $115 Yes | 54.1c | 57.0c | 53.1c | 2.9c |
| HIGH $120 Yes | 46.0c | 48.0c | 47.0c | 2.0c |
| HIGH $130 Yes | 36.0c | 38.0c | 38.0c | 2.0c |
| HIGH $140 Yes | 27.0c | 28.0c | 27.0c | 1.0c |

流动性层面:

- `HIGH $115` 流动性大约 `$33.6k`
- 成交量大约 `$242k`
- 说明它不是死盘，但也不够便宜到可以无脑吃单

## 四、分析迭代过程

### 1. 事件级别初始判断

最初对整个事件链的判断是 `NO TRADE`，理由如下:

- 规则虽然清晰，但尾部场景区间必须放宽
- 市场对极端 high strike 的定价很大程度是在卖尾部风险
- 即便对冲突升级持偏多看法，也不代表应该买更深虚值的 high strike

当时的核心结论是:

- 若硬要在整条事件链里选一个更干净的表达，反而是 `No on HIGH $200`
- 但在保守边界下，它也没有足够 edge 支撑建仓

### 2. 用户 thesis 更新后

用户随后明确给出新观点:

- 停火不会持续
- 谈判破裂的可能性非常高

这会改变方向判断，但不会自动让所有上行合约都变成好买点。

调整后的结论是:

- 该 thesis 确实提升了 `HIGH $115` 和 `HIGH $120` 的价值
- 但它主要提升的是方向概率，不是无限抬高所有高 strike 的幅度概率
- 所以 “停火大概率破裂” 更支持 `HIGH $115 Yes`，而不是 `HIGH $175 Yes` 或 `HIGH $200 Yes`

### 3. 合约级别判断

对 `HIGH $115 Yes` 的主观看法后来收敛为:

- anchor probability: 约 `55.6%`，来自市场价格
- adjusted main probability: 约 `60%-61%`
- confidence interval: 约 `52%-69%`

对应的结论是:

- `57c` 吃 ask 时，edge 太薄
- 市场已经部分计入了“停火脆弱”和“Hormuz 恢复不稳”的信息
- 这不是“看错方向”，而是“价格不够便宜”

## 五、证据框架

### 支持 `HIGH $115` 的证据

- [AP, 2026-04-08](https://apnews.com/article/financial-markets-iran-oil-bcd3342cd0b4e60ebedc1e81db08f465)
  报道 WTI 曾一度冲到 `117+`，说明 `115` 不是一个遥远的 strike
- [Reuters 转载, 2026-04-09](https://gvwire.com/2026/04/09/oil-prices-rise-about-5-as-hormuz-concerns-keep-supply-risks-elevated/)
  报道 Hormuz 流量仍显著低于正常，说明风险并未完全解除
- [EIA, 2026-04-07](https://www.eia.gov/pressroom/releases/press586.php)
  在其相对温和的基准假设下，2Q26 Brent 峰值仍可到约 `115`

### 压制该合约价值的证据

- [EIA WPSR](https://ir.eia.gov/wpsr/overview.pdf)
  截至 2026-04-03 的美国商业原油库存增加 `310万桶`
- [TheStreet 转述 Goldman, 2026-04-10](https://www.thestreet.com/investing/goldman-sachs-resets-its-oil-price-forecasts-for-the-rest-of-2026)
  指向更低的 Q2 WTI 预期
- 政策释放和库存缓冲会降低 “6 月底前 official settlement >= 115” 的确定性

### 最关键的规则提醒

这张票最大的误判来源不是方向，而是结算口径:

- 盘中摸到 115 不够
- 必须是 `official settlement >= 115`

这会显著降低 “看起来很接近” 对应的真实支付概率。

## 六、价格与 edge 判断

### 为什么 57c 不值得买

`HIGH $115 Yes` 的主观主概率虽然可上调到 `60%-61%`，但:

- 保守公允值大致只有 `52c` 左右
- `57c` 的 ask 已经提前收走了大部分 edge
- 在 conservative boundary 下，这笔单不通过

因此直接扫单的结论是:

- `NO TRADE`

### 哪个价格才开始变得可做

之前的结论是:

- `54c` 是重新评估的上边界
- 更偏好的入场区间是 `52-53c`

在后续执行层面的判断里，标准进一步收紧为:

- 只有 `<= 50c` 的 `Yes` 限价成交，才把这笔单视为可交易 setup

## 七、执行方案

如果一定要参与，唯一合理的方法是挂被动限价单，不追价。

### 执行纪律

- 不吃 `57c` ask
- 不在 `51-57c` 区间追价
- 若无法在更低价成交，则放弃

### 建议挂单

- `25%` 目标仓位挂在 `50c`
- `35%` 目标仓位挂在 `49c`
- `40%` 目标仓位挂在 `48c`

### 仓位建议

在未提供 bankroll 和现有持仓的情况下:

- 总仓位建议: `0.25%-0.5% bankroll`
- 若只是测试 thesis: 可压到 `0.25%`
- 若已知自己没有相关暴露且只做试探仓: 上限也不超过 `0.5%`

### 为什么仓位要这么小

- 这是事件驱动、叙事相关性很强的一笔单
- 同类仓位之间高度相关，不能当分散
- 缺少完整组合信息时必须做 portfolio-blind haircut

## 八、最终操作结论

### 当前主结论

- `HIGH $115 Yes` 是这条链里最像 “停火会破裂” 这个 thesis 的表达
- 但它只在低价成交时才值得做

### 明确结论

- `57c` 直接买: `NO TRADE`
- `<= 50c` 被动成交: `TRADE`
- 未成交: 取消挂单，不追价

## 九、Kill Criteria

以下情况会削弱或推翻这笔单的逻辑:

- 2026 年 4 月中下旬出现可验证的持续复航
- 停火被主要交战方实质遵守
- 没有新的关键能源基础设施受损
- 库存继续累积，且政策性释放有效压低近月风险溢价

若已经低价成交，则以下情况应触发减仓或退出:

- 官方或高质量媒体确认航运恢复显著改善
- 市场风险溢价迅速回落，但 thesis 没有新的增量证据支撑
- 合约价格抬升主要来自情绪，而非新的高质量一手信息

## 十、文档用途

这份文档的用途是:

- 记录此前几轮判断
- 固化 “方向对不代表合约对” 的分析过程
- 给后续复盘提供明确的价格阈值和执行纪律

后续若需要继续更新，建议直接在本文档末尾追加:

- 新的价格快照
- 新的高质量证据
- 对公允值区间的修正

## Sources

- [Polymarket event page](https://polymarket.com/event/cl-hit-jun-2026)
- [Polymarket Gamma API](https://gamma-api.polymarket.com/events?slug=cl-hit-jun-2026)
- [AP, 2026-04-08](https://apnews.com/article/financial-markets-iran-oil-bcd3342cd0b4e60ebedc1e81db08f465)
- [Reuters republished by GV Wire, 2026-04-09](https://gvwire.com/2026/04/09/oil-prices-rise-about-5-as-hormuz-concerns-keep-supply-risks-elevated/)
- [EIA press release, 2026-04-07](https://www.eia.gov/pressroom/releases/press586.php)
- [EIA Weekly Petroleum Status Report overview PDF](https://ir.eia.gov/wpsr/overview.pdf)
- [TheStreet on Goldman oil forecast reset, 2026-04-10](https://www.thestreet.com/investing/goldman-sachs-resets-its-oil-price-forecasts-for-the-rest-of-2026)

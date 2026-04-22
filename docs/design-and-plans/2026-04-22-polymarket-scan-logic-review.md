# Polymarket 机会扫描与判断逻辑复盘

**日期：** 2026-04-22
**范围：** `runtime/` 当前扫描、预筛、证据整合、judgment 上下文构造，以及与 `skills/prediction-market-analysis/` 设计目标的偏差

## 结论先行

当前这套 runtime 更像一个：

1. 拉取高成交市场
2. 做非常薄的硬过滤
3. 从里面抽少数候选交给 judgment

它还不是一个真正的 “opportunity discovery engine”。

最关键的问题不是 LLM 判断不够强，而是 **进入 judgment 之前，候选市场信息丢失太多、排序太粗糙、证据也没有按候选定向收敛**。这会直接导致：

- 好机会可能根本进不了 judgment
- 进了 judgment 的市场也缺少足够上下文去判断 “是不是 cleaner expression”
- 模型容易变成“对单一市场做研究判断”，而不是“在一组相关表达里找最优下注入口”

如果只做一件最值的事，我会优先做：

**把 scan 从“薄过滤 + 抽样判断”升级成“保留丰富特征的多阶段排序管线”。**

---

## 一、当前链路的真实形态

从代码上看，当前链路是：

1. Gamma 拉市场，默认只按 `volume24hr` 排序抓一段活跃市场。
2. 标准化后，只保留非常少的字段。
3. 预筛只看：
   - 是否 active/open
   - liquidity
   - spread
   - 同表达去重
4. 按一个很粗的 priority key 排序。
5. 默认只取前 `2` 个候选进入 judgment。
6. judgment 拿到的是单市场上下文，不是完整 expression set。
7. 证据是全局 news/X feed 合并后直接喂给每个候选。

这条链路能跑，但天然更适合：

- 做 demo
- 做 runtime 打通
- 做小规模 alert 验证

不适合做你真正想要的那种：

- 宽覆盖
- 高频率发现
- 自动识别 cleaner expression
- fat pitch 优先
- 明确知道自己“看过了什么、没看什么、为什么没看”

---

## 二、最伤机会发现效率的几个结构性问题

## 1. 候选市场在进入 judgment 前被“压缩得过头了”

`ScanCandidate` 只保留了：

- `question`
- `liquidity_usd`
- `spread_bps`
- `slippage_bps`
- `rules_text`
- 少量 id / slug

但扫描真正需要的很多核心信号没有被保留下来，例如：

- 当前 `best_bid` / `best_ask` / `mid`
- 最新成交价或 implied price
- 24h volume / volume acceleration
- 结算时间 / deadline / close time
- 分类 / tag / theme
- outcome labels
- 同 event 下其他 bucket / 邻近 strike / 对手表达
- 盘口深度和可吃单容量

结果是：**judgment 看不到真正决定可交易性的关键变量。**

最典型的是，CLOB 明明抓到了 `best_bid` 和 `best_ask`，但传到 seed/context 时只剩下 `spread_bps` 和 `slippage_bps`。这意味着 judgment 很难真正计算 executable edge，只能做偏研究型的结论。

更严重的一层是，runtime 的官方 eval fixture 其实假设 judgment 应该拿到 `best_bid_cents`、`best_ask_cents`、`mid_cents` 这一类字段，但当前真实 scan path 没把这些字段传进去。也就是说，**设计目标和真实运行路径之间已经出现信息层断裂。**

### 为什么这会伤 discovery

- 没有价格上下文，就不能稳定比较“有 edge 的市场”和“只是 thesis 看起来不错的市场”
- 没有 deadline / category / outcome 结构，就不能优先找短期、清晰、好表达的机会
- 没有相邻表达，就没法系统性做 cross-bucket / cleaner-expression 判断

### 建议

- 把 `ScanCandidate` / `AlertSeed` 扩成“可排序的 market snapshot”，至少保留：
  - `best_bid`
  - `best_ask`
  - `mid`
  - `last_price`
  - `volume_24h`
  - `deadline`
  - `event_title`
  - `category/tag`
  - `outcome_name`
  - `book_depth_top_n`
- judgment 上下文必须能看到这些字段，而不只是 spread/slippage

---

## 2. 当前不是“全面扫描后排序”，而是“高成交抽样后再判断”

Gamma 拉取默认按 `volume24hr` 排序，`gamma_limit` 默认是 `200`。这本身就会造成两个偏差：

- 偏向最热、最拥挤、最 headline-driven 的市场
- 更容易错过没那么热但结构更干净、edge 更大的中腰部机会

后面 `_candidate_priority_key()` 又只按下面这些东西排：

- 是否 degraded
- 是否命中静态 domain marker
- liquidity
- spread

再加上默认 `scan_max_judgment_candidates=2`，实质上变成了：

**从高成交市场里挑两个“看起来最像主流 domain、流动性还不错”的候选去做判断。**

这不是你要的 fat-pitch 搜索器，而是一个非常保守的 sample-and-judge 机制。

### 为什么这会伤 discovery

- `2` 个 judgment 配额太少，漏检率会很高
- 静态关键词白名单会天然偏 politics / macro / crypto，压制新主题
- 没有 category quota / thesis-family diversification，前几个热点可能把预算吃完

### 建议

- 不要只按 `volume24hr` 单维排序拉取 universe，改成多入口：
  - 热门板
  - 各 category 分桶
  - 短期限市场
  - 新近 price dislocation 板
  - 低关注但高结构性异常板
- judgment 配额不要固定 `2`，改成：
  - `top_k_global`
  - `top_n_per_family`
  - `top_n_per_category`
- 预筛后增加一个 **pre-LLM ranking layer**，让更多候选先过结构分数，再决定谁值得花 judgment 成本

---

## 3. skill 要求“先看完整表达集”，runtime 实际只给单市场

`prediction-market-analysis` 这个 skill 的核心方法论非常明确：

- 先判断 archetype
- 先发现完整 expression set
- 再比较 adjacent buckets / rule-scope variants / named-actor variants
- 最后才决定 asked contract 是否值得做

但当前 runtime 传给 judgment 的 `candidate_facts` 只有单市场信息，没有：

- 同 event 的其他 outcome
- 邻近时间桶
- 相似 strike
- 对手表达
- 跨平台对照
- “更 cleaner 的备选表达”

这意味着：

**你最看重的“选对表达”这一层，当前几乎完全依赖模型在缺上下文的情况下自己脑补。**

它当然偶尔能做对，但不可能稳定。

### 为什么这会伤 discovery

- 你真正的 edge 很多时候不在 asked market，而在邻近 bucket
- 没有 expression graph，就无法系统性发现“早桶买 No / 晚桶买 Yes / 更宽表达更优”这类交易
- 模型更容易输出“这个市场可研究”，而不是“这个市场不如隔壁那个”

### 建议

- 在 scan 阶段就构建 `expression family`：
  - 同 event 的所有 markets
  - 相邻截止时间
  - 相邻 threshold
  - 规则口径相近但 actor / verb 不同的表达
- judgment 输入不该只是一个 market，而应是：
  - `primary_expression`
  - `adjacent_expressions`
  - `family_summary`
  - `monotonicity_checks`
  - `dominance_flags`

---

## 4. 证据层现在是“全局 feed 拼接”，不是“围绕候选定向找证据”

目前 scan flow 会先加载配置好的 news/X feed，然后把这些全局 evidence 直接合并进每个 seed。

这相当于：

- 不是先根据候选市场去定向检索证据
- 也不是先判断证据和候选之间是否高度相关
- 更没有先做 claim-level dedupe，再传给 judgment

同时，`strict_allowed` 的逻辑也很薄：

- 至少 2 个 primary
- 没有 unresolved conflict

但它并不判断：

- 这些 primary 是否直接作用于 settlement
- 是否只是重复同一 underlying claim
- 是否只是 broad narrative，而非 deadline-sensitive evidence

而 skill 的 `evidence-engine.md` 明确要求按：

- `directness_to_settlement`
- `timeliness`
- `uniqueness`
- `impact_on_resolution`

来打分。

也就是说，**设计上要求的是“证据 relevance engine”，实现上只有“来源 tier gate”。**

### 为什么这会伤 discovery

- 高相关候选会被低相关 feed 噪音稀释
- strict/research 的分界可能偏机械
- 很多 timing edge 或 rule-scope edge，本来就依赖高度定向证据，不能靠全局 feed 解决

### 建议

- 证据改成两阶段：
  1. `global cheap feed` 只用于发现催化剂和线索
  2. 对 shortlist 候选做 `candidate-targeted retrieval`
- 证据入 judgment 前先做：
  - claim dedupe
  - relevance score
  - directness-to-settlement score
  - timing-vs-direction 标签
- `strict_allowed` 不要只看 primary 数量，要看：
  - 至少一个 settlement-direct claim
  - 至少一个独立 claim cluster
  - timing trade 需要 deadline-relevant evidence

---

## 5. 现在缺一个真正的“结构先验分数”

设计文档里写的是：

- 先 filter and rank candidates
- 再由 judgment 去做深判断
- 最后按 `edge x confidence x liquidity` 排序

但现在 runtime 里几乎没有这个 ranking layer。

缺失的不是“再多一点模型分析”，而是缺一层 **结构先验**，用来在 LLM 前就判断：

- 这个市场是不是表达清晰
- 这个机会是不是更像 timing edge 而不是 narrative trap
- 这个盘口有没有可执行性
- 这个市场是不是同一 thesis 的重复表达
- 这个机会是不是值得耗费检索和 judgment 成本

### 建议

增加一个 `candidate_score`，至少分成五部分：

- `structure_score`
  - rule clarity
  - 是否属于 clean binary / clean bucket
  - 是否有邻近表达可比较
- `execution_score`
  - spread
  - top-of-book depth
  - 预估 capacity
- `timing_score`
  - deadline proximity
  - catalyst proximity
  - 是否存在制度性等待/推进机制
- `mispricing_prior_score`
  - 邻近桶单调性异常
  - 同主题表达不一致
  - 场外 anchor 偏离
- `novelty_score`
  - 是否是新 thesis
  - 是否已在近期 alert 过

然后只把 `candidate_score` 前列的候选送入 targeted retrieval 和 judgment。

---

## 6. 反馈与 calibration 还不能告诉你“为什么没挖到机会”

现在 calibration 更偏 alert 结果面，而不是 discovery 过程面。
这会让你很难回答下面这些真正重要的问题：

- 这轮 scan 一共看了多少 family？
- 哪些 category 被系统性低估了？
- 为什么某个机会没进 judgment？
- 是被 liquidity 卡掉，还是被 ranking 压掉，还是 evidence 没跟上？
- 最近一个月的 false negative 多来自哪种 archetype？

而且当前 run 持久化里，`scanned_events` 实际写入的是 `total_markets`，连基础 coverage 指标都已经有偏差。

### 建议

- 把 calibration 拆成：
  - `scan coverage`
  - `ranking quality`
  - `judgment quality`
  - `alert usefulness`
- 每个被拒候选都保留 `rejection_reason` 和关键特征摘要
- 新增 “missed-opportunity review”：
  - 回看后来大幅波动/兑现的市场，当时为什么没进候选

---

## 三、最值得做的优化顺序

## P0：先补齐 candidate context

先做这些，不然别的优化收益会被吃掉：

- 在 `ScanCandidate` / `AlertSeed` / judgment context 中加入价格与 deadline 相关字段
- 保留 category / tag / event title / outcome name
- 把同 event 的 sibling expressions 带进 context
- 修正 coverage 指标

这是最小但杠杆最大的改动。

## P1：增加 pre-LLM ranking layer

目标不是立刻变聪明，而是让 judgment 成本花在对的地方：

- 扩大 universe
- 先做结构评分
- 再做 shortlist
- 再做 evidence / judgment

这一步会显著提高“发现新机会”的真实效率。

## P1：把 evidence 改成 candidate-targeted

如果 evidence 还是全局拼接，很多 high-edge setup 还是会被噪音掩盖。

建议做成：

- global feed 找线索
- shortlist 候选再做定向 evidence pull
- claim 级去重和 relevance 打分

## P2：引入 family-aware judgment

让 judgment 直接回答这些问题：

- asked market 值不值得做
- cleaner expression 是什么
- 这是 timing edge、rule-scope edge，还是 narrative trap
- 如果 thesis 对但时间错，最佳表达是什么

---

## 四、我会怎么重构这套 discovery 管线

理想中的链路应该是：

```text
Universe Pull
  -> Feature Extraction
  -> Expression Family Build
  -> Structural Ranking
  -> Candidate-Targeted Evidence Retrieval
  -> Family-Aware Judgment
  -> Portfolio / Dedupe Layer
  -> Alert or No-Trade with coverage accounting
```

更具体一点：

1. `Universe Pull`
   拉更多板块，不只看高成交前排。
2. `Feature Extraction`
   保留价格、deadline、depth、category、volume、outcome 等完整特征。
3. `Expression Family Build`
   找相邻桶、对手表达、规则相近表达。
4. `Structural Ranking`
   先筛掉明显不值得深入的候选。
5. `Targeted Evidence Retrieval`
   针对 shortlist 找真正相关证据。
6. `Family-Aware Judgment`
   不是问“这个市场好不好”，而是问“这组表达里哪个最好”。
7. `Portfolio / Dedupe`
   避免同 thesis 反复报警。
8. `Calibration`
   记录为什么入选、为什么淘汰、后验是否正确。

---

## 五、最核心的一句话

目前系统最大的瓶颈，不是“判断逻辑还不够聪明”，而是：

**在进入判断之前，机会发现层没有把候选市场组织成一个可比较、可排序、可定向取证的对象。**

所以优化重点不该先放在“让 skill 再多想一点”，而应该放在：

**让 scan 层先保留足够多的结构信息，再把 judgment 预算花在最值得深挖的候选上。**

---

## 代码与文档锚点

- 扫描默认只抓按 `volume24hr` 排序的一段市场，并且默认 `limit=200`：
  - `runtime/src/polymarket_alert_bot/scanner/gamma_client.py`
  - `runtime/src/polymarket_alert_bot/config/settings.py`
- 预筛目前只看 active/liquidity/spread/duplicate：
  - `runtime/src/polymarket_alert_bot/scanner/board_scan.py`
- judgment 候选优先级目前主要靠 domain marker + liquidity + spread：
  - `runtime/src/polymarket_alert_bot/scanner/board_scan.py`
- `ScanCandidate` 当前没有保留 bid/ask/mid/deadline/category：
  - `runtime/src/polymarket_alert_bot/scanner/normalizer.py`
- judgment 实际拿到的上下文里没有完整 expression family，也没有成交价格：
  - `runtime/src/polymarket_alert_bot/flows/scan.py`
  - `runtime/src/polymarket_alert_bot/flows/shared.py`
- eval fixture 期望 runtime judgment 拿到 richer executable fields：
  - `evals/runtime-v1-scan-payload.json`
- skill 自身的方法论要求先发现完整表达集、比较 adjacent buckets：
  - `skills/prediction-market-analysis/SKILL.md`
- skill 的 evidence engine 要求 relevance / uniqueness / settlement directness 打分：
  - `skills/prediction-market-analysis/references/evidence-engine.md`
- 产品设计目标本来就要求 `filter and rank` 以及 `edge x confidence x liquidity`：
  - `docs/workflow-references/2026-04-17-gstack-design-polymarket-alert-bot.md`

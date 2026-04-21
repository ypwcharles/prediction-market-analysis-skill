# BOJ 2026 年 4 月决议市场分析

- 文档日期: 2026-04-13
- 分析主题: Polymarket `economy` 板块机会扫描，重点聚焦 `Bank of Japan Decision in April?`
- 分析时间窗口: 2026-04-10 至 2026-04-13
- 市场快照说明: 文中盘口价格主要来自 2026-04-10 抓取的 Polymarket API 快照，用于保存当时的分析判断，不代表后续实时价格

## 1. 结论摘要

在 2026-04-10 对 Polymarket `economy` 板块的扫描中，最值得下注的不是美国通胀分桶，也不是 Fed 全年降息次数，而是 `Bank of Japan Decision in April?` 市场中的 `Yes` on `No change`。

核心判断是:

- 日本通胀压力真实存在，年内继续偏鹰是更强命题
- 但市场可能把 BOJ 加息时点前置得过头，过度押注 2026-04-28 这次会议就会立即行动
- 因此，更干净的表达不是赌 `BOJ 不会加息`，而是赌 `BOJ 4 月这次先不动`

最终交易结论:

- 市场: `Bank of Japan Decision in April?`
- 推荐选项: `Yes` on `No change`
- 结论: `TRADE`
- 推荐仓位: 总本金的 `0.5%-1.0%`
- 最大入场价: `0.36`
- `0.38` 以上转为 `NO TRADE`

## 2. Economy 板块机会筛选结果

### 2.1 候选机会排序

1. `TRADE`: `Bank of Japan Decision in April?` 的 `Yes` on `No change`
2. `NO TRADE`: `Fed rate cut by...?` / `How many Fed rate cuts in 2026?`
3. `NO TRADE`: 4 月 10 日刚公布数据后的美国通胀与鸡蛋价格分桶

### 2.2 为什么其他机会被否掉

#### Fed 相关市场

被重点检查的市场:

- `Fed decision in April?`
- `Fed Decision in June?`
- `Fed rate cut by...?`
- `How many Fed rate cuts in 2026?`

否决原因:

- `全年降息几次` 不是最干净的表达，因为你要同时押方向和全年时点分布
- `6 月前会不会降息` 虽然表达更干净，但当时盘口给出的边际已经很薄
- 市场真正的错价更像是 `时间表达` 的问题，而不是 `方向完全错`

#### 通胀和鸡蛋价格分桶

被检查的市场:

- `March Inflation US - Annual`
- `March Inflation US - Annual (Higher Brackets)`
- `March Inflation US - Monthly`
- `Price of Dozen Eggs in March?`

否决原因:

- 这些市场在官方数据公布后已经基本收敛到 `0.999 / 0.001`
- resolution arb 基本消失
- 剩余空间不足以覆盖执行和尾部风险

## 3. 重点交易: BOJ 4 月决议

### 3.1 市场定义

- 平台: Polymarket
- 市场: `Bank of Japan Decision in April?`
- 结算时间: 2026-04-28
- 结算规则: 以 BOJ 4 月会议公布的政策利率变动幅度结算

### 3.2 抓取到的盘口快照

2026-04-10 抓取到的主要价格如下:

- `No change`: `0.33 bid / 0.36 ask`
- `25 bps increase`: `0.62 bid / 0.63 ask`
- `50+ bps increase`: `0.008 bid / 0.015 ask`
- `Decrease rates`: `0.004 bid / 0.005 ask`

当时分析结论:

- 市场给 `No change` 的隐含概率大约是 `34.5%`
- 主观调整后给 `No change` 的概率是 `42%`
- 置信区间为 `38%-50%`

### 3.3 最佳表达为什么是 `No change`

关键不是赌 `BOJ 偏鸽`，而是赌 `BOJ 没有必要在 4 月这次立刻行动`，因此在这个多结果市场里应买 `Yes` on `No change`。

这笔交易的优势在于:

- 如果 BOJ 6 月或 7 月再加息，`No change` 仍然会赢
- 如果你直接买 `25 bps increase`，你是在为过高的时点精度付钱
- 这使 `No change` 成为更干净、更抗“方向对但时点错”的表达

## 4. 经济逻辑

### 4.1 为什么“日本通胀很严重”不自动等于“4 月必加”

这个问题需要拆成两件事:

- 日本是否已经有持续通胀压力
- BOJ 是否必须在 2026-04-28 这次会议就回应

前者更接近 `年内继续偏鹰`

后者才是这个合约真正结算的命题

两者相关，但不等价。

### 4.2 战争、油价与 BOJ 的关系

美国与伊朗冲突如果推高油价，会同时造成两种效果:

- 物价上升: 汽油、电力、燃气、运输和食品成本上涨
- 增长受损: 家庭实际购买力下降，企业成本上升，经济活动受压

这类冲击更像 `供给冲击`，不是 `需求过热`。

因此:

- 加息不能直接让油价回落
- 但如果高油价进一步推高更广泛的价格、工资和通胀预期，BOJ 会担心形成二轮通胀

BOJ 真正关心的不是“油贵了”，而是:

> 这次外部冲击会不会把日本从温和通胀，推成持续性的工资-价格循环。

### 4.3 为什么 `4 月不动、以后再加` 更合理

当时的判断是:

- 日本通胀和工资数据都偏鹰
- 但 4 月会议前，BOJ 仍有充分理由再确认一轮信息
- 因此 `年内更鹰` 强于 `4 月这次就加`

更直白地说:

- `方向命题`: BOJ 可能还会继续加息
- `时点命题`: 4 月 28 日这次会议不一定就是执行点

## 5. 客观评估框架

为了避免只靠“朋友体感通胀”做交易，分析中采用了如下框架:

### 5.1 主证据

- 官方 CPI 数据
- 工资谈判结果
- BOJ 官方讲话与会议纪要
- 官方对油价、通胀和金融条件的表述

### 5.2 辅助证据

- 居民体感通胀
- 媒体采访
- 市场叙事

### 5.3 具体观察项

#### 基础通胀

- 东京区部 2026 年 3 月 `core` 同比 `1.7%`
- 东京区部 2026 年 3 月 `core-core` 同比 `2.3%`
- 日本全国 2026 年 2 月 `core` 同比 `1.6%`
- 日本全国 2026 年 2 月 `core-core` 同比 `2.5%`

解释:

- 说明底层通胀不低
- 但还没到“必须立刻紧急加息”的程度

#### 居民高频体感

- 全国 2026 年 2 月“生鲜以外食品”同比 `5.7%`
- 东京 2026 年 3 月“生鲜以外食品”同比 `4.9%`

解释:

- 居民觉得“物价很痛”是有数据支持的
- 但这类体感证据更强地支持“通胀压力存在”，不等于直接锁定 4 月加息

#### 工资-通胀循环

- 连合 2026 年 3 月 23 日首轮春斗显示整体加薪 `5.26%`
- 中小企业加薪 `5.05%`

解释:

- 这是偏鹰的高权重证据
- 因为这比“食品涨价”更接近 BOJ 真正关心的持续性通胀

#### BOJ 官方口风

2026 年 3 月 18-19 日会议意见摘要显示:

- BOJ 承认中东与油价上行可能抬高通胀
- 但同时表示当前没有必要修改基线判断
- 并强调从下一次会议开始再细看工资、价格与金融条件

解释:

- 这是典型的 `偏鹰但仍要确认`
- 不是 `4 月加息已经锁死`

### 5.4 评估结论

如果用机械框架打分:

- 基础通胀: `偏鹰`
- 食品和生活成本压力: `偏鹰`
- 工资和二轮通胀迹象: `强偏鹰`
- 油价冲击对增长的伤害: `偏鸽`
- BOJ 对 4 月立刻行动的沟通强度: `中性偏鸽`

综合之后:

- `年内继续偏鹰` 的概率高
- `4 月 28 日这次就加` 的概率没有市场价格显示得那么确定

## 6. 交易定价与仓位

### 6.1 概率与边际

当时给出的估计为:

- 市场隐含: `No change` 约 `34.5%`
- 主观主概率: `42%`
- 保守下沿: `38%`

据此:

- 保守公允值大约在 `0.38`
- 若能在 `0.36` 或以下成交，仍有薄边
- 若价格被买到 `0.38` 以上，边际基本消失

### 6.2 仓位建议

原始 Kelly 很小，且需要进一步打折。

最终给出的执行建议:

- 推荐仓位: 总本金的 `0.5%-1.0%`
- 更稳健的区间: `0.5%-0.75%`
- 入场方式: 分两笔挂限价，不追市价
- 最大入场价: `0.36`

### 6.3 风险控制

失效条件:

- 会前出现 BOJ 官员或高可信媒体把 `4 月加息` 明确转成主情景
- `No change` 被重新买到 `0.38+`，但没有新增偏鸽证据
- 新数据同时支持更强的工资-通胀循环，而市场尚未充分反映

## 7. 最终判断

这次分析最重要的结论不是“日本没有通胀”，而是:

> 日本通胀压力是真实的，但这更强地支持 `BOJ 年内继续偏鹰`，不如支持 `BOJ 4 月 28 日这次必须立刻加息`。

因此，在当时的 Polymarket `economy` 板块里，最好的下注表达是:

- 买 `Bank of Japan Decision in April?` 的 `Yes` on `No change`
- 用小仓位表达 `方向偏鹰，但时点可能被市场前置过头`

## 8. 主要来源

- Polymarket Economy 页面: https://polymarket.com/economy
- Polymarket BOJ 市场: https://polymarket.com/event/bank-of-japan-decision-in-april
- Polymarket API 事件接口: https://gamma-api.polymarket.com/events?slug=bank-of-japan-decision-in-april
- BOJ Summary of Opinions, 2026-03-18/19: https://www.boj.or.jp/en/mopo/mpmsche_minu/opinion_2026/opi260319.pdf
- BOJ Takata speech, 2026-02-26: https://www.boj.or.jp/en/about/press/koen_2026/ko260226a.htm
- Japan Statistics Bureau, Tokyo CPI March 2026: https://www.stat.go.jp/data/cpi/sokuhou/tsuki/pdf/kubu.pdf
- Japan Statistics Bureau, National CPI February 2026: https://www.stat.go.jp/data/cpi/sokuhou/tsuki/pdf/zenkoku.pdf
- JTUC-Rengo spring wage tally, 2026-03-23: https://www.jtuc-rengo.or.jp/info/rengotv/kaiken/20260323_kaito01.html

## 9. 2026-04-16 复盘补充

### 9.1 这笔交易真正成功的地方

从事后回看，这笔交易最有价值的不是“盈利很多”，而是以下几条在入场时就已经成立:

- 表达正确: 选的是 `Yes` on `No change`，而不是去买 `25 bps increase`
- 方向与时点拆分正确: `BOJ 继续偏鹰` 与 `BOJ 4 月这次就动` 被明确分开
- 证据质量够高: 关键证据来自 BOJ 官方摘要、官方 CPI、工资数据，而不是情绪或二手讨论
- payoff 结构好: 如果 BOJ 6 月或 7 月再动，这笔仓位依然能赢
- 市场可能过度给了“立刻行动”溢价

### 9.2 不应被过度学习的部分

以下不能直接被当成未来放大仓位的理由:

- 浮盈本身
- 会后市场进一步确认的消息
- 只因为这次行情走得很快，就默认未来类似交易都该更大仓位

### 9.3 可提炼成 skill 的经验

如果未来再次出现类似 setup，应优先检查:

- 这是不是一个高质量 deferred-action / timing-fade
- 早窗口的不发生腿是否能在多个“方向对但更晚”的路径上获利
- 关键等待逻辑是否已经有 primary source 支撑
- 是否存在更干净的表达使仓位能够从试仓提升到核心小仓

### 9.4 对 sizing 的复盘结论

这笔交易说明原始仓位偏小，但不能因为结果好就机械放大。

更合理的改进是:

- 对满足高质量 timing fade 条件的 setup，不要自动只给“试仓”
- 先做 outcome-blind 复核
- 只有在 clean settlement、expression dominance、primary-source evidence、multi-path payoff 都成立时，才把未来同类 setup 提升到更高 sizing bucket

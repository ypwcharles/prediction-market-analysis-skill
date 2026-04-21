# Polymarket 票房市场扫描

- 分析快照日期：`2026-04-13`
- 保存日期：`2026-04-13`
- 范围：扫描当前 Polymarket 上的 `box office` 相关市场，重点判断在没有天气 infra 的前提下，哪些票房市场最适合先做成第一套系统化研究框架
- 主入口页面：[Polymarket Movies](https://polymarket.com/predictions/movies)

## 摘要

- 票房是 Polymarket `culture` 里最干净的一类子市场之一，但它并不是单一市场类型。当前至少可以拆成五种结构明显不同的合约家族。
- 最值得作为起点的，不是长周期的全年 outrights，而是短周期的 `单片开画周末分桶` 市场，其次是 `第 2 / 3 周末 holdover 分桶` 市场。
- 这个方向最大的隐性风险不是预测误差，而是规则错配。Polymarket 上不同票房市场的结算来源和定义并不统一：
  - 有些用 [Box Office Mojo 电影详情页](https://www.boxofficemojo.com/title/tt28650488/)
  - 有些用 [The Numbers 电影详情页](https://www.the-numbers.com/)
  - 有些用 [Box Office Mojo 年度 calendar grosses 页面](https://www.boxofficemojo.com/year/2026/?grossesOption=calendarGrosses)
  - 有些用 [The Numbers 年度电影列表页](https://www.the-numbers.com/)
- 如果你现在没有现成 infra，票房依然是很适合先做的第一套系统，因为它的 ETL 明显比天气简单：
  - 更新频率更低
  - 结算源更清晰
  - 每周都会重复出现新的可研究机会
  - 不需要天气里那种站点映射和地理匹配
- 当前票房市场确实值得研究，但仅靠今天能公开拿到的数据，我还没有看到一个足够干净、足够有证据支撑的 live `TRADE`。更合理的第一步，是先搭好一层可复用的 `规则解析 + 数据抓取` 基础设施，专门服务短周期的电影票房市场。

## 市场地图

### 1. 单片开画周末分桶市场

例子：

- [`"Michael" Opening Weekend Box Office`](https://polymarket.com/event/michael-opening-weekend-box-office)
- [`"The Super Mario Galaxy Movie" Opening Weekend Box Office`](https://polymarket.com/event/the-super-mario-galaxy-movie-opening-weekend-box-office)

观察到的特征：

- 通常会有 `6` 个左右相邻的 strike buckets
- 高热度影片的参与度很高
- 距离结算时间短
- 评论区和价格重定价都很活跃

当前证据：

- 到 `2026-04-13` 为止，`Michael` 这个市场页面上最靠前的两个桶大致是平手：
  - `<60m` 大约 `50%`
  - `60-65m` 大约 `50%`
- 已经结束的 `Super Mario Galaxy` 开画市场，成交量大约 `$2.2M`，最后落在 `190-200m` 这个区间。

结算细节：

- `Super Mario Galaxy` 的开画市场，结算依据是其 [Box Office Mojo 详情页](https://www.boxofficemojo.com/title/tt28650488/) 中 `"Domestic Daily"` 标签页的数据，使用的是 `Apr 1 - Apr 5` 这段 `5-day` opening weekend 的最终值，而不是 studio estimates。
- 同一个市场还明确写了：如果存在歧义，会一直保持未结算状态，直到 [Box Office Mojo](https://www.boxofficemojo.com/) 和 [The Numbers](https://www.the-numbers.com/) 都确认 final figures。

为什么这是最好的起始表达：

- 市场结构重复度高
- 历史标签干净
- 资金占用时间短
- 规则比年榜类叙事市场更具体
- 催化节点清楚：
  - theater count
  - preview gross
  - Friday actual
  - Saturday estimate
  - Sunday / Monday finalization

主要陷阱：

- `3-day` 和 `5-day` 开画经常混淆
- 某些 weekend figures 会隐含包含 Thursday previews
- 规则文字可能写一个 source，但实际又要求两个站点都收敛后才结算
- 公开 tracking headlines 会提前推动价格，但不等于真的有 edge

结论：

- `最值得优先研究`

## 2. holdover 周末分桶市场

例子：

- [`"Project Hail Mary" 2nd Weekend Box Office`](https://polymarket.com/predictions/movies)
- [`"Hoppers" 4th Weekend Box Office`](https://polymarket.com/event/hoppers-4th-weekend-box-office/will-hoppers-4th-weekend-box-office-be-between-12m-and-13m)

观察到的特征：

- 成交量低于头部开画市场，但仍然足够有研究价值
- 到 `2026-04-13` 为止，Movies 页面显示：
  - `Project Hail Mary 2nd Weekend` 约有 `$43.5K` 成交量和 `$32.2K` 流动性
  - `Hoppers 4th Weekend` 约有 `$23.8K` 成交量和 `$19.1K` 流动性

为什么这个方向有吸引力：

- 一旦首周票房出来，建模会比开画周末更容易
- holdover 的衰减曲线更结构化、更可重复
- daily grosses、theater changes、weekday-to-weekend ratio 这些变量，比纯粹的上映前 hype 更适合量化

为什么它不该是第一套要做的东西：

- 你依然需要和 opening weekend 一样的 rules parser 和 daily box office ETL
- 最有 edge 的时点通常出现在 Friday actual 之后，如果你还是以 taker 身份进场，可能已经没剩多少空间

结论：

- `第二优先级研究目标`

## 3. 周末冠军市场

例子：

- [`Highest grossing movie this weekend (March 27)`](https://polymarket.com/event/highest-grossing-movie-this-weekend-march-27)

观察到的特征：

- 这是多结果排名市场，不是分桶市场
- 成交量通常低于最好的单片市场
- 这个示例页面显示的总成交量大约是 `$28.6K`

为什么它看起来容易，实际上没那么好做：

- 一旦某部片子明显会拿下周末冠军，市场很快就会接近确定性
- 真正的 edge 往往来自上映排期细节或 preview 信息，而这些信息出现时离周末已经很近
- 如果冠军已经很清楚，这类市场除了结算套利或捡 stale pricing 之外，通常没太多可做空间

结论：

- `可以交易，但不适合作为第一套系统的核心`

## 4. 月度累计冠军市场

例子：

- [`Highest Domestically Grossing March Film on April 30?`](https://polymarket.com/predictions/movies)
- [`Highest Domestically Grossing April Film on May 31?`](https://polymarket.com/event/highest-domestically-grossing-april-film-on-may-31)

观察到的特征：

- 这个 April 市场的 event 页面显示总成交量大约是 `$101.6K`
- 到 `2026-04-13` 为止，`The Super Mario Galaxy Movie` 的隐含概率大约在 `98.3%`

结算细节：

- 这个 April 市场使用相关电影在 [The Numbers](https://www.the-numbers.com/) 页面的 `"Daily Box Office Performance"` 作为结算依据
- 统计的是从上映开始到 `May 30, 2026` 之间的累计 domestic gross
- 若并列则按字母顺序决胜

为什么这类市场没有想象中那么强：

- 一旦月初就有一部大爆款开出来，市场很容易连续几周变成单边盘
- 这个合约极强依赖路径
- 后上映的电影除非前面领跑者崩得很厉害，否则通常几乎没有反超机会

结论：

- `规则很干净，但可重复 edge 较弱`

## 5. 年度 outrights 与长周期跨片市场

例子：

- [`Highest grossing movie in 2026?`](https://polymarket.com/event/highest-grossing-movie-in-2026)
- [`Which movie has biggest opening weekend in 2026?`](https://polymarket.com/event/which-movie-has-biggest-opening-weekend-in-2026/will-scream-7-have-the-best-domestic-opening-weekend-in-2026)
- Polymarket 页面上还能看到相关 head-to-head 表达：`Will Dune 3 or Avengers: Doomsday gross more on their opening weekend?`

观察到的特征：

- 成交量明显更大：
  - `Highest grossing movie in 2026?` 约为 `$3.46M`
  - `Which movie has biggest opening weekend in 2026?` 约为 `$1.39M`

结算细节：

- `Highest grossing movie in 2026?` 是按 [Box Office Mojo 2026 calendar grosses 页面](https://www.boxofficemojo.com/year/2026/?grossesOption=calendarGrosses) 中 `"Gross"` 列结算
- `biggest opening weekend` 这个年度市场则使用 The Numbers 年度电影列表页里的最终 `3-day` opening weekend 数字

为什么我不建议从这里起步：

- 这类市场的叙事性和排期风险都更强
- release date changes 的影响很大
- reshoots、marketing shifts、format rollout、franchise narrative 会在很长一段时间里主导价格
- 你的 edge 更可能来自对模糊上映前信息的解释，而不是来自对结构化公开数据的更好处理

结论：

- `流动性很好，但不是第一研究目标`

## 结算源审计

这是这次扫描里最关键的结构性发现。

表面上都叫 `box office market`，但底层其实混着几套彼此不兼容的结算 schema：

1. `Box Office Mojo title page`
   - 例子：[The Super Mario Galaxy Movie](https://www.boxofficemojo.com/title/tt28650488/)
   - 用于单片开画周末分桶市场
   - 可能依赖 `"Domestic Daily"` 数值
   - 可能是 `5-day` opening

2. `The Numbers title page`
   - `Highest Domestically Grossing April Film on May 31?` 这类市场就是这一类
   - 用电影详情页里的累计日票房

3. `Box Office Mojo annual calendar gross page`
   - [Domestic Box Office For 2026](https://www.boxofficemojo.com/year/2026/?grossesOption=calendarGrosses)
   - 用于全年 calendar-gross outrights
   - 这和 total lifetime domestic gross 不是一回事

4. `The Numbers yearly movie table`
   - 用于 `Which movie has biggest opening weekend in 2026?`
   - 关键字段是最终的 `3-day` weekend performance

这意味着，如果要做成可复用系统，必须先有一张 `market-type -> resolution-source -> parsing-rule` 的映射表。只做一个统一的 `movie_gross` 表不够。

## 真正可能产生 edge 的地方

### 最强的 edge 来源

- 规则解释：
  - `3-day` vs `5-day`
  - `calendar gross` vs total domestic gross
  - title page 总数 vs yearly ranking table
- 上映日历变化：
  - [The Numbers release schedule changes](https://www.the-numbers.com/movies/release-schedule-changes/2025/12/07)
- theater count 更新：
  - The Numbers 首页会持续给出和周末档期有关的 theaters context
- 来自靠谱行业 tracker 的 forecast revisions：
  - [Boxoffice Pro 对 Michael 的 long-range forecast](https://www.boxofficepro.com/long-range-forecast-lionsgate-bets-big-on-music-biopic-michael/)
  - The Numbers 首页也会持续发布自己的周末预测和模型 commentary
- 上映后的 hold 建模：
  - Friday actual
  - Saturday estimate
  - Sunday final
  - weekday decay

### 较弱的 edge 来源

- 泛化的 trailer view headlines
- 没有票务数据支撑的社交情绪
- 宽泛的 “franchise hype” 叙事
- 除非评论区贴出可验证来源，否则 Polymarket comments 不应作为核心依据

## 建议的第一版搭建顺序

如果从零开始，我会按下面这个顺序做：

1. `rules registry`
   - 先把每一个 box office 市场归类到上面几种 source schema
   - 记录它到底是 `3-day`、`5-day`、`calendar-gross`、`month-to-date` 还是 `holdover`

2. `source ingestors`
   - Box Office Mojo title pages
   - Box Office Mojo annual calendar page
   - The Numbers home page 和 title pages
   - The Numbers release schedule changes page

3. `historical normalization`
   - opening weekend
   - second weekend drop
   - theater count
   - release month
   - distributor
   - franchise / sequel flag
   - genre
   - rating

4. `first model`
   - 只先打 `single-title opening weekend bucket` 这一类
   - 先输出 bracket probabilities，不要一上来就做 point forecast

5. `second model`
   - 再扩展到 `2nd / 3rd weekend hold` 市场

我不建议一开始就做 annual outrights。它们成交量看起来更大，但对第一版系统来说不是更好的起点。

## 当前观察名单

### `Michael` 开画周末

- 当前状态：
  - 这个市场大约在 `2026-04-09` 左右上线
  - 按 `2026-04-10` 附近抓到的页面，最前面的两个桶大概是 `<60m` 和 `60-65m` 的 `50 / 50`
- 为什么值得盯：
  - 这是当前最典型的一个 live、均衡、且接近上映期的 opening-weekend 市场
  - 随着上映临近，tracking revisions 理应会持续影响价格
- 为什么我现在还不给 `TRADE`：
  - 我手里没有足够新的 primary-source tracking、theater count、review trend 或 preview 数据
  - 一篇公开的 [Boxoffice Pro long-range forecast](https://www.boxofficepro.com/long-range-forecast-lionsgate-bets-big-on-music-biopic-michael/) 在 `2026-03-27` 还给了 `80M - 90M` 区间，但这条信息本身已经太旧，不能单独拿来做纪律化入场
- 当前判断：
  - `WATCH`，不是 `TRADE`

### 短周期的小片 opening markets

- 当前 Movies 页面里还能看到 `They Will Kill You`、`You, Me & Tuscany` 这类市场
- 这些盘可能比超级大片更容易出 edge，因为盯的人少，但流动性也更差
- 当前判断：
  - `适合拿来做模型测试的观察名单`

### 月度与年度 outrights

- 适合用来观察 crowd 在看什么
- 但不适合拿来作为第一版系统的主要部署对象
- 当前判断：
  - `NO TRADE / 研究用途`

## 最终结论

- 板块级结论：`RESEARCH`
- 最好的第一类票房市场：`单片开画周末分桶`
- 第二好的市场家族：`第 2 / 3 周末 hold 市场`
- 不建议作为第一版核心的方向：
  - 全年最高票房市场
  - 全年最大 opening weekend 市场
  - 月底累计冠军市场

## 参考来源

- [Polymarket Movies](https://polymarket.com/predictions/movies)
- [`"The Super Mario Galaxy Movie" Opening Weekend Box Office`](https://polymarket.com/event/the-super-mario-galaxy-movie-opening-weekend-box-office)
- [`Highest Domestically Grossing April Film on May 31?`](https://polymarket.com/event/highest-domestically-grossing-april-film-on-may-31)
- [`Highest grossing movie in 2026?`](https://polymarket.com/event/highest-grossing-movie-in-2026)
- [`Which movie has biggest opening weekend in 2026?`](https://polymarket.com/event/which-movie-has-biggest-opening-weekend-in-2026/will-scream-7-have-the-best-domestic-opening-weekend-in-2026)
- [`"Michael" Opening Weekend Box Office`](https://polymarket.com/event/michael-opening-weekend-box-office)
- [Box Office Mojo title page for The Super Mario Galaxy Movie](https://www.boxofficemojo.com/title/tt28650488/)
- [Box Office Mojo 2026 calendar grosses](https://www.boxofficemojo.com/year/2026/?grossesOption=calendarGrosses)
- [The Numbers home page](https://www.the-numbers.com/)
- [The Numbers release schedule changes](https://www.the-numbers.com/movies/release-schedule-changes/2025/12/07)
- [Boxoffice Pro: Long Range Forecast for Michael](https://www.boxofficepro.com/long-range-forecast-lionsgate-bets-big-on-music-biopic-michael/)

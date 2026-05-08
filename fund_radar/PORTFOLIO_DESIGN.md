# 基金持仓管理设计

## 目标

`fund_radar` 的持仓管理使用 Python 实现，`fund-baby/` 只作为参考实现。第一版使用 JSON 文件管理数据，后续迁移到 SQLite 时保持业务对象和计算规则不变。

## 数据文件结构

```json
{
  "version": 1,
  "positions": {},
  "watchlist": {},
  "pending_trades": [],
  "trade_history": []
}
```

- `version`：数据结构版本号，用于后续迁移。
- `positions`：持仓基金集合，键为基金代码。
- `watchlist`：自选基金集合，键为基金代码。
- `pending_trades`：待结算交易队列，今天提交、需要下一交易日净值确认的加减仓在这里等待。
- `trade_history`：已结算交易记录。

## 单个基金行情 FundSnapshot

- `code`：基金代码，6 位数字。
- `name`：基金名称。
- `latest_nav`：最新单位净值，用于计算持有金额。
- `nav_date`：最新净值日期。
- `previous_nav`：上一交易日单位净值，可用于校验涨跌幅。
- `yesterday_change_percent`：昨日涨跌幅，单位为百分比，例如 `0.53` 表示上涨 `0.53%`。
- `estimated_nav`：盘中估算净值。
- `estimated_change_percent`：盘中估值涨跌幅。
- `estimated_time`：盘中估值时间。

## 持仓基金 FundPosition

- `code`：基金代码。
- `name`：基金名称。
- `share`：持有份额。
- `cost_nav`：持仓成本价，即每份平均成本。
- `latest_nav`：最新单位净值。
- `nav_date`：最新净值日期。
- `first_buy_date`：初次买入时间，用于记录用户第一次买入该基金的日期。
- `yesterday_change_percent`：昨日涨跌幅。
- `estimated_nav`：盘中估算净值。
- `estimated_change_percent`：盘中估算涨跌幅。
- `estimated_time`：盘中估算时间。
- `estimated_profit`：当日估算收益，优先用于盘中看账户波动。
- `sector_tags`：关联板块或人工标签，例如 `CPO`、`AI算力`。
- `holding_amount`：持有金额，计算公式为 `share * latest_nav`。
- `holding_profit`：持有收益，计算公式为 `(latest_nav - cost_nav) * share`。
- `holding_profit_rate`：持有收益率，计算公式为 `holding_profit / (cost_nav * share) * 100`。
- `yesterday_profit`：昨日收益，计算公式为 `holding_amount - holding_amount / (1 + yesterday_change_percent / 100)`。
- `updated_at`：本条持仓最后更新时间。

## 自选基金 WatchFund

- `code`：基金代码。
- `name`：基金名称。
- `created_at`：加入自选时间。
- `note`：备注，第一版可为空。

## 交易记录 TradeRecord

- `id`：交易唯一编号。
- `code`：基金代码。
- `name`：基金名称。
- `type`：交易类型，`buy` 表示加仓，`sell` 表示减仓。
- `share`：交易份额。按比例卖出时由当前份额乘以比例得到。
- `amount`：交易金额。买入时可填写金额；卖出结算后按 `share * nav` 得到。
- `fraction`：卖出比例，例如 `1/2`、`1/3`、`1/4`。
- `trade_date`：提交交易日期。
- `settle_nav`：结算净值。
- `settle_date`：结算净值日期。
- `status`：交易状态，`pending` 或 `settled`。
- `created_at`：创建时间。
- `settled_at`：结算时间。

## 计算规则

新增持仓支持两种方式：

- 详细新增：输入 `share`、`cost_nav`、`latest_nav`。
- 简化新增：输入 `holding_amount`、`holding_profit`、`latest_nav`，反推 `share = holding_amount / latest_nav`，`cost_nav = (holding_amount - holding_profit) / share`。

`set` 指令用于修正单个基金的详细数据，例如成本价、份额、最新净值或初次买入时间。修改任意基础字段后统一重算 `holding_amount`、`holding_profit`、`holding_profit_rate` 和 `yesterday_profit`。

更新行情只改变净值、日期、涨跌幅和派生字段，不改变 `share`、`cost_nav` 与 `first_buy_date`。

盘中展示优先使用 `estimated_change_percent` 计算 `estimated_profit`；如果没有估值数据，则回退展示 `yesterday_profit`。板块标签支持手动设置，手动标签不应被后续导入覆盖。

加仓先进入待结算队列，结算时使用确认净值：

```text
new_share = old_share + amount / settle_nav
new_cost_nav = (old_share * old_cost_nav + amount) / new_share
```

减仓同样先进入待结算队列。按比例减仓先计算 `sell_share = current_share * fraction`。结算时：

```text
new_share = old_share - sell_share
cost_nav 不变
如果 new_share == 0，则 cost_nav = 0
```

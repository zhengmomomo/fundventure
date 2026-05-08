# fund_radar 使用说明

`fund_radar` 是一个 Python 版基金持仓管理工具。当前版本以 `fund-baby/` 作为参考实现，使用 JSON 保存数据，支持基金估算涨跌幅查询、持仓增删改查、持仓刷新、加减仓待结算、自选基金和终端看板展示。

## 环境准备

项目使用 conda 虚拟环境 `fund`：

```bash
conda activate fund
cd /home/zhengmomomo/nanopoc/fundventrue/fund_radar
```

默认数据文件是 `data/portfolio.json`。所有命令都可以通过 `--data` 指定其他 JSON 文件：

```bash
python scripts/portfolio_cli.py --data data/test.json list
```

## 当前项目结构

- `core/models.py`：基金行情、持仓、自选和交易记录的数据对象。
- `core/portfolio.py`：持仓增删改查、收益计算、行情更新和交易结算逻辑。
- `core/fund_data.py`：基金代码解析、净值和估算涨跌幅查询。
- `scripts/portfolio_cli.py`：持仓管理命令行入口。
- `scripts/query_fund_estimate.py`：最小化基金估算涨跌幅查询脚本。
- `scripts/import_holdings_md.py`：从 `data/holding.md` 批量导入持仓。
- `data/portfolio.json`：当前持仓数据。
- `PORTFOLIO_DESIGN.md`：数据结构和计算规则设计文档。

## 数据说明

单个持仓基金主要字段包括：

- `code`、`name`：基金代码和名称。
- `share`：持有份额。
- `cost_nav`：持仓成本价。
- `latest_nav`、`nav_date`：最新单位净值和净值日期。
- `first_buy_date`：初次买入时间。
- `holding_amount`：持有金额，按 `share * latest_nav` 计算。
- `holding_profit`：持有收益，按 `(latest_nav - cost_nav) * share` 计算。
- `holding_profit_rate`：持有收益率。
- `yesterday_change_percent`、`yesterday_profit`：昨日涨跌幅和昨日收益。
- `estimated_nav`、`estimated_change_percent`、`estimated_time`：盘中估算净值、估算涨跌幅和估算时间。
- `estimated_profit`：当日估算收益。
- `sector_tags`：关联板块或人工标签，例如 `CPO`。

说明：支付宝等平台的昨日收益、成本价可能包含手续费、分红、四舍五入或确认日规则，本工具按公开净值和本地字段计算，允许用 `set` 手动校准。

## 查询估算涨跌幅

查询一个基金：

```bash
python scripts/query_fund_estimate.py 013841
```

查询多个基金：

```bash
python scripts/query_fund_estimate.py 013841 002112 永赢科技智选混合发起C
```

返回字段包括基金代码、名称、净值日期、估算净值、估值时间和预估涨跌幅。

## 新增和查看持仓

最简新增方式只需要基金代码或名称、持有金额和持有收益。基金名称、最新净值、净值日期和估算涨跌幅会自动查询：

```bash
python scripts/portfolio_cli.py add 013841 --amount 957.09 --profit 161.63
```

## 基金名称和代码匹配

持仓相关命令支持用基金代码、完整基金名、名称前缀或名称片段定位基金。匹配顺序为：代码精确匹配、基金名精确匹配、基金名前缀匹配、基金名包含匹配。

例如下面几种写法都可以匹配 `002112 德邦鑫星价值灵活配置混合C`：

```bash
python scripts/portfolio_cli.py show 002112
python scripts/portfolio_cli.py show 德邦鑫星价值灵活配置混合C
python scripts/portfolio_cli.py show 德邦鑫星价值灵活
python scripts/portfolio_cli.py show 鑫星价值
```

如果输入同时匹配多只基金，命令不会自动猜测，会输出候选基金代码和名称，要求输入更精确的名称或代码。

目前支持模糊匹配的持仓命令包括：

```text
show, set, edit, delete, update, buy, sell
```

查看全部持仓：

```bash
python scripts/portfolio_cli.py list
```

查看单个基金详情：

```bash
python scripts/portfolio_cli.py show 013841
```

删除持仓：

```bash
python scripts/portfolio_cli.py delete 013841
```

## 修改详细数据

当自动反推的份额、成本价和实际平台不一致时，用 `set` 校准。修改后会自动重算持有金额、持有收益、收益率、昨日收益和估算收益。

```bash
python scripts/portfolio_cli.py set 013841 --share 435.94 --cost-nav 1.7873
```

设置昨日涨跌幅：

```bash
python scripts/portfolio_cli.py set 013841 --change-percent 1.97
```

设置初次买入时间：

```bash
python scripts/portfolio_cli.py set 013841 --first-buy-date 2026-05-06
```

设置关联板块，`--sector` 可以重复：

```bash
python scripts/portfolio_cli.py set 002112 --sector CPO
python scripts/portfolio_cli.py set 德邦鑫星价值灵活 --sector CPO
python scripts/portfolio_cli.py set 002112 --sector CPO --sector AI算力
```

手动设置估算数据：

```bash
python scripts/portfolio_cli.py set 013841 --estimated-nav 2.20 --estimated-change-percent 1.5 --estimated-time "2026-05-07 14:50"
```

## 刷新行情和看板

联网刷新全部持仓的最新净值和盘中估算涨跌幅：

```bash
python scripts/portfolio_cli.py refresh
```

手动刷新始终保留。自动刷新使用系统 `crontab`，不会占用一个长期运行的 Python 进程：

```bash
# 开启自动刷新
python scripts/portfolio_cli.py auto-refresh on

# 查看自动刷新状态
python scripts/portfolio_cli.py auto-refresh status

# 关闭自动刷新
python scripts/portfolio_cli.py auto-refresh off
```

开启后会写入当前用户 crontab，只管理 `fund_radar auto-refresh` 标记块，不会修改其他定时任务。刷新计划为工作日 `09:30` 到 `14:30` 每小时一次，并在 `15:00`、`22:00` 再刷新一次：

```text
09:30, 10:30, 11:30, 12:30, 13:30, 14:30, 15:00, 22:00
```

自动刷新日志写入 `data/auto_refresh.log`。如果系统未启动 cron 服务，或 cron 环境无法找到 `conda`，需要先修复系统环境；手动刷新不受影响。

桌面终端看板：

```bash
python scripts/portfolio_cli.py dashboard
```

`dashboard` 会先执行一次静默 `refresh`，再展示账户总持有金额、当日预估或昨日收益、盈利和亏损基金数量。盘中有估算数据时按估算涨跌幅分组排序；没有估算数据时按昨日涨跌幅分组排序。

手机紧凑看板：

```bash
python scripts/portfolio_cli.py dashboard-mobile
python scripts/portfolio_cli.py dashboard-mobile --width 42
```

`dashboard-mobile` 用更窄的列和 emoji 分组，适合复制到手机、IM 或移动终端查看。

## 批量导入持仓

把支付宝等平台导出的持仓整理成 Markdown 表格，放到 `data/holding.md`，然后执行：

```bash
python scripts/import_holdings_md.py
```

导入时会按基金名称自动解析代码和净值。如果已有同代码持仓，会保留原来的 `first_buy_date` 和手动设置的 `sector_tags`。

## 加仓、减仓和结算

加仓会先进入待结算队列，因为今天的操作需要下一交易日确认净值：

```bash
python scripts/portfolio_cli.py buy 013841 --amount 500 --date 2026-05-07
```

按份额减仓：

```bash
python scripts/portfolio_cli.py sell 013841 --share 100 --date 2026-05-07
```

按比例减仓：

```bash
python scripts/portfolio_cli.py sell 013841 --fraction 1/4 --date 2026-05-07
```

查看待结算交易：

```bash
python scripts/portfolio_cli.py pending
```

按确认净值结算交易：

```bash
python scripts/portfolio_cli.py settle <trade_id> --nav 2.1581 --date 2026-05-08
```

买入结算会增加份额并重算加权成本价；卖出结算只减少份额，单位成本价保持不变，清仓后成本价归零。

## 自选基金

添加自选：

```bash
python scripts/portfolio_cli.py watch 013841 --name 银华集成电路混合C --note 半导体观察
```

移除自选：

```bash
python scripts/portfolio_cli.py unwatch 013841
```

## 测试

从仓库根目录执行完整测试：

```bash
cd /home/zhengmomomo/nanopoc/fundventrue
conda run -n fund python -m unittest discover -s fund_radar/test
```

当前测试覆盖基金估算查询、持仓计算、CLI 修改、批量导入、刷新和 dashboard 输出。

## 建议使用流程

日常盘中使用：

```bash
python scripts/portfolio_cli.py refresh
python scripts/portfolio_cli.py dashboard-mobile
```

低频自动刷新：

```bash
python scripts/portfolio_cli.py auto-refresh on
python scripts/portfolio_cli.py auto-refresh status
```

新增持仓后校准：

```bash
python scripts/portfolio_cli.py add 013841 --amount 957.09 --profit 161.63
python scripts/portfolio_cli.py set 013841 --share 435.94 --cost-nav 1.7873 --first-buy-date 2026-05-06
python scripts/portfolio_cli.py show 013841
```

板块观察：

```bash
python scripts/portfolio_cli.py set 002112 --sector CPO
python scripts/portfolio_cli.py dashboard
```

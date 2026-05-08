from fractions import Fraction
from uuid import uuid4

from .models import FundPosition, FundSnapshot, TradeRecord, WatchFund, now_iso


class PortfolioService:
    """持仓业务服务，负责增删改查、收益计算和交易结算。"""

    def __init__(self, store):
        self.store = store

    def _load(self):
        return self.store.load()

    def _save(self, data):
        self.store.save(data)

    def list_positions(self):
        data = self._load()
        return [FundPosition.from_dict(item) for item in data["positions"].values()]

    def resolve_position_code(self, identifier):
        """把基金代码、完整名称、名称前缀或名称片段解析为持仓代码。"""
        identifier = str(identifier).strip()
        data = self._load()
        if identifier in data["positions"]:
            return identifier

        positions = [FundPosition.from_dict(item) for item in data["positions"].values()]
        exact_matches = [item for item in positions if item.name == identifier]
        if exact_matches:
            return self._single_match_code(identifier, exact_matches)

        prefix_matches = [item for item in positions if item.name.startswith(identifier)]
        if prefix_matches:
            return self._single_match_code(identifier, prefix_matches)

        contains_matches = [item for item in positions if identifier in item.name]
        if contains_matches:
            return self._single_match_code(identifier, contains_matches)

        raise KeyError(f"未找到持仓基金：{identifier}")

    def resolve_position_name(self, identifier):
        """把基金代码或模糊名称解析为持仓中的规范基金名称。"""
        code = self.resolve_position_code(identifier)
        return self.get_position(code).name

    def _single_match_code(self, identifier, matches):
        if len(matches) == 1:
            return matches[0].code
        candidates = "；".join(f"{item.code} {item.name}" for item in matches)
        raise ValueError(f"匹配到多个持仓：{identifier}。候选：{candidates}")

    def get_position(self, code):
        data = self._load()
        raw = data["positions"].get(code)
        if not raw:
            raise KeyError(f"未找到持仓基金：{code}")
        return FundPosition.from_dict(raw)

    def add_position_by_detail(
        self,
        code,
        name,
        share,
        cost_nav,
        latest_nav,
        nav_date,
        yesterday_change_percent=None,
        first_buy_date=None,
        estimated_nav=None,
        estimated_change_percent=None,
        estimated_time=None,
        sector_tags=None,
    ):
        position = FundPosition(
            code=code,
            name=name,
            share=float(share),
            cost_nav=float(cost_nav),
            latest_nav=float(latest_nav),
            nav_date=nav_date,
            first_buy_date=first_buy_date or nav_date,
            yesterday_change_percent=self._optional_float(yesterday_change_percent),
            estimated_nav=self._optional_float(estimated_nav),
            estimated_change_percent=self._optional_float(estimated_change_percent),
            estimated_time=estimated_time,
            sector_tags=list(sector_tags or []),
        ).recalculate()
        data = self._load()
        data["positions"][code] = position.to_dict()
        self._save(data)
        return position

    def add_position_by_amount(
        self,
        code,
        name,
        holding_amount,
        holding_profit,
        latest_nav,
        nav_date,
        yesterday_change_percent=None,
        first_buy_date=None,
        estimated_nav=None,
        estimated_change_percent=None,
        estimated_time=None,
        sector_tags=None,
    ):
        latest_nav = float(latest_nav)
        holding_amount = float(holding_amount)
        holding_profit = float(holding_profit)
        if latest_nav <= 0:
            raise ValueError("最新净值必须大于 0")

        # 原项目支持“持有金额 + 持有收益”录入；这里先反推份额和成本价。
        share = holding_amount / latest_nav
        principal = holding_amount - holding_profit
        cost_nav = principal / share if share else 0
        return self.add_position_by_detail(
            code=code,
            name=name,
            share=share,
            cost_nav=cost_nav,
            latest_nav=latest_nav,
            nav_date=nav_date,
            yesterday_change_percent=yesterday_change_percent,
            first_buy_date=first_buy_date,
            estimated_nav=estimated_nav,
            estimated_change_percent=estimated_change_percent,
            estimated_time=estimated_time,
            sector_tags=sector_tags,
        )

    def edit_position(self, code, **changes):
        return self.set_position_detail(code, **changes)

    def set_position_detail(self, code, **changes):
        position = self.get_position(code)
        editable_fields = [
            "name",
            "share",
            "cost_nav",
            "latest_nav",
            "nav_date",
            "yesterday_change_percent",
            "first_buy_date",
            "estimated_nav",
            "estimated_change_percent",
            "estimated_time",
            "sector_tags",
        ]
        for field in editable_fields:
            if field in changes and changes[field] is not None:
                value = changes[field]
                if field in {"share", "cost_nav", "latest_nav", "yesterday_change_percent", "estimated_nav", "estimated_change_percent"}:
                    value = float(value)
                if field == "sector_tags":
                    value = list(value)
                setattr(position, field, value)
        position.recalculate()

        data = self._load()
        data["positions"][code] = position.to_dict()
        self._save(data)
        return position

    def delete_position(self, code):
        data = self._load()
        existed = code in data["positions"]
        data["positions"].pop(code, None)
        data["pending_trades"] = [trade for trade in data["pending_trades"] if trade.get("code") != code]
        self._save(data)
        return existed

    def add_watch(self, code, name, note=""):
        data = self._load()
        watch = WatchFund(code=code, name=name, note=note, created_at=now_iso())
        data["watchlist"][code] = watch.to_dict()
        self._save(data)
        return watch

    def remove_watch(self, code):
        data = self._load()
        existed = code in data["watchlist"]
        data["watchlist"].pop(code, None)
        self._save(data)
        return existed

    def list_watchlist(self):
        data = self._load()
        return [WatchFund.from_dict(item) for item in data["watchlist"].values()]

    def update_position_market(self, code, snapshot: FundSnapshot):
        position = self.get_position(code)
        position.name = snapshot.name or position.name
        position.latest_nav = float(snapshot.latest_nav)
        position.nav_date = snapshot.nav_date
        position.yesterday_change_percent = snapshot.yesterday_change_percent
        position.estimated_nav = snapshot.estimated_nav
        position.estimated_change_percent = snapshot.estimated_change_percent
        position.estimated_time = snapshot.estimated_time
        if snapshot.sector_tags:
            position.sector_tags = snapshot.sector_tags
        position.recalculate()

        data = self._load()
        data["positions"][code] = position.to_dict()
        self._save(data)
        return position

    def buy(self, code, amount, trade_date):
        position = self.get_position(code)
        trade = TradeRecord(
            id=str(uuid4()),
            code=code,
            name=position.name,
            type="buy",
            share=None,
            amount=float(amount),
            fraction=None,
            trade_date=trade_date,
            status="pending",
            created_at=now_iso(),
        )
        self._append_pending(trade)
        return trade

    def sell(self, code, trade_date, share=None, fraction=None):
        position = self.get_position(code)
        if fraction:
            sell_share = position.share * self._parse_fraction(fraction)
        elif share is not None:
            sell_share = float(share)
        else:
            raise ValueError("减仓必须提供份额或比例")
        if sell_share <= 0:
            raise ValueError("卖出份额必须大于 0")
        if sell_share > position.share:
            raise ValueError("卖出份额不能超过当前持有份额")

        trade = TradeRecord(
            id=str(uuid4()),
            code=code,
            name=position.name,
            type="sell",
            share=sell_share,
            amount=None,
            fraction=fraction,
            trade_date=trade_date,
            status="pending",
            created_at=now_iso(),
        )
        self._append_pending(trade)
        return trade

    def list_pending_trades(self):
        data = self._load()
        return [TradeRecord.from_dict(item) for item in data["pending_trades"]]

    def settle_trade(self, trade_id, settle_nav, settle_date):
        data = self._load()
        pending = [TradeRecord.from_dict(item) for item in data["pending_trades"]]
        trade = next((item for item in pending if item.id == trade_id), None)
        if not trade:
            raise KeyError(f"未找到待结算交易：{trade_id}")

        position = FundPosition.from_dict(data["positions"][trade.code])
        settle_nav = float(settle_nav)
        if settle_nav <= 0:
            raise ValueError("结算净值必须大于 0")

        if trade.type == "buy":
            # 买入按确认净值折算份额，并用总投入金额重算加权平均成本。
            buy_share = trade.amount / settle_nav
            new_share = position.share + buy_share
            new_cost_nav = (position.cost_nav * position.share + trade.amount) / new_share
            position.share = new_share
            position.cost_nav = new_cost_nav
        elif trade.type == "sell":
            # 卖出只减少份额，单位成本保持不变；清仓后成本归零。
            position.share = max(0.0, position.share - trade.share)
            if position.share == 0:
                position.cost_nav = 0.0
            trade.amount = trade.share * settle_nav
        else:
            raise ValueError(f"未知交易类型：{trade.type}")

        position.latest_nav = settle_nav
        position.nav_date = settle_date
        position.recalculate()
        trade.status = "settled"
        trade.settle_nav = settle_nav
        trade.settle_date = settle_date
        trade.settled_at = now_iso()

        data["positions"][position.code] = position.to_dict()
        data["pending_trades"] = [item.to_dict() for item in pending if item.id != trade_id]
        data["trade_history"].append(trade.to_dict())
        self._save(data)
        return trade

    def _append_pending(self, trade):
        data = self._load()
        data["pending_trades"].append(trade.to_dict())
        self._save(data)

    def _parse_fraction(self, value):
        try:
            number = float(Fraction(str(value)))
        except Exception as exc:
            raise ValueError(f"无效比例：{value}") from exc
        if number <= 0 or number > 1:
            raise ValueError("比例必须大于 0 且不超过 1")
        return number

    def _optional_float(self, value):
        if value is None:
            return None
        return float(value)

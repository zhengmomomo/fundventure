from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class FundSnapshot:
    """单个基金行情快照。"""

    code: str
    name: str
    latest_nav: float
    nav_date: str
    previous_nav: Optional[float] = None
    yesterday_change_percent: Optional[float] = None
    estimated_nav: Optional[float] = None
    estimated_change_percent: Optional[float] = None
    estimated_time: Optional[str] = None
    sector_tags: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class FundPosition:
    """用户持有的一只基金。"""

    code: str
    name: str
    share: float
    cost_nav: float
    latest_nav: float
    nav_date: str
    first_buy_date: str = ""
    yesterday_change_percent: Optional[float] = None
    estimated_nav: Optional[float] = None
    estimated_change_percent: Optional[float] = None
    estimated_time: Optional[str] = None
    estimated_profit: Optional[float] = None
    sector_tags: list[str] = field(default_factory=list)
    holding_amount: float = 0.0
    holding_profit: float = 0.0
    holding_profit_rate: float = 0.0
    yesterday_profit: Optional[float] = None
    updated_at: str = ""

    def recalculate(self):
        """根据份额、成本价、最新净值重算所有派生字段。"""
        self.holding_amount = self.share * self.latest_nav
        self.holding_profit = (self.latest_nav - self.cost_nav) * self.share
        principal = self.cost_nav * self.share
        self.holding_profit_rate = (self.holding_profit / principal * 100) if principal else 0.0

        if self.yesterday_change_percent is None:
            self.yesterday_profit = None
        else:
            rate = self.yesterday_change_percent / 100
            self.yesterday_profit = self.holding_amount - self.holding_amount / (1 + rate)

        if self.estimated_change_percent is None:
            self.estimated_profit = None
        else:
            estimated_amount = self.share * (self.estimated_nav or self.latest_nav)
            rate = self.estimated_change_percent / 100
            self.estimated_profit = estimated_amount - estimated_amount / (1 + rate)

        self.updated_at = now_iso()
        return self

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        # 兼容旧 JSON：历史数据没有初次买入时间时，用净值日期兜底。
        normalized = dict(data)
        normalized.setdefault("first_buy_date", normalized.get("nav_date", ""))
        normalized.setdefault("estimated_nav", None)
        normalized.setdefault("estimated_change_percent", None)
        normalized.setdefault("estimated_time", None)
        normalized.setdefault("estimated_profit", None)
        normalized.setdefault("sector_tags", [])
        return cls(**normalized).recalculate()


@dataclass
class WatchFund:
    """自选基金，不要求有实际持仓。"""

    code: str
    name: str
    created_at: str
    note: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class TradeRecord:
    """基金加仓或减仓记录。"""

    id: str
    code: str
    name: str
    type: str
    share: Optional[float]
    amount: Optional[float]
    fraction: Optional[str]
    trade_date: str
    status: str
    created_at: str
    settle_nav: Optional[float] = None
    settle_date: Optional[str] = None
    settled_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

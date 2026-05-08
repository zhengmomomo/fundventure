import json
from pathlib import Path


DEFAULT_DATA = {
    "version": 1,
    "positions": {},
    "watchlist": {},
    "pending_trades": [],
    "trade_history": [],
}


class JsonPortfolioStore:
    """JSON 文件存储，后续可用 SQLite 实现同样的 load/save 接口。"""

    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return json.loads(json.dumps(DEFAULT_DATA))
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return self.normalize(data)

    def save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        normalized = self.normalize(data)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(normalized, handle, ensure_ascii=False, indent=2)

    def normalize(self, data):
        base = json.loads(json.dumps(DEFAULT_DATA))
        if isinstance(data, dict):
            base.update({key: data.get(key, base[key]) for key in base})
        if not isinstance(base["positions"], dict):
            base["positions"] = {}
        if not isinstance(base["watchlist"], dict):
            base["watchlist"] = {}
        if not isinstance(base["pending_trades"], list):
            base["pending_trades"] = []
        if not isinstance(base["trade_history"], list):
            base["trade_history"] = []
        return base

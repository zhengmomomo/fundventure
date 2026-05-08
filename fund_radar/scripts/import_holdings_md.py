#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fund_radar.core.fund_data import fetch_fund_snapshot
from fund_radar.core.portfolio import PortfolioService
from fund_radar.core.storage import JsonPortfolioStore


DEFAULT_DATA_PATH = ROOT / "fund_radar" / "data" / "portfolio.json"
DEFAULT_HOLDING_PATH = ROOT / "fund_radar" / "data" / "holding.md"


def parse_money(value):
    """解析金额文本，支持 +161.63、-90.35、1,234.56。"""
    cleaned = str(value).strip().replace(",", "").replace("¥", "")
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return float(cleaned)


def parse_holding_table(path):
    """解析 holding.md 的 Markdown 表格，返回持仓行。"""
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or cells[0] in {"基金名称", ""}:
            continue
        if re.fullmatch(r"-+", cells[0].replace(" ", "")):
            continue
        if len(cells) < 3:
            continue
        rows.append({
            "name": cells[0],
            "amount": parse_money(cells[1]),
            "profit": parse_money(cells[2]),
            "profit_rate_text": cells[3] if len(cells) > 3 else "",
        })
    return rows


def import_holdings(table_path, data_path):
    service = PortfolioService(JsonPortfolioStore(data_path))
    existing_by_code = {}
    try:
        existing_by_code = {position.code: position for position in service.list_positions()}
    except Exception:
        existing_by_code = {}

    imported = []
    failures = []
    for row in parse_holding_table(table_path):
        try:
            snapshot = fetch_fund_snapshot(row["name"])
            # 如果已有持仓，保留初次买入时间；新增时用净值日期兜底。
            first_buy_date = existing_by_code.get(snapshot.code).first_buy_date if snapshot.code in existing_by_code else snapshot.nav_date
            # 手动板块标签优先；没有手动标签时使用接口主题标签。
            sector_tags = existing_by_code.get(snapshot.code).sector_tags if snapshot.code in existing_by_code else snapshot.sector_tags
            position = service.add_position_by_amount(
                code=snapshot.code,
                name=snapshot.name or row["name"],
                holding_amount=row["amount"],
                holding_profit=row["profit"],
                latest_nav=snapshot.latest_nav,
                nav_date=snapshot.nav_date,
                yesterday_change_percent=snapshot.yesterday_change_percent,
                first_buy_date=first_buy_date,
                estimated_nav=snapshot.estimated_nav,
                estimated_change_percent=snapshot.estimated_change_percent,
                estimated_time=snapshot.estimated_time,
                sector_tags=sector_tags,
            )
            imported.append(position)
        except Exception as exc:
            failures.append((row["name"], str(exc)))
    return imported, failures


def main():
    parser = argparse.ArgumentParser(description="从 holding.md 批量导入基金持仓")
    parser.add_argument("--input", default=str(DEFAULT_HOLDING_PATH), help="Markdown 持仓表路径")
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH), help="portfolio.json 路径")
    args = parser.parse_args()

    imported, failures = import_holdings(Path(args.input), Path(args.data))
    for position in imported:
        print(f"已导入：{position.code} {position.name} 持有金额=¥{position.holding_amount:.2f} 持有收益=¥{position.holding_profit:.2f}")
    if failures:
        print("\n导入失败：", file=sys.stderr)
        for name, error in failures:
            print(f"- {name}: {error}", file=sys.stderr)
        return 1
    print(f"\n共导入 {len(imported)} 只基金")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

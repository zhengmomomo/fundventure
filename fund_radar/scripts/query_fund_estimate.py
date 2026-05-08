#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fund_radar.core.fund_data import fetch_estimate, resolve_fund_code


def query_one(keyword):
    code = resolve_fund_code(keyword)
    data = fetch_estimate(code)
    change = data.get("gszzl", "-")
    if change != "-":
        change = f"{change}%"
    return {
        "input": keyword,
        "code": data.get("fundcode", code),
        "name": data.get("name", "-"),
        "nav_date": data.get("jzrq", "-"),
        "estimate": data.get("gsz", "-"),
        "estimate_time": data.get("gztime", "-"),
        "change": change,
    }


def query_many(keywords):
    rows = []
    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue
        try:
            rows.append(query_one(keyword))
        except Exception as exc:
            rows.append({
                "input": keyword,
                "code": "-",
                "name": "-",
                "nav_date": "-",
                "estimate": "-",
                "estimate_time": "-",
                "change": "-",
                "error": str(exc),
            })
    return rows


def display_width(value):
    return sum(2 if ord(char) > 127 else 1 for char in str(value))


def pad(value, width):
    value = str(value)
    return value + " " * max(width - display_width(value), 0)


def format_rows(rows):
    columns = [
        ("input", "输入"),
        ("code", "代码"),
        ("name", "名称"),
        ("nav_date", "净值日期"),
        ("estimate", "估算净值"),
        ("estimate_time", "估值时间"),
        ("change", "预估涨跌幅"),
        ("error", "错误"),
    ]
    visible_columns = [
        column for column in columns
        if column[0] != "error" or any(row.get("error") for row in rows)
    ]
    widths = {
        key: max(display_width(title), *(display_width(row.get(key, "")) for row in rows))
        for key, title in visible_columns
    }
    lines = [
        "  ".join(pad(title, widths[key]) for key, title in visible_columns),
        "  ".join("-" * widths[key] for key, _ in visible_columns),
    ]
    for row in rows:
        lines.append("  ".join(pad(row.get(key, ""), widths[key]) for key, _ in visible_columns))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="查询一个或多个基金的当日预估涨跌幅")
    parser.add_argument("funds", nargs="+", help="基金代码或名称，例如 110022 易方达消费 161725")
    args = parser.parse_args()

    rows = query_many(args.funds)
    print(format_rows(rows))
    return 1 if any(row.get("error") for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fund_radar.core.models import FundSnapshot
from fund_radar.core.fund_data import fetch_fund_snapshot
from fund_radar.core.portfolio import PortfolioService
from fund_radar.core.storage import JsonPortfolioStore


DEFAULT_DATA_PATH = ROOT / "fund_radar" / "data" / "portfolio.json"
DEFAULT_LOG_PATH = ROOT / "fund_radar" / "data" / "auto_refresh.log"
AUTO_REFRESH_BEGIN = "# fund_radar auto-refresh begin"
AUTO_REFRESH_END = "# fund_radar auto-refresh end"
AUTO_REFRESH_SCHEDULE_TEXT = "09:30, 10:30, 11:30, 12:30, 13:30, 14:30, 15:00, 22:00"
RED = "\033[31m"
GREEN = "\033[32m"
RESET = "\033[0m"


def make_service(path):
    return PortfolioService(JsonPortfolioStore(path))


def resolve_position_code(service, identifier):
    """把命令行输入的代码或基金名称解析为真实持仓代码。"""
    return service.resolve_position_code(identifier)


def run_refresh(service, verbose=True):
    """刷新全部持仓行情。"""
    positions = service.list_positions()
    print(f"正在刷新持仓数据，共 {len(positions)} 只基金...")
    for position in positions:
        snapshot = fetch_fund_snapshot(position.code)
        updated = service.update_position_market(position.code, snapshot)
        if verbose:
            print(f"已刷新：{updated.code} {updated.name} 估算涨跌幅={updated.estimated_change_percent if updated.estimated_change_percent is not None else '-'}%")
    print("持仓数据刷新完成。")


def read_crontab():
    """读取当前用户 crontab；没有 crontab 时返回空字符串。"""
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout
    if result.returncode == 1:
        return ""
    raise RuntimeError(result.stderr.strip() or "读取 crontab 失败")


def write_crontab(content):
    """写入当前用户 crontab。"""
    result = subprocess.run(["crontab", "-"], input=content, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "写入 crontab 失败")


def remove_auto_refresh_block(crontab_text):
    """只移除本项目自动刷新块，保留用户其他定时任务。"""
    pattern = rf"{re.escape(AUTO_REFRESH_BEGIN)}.*?{re.escape(AUTO_REFRESH_END)}\n?"
    cleaned = re.sub(pattern, "", crontab_text, flags=re.S)
    return cleaned.strip() + ("\n" if cleaned.strip() else "")


def build_auto_refresh_block(data_path, log_path=DEFAULT_LOG_PATH):
    """生成自动刷新 crontab：交易时段每小时、15:00 和 22:00 再刷新。"""
    project_dir = ROOT / "fund_radar"
    conda_bin = shutil.which("conda") or "conda"
    command = (
        f"cd {shlex.quote(str(project_dir))} && "
        f"{shlex.quote(conda_bin)} run -n fund python scripts/portfolio_cli.py --data {shlex.quote(str(data_path))} refresh "
        f">> {shlex.quote(str(log_path))} 2>&1"
    )
    cron_command = f"bash -lc {shlex.quote(command)}"
    return "\n".join([
        AUTO_REFRESH_BEGIN,
        "# 工作日 09:30-14:30 每小时刷新一次；15:00 和 22:00 再刷新一次",
        f"30 9-14 * * 1-5 {cron_command}",
        f"0 15 * * 1-5 {cron_command}",
        f"0 22 * * 1-5 {cron_command}",
        AUTO_REFRESH_END,
        "",
    ])


def set_auto_refresh(enabled, data_path):
    crontab_text = read_crontab()
    cleaned = remove_auto_refresh_block(crontab_text)
    if enabled:
        cleaned += build_auto_refresh_block(data_path)
    write_crontab(cleaned)


def auto_refresh_enabled():
    return AUTO_REFRESH_BEGIN in read_crontab()


def print_auto_refresh_schedule():
    print("计划：工作日 09:30-14:30 每小时刷新一次，15:00 和 22:00 再刷新一次")
    print(f"时间：{AUTO_REFRESH_SCHEDULE_TEXT}")


def build_add_snapshot(args):
    """add 命令缺字段时自动查询；手动字段完整时避免不必要的联网。"""
    has_manual_market = re.fullmatch(r"\d{6}", args.fund) and args.name and args.nav is not None and args.date
    if has_manual_market:
        return FundSnapshot(
            code=args.fund,
            name=args.name,
            latest_nav=args.nav,
            nav_date=args.date,
            yesterday_change_percent=args.change_percent,
            sector_tags=[],
        )
    return fetch_fund_snapshot(args.fund)


def print_position(position):
    print(f"代码：{position.code}")
    print(f"名称：{position.name}")
    print(f"初次买入时间：{position.first_buy_date or '-'}")
    print(f"持有份额：{position.share:.4f}")
    print(f"持仓成本价：{position.cost_nav:.4f}")
    print(f"最新净值：{position.latest_nav:.4f}")
    print(f"净值日期：{position.nav_date}")
    print(f"关联板块：{','.join(position.sector_tags) if position.sector_tags else '-'}")
    print(f"昨日涨跌幅：{position.yesterday_change_percent if position.yesterday_change_percent is not None else '-'}%")
    print(f"估算涨跌幅：{position.estimated_change_percent if position.estimated_change_percent is not None else '-'}%")
    if position.estimated_profit is not None:
        print(f"当日估算收益：¥{position.estimated_profit:.2f}")
    else:
        print("当日估算收益：-")
    print(f"持有金额：¥{position.holding_amount:.2f}")
    print(f"持有收益：¥{position.holding_profit:.2f}")
    print(f"持有收益率：{position.holding_profit_rate:.2f}%")
    if position.yesterday_profit is not None:
        print(f"昨日收益：¥{position.yesterday_profit:.2f}")
    else:
        print("昨日收益：-")


def print_table(positions):
    """打印所有持仓，统一排版，对齐表头和数据"""
    headers = ["代码", "名称", "板块", "初次买入", "持有金额", "持有收益", "收益率", "昨日收益", "估算涨跌", "估算收益", "份额", "成本价", "最新净值"]
    rows = []
    for item in positions:
        rows.append([
            item.code,
            item.name,
            ",".join(item.sector_tags) if item.sector_tags else "-",
            item.first_buy_date or "-",
            f"¥{item.holding_amount:,.0f}",
            f"{item.holding_profit:+.2f}",
            f"{item.holding_profit_rate:+.2f}%",
            "-" if item.yesterday_profit is None else f"{item.yesterday_profit:+.2f}",
            "-" if item.estimated_change_percent is None else f"{item.estimated_change_percent:+.2f}%",
            "-" if item.estimated_profit is None else f"{item.estimated_profit:+.2f}",
            f"{item.share:.2f}",
            f"{item.cost_nav:.4f}",
            f"{item.latest_nav:.4f}",
        ])

    # 按显示宽度计算每列宽度
    widths = []
    for col_idx in range(len(headers)):
        max_width = 0
        for row in [headers] + rows:
            cell_width = display_width(str(row[col_idx]))
            if cell_width > max_width:
                max_width = cell_width
        widths.append(max_width + 1)  # 多留1个空格作为列间隔

    # 打印表头
    header_line = ""
    for idx, h in enumerate(headers):
        header_line += pad_display(h, widths[idx])
    print(header_line)

    # 打印分隔线
    separator_line = ""
    for idx, w in enumerate(widths):
        separator_line += "─" * (w - 1) + " "
    print(separator_line.rstrip())

    # 打印数据行
    for row in rows:
        row_line = ""
        for idx, cell in enumerate(row):
            row_line += pad_display(str(cell), widths[idx])
        print(row_line)


def color_money(value):
    if value is None:
        return "-"
    text = f"{value:+.2f}"
    if value > 0:
        return f"{RED}{text}{RESET}"
    if value < 0:
        return f"{GREEN}{text}{RESET}"
    return text


def color_percent(value):
    if value is None:
        return "-"
    text = f"{value:+.2f}%"
    if value > 0:
        return f"{RED}{text}{RESET}"
    if value < 0:
        return f"{GREEN}{text}{RESET}"
    return text


def today_profit(position):
    """盘中优先展示估算收益；没有估值时退回昨日收益。"""
    if position.estimated_profit is not None:
        return position.estimated_profit
    return position.yesterday_profit


def dashboard_metric_mode(positions):
    """有盘中估算时展示估算数据；否则展示昨日确认数据。"""
    if any(item.estimated_change_percent is not None for item in positions):
        return "estimate"
    return "yesterday"


def dashboard_change(position, mode):
    if mode == "estimate":
        return position.estimated_change_percent
    return position.yesterday_change_percent


def dashboard_profit(position, mode):
    if mode == "estimate":
        return position.estimated_profit
    return position.yesterday_profit


def strip_ansi(value):
    return re.sub(r"\033\[[0-9;]*m", "", value)


def pad_ansi(value, width):
    return value + " " * max(width - len(strip_ansi(value)), 0)


def format_change_emoji(value):
    """涨跌 emoji"""
    if value is None:
        return "➖"
    if value > 0:
        return "📈"
    if value < 0:
        return "📉"
    return "➖"


def format_change_sign(value):
    """涨跌符号（不含颜色）"""
    if value is None:
        return "--"
    return f"{value:+.2f}%"


def format_money(value):
    """金额格式化（不含颜色）"""
    if value is None:
        return "--"
    return f"{value:+.2f}"


def display_width(text):
    """计算字符串在终端的显示宽度（中文算2个字符）"""
    width = 0
    for char in text:
        if ord(char) > 127:  # 非ASCII字符（中文等）
            width += 2
        else:
            width += 1
    return width


def pad_display(text, target_width, align="left"):
    """按显示宽度填充文本"""
    current = display_width(text)
    if current >= target_width:
        return text
    padding = target_width - current
    if align == "left":
        return text + " " * padding
    elif align == "right":
        return " " * padding + text
    else:  # center
        left = padding // 2
        right = padding - left
        return " " * left + text + " " * right


def print_dashboard_mobile(positions, width=50):
    """手机友好的紧凑输出，适合 IM 等窄屏展示"""
    from datetime import datetime

    mode = dashboard_metric_mode(positions)
    profit_label = "当日预估" if mode == "estimate" else "昨日收益"
    change_header = "预估涨跌" if mode == "estimate" else "昨日涨跌"
    profit_header = "预估收益" if mode == "estimate" else "昨日收益"
    total_amount = sum(item.holding_amount for item in positions)
    total_today_profit = sum(dashboard_profit(item, mode) or 0 for item in positions)
    profit_count = sum(1 for item in positions if (dashboard_profit(item, mode) or 0) > 0)
    loss_count = sum(1 for item in positions if (dashboard_profit(item, mode) or 0) < 0)
    flat_count = len(positions) - profit_count - loss_count

    # 分隔线
    line = "─" * width

    # 标题栏
    title_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"{'📊 基金账户':<{width - len(title_time) - 1}}{title_time}")
    print(line)

    # 总览行
    today_sign = "+" if total_today_profit >= 0 else ""
    print(f"总持有 ¥{total_amount:,.0f}  {profit_label} {today_sign}¥{total_today_profit:,.2f}")
    print(f"📈 {profit_count}只  📉 {loss_count}只  ➖ {flat_count}只")
    print(line)
    print()

    # 分组
    up_positions = sorted(
        [item for item in positions if dashboard_change(item, mode) is not None and dashboard_change(item, mode) > 0],
        key=lambda item: dashboard_change(item, mode),
        reverse=True,
    )
    down_positions = sorted(
        [item for item in positions if dashboard_change(item, mode) is not None and dashboard_change(item, mode) < 0],
        key=lambda item: dashboard_change(item, mode),
    )
    flat_positions = sorted(
        [item for item in positions if dashboard_change(item, mode) is None or dashboard_change(item, mode) == 0],
        key=lambda item: item.name,
    )

    def print_group(title, icon, items):
        if not items:
            return
        print(f"{icon} {title}")
        # 表头：按显示宽度定义列宽（列之间留1空格间隔）
        header = (
            "  " +
            pad_display("名称", 16) + " " +
            pad_display("持有金额", 9, align="right") + " " +
            pad_display(change_header, 7, align="right") + " " +
            pad_display(profit_header, 9, align="right") + " " +
            pad_display("持有收益", 9, align="right")
        )
        print(header)
        for item in items:
            name = item.name[:8]  # 8个中文字符 = 16显示宽度
            amount = f"¥{item.holding_amount:,.0f}"
            change = format_change_sign(dashboard_change(item, mode))
            today = format_money(dashboard_profit(item, mode))
            total = format_money(item.holding_profit)
            row = (
                "  " +
                pad_display(name, 16) + " " +
                pad_display(amount, 9, align="right") + " " +
                pad_display(change, 7, align="right") + " " +
                pad_display(today, 9, align="right") + " " +
                pad_display(total, 9, align="right")
            )
            print(row)
        print()

    print_group("上涨基金", "📈", up_positions)
    print_group("下跌基金", "📉", down_positions)
    print_group("持平/无数据", "➖", flat_positions)


def format_change_colored(value):
    """带颜色的涨跌符号"""
    if value is None:
        return "--"
    text = f"{value:+.2f}%"
    if value > 0:
        return f"{RED}{text}{RESET}"
    if value < 0:
        return f"{GREEN}{text}{RESET}"
    return text


def format_money_colored(value):
    """带颜色的金额"""
    if value is None:
        return "--"
    text = f"{value:+.2f}"
    if value > 0:
        return f"{RED}{text}{RESET}"
    if value < 0:
        return f"{GREEN}{text}{RESET}"
    return text


def strip_ansi(value):
    return re.sub(r"\033\[[0-9;]*m", "", value)


def pad_ansi_color(text, target_width, align="left"):
    """按显示宽度填充文本（支持ANSI颜色）"""
    text_without_ansi = strip_ansi(text)
    current = display_width(text_without_ansi)
    if current >= target_width:
        return text
    padding = target_width - current
    if align == "left":
        return text + " " * padding
    elif align == "right":
        return " " * padding + text
    else:  # center
        left = padding // 2
        right = padding - left
        return " " * left + text + " " * right


def print_dashboard(positions):
    """终端彩色展示，使用类似 dashboard-mobile 的紧凑格式"""
    from datetime import datetime

    mode = dashboard_metric_mode(positions)
    profit_label = "当日预估" if mode == "estimate" else "昨日收益"
    change_header = "预估涨跌" if mode == "estimate" else "昨日涨跌"
    profit_header = "预估收益" if mode == "estimate" else "昨日收益"
    total_amount = sum(item.holding_amount for item in positions)
    total_today_profit = sum(dashboard_profit(item, mode) or 0 for item in positions)
    profit_count = sum(1 for item in positions if (dashboard_profit(item, mode) or 0) > 0)
    loss_count = sum(1 for item in positions if (dashboard_profit(item, mode) or 0) < 0)
    flat_count = len(positions) - profit_count - loss_count

    # 分隔线
    line = "─" * 60

    # 标题栏
    title_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"{'📊 基金账户':<{60 - len(title_time) - 1}}{title_time}")
    print(line)

    # 总览行
    print(f"总持有 ¥{total_amount:,.0f}  {profit_label} {format_money_colored(total_today_profit)}")
    print(f"📈 {profit_count}只  📉 {loss_count}只  ➖ {flat_count}只")
    print(line)
    print()

    # 分组
    up_positions = sorted(
        [item for item in positions if dashboard_change(item, mode) is not None and dashboard_change(item, mode) > 0],
        key=lambda item: dashboard_change(item, mode),
        reverse=True,
    )
    down_positions = sorted(
        [item for item in positions if dashboard_change(item, mode) is not None and dashboard_change(item, mode) < 0],
        key=lambda item: dashboard_change(item, mode),
    )
    flat_positions = sorted(
        [item for item in positions if dashboard_change(item, mode) is None or dashboard_change(item, mode) == 0],
        key=lambda item: item.name,
    )

    def print_group(title, icon, items):
        if not items:
            return
        print(f"{icon} {title}")
        # 表头
        header = (
            "  " +
            pad_display("名称", 16) + " " +
            pad_display("持有金额", 9, align="right") + " " +
            pad_display(change_header, 7, align="right") + " " +
            pad_display(profit_header, 9, align="right") + " " +
            pad_display("持有收益", 9, align="right")
        )
        print(header)
        for item in items:
            name = item.name[:8]
            amount = f"¥{item.holding_amount:,.0f}"
            change = format_change_colored(dashboard_change(item, mode))
            today = format_money_colored(dashboard_profit(item, mode))
            total = format_money_colored(item.holding_profit)
            row = (
                "  " +
                pad_ansi_color(name, 16) + " " +
                pad_ansi_color(amount, 9, align="right") + " " +
                pad_ansi_color(change, 7, align="right") + " " +
                pad_ansi_color(today, 9, align="right") + " " +
                pad_ansi_color(total, 9, align="right")
            )
            print(row)
        print()

    print_group("上涨基金", "📈", up_positions)
    print_group("下跌基金", "📉", down_positions)
    print_group("持平/无数据", "➖", flat_positions)


def print_dashboard_old(positions):
    total_amount = sum(item.holding_amount for item in positions)
    total_today_profit = sum(today_profit(item) or 0 for item in positions)
    profit_count = sum(1 for item in positions if (today_profit(item) or 0) > 0)
    loss_count = sum(1 for item in positions if (today_profit(item) or 0) < 0)

    print("账户总览")
    print(f"账户总持有金额：¥{total_amount:.2f}")
    print(f"当日预估涨跌金额：¥{color_money(total_today_profit)}")
    print(f"盈利基金数量：{profit_count}")
    print(f"亏损基金数量：{loss_count}")
    print("")

    headers = ["基金名称", "关联板块", "持有金额", "当日估算涨跌幅", "当日估算收益", "持有收益"]
    up_positions = sorted(
        [item for item in positions if item.estimated_change_percent is not None and item.estimated_change_percent > 0],
        key=lambda item: item.estimated_change_percent,
        reverse=True,
    )
    down_positions = sorted(
        [item for item in positions if item.estimated_change_percent is not None and item.estimated_change_percent < 0],
        key=lambda item: item.estimated_change_percent,
    )
    flat_positions = sorted(
        [item for item in positions if item.estimated_change_percent is None or item.estimated_change_percent == 0],
        key=lambda item: item.name,
    )

    def build_row(item):
        return [
            item.name,
            ",".join(item.sector_tags) if item.sector_tags else "-",
            f"{item.holding_amount:.2f}",
            color_percent(item.estimated_change_percent),
            color_money(today_profit(item)),
            color_money(item.holding_profit),
        ]

    grouped_rows = [
        ("上涨基金", [build_row(item) for item in up_positions]),
        ("下跌基金", [build_row(item) for item in down_positions]),
        ("持平或暂无估算数据", [build_row(item) for item in flat_positions]),
    ]
    all_rows = [row for _, rows in grouped_rows for row in rows]
    if not all_rows:
        print("持仓明细：暂无持仓")
        return

    print("持仓明细")
    widths = [max(len(strip_ansi(str(row[idx]))) for row in [headers] + all_rows) for idx in range(len(headers))]
    for title, rows in grouped_rows:
        if not rows:
            continue
        print("")
        print(title)
        print("  ".join(headers[idx].ljust(widths[idx]) for idx in range(len(headers))))
        print("  ".join("-" * width for width in widths))
        for row in rows:
            print("  ".join(pad_ansi(str(row[idx]), widths[idx]) for idx in range(len(headers))))


def main(argv=None):
    parser = argparse.ArgumentParser(description="基金持仓管理 CLI")
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH), help="JSON 数据文件路径")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="按持有金额和持有收益新增持仓")
    add.add_argument("fund", help="基金代码或名称")
    add.add_argument("--name", help="基金名称；不填则自动查询")
    add.add_argument("--amount", type=float, required=True, help="持有金额")
    add.add_argument("--profit", type=float, required=True, help="持有收益")
    add.add_argument("--nav", type=float, help="最新净值；不填则自动查询")
    add.add_argument("--date", help="净值日期；不填则自动查询")
    add.add_argument("--change-percent", "--yesterday-change-percent", dest="change_percent", type=float, default=None, help="昨日涨跌幅")
    add.add_argument("--first-buy-date", help="初次买入时间；不填则使用净值日期")

    detail = subparsers.add_parser("set-detail", help="按份额和成本价设置持仓")
    detail.add_argument("code")
    detail.add_argument("--name", required=True)
    detail.add_argument("--share", type=float, required=True)
    detail.add_argument("--cost-nav", type=float, required=True)
    detail.add_argument("--nav", type=float, required=True)
    detail.add_argument("--date", required=True)
    detail.add_argument("--change-percent", "--yesterday-change-percent", dest="change_percent", type=float, default=None)
    detail.add_argument("--first-buy-date", help="初次买入时间")

    def add_set_arguments(command):
        command.add_argument("code")
        command.add_argument("--name")
        command.add_argument("--share", type=float)
        command.add_argument("--cost-nav", type=float)
        command.add_argument("--nav", type=float)
        command.add_argument("--date")
        command.add_argument("--change-percent", "--yesterday-change-percent", dest="change_percent", type=float)
        command.add_argument("--first-buy-date", help="初次买入时间")
        command.add_argument("--sector", action="append", dest="sector_tags", help="关联板块/标签，可重复")
        command.add_argument("--estimated-nav", type=float, help="估算净值")
        command.add_argument("--estimated-change-percent", type=float, help="估算涨跌幅")
        command.add_argument("--estimated-time", help="估算时间")

    edit = subparsers.add_parser("edit", help="修改持仓详细字段；兼容旧命令，建议使用 set")
    add_set_arguments(edit)

    set_cmd = subparsers.add_parser("set", help="修改单个基金详细数据并自动重算派生字段")
    add_set_arguments(set_cmd)

    subparsers.add_parser("list", help="查看全部持仓")
    subparsers.add_parser("dashboard", help="富文本展示账户总览和当日估算明细")
    dashboard_mobile = subparsers.add_parser("dashboard-mobile", help="手机端紧凑展示（调试用，预览 IM 展示效果）")
    dashboard_mobile.add_argument("--width", type=int, default=50, help="模拟屏幕宽度")
    subparsers.add_parser("refresh", help="联网刷新全部持仓的最新净值和估算涨跌幅")
    auto_refresh = subparsers.add_parser("auto-refresh", help="管理系统定时自动刷新任务")
    auto_refresh.add_argument("action", choices=["on", "off", "status"], help="on 开启，off 关闭，status 查看状态")
    show = subparsers.add_parser("show", help="查看单个持仓")
    show.add_argument("code")

    delete = subparsers.add_parser("delete", help="删除持仓")
    delete.add_argument("code")

    update = subparsers.add_parser("update", help="手动更新基金行情")
    update.add_argument("code")
    update.add_argument("--name", required=True)
    update.add_argument("--nav", type=float, required=True)
    update.add_argument("--date", required=True)
    update.add_argument("--change-percent", "--yesterday-change-percent", dest="change_percent", type=float, default=None)

    buy = subparsers.add_parser("buy", help="创建加仓待结算交易")
    buy.add_argument("code")
    buy.add_argument("--amount", type=float, required=True)
    buy.add_argument("--date", required=True)

    sell = subparsers.add_parser("sell", help="创建减仓待结算交易")
    sell.add_argument("code")
    sell.add_argument("--share", type=float)
    sell.add_argument("--fraction", help="卖出比例，例如 1/2、1/3、1/4")
    sell.add_argument("--date", required=True)

    settle = subparsers.add_parser("settle", help="按确认净值结算一笔交易")
    settle.add_argument("trade_id")
    settle.add_argument("--nav", type=float, required=True)
    settle.add_argument("--date", required=True)

    watch = subparsers.add_parser("watch", help="添加自选基金")
    watch.add_argument("code")
    watch.add_argument("--name", required=True)
    watch.add_argument("--note", default="")

    unwatch = subparsers.add_parser("unwatch", help="移除自选基金")
    unwatch.add_argument("code")

    subparsers.add_parser("pending", help="查看待结算交易")

    args = parser.parse_args(argv)
    service = make_service(Path(args.data))

    try:
        if args.command == "add":
            snapshot = build_add_snapshot(args)
            name = args.name or snapshot.name
            latest_nav = args.nav if args.nav is not None else snapshot.latest_nav
            nav_date = args.date or snapshot.nav_date
            change_percent = args.change_percent
            if change_percent is None:
                change_percent = snapshot.yesterday_change_percent
            first_buy_date = args.first_buy_date or nav_date
            print_position(service.add_position_by_amount(
                snapshot.code,
                name,
                args.amount,
                args.profit,
                latest_nav,
                nav_date,
                change_percent,
                first_buy_date=first_buy_date,
                estimated_nav=snapshot.estimated_nav,
                estimated_change_percent=snapshot.estimated_change_percent,
                estimated_time=snapshot.estimated_time,
                sector_tags=snapshot.sector_tags,
            ))
        elif args.command == "set-detail":
            print_position(service.add_position_by_detail(args.code, args.name, args.share, args.cost_nav, args.nav, args.date, args.change_percent, first_buy_date=args.first_buy_date))
        elif args.command in {"edit", "set"}:
            code = resolve_position_code(service, args.code)
            print_position(service.set_position_detail(
                code,
                name=args.name,
                share=args.share,
                cost_nav=args.cost_nav,
                latest_nav=args.nav,
                nav_date=args.date,
                yesterday_change_percent=args.change_percent,
                first_buy_date=args.first_buy_date,
                sector_tags=args.sector_tags,
                estimated_nav=args.estimated_nav,
                estimated_change_percent=args.estimated_change_percent,
                estimated_time=args.estimated_time,
            ))
        elif args.command == "list":
            print_table(service.list_positions())
        elif args.command == "dashboard-mobile":
            print_dashboard_mobile(service.list_positions(), width=args.width)
        elif args.command == "dashboard":
            run_refresh(service, verbose=False)
            print_dashboard(service.list_positions())
        elif args.command == "refresh":
            run_refresh(service)
        elif args.command == "auto-refresh":
            if args.action == "on":
                set_auto_refresh(True, Path(args.data))
                print("自动刷新：已开启")
                print_auto_refresh_schedule()
            elif args.action == "off":
                set_auto_refresh(False, Path(args.data))
                print("自动刷新：已关闭")
            else:
                enabled = auto_refresh_enabled()
                print(f"自动刷新：{'已开启' if enabled else '未开启'}")
                if enabled:
                    print_auto_refresh_schedule()
        elif args.command == "show":
            print_position(service.get_position(resolve_position_code(service, args.code)))
        elif args.command == "delete":
            print("已删除" if service.delete_position(resolve_position_code(service, args.code)) else "未找到")
        elif args.command == "update":
            code = resolve_position_code(service, args.code)
            snapshot = FundSnapshot(code, args.name, args.nav, args.date, yesterday_change_percent=args.change_percent)
            print_position(service.update_position_market(code, snapshot))
        elif args.command == "buy":
            trade = service.buy(resolve_position_code(service, args.code), args.amount, args.date)
            print(f"已创建待结算加仓：{trade.id}")
        elif args.command == "sell":
            trade = service.sell(resolve_position_code(service, args.code), trade_date=args.date, share=args.share, fraction=args.fraction)
            print(f"已创建待结算减仓：{trade.id}，份额：{trade.share:.4f}")
        elif args.command == "settle":
            trade = service.settle_trade(args.trade_id, args.nav, args.date)
            print(f"已结算：{trade.id}")
        elif args.command == "watch":
            watch_fund = service.add_watch(args.code, args.name, args.note)
            print(f"已加入自选：{watch_fund.code} {watch_fund.name}")
        elif args.command == "unwatch":
            print("已移除自选" if service.remove_watch(args.code) else "未找到")
        elif args.command == "pending":
            for trade in service.list_pending_trades():
                print(f"{trade.id} {trade.type} {trade.code} {trade.trade_date} share={trade.share} amount={trade.amount}")
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

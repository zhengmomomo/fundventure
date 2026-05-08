import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from fund_radar.core.models import FundSnapshot
from fund_radar.core.storage import JsonPortfolioStore
from fund_radar.scripts import portfolio_cli


class PortfolioCliTest(unittest.TestCase):
    def test_add_only_requires_amount_and_profit_when_snapshot_can_be_fetched(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            snapshot = FundSnapshot(
                code="013841",
                name="银华集成电路混合A",
                latest_nav=0.9571,
                nav_date="2026-05-07",
                yesterday_change_percent=1.2,
            )

            with patch.object(portfolio_cli, "fetch_fund_snapshot", return_value=snapshot):
                exit_code = portfolio_cli.main([
                    "--data", data_path,
                    "add", "013841",
                    "--amount", "957.09",
                    "--profit", "161.63",
                ])

            self.assertEqual(exit_code, 0)

    def test_add_with_manual_market_fields_does_not_fetch_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            with patch.object(portfolio_cli, "fetch_fund_snapshot") as fetch_mock:
                exit_code = portfolio_cli.main([
                    "--data", data_path,
                    "add", "013841",
                    "--name", "银华集成电路混合C",
                    "--amount", "957.09",
                    "--profit", "161.63",
                    "--nav", "2.1581",
                    "--date", "2026-05-06",
                    "--first-buy-date", "2024-02-01",
                ])

            self.assertEqual(exit_code, 0)
            fetch_mock.assert_not_called()

    def test_set_cost_nav_updates_existing_position_and_keeps_first_buy_date(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            snapshot = FundSnapshot(
                code="013841",
                name="银华集成电路混合C",
                latest_nav=2.0,
                nav_date="2026-05-07",
            )
            with patch.object(portfolio_cli, "fetch_fund_snapshot", return_value=snapshot):
                portfolio_cli.main([
                    "--data", data_path,
                    "add", "013841",
                    "--amount", "200",
                    "--profit", "30",
                    "--first-buy-date", "2024-02-01",
                ])

            exit_code = portfolio_cli.main([
                "--data", data_path,
                "set", "013841",
                "--cost-nav", "1.8",
            ])

            data = JsonPortfolioStore(data_path).load()
            position = data["positions"]["013841"]
            self.assertEqual(exit_code, 0)
            self.assertEqual(position["first_buy_date"], "2024-02-01")
            self.assertAlmostEqual(position["holding_profit"], 20)

    def test_set_accepts_yesterday_change_percent_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            snapshot = FundSnapshot(
                code="013841",
                name="银华集成电路混合C",
                latest_nav=2.0,
                nav_date="2026-05-07",
            )
            with patch.object(portfolio_cli, "fetch_fund_snapshot", return_value=snapshot):
                portfolio_cli.main([
                    "--data", data_path,
                    "add", "013841",
                    "--amount", "200",
                    "--profit", "30",
                ])

            exit_code = portfolio_cli.main([
                "--data", data_path,
                "set", "013841",
                "--yesterday-change-percent", "1.97",
            ])

            data = JsonPortfolioStore(data_path).load()
            position = data["positions"]["013841"]
            self.assertEqual(exit_code, 0)
            self.assertAlmostEqual(position["yesterday_change_percent"], 1.97)

    def test_set_accepts_sector_tags(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            snapshot = FundSnapshot(
                code="002112",
                name="德邦鑫星价值灵活配置混合C",
                latest_nav=3.0,
                nav_date="2026-05-07",
            )
            with patch.object(portfolio_cli, "fetch_fund_snapshot", return_value=snapshot):
                portfolio_cli.main(["--data", data_path, "add", "002112", "--amount", "300", "--profit", "30"])

            exit_code = portfolio_cli.main(["--data", data_path, "set", "002112", "--sector", "CPO", "--sector", "AI算力"])

            data = JsonPortfolioStore(data_path).load()
            self.assertEqual(exit_code, 0)
            self.assertEqual(data["positions"]["002112"]["sector_tags"], ["CPO", "AI算力"])

    def test_single_position_commands_accept_fuzzy_fund_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            snapshot = FundSnapshot(
                code="002112",
                name="德邦鑫星价值灵活配置混合C",
                latest_nav=3.0,
                nav_date="2026-05-07",
            )
            with patch.object(portfolio_cli, "fetch_fund_snapshot", return_value=snapshot):
                portfolio_cli.main(["--data", data_path, "add", "002112", "--amount", "300", "--profit", "30"])

            set_exit = portfolio_cli.main(["--data", data_path, "set", "德邦鑫星价值灵活", "--sector", "CPO"])

            show_output = StringIO()
            with redirect_stdout(show_output):
                show_exit = portfolio_cli.main(["--data", data_path, "show", "鑫星价值"])
            buy_exit = portfolio_cli.main(["--data", data_path, "buy", "德邦鑫星", "--amount", "100", "--date", "2026-05-07"])
            sell_exit = portfolio_cli.main(["--data", data_path, "sell", "德邦鑫星", "--fraction", "1/4", "--date", "2026-05-07"])
            update_exit = portfolio_cli.main([
                "--data", data_path,
                "update", "德邦鑫星",
                "--name", "德邦鑫星价值灵活配置混合C",
                "--nav", "3.2",
                "--date", "2026-05-08",
            ])

            data = JsonPortfolioStore(data_path).load()
            self.assertEqual(set_exit, 0)
            self.assertEqual(show_exit, 0)
            self.assertEqual(buy_exit, 0)
            self.assertEqual(sell_exit, 0)
            self.assertEqual(update_exit, 0)
            self.assertIn("德邦鑫星价值灵活配置混合C", show_output.getvalue())
            self.assertEqual(data["positions"]["002112"]["sector_tags"], ["CPO"])
            self.assertAlmostEqual(data["positions"]["002112"]["latest_nav"], 3.2)
            self.assertEqual(len(data["pending_trades"]), 2)

            delete_exit = portfolio_cli.main(["--data", data_path, "delete", "德邦鑫星价值灵活"])
            data = JsonPortfolioStore(data_path).load()
            self.assertEqual(delete_exit, 0)
            self.assertNotIn("002112", data["positions"])

    def test_single_position_commands_report_ambiguous_fuzzy_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            snapshots = [
                FundSnapshot("002112", "德邦鑫星价值灵活配置混合C", 3.0, "2026-05-07"),
                FundSnapshot("022365", "永赢科技智选混合发起C", 2.0, "2026-05-07"),
            ]
            with patch.object(portfolio_cli, "fetch_fund_snapshot", side_effect=snapshots):
                portfolio_cli.main(["--data", data_path, "add", "002112", "--amount", "300", "--profit", "30"])
                portfolio_cli.main(["--data", data_path, "add", "022365", "--amount", "200", "--profit", "20"])

            error_output = StringIO()
            with redirect_stdout(StringIO()), patch("sys.stderr", error_output):
                exit_code = portfolio_cli.main(["--data", data_path, "show", "混合"])

            self.assertEqual(exit_code, 1)
            self.assertIn("匹配到多个持仓", error_output.getvalue())
            self.assertIn("002112", error_output.getvalue())
            self.assertIn("022365", error_output.getvalue())

    def test_dashboard_outputs_summary_and_colored_details(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            positive = FundSnapshot(
                code="002112",
                name="德邦鑫星价值灵活配置混合C",
                latest_nav=3.0,
                nav_date="2026-05-07",
                estimated_nav=3.06,
                estimated_change_percent=2.0,
            )
            stronger_positive = FundSnapshot(
                code="022365",
                name="永赢科技智选混合发起C",
                latest_nav=2.0,
                nav_date="2026-05-07",
                estimated_nav=2.06,
                estimated_change_percent=3.0,
            )
            negative = FundSnapshot(
                code="014674",
                name="富国中证港股通互联网ETF发起式联接C",
                latest_nav=1.0,
                nav_date="2026-05-07",
                estimated_nav=0.99,
                estimated_change_percent=-1.0,
            )
            stronger_negative = FundSnapshot(
                code="025217",
                name="永赢资源慧选混合发起C",
                latest_nav=1.0,
                nav_date="2026-05-07",
                estimated_nav=0.98,
                estimated_change_percent=-2.0,
            )
            with patch.object(portfolio_cli, "fetch_fund_snapshot", side_effect=[positive, stronger_positive, negative, stronger_negative]):
                portfolio_cli.main(["--data", data_path, "add", "002112", "--amount", "300", "--profit", "30"])
                portfolio_cli.main(["--data", data_path, "add", "022365", "--amount", "200", "--profit", "10"])
                portfolio_cli.main(["--data", data_path, "add", "014674", "--amount", "200", "--profit", "-20"])
                portfolio_cli.main(["--data", data_path, "add", "025217", "--amount", "100", "--profit", "-5"])
            portfolio_cli.main(["--data", data_path, "set", "002112", "--sector", "CPO"])

            output = StringIO()
            with patch.object(portfolio_cli, "fetch_fund_snapshot", side_effect=[positive, stronger_positive, negative, stronger_negative]), redirect_stdout(output):
                exit_code = portfolio_cli.main(["--data", data_path, "dashboard"])

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("基金账户", text)
            self.assertIn("总持有", text)
            self.assertIn("当日", text)
            self.assertIn("📈 2只", text)
            self.assertIn("📉 2只", text)
            self.assertIn("上涨基金", text)
            self.assertIn("下跌基金", text)
            self.assertIn("\033[31m", text)
            self.assertIn("\033[32m", text)
            self.assertLess(text.index("永赢科技智选混合"), text.index("德邦鑫星价值灵活"))
            self.assertLess(text.index("永赢资源慧选混合"), text.index("富国中证港股通互"))

    def test_dashboard_uses_yesterday_labels_when_no_estimate_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            positive = FundSnapshot(
                code="002112",
                name="德邦鑫星价值灵活配置混合C",
                latest_nav=3.0,
                nav_date="2026-05-07",
                yesterday_change_percent=2.0,
            )
            negative = FundSnapshot(
                code="014674",
                name="富国中证港股通互联网ETF发起式联接C",
                latest_nav=1.0,
                nav_date="2026-05-07",
                yesterday_change_percent=-1.0,
            )
            with patch.object(portfolio_cli, "fetch_fund_snapshot", side_effect=[positive, negative]):
                portfolio_cli.main(["--data", data_path, "add", "002112", "--amount", "300", "--profit", "30"])
                portfolio_cli.main(["--data", data_path, "add", "014674", "--amount", "200", "--profit", "-20"])

            output = StringIO()
            with patch.object(portfolio_cli, "fetch_fund_snapshot", side_effect=[positive, negative]), redirect_stdout(output):
                exit_code = portfolio_cli.main(["--data", data_path, "dashboard"])

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("昨日收益", text)
            self.assertIn("昨日涨跌", text)
            self.assertNotIn("预估涨跌", text)
            self.assertNotIn("预估收益", text)

    def test_dashboard_refreshes_positions_before_rendering(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            portfolio_cli.main([
                "--data", data_path,
                "add", "002112",
                "--name", "德邦鑫星价值灵活配置混合C",
                "--amount", "300",
                "--profit", "30",
                "--nav", "3.0",
                "--date", "2026-05-07",
            ])
            refreshed = FundSnapshot(
                code="002112",
                name="德邦鑫星价值灵活配置混合C",
                latest_nav=3.2,
                nav_date="2026-05-08",
                yesterday_change_percent=1.5,
            )

            output = StringIO()
            with patch.object(portfolio_cli, "fetch_fund_snapshot", return_value=refreshed) as fetch_mock, redirect_stdout(output):
                exit_code = portfolio_cli.main(["--data", data_path, "dashboard"])

            data = JsonPortfolioStore(data_path).load()
            self.assertEqual(exit_code, 0)
            fetch_mock.assert_called_once_with("002112")
            self.assertAlmostEqual(data["positions"]["002112"]["latest_nav"], 3.2)
            self.assertEqual(data["positions"]["002112"]["nav_date"], "2026-05-08")
            self.assertIn("正在刷新持仓数据", output.getvalue())
            self.assertNotIn("已刷新：", output.getvalue())

    def test_refresh_updates_estimated_change_for_existing_positions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            initial = FundSnapshot(
                code="013841",
                name="银华集成电路混合C",
                latest_nav=2.0,
                nav_date="2026-05-07",
            )
            refreshed = FundSnapshot(
                code="013841",
                name="银华集成电路混合C",
                latest_nav=2.1,
                nav_date="2026-05-08",
                estimated_nav=2.12,
                estimated_change_percent=1.5,
                estimated_time="2026-05-08 14:30",
            )
            with patch.object(portfolio_cli, "fetch_fund_snapshot", return_value=initial):
                portfolio_cli.main(["--data", data_path, "add", "013841", "--amount", "200", "--profit", "20"])

            with patch.object(portfolio_cli, "fetch_fund_snapshot", return_value=refreshed):
                exit_code = portfolio_cli.main(["--data", data_path, "refresh"])

            data = JsonPortfolioStore(data_path).load()
            position = data["positions"]["013841"]
            self.assertEqual(exit_code, 0)
            self.assertAlmostEqual(position["estimated_change_percent"], 1.5)

    def test_auto_refresh_on_installs_weekday_market_cron(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = str(Path(temp_dir) / "portfolio.json")
            calls = []

            def fake_run(cmd, **kwargs):
                calls.append((cmd, kwargs))
                if cmd == ["crontab", "-l"]:
                    return Mock(returncode=1, stdout="", stderr="")
                if cmd == ["crontab", "-"]:
                    return Mock(returncode=0, stdout="", stderr="")
                raise AssertionError(cmd)

            with patch.object(portfolio_cli.subprocess, "run", side_effect=fake_run), \
                    patch.object(portfolio_cli.shutil, "which", return_value="/opt/conda/bin/conda"):
                exit_code = portfolio_cli.main(["--data", data_path, "auto-refresh", "on"])

            written = calls[-1][1]["input"]
            self.assertEqual(exit_code, 0)
            self.assertIn("fund_radar auto-refresh begin", written)
            self.assertIn("30 9-14 * * 1-5", written)
            self.assertIn("0 15 * * 1-5", written)
            self.assertIn("0 22 * * 1-5", written)
            self.assertIn("/opt/conda/bin/conda run -n fund python scripts/portfolio_cli.py", written)
            self.assertIn(f"--data {data_path}", written)
            self.assertIn("refresh", written)

    def test_auto_refresh_off_removes_only_fund_radar_cron_block(self):
        existing = "\n".join([
            "1 1 * * * echo keep",
            "# fund_radar auto-refresh begin",
            "30 9-14 * * 1-5 old",
            "# fund_radar auto-refresh end",
            "2 2 * * * echo also_keep",
            "",
        ])
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if cmd == ["crontab", "-l"]:
                return Mock(returncode=0, stdout=existing, stderr="")
            if cmd == ["crontab", "-"]:
                return Mock(returncode=0, stdout="", stderr="")
            raise AssertionError(cmd)

        with patch.object(portfolio_cli.subprocess, "run", side_effect=fake_run):
            exit_code = portfolio_cli.main(["auto-refresh", "off"])

        written = calls[-1][1]["input"]
        self.assertEqual(exit_code, 0)
        self.assertIn("echo keep", written)
        self.assertIn("echo also_keep", written)
        self.assertNotIn("fund_radar auto-refresh begin", written)

    def test_auto_refresh_status_reports_enabled(self):
        existing = "\n".join([
            "# fund_radar auto-refresh begin",
            "30 9-14 * * 1-5 refresh",
            "# fund_radar auto-refresh end",
        ])

        with patch.object(portfolio_cli.subprocess, "run", return_value=Mock(returncode=0, stdout=existing, stderr="")):
            output = StringIO()
            with redirect_stdout(output):
                exit_code = portfolio_cli.main(["auto-refresh", "status"])

        self.assertEqual(exit_code, 0)
        self.assertIn("自动刷新：已开启", output.getvalue())
        self.assertIn("09:30", output.getvalue())
        self.assertIn("22:00", output.getvalue())


if __name__ == "__main__":
    unittest.main()

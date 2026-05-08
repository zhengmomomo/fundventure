import tempfile
import unittest
from pathlib import Path

from fund_radar.core.models import FundSnapshot
from fund_radar.core.portfolio import PortfolioService
from fund_radar.core.storage import JsonPortfolioStore


class PortfolioServiceTest(unittest.TestCase):
    def make_service(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        store = JsonPortfolioStore(Path(temp_dir.name) / "portfolio.json")
        return PortfolioService(store)

    def test_add_position_by_amount_and_profit_derives_share_and_cost(self):
        service = self.make_service()

        position = service.add_position_by_amount(
            code="110022",
            name="易方达消费行业股票",
            holding_amount=3100,
            holding_profit=100,
            latest_nav=3.1,
            nav_date="2026-05-07",
            yesterday_change_percent=1,
        )

        self.assertEqual(position.code, "110022")
        self.assertAlmostEqual(position.share, 1000)
        self.assertAlmostEqual(position.cost_nav, 3.0)
        self.assertAlmostEqual(position.holding_amount, 3100)
        self.assertAlmostEqual(position.holding_profit, 100)
        self.assertAlmostEqual(position.holding_profit_rate, 100 / 3000 * 100)
        self.assertAlmostEqual(position.yesterday_profit, 3100 - 3100 / 1.01)

    def test_edit_position_with_detail_data_recalculates_derived_fields(self):
        service = self.make_service()
        service.add_position_by_detail("110022", "易方达消费行业股票", 100, 3.0, 3.1, "2026-05-07")

        position = service.edit_position("110022", share=200, cost_nav=2.8, latest_nav=3.2)

        self.assertAlmostEqual(position.share, 200)
        self.assertAlmostEqual(position.cost_nav, 2.8)
        self.assertAlmostEqual(position.holding_amount, 640)
        self.assertAlmostEqual(position.holding_profit, 80)

    def test_set_position_cost_recalculates_derived_fields_and_keeps_first_buy_date(self):
        service = self.make_service()
        service.add_position_by_detail(
            "013841",
            "银华集成电路混合C",
            100,
            1.7,
            2.0,
            "2026-05-07",
            first_buy_date="2024-02-01",
        )

        position = service.set_position_detail("013841", cost_nav=1.8)

        self.assertEqual(position.first_buy_date, "2024-02-01")
        self.assertAlmostEqual(position.share, 100)
        self.assertAlmostEqual(position.latest_nav, 2.0)
        self.assertAlmostEqual(position.cost_nav, 1.8)
        self.assertAlmostEqual(position.holding_amount, 200)
        self.assertAlmostEqual(position.holding_profit, 20)
        self.assertAlmostEqual(position.holding_profit_rate, 20 / 180 * 100)

    def test_update_position_market_keeps_share_and_cost(self):
        service = self.make_service()
        service.add_position_by_detail("110022", "易方达消费行业股票", 100, 3.0, 3.1, "2026-05-07")

        position = service.update_position_market(
            "110022",
            FundSnapshot(
                code="110022",
                name="易方达消费行业股票",
                latest_nav=3.2,
                nav_date="2026-05-08",
                yesterday_change_percent=2,
            ),
        )

        self.assertAlmostEqual(position.share, 100)
        self.assertAlmostEqual(position.cost_nav, 3.0)
        self.assertAlmostEqual(position.holding_amount, 320)
        self.assertAlmostEqual(position.holding_profit, 20)

    def test_estimated_change_calculates_estimated_profit(self):
        service = self.make_service()
        service.add_position_by_detail("110022", "易方达消费行业股票", 100, 3.0, 3.1, "2026-05-07")

        position = service.update_position_market(
            "110022",
            FundSnapshot(
                code="110022",
                name="易方达消费行业股票",
                latest_nav=3.1,
                nav_date="2026-05-07",
                estimated_nav=3.2,
                estimated_change_percent=2,
                estimated_time="2026-05-07 14:30",
            ),
        )

        self.assertAlmostEqual(position.estimated_nav, 3.2)
        self.assertAlmostEqual(position.estimated_change_percent, 2)
        self.assertAlmostEqual(position.estimated_profit, 320 - 320 / 1.02)

    def test_set_position_sector_tags(self):
        service = self.make_service()
        service.add_position_by_detail("002112", "德邦鑫星价值灵活配置混合C", 100, 3.0, 3.1, "2026-05-07")

        position = service.set_position_detail("002112", sector_tags=["CPO", "AI算力"])

        self.assertEqual(position.sector_tags, ["CPO", "AI算力"])

    def test_resolve_position_identifier_accepts_code_full_name_prefix_and_keyword(self):
        service = self.make_service()
        service.add_position_by_detail("002112", "德邦鑫星价值灵活配置混合C", 100, 3.0, 3.1, "2026-05-07")

        self.assertEqual(service.resolve_position_code("002112"), "002112")
        self.assertEqual(service.resolve_position_code("德邦鑫星价值灵活配置混合C"), "002112")
        self.assertEqual(service.resolve_position_code("德邦鑫星价值灵活"), "002112")
        self.assertEqual(service.resolve_position_code("鑫星价值"), "002112")
        self.assertEqual(service.resolve_position_name("002112"), "德邦鑫星价值灵活配置混合C")
        self.assertEqual(service.resolve_position_name("德邦鑫星价值灵活"), "德邦鑫星价值灵活配置混合C")

    def test_resolve_position_identifier_rejects_ambiguous_name(self):
        service = self.make_service()
        service.add_position_by_detail("002112", "德邦鑫星价值灵活配置混合C", 100, 3.0, 3.1, "2026-05-07")
        service.add_position_by_detail("022365", "永赢科技智选混合发起C", 100, 2.0, 2.1, "2026-05-07")

        with self.assertRaisesRegex(ValueError, "匹配到多个持仓"):
            service.resolve_position_code("混合")

    def test_sell_fraction_creates_pending_trade_and_settle_updates_share(self):
        service = self.make_service()
        service.add_position_by_detail("110022", "易方达消费行业股票", 1200, 3.0, 3.1, "2026-05-07")

        trade = service.sell("110022", fraction="1/3", trade_date="2026-05-07")
        self.assertEqual(trade.status, "pending")
        self.assertAlmostEqual(trade.share, 400)

        settled = service.settle_trade(trade.id, settle_nav=3.2, settle_date="2026-05-08")
        position = service.get_position("110022")

        self.assertEqual(settled.status, "settled")
        self.assertAlmostEqual(position.share, 800)
        self.assertAlmostEqual(position.cost_nav, 3.0)

    def test_buy_creates_pending_trade_and_settle_updates_average_cost(self):
        service = self.make_service()
        service.add_position_by_detail("110022", "易方达消费行业股票", 1000, 3.0, 3.1, "2026-05-07")

        trade = service.buy("110022", amount=3200, trade_date="2026-05-07")
        service.settle_trade(trade.id, settle_nav=3.2, settle_date="2026-05-08")
        position = service.get_position("110022")

        self.assertAlmostEqual(position.share, 2000)
        self.assertAlmostEqual(position.cost_nav, 3.1)


if __name__ == "__main__":
    unittest.main()

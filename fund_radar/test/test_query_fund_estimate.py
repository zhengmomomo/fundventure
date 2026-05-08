import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import query_fund_estimate as q
from fund_radar.core import fund_data


class QueryFundEstimateTest(unittest.TestCase):
    def test_query_many_returns_success_and_error_rows(self):
        def fake_fetch_text(url):
            if "FundSearchAPI" in url:
                if "key=bad" in url:
                    return 'cb({"Datas":[]})'
                return 'cb({"Datas":[{"CATEGORY":700,"CODE":"009265","NAME":"易方达消费精选股票"}]})'
            if "110022.js" in url:
                return 'jsonpgz({"fundcode":"110022","name":"易方达消费行业股票","jzrq":"2026-05-06","dwjz":"3.0990","gsz":"3.1005","gztime":"2026-05-07 14:11","gszzl":"0.05"});'
            if "009265.js" in url:
                return 'jsonpgz({"fundcode":"009265","name":"易方达消费精选股票","jzrq":"2026-05-06","dwjz":"0.7965","gsz":"0.7997","gztime":"2026-05-07 14:12","gszzl":"0.40"});'
            raise AssertionError(url)

        with patch.object(fund_data, "fetch_text", side_effect=fake_fetch_text):
            rows = q.query_many(["110022", "易方达消费", "bad"])

        self.assertEqual(rows[0]["code"], "110022")
        self.assertEqual(rows[0]["change"], "0.05%")
        self.assertEqual(rows[1]["code"], "009265")
        self.assertEqual(rows[1]["change"], "0.40%")
        self.assertEqual(rows[2]["input"], "bad")
        self.assertIn("error", rows[2])

    def test_format_rows_outputs_a_table(self):
        output = q.format_rows([
            {
                "input": "110022",
                "code": "110022",
                "name": "易方达消费行业股票",
                "nav_date": "2026-05-06",
                "estimate": "3.1005",
                "estimate_time": "2026-05-07 14:11",
                "change": "0.05%",
            }
        ])

        self.assertIn("输入", output)
        self.assertIn("代码", output)
        self.assertIn("预估涨跌幅", output)
        self.assertIn("110022", output)
        self.assertIn("0.05%", output)

    def test_choose_best_fund_prefers_same_share_class_suffix(self):
        fund = fund_data.choose_best_fund("华泰柏瑞中证港股通红利ETF联接C", [
            {"CODE": "513530", "NAME": "港股通红利ETF华泰柏瑞", "FundBaseInfo": {}},
            {"CODE": "018387", "NAME": "华泰柏瑞港股通红利ETF联接基金A", "FundBaseInfo": {}},
            {"CODE": "018388", "NAME": "华泰柏瑞港股通红利ETF联接基金C", "FundBaseInfo": {}},
        ])

        self.assertEqual(fund["CODE"], "018388")

    def test_fetch_fund_snapshot_prefers_newer_tencent_confirmed_nav(self):
        def fake_fetch_text(url):
            if "fundgz.1234567.com.cn" in url:
                return 'jsonpgz({"fundcode":"013841","name":"银华集成电路混合C","jzrq":"2026-05-06","dwjz":"2.1581","gsz":"2.2131","gztime":"2026-05-07 15:00","gszzl":"2.55"});'
            if "qt.gtimg.cn" in url:
                return 'v_jj013841="013841~银华集成电路混合C~0.0000~0.0000~~2.2208~2.2208~2.9053~2026-05-07~";'
            raise AssertionError(url)

        with patch.object(fund_data, "fetch_text", side_effect=fake_fetch_text):
            snapshot = fund_data.fetch_fund_snapshot("013841")

        self.assertEqual(snapshot.latest_nav, 2.2208)
        self.assertEqual(snapshot.nav_date, "2026-05-07")
        self.assertEqual(snapshot.yesterday_change_percent, 2.9053)
        self.assertIsNone(snapshot.estimated_nav)
        self.assertIsNone(snapshot.estimated_change_percent)
        self.assertIsNone(snapshot.estimated_time)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from fund_radar.scripts.import_holdings_md import parse_holding_table


class ImportHoldingsMdTest(unittest.TestCase):
    def test_parse_holding_table_reads_name_amount_and_profit(self):
        content = """| 基金名称 | 持有金额(元) | 持有收益(元) | 持有收益率 |
| --- | --- | --- | --- |
| 银华集成电路混合C | 957.09 | +161.63 | +20.74% |
| 富国中证港股通互联网ETF联接C | 521.45 | -90.35 | -14.77% |
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "holding.md"
            path.write_text(content, encoding="utf-8")

            rows = parse_holding_table(path)

        self.assertEqual(rows[0]["name"], "银华集成电路混合C")
        self.assertEqual(rows[0]["amount"], 957.09)
        self.assertEqual(rows[0]["profit"], 161.63)
        self.assertEqual(rows[1]["profit"], -90.35)


if __name__ == "__main__":
    unittest.main()

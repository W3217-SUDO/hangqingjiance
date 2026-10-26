import unittest
from unittest.mock import Mock, patch

import httpx

from src.market_stream.translation import (
    TranslationUnavailable,
    translate_text_to_chinese,
    validate_numeric_facts,
)


class TranslationTests(unittest.TestCase):
    def tearDown(self):
        translate_text_to_chinese.cache_clear()

    def test_numeric_facts_accept_equivalent_chinese_magnitudes(self):
        validate_numeric_facts(
            "1.5 billion barrels and $301M, down 2%",
            "15亿桶和3.01亿美元，下跌2%",
        )

    def test_numeric_facts_reject_wrong_magnitudes(self):
        with self.assertRaises(TranslationUnavailable):
            validate_numeric_facts("1.5 billion barrels", "1.5亿桶")
        with self.assertRaises(TranslationUnavailable):
            validate_numeric_facts("$301M inflow", "301万美元流入")

    def test_small_period_count_can_be_written_in_chinese(self):
        validate_numeric_facts("2-week outflow streak", "连续两周资金流出")

    @patch("src.market_stream.translation.httpx.post")
    def test_local_translation_restores_facts(self, post):
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "比特币 ETF 迎来3.01亿美元回流，扭转两周的资金流出"}}]
        }
        post.return_value = response
        result = translate_text_to_chinese("Bitcoin ETFs return with $301M after 2 weeks of outflows")
        self.assertIn("3.01亿美元", result)
        self.assertNotIn("ZXQ", result)
        self.assertIn("127.0.0.1", post.call_args.args[0])
        self.assertIn("$301M", post.call_args.kwargs["json"]["messages"][1]["content"])

    @patch("src.market_stream.translation.httpx.post", side_effect=httpx.ConnectTimeout("offline"))
    def test_transport_error_is_not_silently_cached_as_translation(self, post):
        with self.assertRaises(TranslationUnavailable):
            translate_text_to_chinese("Oil prices rise")
        with self.assertRaises(TranslationUnavailable):
            translate_text_to_chinese("Oil prices rise")
        self.assertEqual(post.call_count, 2)

    def test_missing_numeric_fact_rejects_translation(self):
        with self.assertRaises(TranslationUnavailable):
            validate_numeric_facts("Oil prices rise 2%", "油价上涨")


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from src.market_stream.chinese_sources import parse_json_source
from src.market_stream.config import SOURCES
from src.market_stream.hedge import decorate, relevant, event_key
from src.market_stream.models import StreamItem
from src.market_stream.pipeline import NewsStreamService
from src.market_stream.storage import SQLiteStore


class HedgeTests(unittest.TestCase):
    def test_distinct_chinese_titles_survive_dedup(self):
        service = NewsStreamService
        a = service._normalized_title('美联储宣布降息')
        b = service._normalized_title('原油库存意外下降')
        self.assertNotEqual(a, b)
        self.assertFalse(service._titles_similar(a, {a}, b, {b}))
        self.assertTrue(service._titles_similar(a, {a}, a, {a}))

    def test_jin10_locked_rows_filtered_and_time_is_utc(self):
        source = next(s for s in SOURCES if s.parser == 'jin10')
        raw = 'var newest = ' + json.dumps([
            {'id':'1','time':'2026-10-20 20:00:00','data':{'content':'【快讯】美联储公布利率决议'},'important':1},
            {'id':'2','time':'2026-10-20 20:00:00','data':{'content':'会员内容','lock':True}},
            {'id':'3','time':'2026-10-20 20:00:00','data':{'content':'过滤频道'},'channel':[5]},
        ]) + ';'
        result = parse_json_source(source, raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].published_at.hour, 12)
        self.assertIn('source_important', result[0].matched_terms)
        self.assertEqual(set(decorate(result[0])['assets']), {'US30','US500','BTC','ETH'})

    def test_energy_and_crypto_associations(self):
        def make(title):
            return StreamItem('test','flash','global',title,'','https://example.org','https://example.org',datetime.now(timezone.utc))
        self.assertEqual(set(decorate(make('OPEC agrees oil production cut'))['assets']), {'XBR','XTI'})
        self.assertEqual(decorate(make('Bitcoin ETF inflows rise'))['assets'], ['BTC'])
        self.assertEqual(decorate(make('苹果投入1亿美元收购公司'))['assets'], ['US30','US500'])
        self.assertIn('BTC', decorate(make('US private payrolls rise'))['assets'])

    def test_storage_does_not_translate_during_ingestion(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SQLiteStore(str(Path(temp) / 'test.db'))
            store._translate_if_needed = lambda text: self.fail('Translation must not block ingestion')
            item = StreamItem('test','flash','global','Federal Reserve announces rates','','https://example.org/news','https://example.org',datetime.now(timezone.utc))
            store.insert_items([item])
            self.assertEqual(store.recent_items(1)[0].title, item.title)

    def test_brief_noise_and_event_grouping(self):
        item = StreamItem('BBC','world','global','Tennis star says Ukraine war led to separation','','https://example.org','https://example.org',datetime.now(timezone.utc))
        self.assertFalse(relevant(item))
        self.assertEqual(event_key({'id':'1','title_original':'ADP private payrolls rise'}), event_key({'id':'2','title_original':'美国ADP就业数据公布'}))


if __name__ == '__main__': unittest.main()

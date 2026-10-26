import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from src.market_stream.chinese_sources import parse_json_source
from src.market_stream.config import SOURCES, Source
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
        # Retained adapter regression; this source is deliberately not enabled.
        source = Source('金十快讯','flash','','https://www.jin10.com/',parser='jin10')
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
            store = SQLiteStore(str(Path(temp) / 'test.db'), source_names={'test'})
            store._translate_if_needed = lambda text: self.fail('Translation must not block ingestion')
            item = StreamItem('test','flash','global','Federal Reserve announces rates','','https://example.org/news','https://example.org',datetime.now(timezone.utc))
            store.insert_items([item])
            self.assertEqual(store.recent_items(1)[0].title, item.title)

    def test_brief_noise_and_event_grouping(self):
        item = StreamItem('BBC World','world','global','Tennis star says Ukraine war led to separation','','https://example.org','https://example.org',datetime.now(timezone.utc))
        self.assertFalse(relevant(item))
        self.assertEqual(event_key({'id':'1','title_original':'ADP private payrolls rise'}), event_key({'id':'2','title_original':'美国ADP就业数据公布'}))

    def test_overseas_source_policy_and_index_disclosure(self):
        names = {s.name for s in SOURCES}
        self.assertTrue({'WSJ Markets','Financial Times','CNBC World','Oilprice','MarketWatch Top Stories'} <= names)
        self.assertTrue(names.isdisjoint({'金十快讯','华尔街见闻','MKTNews'}))
        reuters = next(s for s in SOURCES if s.publisher_domain == 'reuters.com')
        self.assertEqual(reuters.via, 'google_news')
        self.assertIn('索引', reuters.name)

    def test_disabled_history_is_filtered_before_limit_and_in_search(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SQLiteStore(str(Path(temp) / 'test.db'), source_names={'CNBC World'})
            def item(name, hour):
                return StreamItem(name,'markets','global','Oil market news','','https://example.org/'+name,'https://example.org',datetime(2026,10,25,hour,tzinfo=timezone.utc))
            store.insert_items([item('CNBC World',10),item('金十快讯',11),item('华尔街见闻',12)])
            self.assertEqual([r.source_name for r in store.recent_items(limit=1)], ['CNBC World'])
            self.assertEqual([r.source_name for r in store.search_items('Oil',limit=1)], ['CNBC World'])
            with store._connect() as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM alerts').fetchone()[0],3)

    def test_index_entry_publisher_is_verified(self):
        import asyncio
        import httpx
        from src.market_stream.fetcher import fetch_source
        source = next(s for s in SOURCES if s.publisher_domain == 'reuters.com')
        xml = '''<rss version="2.0"><channel><title>Index</title>
          <item><title>Oil prices rise - Reuters</title><link>https://news.google.com/rss/articles/one</link><pubDate>Sun, 25 Oct 2026 12:00:00 GMT</pubDate><source url="https://www.reuters.com">Reuters</source></item>
          <item><title>Oil rises - another outlet</title><link>https://news.google.com/rss/articles/two</link><pubDate>Sun, 25 Oct 2026 13:00:00 GMT</pubDate><source url="https://not-reuters.example">Other</source></item>
        </channel></rss>'''
        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200,text=xml))) as client:
                return await fetch_source(client,source)
        result=asyncio.run(run())
        self.assertEqual(len(result),1)
        self.assertIn('Reuters',result[0].title)


if __name__ == '__main__': unittest.main()

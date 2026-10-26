import unittest
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.market_stream.hedge import create_router
from src.market_stream.models import StreamItem
from src.market_stream.pipeline import NewsStreamService


class FixtureService:
    _is_duplicate_signature = staticmethod(NewsStreamService._is_duplicate_signature)
    _normalized_title = staticmethod(NewsStreamService._normalized_title)
    _title_tokens = staticmethod(NewsStreamService._title_tokens)

    def __init__(self):
        now = datetime.now(timezone.utc)
        titles = ['Apple launches a new phone color','Nvidia raises revenue guidance after earnings beat',
                  'OPEC cuts oil production','ECB announces interest rate decision','Bitcoin ETF inflows rise']
        self.rows = [StreamItem('CNBC World','markets','global',title,'',f'https://example.org/{n}',
                               'https://www.cnbc.com/',now-timedelta(minutes=n)) for n,title in enumerate(titles)]

    def history_items(self, limit=50, start_at=None, **kwargs):
        return [r for r in self.rows if start_at is None or r.published_at>=start_at][:limit]

    def search_items(self, query, **kwargs):
        return [r for r in self.history_items(**kwargs) if query.lower() in r.title.lower()]

    def health_status(self):
        return {'status':'ok'}


class FilterApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(create_router(FixtureService()))
        self.client = TestClient(app)

    def test_default_is_strict_and_expanded_adds_only_scored_background(self):
        strict = self.client.get('/api/hedge/snapshot').json()
        expanded = self.client.get('/api/hedge/snapshot?mode=related').json()
        self.assertEqual(strict['filter']['mode'],'strict')
        self.assertEqual(len(strict['items']),3)
        self.assertEqual(len(expanded['items']),4)
        self.assertEqual(strict['filter']['weak_hidden'],2)
        self.assertTrue(all(all(i['asset_scores'][a]>=75 for a in i['assets']) for i in strict['items']))
        self.assertEqual(self.client.get('/api/hedge/snapshot?mode=anything').status_code,422)

    def test_low_score_for_selected_asset_is_not_rescued_by_other_assets(self):
        strict = self.client.get('/api/hedge/snapshot?asset=US30').json()
        expanded = self.client.get('/api/hedge/snapshot?asset=US30&mode=related').json()
        self.assertEqual(strict['items'],[])
        self.assertEqual(len(expanded['items']),2)
        self.assertTrue(all(i['assets']==['US30'] for i in expanded['items']))

    def test_brief_and_search_use_the_same_relevance_rules(self):
        brief=self.client.get('/api/hedge/brief?asset=BTC').json()
        rows=[i for g in brief['groups'] for i in g['items']]
        self.assertEqual(len(rows),1)
        self.assertIn('Bitcoin', rows[0]['title_original'])
        self.assertEqual(self.client.get('/api/hedge/snapshot?q=phone').json()['items'],[])

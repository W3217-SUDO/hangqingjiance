import unittest
from src.market_stream.relevance import analyze, select_assets


class RelevanceTests(unittest.TestCase):
    def test_material_headlines_map_to_specific_assets(self):
        cases = [
            ('US CPI inflation comes in above forecasts', {'US30','US500','BTC','ETH'}),
            ('Federal Reserve holds interest rates steady', {'US30','US500','BTC','ETH'}),
            ('US 10-year Treasury yields rise after payrolls', {'US30','US500','BTC','ETH'}),
            ('S&P 500 futures fall 1% ahead of inflation data', {'US500'}),
            ('Dow Jones futures jump 300 points', {'US30'}),
            ('Nvidia raises revenue guidance after earnings beat', {'US500'}),
            ('OPEC agrees oil production cuts', {'XBR','XTI'}),
            ('Oil inventories fall sharply as crude demand rises', {'XBR','XTI'}),
            ('Attack shuts oil terminal at Strait of Hormuz', {'XBR','XTI'}),
            ('Bitcoin ETF inflows rise to a record', {'BTC'}),
            ('Ethereum network outage halts validators', {'ETH'}),
            ('Coinbase halts withdrawals after hack', {'BTC','ETH'}),
            ('US imposes new tariffs on Chinese imports', {'US30','US500'}),
        ]
        for title, expected in cases:
            with self.subTest(title=title):
                result=analyze(title)
                self.assertEqual(set(select_assets(result)),expected)
                for asset in expected:
                    self.assertTrue(result['asset_evidence'][asset])
                    self.assertTrue(result['asset_reasons'][asset])

    def test_generic_country_publisher_and_feed_do_not_imply_impact(self):
        noise = [
            'Iran announces a national cultural festival',
            'Amazon rainforest gets a new conservation program',
            'Crypto startup launches an NFT game on Solana',
            'Apple introduces a new phone color',
            'US household budgeting tips amid inflation',
            'Why central banks matter to us during inflation',
            'A shadow falls over the annual film festival',
            'Dow Inc profits fall at chemical plants',
            'Hybrids sell better than electric cars this year',
            'Bitcoin ETF explained for retirement savers',
            'How to buy Bitcoin before the next rally',
            'Olive oil prices rise after poor harvest',
            'Galp raises full-year view after oil-price assumption increase',
            'Gold gains on softer oil prices; Fed decision in focus',
            'Trump announces Audi US factory in Georgia as tariffs hit',
        ]
        for source in ['CNBC World','CoinDesk Markets','EIA Today in Energy']:
            for title in noise:
                with self.subTest(title=title,source=source):
                    self.assertEqual(select_assets(analyze(title,source)),[])

    def test_background_and_opinion_are_excluded_by_default(self):
        for title in ['ECB announces interest rate decision','Bitcoin could surge after ETF approval','Analysts predict WTI oil prices will fall']:
            with self.subTest(title=title):
                result=analyze(title)
                self.assertEqual(select_assets(result,'strict'),[])
                self.assertTrue(select_assets(result,'related'))

    def test_asset_filter_requires_its_own_score(self):
        result=analyze('Nvidia raises revenue guidance after earnings beat')
        self.assertEqual(select_assets(result,'strict','US30'),[])
        self.assertEqual(select_assets(result,'strict','US500'),['US500'])
        self.assertEqual(select_assets(result,'related','US30'),['US30'])

    def test_fed_administrative_and_generic_war_stories_are_hidden(self):
        for title in ['Federal Reserve approves a banking application','Tennis star says Ukraine war hurt her marriage','Russia opens an art museum about war']:
            self.assertEqual(select_assets(analyze(title,'Federal Reserve Press Releases')),[])

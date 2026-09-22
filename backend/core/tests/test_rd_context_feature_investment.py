"""W-CE-03: the R&D context says what the server will not accept.

The R&D page offered "Invest next level" on every feature below its ceiling
and every click was refused (R10 retired feature-level R&D investment for
every row). The page now offers only what the server accepts, and reads
that from the context endpoint: feature-level investment is unavailable,
with the refusal sentence itself in the reader's language.
"""
from core.tests.test_committed_spend_one_calculator import CommittedSpendBase


class RDContextFeatureInvestmentTests(CommittedSpendBase):

    def context(self, language='en'):
        response = self.client.get(f'{self.base}/context/rd/',
                                   HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_feature_investment_is_declared_unavailable_with_the_reason(self):
        published = self.context()['feature_investment']
        self.assertFalse(published['available'])
        self.assertEqual(
            published['reason'],
            'Feature-level R&D investment is no longer available. Develop a '
            'new platform and move the product to it to improve the product.')

    def test_the_reason_is_in_chinese_for_a_chinese_reader(self):
        published = self.context('zh-CN')['feature_investment']
        self.assertFalse(published['available'])
        self.assertEqual(
            published['reason'],
            '功能级研发投入现已不可用。请开发新的平台，并将产品迁移到该平台以改进产品。')

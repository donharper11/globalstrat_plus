from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework import serializers
from rest_framework.test import APIRequestFactory

from core.serializers.decisions import (
    DecisionBudgetAllocationSerializer, DecisionMarketingSerializer,
    DecisionFinancingSerializer, DecisionProductCreateSerializer,
    validate_rd_investment_targets,
)
from core.serializers.decision_limits import non_negative_message
from core.services.rd_costs import describe_budget_problems
from core.utils.participant_messages import MESSAGES, participant_message


class ParticipantMessageTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _context(self, language):
        return {'request': self.factory.post('/', HTTP_ACCEPT_LANGUAGE=language)}

    def test_non_negative_message_uses_business_wording_in_english(self):
        self.assertEqual(
            non_negative_message('promotion_budget'),
            'promotion budget cannot be negative. Enter zero or a positive value.',
        )

    def test_non_negative_message_is_localised_for_a_zh_request(self):
        serializer = DecisionBudgetAllocationSerializer(
            data={'rd_budget': '-1', 'marketing_budget': '0',
                  'strategy_budget': '0'},
            context=self._context('zh-CN'),
        )
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors['rd_budget'][0]),
            '研发预算不能为负数。请输入零或正数。',
        )

    def test_product_market_error_contains_no_storage_field_name(self):
        serializer = DecisionProductCreateSerializer(
            context=self._context('en'),
        )
        with self.assertRaises(serializers.ValidationError) as raised:
            serializer.validate_target_market_ids([])
        self.assertEqual(
            str(raised.exception.detail[0]),
            'Choose at least one target market before creating the product.',
        )

    def test_price_error_is_localised_and_uses_business_wording(self):
        serializer = DecisionMarketingSerializer(
            context=self._context('zh-CN'),
        )
        with self.assertRaises(serializers.ValidationError) as raised:
            serializer.validate_retail_price(Decimal('0'))
        self.assertEqual(
            str(raised.exception.detail[0]),
            '单价必须大于零。请输入正数金额。',
        )

    def test_budget_refusal_is_localised_for_a_zh_participant(self):
        # W-CE3-02: the refusal compares committed spend with available funds
        # -- cash plus the financing decided this round -- and names the line
        # the team can still cut, in the reader's language.
        assessment = {
            'within_cash': False, 'within_rd_budget': True,
            'committed_total': '1000', 'cash_on_hand': '900',
            'available_funds': '900', 'financing_decided': '0',
            'debt_refused_in_distress': False,
            'largest_reducible_line': 'budget_marketing',
            'largest_reducible_amount': '600',
            'lines': {'platform_development': '0'},
        }
        self.assertEqual(describe_budget_problems(assessment, language='zh-CN'), [
            '承诺支出 $1,000.00 超过可用资金 $900.00——现金 $900.00 加上本回合已决定的融资 $0.00。'
            '需要削减 $100.00：目前可削减的最大承诺是营销预算，金额 $600.00。'
            '增加债务或股权融资也可达到同样效果。',
        ])

    def test_the_nothing_left_to_cut_refusal_is_localised(self):
        assessment = {
            'within_cash': False, 'within_rd_budget': True,
            'committed_total': '0', 'cash_on_hand': '-900',
            'available_funds': '-900', 'financing_decided': '0',
            'debt_refused_in_distress': False,
            'largest_reducible_line': None, 'largest_reducible_amount': '0',
            'lines': {'platform_development': '0'},
        }
        self.assertEqual(describe_budget_problems(assessment, language='zh-CN'), [
            '可用资金为 $-900.00——现金 $-900.00 加上本回合已决定的融资 $0.00——'
            '本回合仍承诺支出 $0.00。已承诺的支出无法再削减，'
            '请在财务页面至少增加 $900.00 的债务或股权融资后再锁定。',
        ])

    def test_financing_error_uses_business_wording_in_both_languages(self):
        english = DecisionFinancingSerializer(data={'new_debt': '-1'})
        chinese = DecisionFinancingSerializer(
            data={'new_debt': '-1'}, context=self._context('zh-CN'))

        self.assertFalse(english.is_valid())
        self.assertFalse(chinese.is_valid())
        self.assertEqual(
            str(english.errors['new_debt'][0]),
            'new borrowing cannot be negative. Enter zero or a positive value.',
        )
        self.assertEqual(
            str(chinese.errors['new_debt'][0]),
            '新增借款不能为负数。请输入零或正数。',
        )

    def test_shared_catalogue_has_an_english_and_chinese_entry_for_every_key(self):
        for key, translations in MESSAGES.items():
            with self.subTest(key=key):
                self.assertEqual(set(translations), {'en', 'zh-CN'})
                self.assertTrue(translations['en'])
                self.assertTrue(translations['zh-CN'])

    def test_duplicate_rd_error_is_localised_without_storage_identifiers(self):
        class _Object:
            def __init__(self, pk):
                self.pk = pk

        investments = [
            {'team_platform': _Object(1), 'feature': _Object(2)},
            {'team_platform': _Object(1), 'feature': _Object(2)},
        ]
        with self.assertRaises(serializers.ValidationError) as raised:
            validate_rd_investment_targets(investments, language='zh-CN')

        self.assertEqual(
            str(raised.exception.detail[0]),
            '本回合每项平台功能只能选择一次。',
        )
        self.assertNotIn('team_platform', str(raised.exception.detail))

    def test_catalogue_renders_submission_refusal_in_both_languages(self):
        self.assertEqual(
            participant_message('round_closed', language='en', round=3),
            'Round 3 is closed and no longer accepts decisions.',
        )
        self.assertEqual(
            participant_message('round_closed', language='zh-CN', round=3),
            '第 3 回合已关闭，不能再提交决策。',
        )

"""W-CE4-10: negative equity must not invert the debt ceiling.

The fourth walkthrough found a team with -$415,575.79 equity and $17M debt.
The lock refused the exact equity raise it prescribed because the repair made
the ratio finite at 3.40, while another $10M of debt passed because a negative
ratio skipped the old ``projected_equity > 0`` guard. These tests keep the
walkthrough figures and exercise the shared lock/engine/context rule.
"""
from decimal import Decimal as D

from core.services.debt_ceiling import assess as assess_debt_ceiling
from core.tests.test_lock_always_reachable import LockReachableBase


OPENING_EQUITY = D('-415575.79')
OPENING_DEBT = D('17000000')
REPAIR_RAISE = D('5421575.79')
REPAIR_CASH = D('-5221575.79')


class NegativeEquityDebtCeilingTests(LockReachableBase):

    def set_balance_sheet(self, *, cash=D('1000000'), distressed=False):
        self.team.cash_on_hand = cash
        self.team.total_equity = OPENING_EQUITY
        self.team.total_debt = OPENING_DEBT
        self.team.is_in_distress = distressed
        self.team.save(update_fields=[
            'cash_on_hand', 'total_equity', 'total_debt', 'is_in_distress'])

    def test_the_prescribed_equity_repair_can_lock(self):
        self.set_balance_sheet(cash=REPAIR_CASH)
        self.commit_something_standing()
        self.finance(new_equity=REPAIR_RAISE)

        # $17M / ($-415,575.79 + $5,421,575.79) = 3.40. The ceiling
        # must not reject an equity-only improvement of an inherited state.
        self.assertEqual(self.blockers(), [])
        response = self.client.post(f'{self.base}lock/', format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_negative_equity_cannot_make_more_borrowing_legal(self):
        self.set_balance_sheet()
        self.finance(new_debt=D('10000000'))

        blockers = self.blockers()

        self.assertTrue(any(
            'cannot support additional borrowing' in error
            for error in blockers), blockers)
        self.assertTrue(any('$10,000,000.00' in error for error in blockers))

    def test_the_shared_assessment_marks_the_same_unsupported_debt(self):
        self.set_balance_sheet()
        self.finance(new_debt=D('10000000'))

        assessment = assess_debt_ceiling(
            self.team, self.submission.financing)

        self.assertTrue(assessment['blocks_new_debt'])
        self.assertTrue(assessment['nonpositive_equity'])
        self.assertEqual(assessment['requested_new_debt'], D('10000000'))
        self.assertIsNone(assessment['projected_ratio'])

    def test_repayment_and_equity_improvements_do_not_trigger_the_ceiling(self):
        self.set_balance_sheet()
        self.finance(debt_repayment=D('1000000'), new_equity=D('100000'))

        assessment = assess_debt_ceiling(
            self.team, self.submission.financing)

        self.assertFalse(assessment['blocks_new_debt'])
        self.assertEqual(assessment['projected_debt'], D('16000000'))

    def test_the_refusal_is_actionable_in_chinese(self):
        self.set_balance_sheet()
        self.finance(new_debt=D('10000000'))

        blockers = self.blockers(language='zh-CN')

        self.assertTrue(any('无法支持额外借款' in error for error in blockers),
                        blockers)
        self.assertTrue(any('增加股权或偿还债务' in error
                            for error in blockers), blockers)

    def test_finance_context_marks_current_ratio_unavailable_and_shows_repair(self):
        self.set_balance_sheet(cash=REPAIR_CASH)
        self.finance(new_equity=REPAIR_RAISE)

        response = self.client.get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/context/finance/')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['key_ratios']['debt_to_equity'])
        self.assertEqual(
            response.data['key_ratios']['debt_to_equity_status'],
            'nonpositive_equity')
        self.assertAlmostEqual(
            response.data['capital']['projected_debt_to_equity'], 3.395925,
            places=5)
        self.assertEqual(response.data['capital']['available_credit'], 0.0)
        self.assertFalse(response.data['capital']['blocks_new_debt'])

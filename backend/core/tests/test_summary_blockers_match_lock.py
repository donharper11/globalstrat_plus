"""W-CE-25: the Decision Summary lists every precondition the lock enforces.

The walkthrough's Chinese team saw a checklist with every requirement
complete, a summary saying `can_lock: true` with no blockers, and an enabled
button -- and the lock was then refused inside the confirmation dialog for a
projected debt-to-equity ratio of 2.35 above the 2.0 cap. Nothing on the
page had warned of it.

The lock validator (`DecisionLockView._full_validate`) and the summary view
each kept their own list of blockers. The summary's was a hand-picked
subset: the budget-versus-cash rule, projected cash (and only when a
financing row existed), the V2-024 funding rule and the three required
sections. The debt ceiling, the repayment cap, the dividend cap, the R&D and
marketing budget caps, the channel split, the price rule, the market-entry
rules and the mandatory communications were enforced at lock and shown
nowhere before it.

There is one list now: the summary publishes the validator's own result as
`lock_blockers`, in the reader's language, and `can_lock` is its emptiness.
The validator also gains the V2-024 funding check the summary already
carried -- the engine refuses to resolve a round with a raise above the
funding need, and the lock is the last point before the decisions are
frozen, so a lock that accepted it would have blocked every team's round.
"""
from decimal import Decimal as D

from core.models.decisions import DecisionFinancing
from core.tests.test_committed_spend_one_calculator import CommittedSpendBase

# `build_minimal_game`: no debt, $1,000,000 of equity, a 2.0 default cap.
DEBT_OVER_THE_CAP = D('2500000')          # 2.50 > 2.0
EQUITY_ABOVE_THE_NEED = D('900000')       # nothing to fund, so the maximum is $0


class SummaryBlockersMatchLockTests(CommittedSpendBase):

    def borrow(self, amount):
        DecisionFinancing.objects.filter(submission=self.submission).delete()
        DecisionFinancing.objects.create(
            submission=self.submission, new_debt=amount)

    def raise_equity(self, amount):
        DecisionFinancing.objects.filter(submission=self.submission).delete()
        DecisionFinancing.objects.create(
            submission=self.submission, new_equity=amount)

    def lock_errors(self, language='en'):
        response = self.client.post(f'{self.url()}lock/', format='json',
                                    HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(response.status_code, 400, response.data)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'draft')
        return list(response.data['errors'])

    def summary_blockers(self, language='en'):
        response = self.client.get(f'{self.url()}summary/',
                                   HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['can_lock'])
        return list(response.data['lock_blockers'])

    def test_the_debt_ceiling_is_a_blocker_on_the_summary(self):
        self.declare()
        self.borrow(DEBT_OVER_THE_CAP)

        blockers = self.summary_blockers()
        self.assertIn('The projected debt-to-equity ratio of 2.50 exceeds '
                      'the maximum of 2.0. Adjust financing.', blockers)

    def test_the_summary_lists_exactly_what_the_lock_refuses(self):
        """One list: the summary's blockers are the lock's errors."""
        self.declare()
        self.borrow(DEBT_OVER_THE_CAP)

        self.assertEqual(self.summary_blockers(), self.lock_errors())

    def test_in_chinese_too(self):
        self.declare()
        self.borrow(DEBT_OVER_THE_CAP)

        blockers = self.summary_blockers('zh-CN')
        self.assertIn('预计资产负债率 2.50 超过上限 2.0。请调整融资。', blockers)
        self.assertEqual(blockers, self.lock_errors('zh-CN'))

    def test_a_raise_above_the_funding_need_is_refused_at_lock(self):
        """V2-024 is enforced at the lock, not only at save and resolution."""
        self.declare()
        self.raise_equity(EQUITY_ABOVE_THE_NEED)

        errors = self.lock_errors()
        self.assertTrue(any('funding' in e.lower() or '融资' in e for e in errors),
                        errors)
        self.assertEqual(self.summary_blockers(), errors)

    def test_projected_cash_is_checked_without_a_financing_row(self):
        """The summary used to check projected cash only inside the
        financing branch; the lock always did.

        W-CE3-02 merged the two sentences that described this one condition.
        Projected ending cash is `available_funds - committed_total`, so it is
        negative exactly when committed spend exceeds available funds, and the
        lock states it once -- in the sentence that names what to change. What
        this test guards is unchanged: with no financing row at all, the
        Summary and the lock refuse the same submission with the same words.
        """
        self.team.cash_on_hand = D('900')
        self.team.save(update_fields=['cash_on_hand'])
        self.declare(rd=D('1000'))
        DecisionFinancing.objects.filter(submission=self.submission).delete()

        blockers = self.summary_blockers()
        self.assertTrue(any('exceeds available funds of $900.00' in b
                            for b in blockers), blockers)
        self.assertEqual(blockers, self.lock_errors())

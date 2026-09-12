"""Paid market research: what a team bought, and what it was charged.

Market research was always intended to cost money. The rails for it were built
and left wired to zero: `research_expense` is read by `engine/financials.py:96`
into `total_opex`, carried into operating income, cash and
`RoundResultFinancials.research_expense`, and `engine/costs.py:650` handed it a
hardcoded `D('0')` because nothing ever produced a figure. The reports
themselves have been free and unlimited since CC-19.

Why a new table rather than `DecisionResearchAllocation`
-------------------------------------------------------
`DecisionResearchAllocation` (`decisions.py:414`) is a per-market *allocation*:
`submission`, a non-null `market`, and `allocation_amount`. It is already a
manifest section keyed on `('submission_id', 'market_id')`. Nothing reads or
writes it.

A purchase is a different fact, and three of the six purchasable items are not
market-scoped at all -- `products`, `markets` and `stakeholders` are whole-game
reports, and an analyst query is a question, not a market. Reusing the
allocation table would mean making `market` nullable, which is a natural-key
column in a live manifest section: PostgreSQL treats NULLs as distinct, so the
"buy once per round" rule would stop being enforceable by the database for
exactly the reports that are not market-scoped. Widening a determinism natural
key to hold a value it cannot identify rows by is the more expensive change,
not the cheaper one.

So the allocation table is left exactly as it is, and a purchase gets its own
row. This keeps one path per fact rather than two half-wired ones.

`scope_key`
-----------
The discriminator that makes "bought once" a database rule rather than a
convention, and the reason it is a string rather than the `market` foreign key:

* a market-scoped report (`segments`, `channels`) stores the market's code;
* a whole-game report stores `''`;
* an analyst query stores its ordinal within the round, because a query has a
  real marginal cost every time it is asked and is quota-limited per round
  (`max_research_queries_per_round`) rather than bought once.

`market` is kept alongside it as a real foreign key so referential integrity
and the admin still work, but `scope_key` is what the unique constraint and the
manifest natural key are taken over. A nullable foreign key cannot do either
job.
"""
from django.db import models


class DecisionResearchPurchase(models.Model):
    """One report or analyst query a team bought, at the price it was charged.

    The price is frozen onto the row at purchase. Prices are authored per
    scenario and calibration will move them (R3); a later change to the
    authored figure must not retroactively restate what a team was charged in
    a round that has already resolved.
    """

    SEGMENTS = 'segments'
    PRODUCTS = 'products'
    MARKETS = 'markets'
    CHANNELS = 'channels'
    STAKEHOLDERS = 'stakeholders'
    ANALYST_QUERY = 'analyst_query'

    REPORT_TYPE_CHOICES = [
        (SEGMENTS, 'Segment report'),
        (PRODUCTS, 'Product report'),
        (MARKETS, 'Market report'),
        (CHANNELS, 'Channel report'),
        (STAKEHOLDERS, 'Stakeholder report'),
        (ANALYST_QUERY, 'Analyst query'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        'core.DecisionSubmission', on_delete=models.CASCADE,
        related_name='research_purchases',
    )
    report_type = models.CharField(max_length=32, choices=REPORT_TYPE_CHOICES)
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
        null=True, blank=True, related_name='research_purchases',
        help_text='Set only for a market-scoped report.',
    )
    scope_key = models.CharField(
        max_length=40, blank=True, default='',
        help_text="Market code, '' for a whole-game report, or the query "
                  'ordinal for an analyst query.',
    )
    price = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text='The authored price charged, frozen at purchase.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'decision_research_purchase'
        unique_together = [('submission', 'report_type', 'scope_key')]
        ordering = ['id']

    def __str__(self):
        where = f' ({self.scope_key})' if self.scope_key else ''
        return f'Research: {self.report_type}{where} — ${self.price}'

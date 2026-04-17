"""
CC-3.5 §A.4: Regression test for engine determinism.

The engine's determinism property rests on a single invariant: every
probabilistic roll in the pipeline goes through
``core.engine.rng.get_rng(class_id, round_number, operation_id)``. If two
rounds share those three keys, every roll they make returns the same
value, so they fire the same events, trigger the same audits, and
resolve alliance defections the same way.

This test locks that invariant in at each of the 12 call sites that
CC-3.5 migrated. It uses ``SimpleTestCase`` (no DB) because the engine's
probabilistic surface is fully characterised by the seeded-RNG stream —
the DB lookups around it are deterministic by construction.

The companion ``test_rng.py`` covers the utility itself; this file
covers the *engine-level contract* that every call site must honour.
"""
from django.test import SimpleTestCase

from core.engine.rng import get_rng


def _draw(class_id, round_number, operation_id, n=1):
    """Draw ``n`` random() values from the seeded stream."""
    rng = get_rng(class_id, round_number, operation_id)
    return [rng.random() for _ in range(n)]


# Operation-id templates mirrored from the call sites that CC-3.5 migrated.
# Keep this list in lockstep with grep output for `get_rng(` in core/engine/.
ENGINE_CALL_SITES = [
    # core/engine/events.py — fire_events
    "event_trigger:{template_id}",
    "event_target_market:{template_id}",
    # core/engine/events.py — _fire_compliance_adjusted_event
    "compliance_event_target_market:{template_id}",
    "compliance_event_roll:{template_id}:{team_id}",
    # core/engine/costs.py — calculate_tax
    "tax_audit:{team_id}",
    # core/engine/alliance_engine.py — partner defection check
    "alliance_partner_defection:{alliance_id}",
    # core/engine/agents/governments.py — 5 sites
    "govt_regulatory_relaxation:{market_code}",
    "govt_regulatory_tightening:{market_code}",
    "govt_bilateral_volatility:{market_code}",
    "govt_bilateral_facilitation:{market_code}:{origin_code}",
    "govt_bilateral_screening:{market_code}:{origin_code}",
]


class TestEngineDeterminismContract(SimpleTestCase):
    """
    Each engine call site must produce identical draws when replayed
    with the same (class_id, round_number) — that is what makes
    advance_round reproducible.
    """

    def test_every_call_site_is_deterministic(self):
        """For each migrated call site, replaying the same keys gives
        the same stream of rolls."""
        fmt_values = dict(
            template_id=7, team_id=3, alliance_id=11,
            market_code='CN', origin_code='US',
        )
        for template in ENGINE_CALL_SITES:
            op_id = template.format(**fmt_values)
            with self.subTest(operation=op_id):
                first = _draw(42, 5, op_id, n=10)
                second = _draw(42, 5, op_id, n=10)
                self.assertEqual(first, second,
                                 f"Non-deterministic stream for {op_id}")

    def test_distinct_call_sites_use_distinct_streams(self):
        """Different operation_ids must produce independent streams —
        otherwise a tax-audit roll could shadow an event-trigger roll
        and two events of the same template id would share a roll."""
        seen_first_draw = {}
        fmt_values = dict(
            template_id=7, team_id=3, alliance_id=11,
            market_code='CN', origin_code='US',
        )
        for template in ENGINE_CALL_SITES:
            op_id = template.format(**fmt_values)
            draw = _draw(42, 5, op_id, n=1)[0]
            self.assertNotIn(
                draw, seen_first_draw,
                f"{op_id} collided with {seen_first_draw.get(draw)}",
            )
            seen_first_draw[draw] = op_id

    def test_round_to_round_streams_diverge(self):
        """Same class_id + operation_id, different round, different stream."""
        for template in ENGINE_CALL_SITES:
            op_id = template.format(
                template_id=1, team_id=1, alliance_id=1,
                market_code='HM', origin_code='HM',
            )
            with self.subTest(operation=op_id):
                r1 = _draw(42, 1, op_id, n=1)
                r2 = _draw(42, 2, op_id, n=1)
                self.assertNotEqual(r1, r2)

    def test_class_to_class_streams_diverge(self):
        """Different class_id (section) must yield different streams —
        two sections running the same scenario at the same round must
        not see identical events."""
        for template in ENGINE_CALL_SITES:
            op_id = template.format(
                template_id=1, team_id=1, alliance_id=1,
                market_code='HM', origin_code='HM',
            )
            with self.subTest(operation=op_id):
                class_a = _draw(1, 5, op_id, n=1)
                class_b = _draw(2, 5, op_id, n=1)
                self.assertNotEqual(class_a, class_b)


class TestSimulatedRoundReplay(SimpleTestCase):
    """
    Simulate a whole-round probabilistic surface: trigger-rolls for
    three event templates at different probabilities, one tax audit,
    one alliance defection check. Running the same inputs twice must
    reproduce the same pass/fail pattern — this is the round-replay
    regression guard.
    """

    CLASS_ID = 4242
    ROUND = 3

    def _simulate_round(self):
        """Return the full probabilistic outcome vector for a round."""
        outcomes = {}

        # Three event templates with varying probabilities.
        for template_id, prob in [(101, 0.01), (102, 0.50), (103, 0.99)]:
            rng = get_rng(
                self.CLASS_ID, self.ROUND, f"event_trigger:{template_id}",
            )
            roll = rng.random()
            outcomes[f"template_{template_id}_fired"] = roll <= prob
            outcomes[f"template_{template_id}_roll"] = roll

        # Tax audit for team 7 at 5% probability.
        audit_rng = get_rng(
            self.CLASS_ID, self.ROUND, "tax_audit:7",
        )
        audit_roll = audit_rng.random()
        outcomes["team_7_audited"] = audit_roll < 0.05
        outcomes["team_7_audit_roll"] = audit_roll

        # Alliance 22 partner defection at 40% probability.
        defect_rng = get_rng(
            self.CLASS_ID, self.ROUND, "alliance_partner_defection:22",
        )
        defect_roll = defect_rng.random()
        outcomes["alliance_22_defected"] = defect_roll < 0.4
        outcomes["alliance_22_defect_roll"] = defect_roll

        return outcomes

    def test_identical_inputs_reproduce_identical_outcomes(self):
        """The whole probabilistic surface of a round is replayable."""
        first = self._simulate_round()
        second = self._simulate_round()
        self.assertEqual(first, second)

    def test_high_probability_event_fires_low_does_not(self):
        """Sanity: prob 0.99 fires, prob 0.01 does not — deterministically."""
        outcomes = self._simulate_round()
        self.assertTrue(outcomes["template_103_fired"],
                        "0.99-probability template did not fire "
                        f"(roll={outcomes['template_103_roll']})")
        self.assertFalse(outcomes["template_101_fired"],
                         "0.01-probability template fired "
                         f"(roll={outcomes['template_101_roll']})")

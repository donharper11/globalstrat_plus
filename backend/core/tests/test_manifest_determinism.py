"""GSP-CRV2-01: the manifest envelope, canonical bytes, and iteration order.

Four things are locked in here.

1. **Canonical serialisation is a property of the value, not of the machine.**
   Decimal exponent, float formatting, timezone, locale and mapping order must
   not reach the hashed bytes.
2. **The envelope is enumerated and cannot drift.** The section list, each
   section's natural key, and the classification of every single model field
   are compared against a checked-in inventory. A model that gains a field
   fails here instead of silently changing a hash.
3. **Iteration order is imposed, not inherited.** An AST sweep of the engine
   fails any `for` loop over a queryset that has no explicit ordering, with a
   short allowlist of loops whose result provably cannot depend on order.
4. **Row insertion order does not change a manifest.** The same logical state
   built forwards and backwards produces the same bytes.
"""
import ast
import datetime
import decimal
import json
import pathlib

from django.contrib.auth.models import User as DjangoUser
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.services import canonical_json as cj
from core.services import manifest_sections as ms
from core.services.manifest_version import MANIFEST_SCHEMA_VERSION
from core.services.manifest_schema import (
    SCHEMA_INVENTORY_PATH, build_schema_inventory,
)
from core.services.manifest_snapshot import (
    SnapshotError, _model, natural_key_attnames, section_field_plan,
)


# ---------------------------------------------------------------------------
# 1. Canonical serialisation
# ---------------------------------------------------------------------------

class CanonicalSerialisationTests(SimpleTestCase):
    def test_decimal_representation_is_collapsed(self):
        """Three spellings of one number must hash identically."""
        forms = ['1234.5600', '1234.56', '1.23456E+3']
        digests = {cj.canonical_sha256({'v': decimal.Decimal(f)}) for f in forms}
        self.assertEqual(len(digests), 1, f'Decimal spelling leaked: {forms}')

    def test_decimal_zero_and_negative_zero_collapse(self):
        for form in ['0', '0.00', '0E-8', '-0.000']:
            self.assertEqual(cj.normalize_decimal(decimal.Decimal(form)), '0')

    def test_decimal_exponent_is_expanded_not_kept(self):
        self.assertEqual(cj.normalize_decimal(decimal.Decimal('1.2E+3')), '1200')
        self.assertNotIn('E', cj.normalize_decimal(decimal.Decimal('1.2E+3')))

    def test_float_negative_zero_folds_and_bits_round_trip(self):
        self.assertEqual(cj.normalize_float(-0.0), '0.0')
        self.assertEqual(float(cj.normalize_float(0.1 + 0.2)), 0.1 + 0.2)

    def test_non_finite_values_are_tagged_not_emitted_as_json_literals(self):
        rendered = cj.canonical_dumps({'v': float('nan')})
        self.assertNotIn('NaN', rendered)
        self.assertIn(cj.NONFINITE_PREFIX, rendered)

    def test_aware_datetimes_normalise_to_utc(self):
        utc = datetime.datetime(2026, 8, 28, 12, 0, tzinfo=datetime.timezone.utc)
        offset = utc.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
        self.assertEqual(cj.canonical_dumps(utc), cj.canonical_dumps(offset))
        self.assertTrue(cj.normalize_datetime(utc).endswith('Z'))

    def test_naive_datetimes_are_tagged_so_they_cannot_pass_as_utc(self):
        naive = datetime.datetime(2026, 8, 28, 12, 0)
        self.assertTrue(cj.normalize_datetime(naive).endswith(
            cj.NAIVE_DATETIME_SUFFIX))

    def test_mapping_order_does_not_change_the_bytes(self):
        forward = {'a': 1, 'b': 2, 'c': 3}
        backward = {'c': 3, 'b': 2, 'a': 1}
        self.assertEqual(cj.canonical_dumps(forward), cj.canonical_dumps(backward))

    def test_sets_are_ordered_before_serialisation(self):
        self.assertEqual(cj.canonical_dumps({'a', 'b'}), cj.canonical_dumps({'b', 'a'}))

    def test_output_is_pure_ascii(self):
        rendered = cj.canonical_dumps({'name': 'Zürich 北京'})
        rendered.encode('ascii')  # raises if the encoder emitted raw UTF-8

    def test_unknown_types_are_refused_rather_than_stringified(self):
        class Opaque:
            pass
        with self.assertRaises(TypeError):
            cj.canonical_dumps({'v': Opaque()})


# ---------------------------------------------------------------------------
# 2. Envelope enumeration and schema drift
# ---------------------------------------------------------------------------

EXPECTED_CONFIG_SECTIONS = {
    'scenario', 'scenario_config', 'feature_definition', 'platform_generation',
    'market_definition', 'entry_mode', 'strategy_option',
    'strategy_option_effect', 'ai_competitor', 'ai_competitor_behavior',
    'ai_competitor_fit', 'platform_feature_ceiling', 'market_readiness',
    'segment_definition', 'segment_preference', 'event_template',
    'event_impact', 'event_response', 'firm_starter_profile',
    'firm_starter_platform_config', 'firm_starter_product', 'feature_level_cost',
    'market_condition_by_round', 'acquisition_target', 'cultural_distance',
    'origin_trust', 'government_profile', 'compliance_regime', 'supplier',
    'shipping_lane', 'trade_finance_instrument', 'tax_structure_type',
    'governance_commitment_type', 'org_structure_type',
    'alliance_partner_profile', 'ai_investor_fund', 'ai_investor_preference',
    'resilience_parameters', 'freight_market',
    'class_disclosure_override', 'class_resilience_weight_override',
}

EXPECTED_OUTPUT_SECTIONS = {
    # lifecycle and roster
    'game', 'round', 'team',
    # accepted decisions
    'decision_submission', 'decision_budget', 'decision_rd', 'decision_platform',
    'decision_product_create', 'decision_product_retire', 'decision_marketing',
    'decision_market_entry', 'decision_financing', 'decision_plant',
    'decision_partnership', 'decision_acquisition', 'decision_esg',
    'decision_event_response', 'decision_research', 'decision_talent',
    'talent_allocation', 'compliance_investment', 'sc_sourcing',
    'sc_sourcing_allocation', 'sc_logistics', 'sc_inventory', 'sc_incoterms',
    'sc_customs', 'sc_trade_finance', 'sc_sinosure', 'sc_fx_hedge',
    'sc_contingency',
    # world state
    'event_instance', 'active_modifier', 'sc_event_instance', 'supplier_state',
    'lane_state', 'government_action', 'government_satisfaction',
    'compliance_enforcement', 'ai_investor_holding',
    # carried team state
    'team_platform', 'team_platform_feature_level', 'pending_feature_gain',
    'team_product', 'team_product_platform_history', 'team_product_market',
    'team_market_presence',
    'team_market_modifier', 'team_strategy_feature_level', 'team_talent_state',
    'team_plant', 'team_partnership', 'team_acquisition', 'team_alliance_state',
    'team_governance_commitment', 'team_market_compliance', 'team_tax_structure',
    'team_org_structure', 'hedge_position',
    # published results
    'financials', 'market_revenue', 'product_market', 'adoption', 'performance',
    'coherence', 'resilience', 'share_price', 'leaderboard', 'esg_impact',
    'talent_impact', 'partnership_impact', 'agent_cycle', 'instructor_alert',
}

EXPECTED_INPUT_ONLY_SECTIONS = {
    'team_member', 'decision_audit_event',
}


class ManifestEnvelopeTests(SimpleTestCase):
    def test_output_sections_are_the_enumerated_competitive_set(self):
        self.assertEqual({s.name for s in ms.OUTPUT_SECTIONS},
                         EXPECTED_OUTPUT_SECTIONS)

    def test_input_sections_add_configuration_and_provenance_only(self):
        self.assertEqual(
            {s.name for s in ms.INPUT_SECTIONS},
            EXPECTED_OUTPUT_SECTIONS | EXPECTED_CONFIG_SECTIONS |
            EXPECTED_INPUT_ONLY_SECTIONS)

    def test_narrative_sections_are_separate_from_the_competitive_hash(self):
        self.assertEqual(
            {s.name for s in ms.NARRATIVE_SECTIONS},
            # `narrative_alert` is the Phase-2 half of InstructorAlert: the
            # engine's alerts stay in the competitive section, the coaching and
            # RAG commentary written after resolution do not (GSP-CRV2-03).
            {'strategic_briefing', 'market_intelligence', 'narrative_alert'})
        self.assertFalse({s.name for s in ms.NARRATIVE_SECTIONS} &
                         EXPECTED_OUTPUT_SECTIONS)

    def test_every_model_field_is_classified_with_a_reason_when_dropped(self):
        """No field may be silently absent from the envelope."""
        for mode, sections in (('input', ms.INPUT_SECTIONS),
                               ('output', ms.OUTPUT_SECTIONS),
                               ('output', ms.NARRATIVE_SECTIONS)):
            for section in sections:
                model = _model(section.model)
                plan = section_field_plan(section, model, mode)
                classified = (set(plan['hashed']) | set(plan['relations']) |
                              set(plan['narrative']) | set(plan['dropped']))
                declared = {f.attname for f in model._meta.fields}
                with self.subTest(section=section.name, mode=mode):
                    self.assertEqual(classified, declared)
                    for name, reason in plan['dropped'].items():
                        self.assertTrue(
                            reason and len(reason) > 15,
                            f'{section.name}.{name} is dropped without a usable '
                            f'justification')

    def test_measured_wall_clock_never_reaches_the_competitive_hash(self):
        for section in ms.OUTPUT_SECTIONS:
            plan = section_field_plan(section, _model(section.model), 'output')
            leaked = set(plan['hashed']) & set(ms.MEASURED_TIME_FIELDS)
            self.assertFalse(leaked, f'{section.name} hashes wall clock {leaked}')

    def test_narrative_fields_are_excluded_from_the_competitive_hash(self):
        for section in ms.OUTPUT_SECTIONS:
            plan = section_field_plan(section, _model(section.model), 'output')
            self.assertFalse(set(plan['hashed']) & set(plan['narrative']))

    def test_no_model_is_claimed_by_two_sections(self):
        self.assertEqual(ms.duplicate_models(ms.INPUT_SECTIONS), set())
        self.assertEqual(ms.duplicate_models(ms.OUTPUT_SECTIONS), set())

    def test_every_section_declares_why_it_is_in_the_manifest(self):
        for section in ms.ALL_SECTIONS:
            self.assertTrue(section.why, f'{section.name} has no rationale')

    def test_natural_keys_resolve_against_the_model(self):
        for section in ms.ALL_SECTIONS:
            natural_key_attnames(section, _model(section.model))

    def test_checked_in_inventory_matches_the_live_registry(self):
        """Schema drift must be a review event, not a silent hash change."""
        stored = json.loads(
            pathlib.Path(SCHEMA_INVENTORY_PATH).read_text(encoding='utf-8'))
        live = json.loads(cj.canonical_dumps(build_schema_inventory()))
        if stored != live:
            differing = sorted(
                name for envelope in ('input', 'output', 'narrative')
                for name in set(stored.get(envelope, {})) | set(live.get(envelope, {}))
                if stored.get(envelope, {}).get(name) != live.get(envelope, {}).get(name))
            self.fail(
                'Manifest envelope drifted from the reviewed inventory. '
                f'Sections that changed: {differing or "(section set changed)"}. '
                'Review the change, then run `manage.py dump_manifest_schema`.')


# ---------------------------------------------------------------------------
# 3. Iteration-order contract in the engine
# ---------------------------------------------------------------------------

ENGINE_ROOT = pathlib.Path(__file__).resolve().parent.parent / 'engine'

# Modules that only produce Phase-2 prose. They are outside the competitive
# hash by construction, so their iteration order cannot move a result.
NARRATIVE_MODULES = {
    'narratives.py', 'briefing.py', 'llm_runner.py', 'strategy_advisory.py',
    # The Phase-2 job queue. Its claim order is deliberately unspecified --
    # `FOR UPDATE SKIP LOCKED` is how workers avoid each other -- and nothing
    # it produces enters the competitive hash.
    'narrative_jobs.py',
}

SERVICES_ROOT = pathlib.Path(__file__).resolve().parent.parent / 'services'

# The services the engine calls during resolution. Anything reached from
# `core/engine` is inside the competitive envelope no matter which directory
# it lives in, so the ordering rule follows it there. Kept honest by
# `test_the_scanned_service_list_is_what_the_engine_actually_calls`.
RESOLUTION_SERVICES = {
    'competition_backup.py', 'competition_locks.py', 'funding_need.py',
    'product_platform.py', 'product_rebase.py', 'rd_costs.py',
    'resolution_manifest.py',
}

QUERYSET_MARKERS = ('.objects.', '.filter(', '.all()', '.exclude(')

# Loops whose result provably cannot depend on iteration order, each with the
# reason it is safe. Matched on the module name plus a distinctive fragment of
# the unparsed iterator expression.
ORDER_EXEMPT = {
    ('sc_engine.py', 'Supplier.objects.filter(scenario=scenario)'):
        'Builds a dict keyed by the unique supplier code / primary key.',
    ('sc_engine.py', 'ShippingLane.objects.filter(scenario=scenario)'):
        'Builds a dict keyed by the unique lane code.',
    ('sc_engine.py', 'SupplierState.objects.filter(round=rnd)'):
        'Builds a dict keyed by supplier id, unique per round.',
    ('governments.py', 'GovernmentProfile.objects.filter(scenario=game.scenario)'):
        'Builds a dict keyed by the unique market code.',
    ('leaderboard.py', 'RoundResultFinancials.objects.filter'):
        'values().annotate() aggregate collected into a dict keyed by team id; '
        'adding an ORDER BY would change the GROUP BY.',
}


def _loop_iterators(node):
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return [node.iter]
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                         ast.GeneratorExp)):
        return [generator.iter for generator in node.generators]
    return []


def _iterators(tree):
    """Every iterator expression in a for-loop or comprehension.

    Includes querysets reached through a local name: `rows = X.objects.filter()`
    followed by `for row in rows` is the same defect as iterating the filter
    inline, and it is the form that hid an unordered TeamMarketPresence scan
    until a cross-environment replay produced a different coherence breakdown.
    """
    found = []
    for scope in ast.walk(tree):
        if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.Module)):
            continue
        assigned = {}
        for node in ast.walk(scope):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)):
                assigned[node.targets[0].id] = node.value
        for node in ast.walk(scope):
            for iterator in _loop_iterators(node):
                if isinstance(iterator, ast.Name) and iterator.id in assigned:
                    found.append((node.lineno, assigned[iterator.id]))
                else:
                    found.append((node.lineno, iterator))
    return found


class SchemaProvenanceTests(SimpleTestCase):
    """A superseded schema definition must stay exactly as it was.

    Version 2's inventory was rewritten twice while still calling itself
    version 2 -- once by CRV2-03 and once by Stage 4 -- so the file named
    `manifest_schema_v2.json` was not the definition any earlier v2 manifest
    was hashed under. `require_schema_version` still refused to compare across
    versions, so no hash was ever wrongly matched; what was lost was the
    ability to reconstruct what a stored v2 hash meant (V2-052).

    Pinning the historical definitions by digest is what makes the chain
    reconstructable, and what stops the next `dump_manifest_schema` from
    quietly overwriting one.
    """

    HISTORY = (pathlib.Path(__file__).resolve().parent.parent
               / 'services' / 'manifest_schema_history')

    def provenance(self):
        return json.loads((self.HISTORY / 'PROVENANCE.json')
                          .read_text(encoding='utf-8'))

    def test_every_recorded_definition_still_hashes_to_its_record(self):
        import hashlib
        offenders = []
        for version, record in self.provenance()['versions'].items():
            for entry in record['definitions']:
                path = (self.HISTORY / entry['path']).resolve()
                if not path.exists():
                    offenders.append(f'v{version} {entry["commit"]}: missing')
                    continue
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest != entry['sha256']:
                    offenders.append(
                        f'v{version} {entry["commit"]}: {path.name} changed')
        self.assertFalse(offenders, (
            'A schema definition that has already been in force was modified. '
            'Superseded definitions are evidence, not working files:\n'
            + '\n'.join(offenders)))

    def test_the_current_inventory_declares_the_current_version(self):
        inventory = json.loads(
            pathlib.Path(SCHEMA_INVENTORY_PATH).read_text(encoding='utf-8'))
        # The canonical writer renders scalars as strings, so compare as one.
        self.assertEqual(str(inventory['schema_version']),
                         str(MANIFEST_SCHEMA_VERSION))

    def test_the_current_version_has_a_provenance_entry(self):
        record = self.provenance()['versions'].get(
            str(MANIFEST_SCHEMA_VERSION))
        self.assertIsNotNone(
            record,
            f'Version {MANIFEST_SCHEMA_VERSION} is in force but unrecorded. '
            'Every version needs its definition written down, or a hash '
            'stored under it cannot be interpreted later.')
        self.assertTrue(record['definitions'])

    def test_the_superseded_canonical_file_is_the_original_definition(self):
        """`manifest_schema_v2.json` is v2 as introduced, not as last edited."""
        import hashlib
        record = self.provenance()['versions']['2']
        canonical = (pathlib.Path(SCHEMA_INVENTORY_PATH).parent
                     / record['canonical_path'])
        expected = next(e['sha256'] for e in record['definitions']
                        if e['commit'] == record['canonical_is'])
        self.assertEqual(
            hashlib.sha256(canonical.read_bytes()).hexdigest(), expected)


class EngineIterationOrderTests(SimpleTestCase):
    def test_every_iterated_queryset_declares_its_order(self):
        offenders = []
        for path in sorted(ENGINE_ROOT.rglob('*.py')):
            if path.name in NARRATIVE_MODULES or '__pycache__' in str(path):
                continue
            if 'tests' in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for lineno, node in _iterators(tree):
                source = ast.unparse(node)
                if not any(marker in source for marker in QUERYSET_MARKERS):
                    continue
                if '.order_by(' in source:
                    continue
                exempt = any(path.name == module and fragment in source
                             for module, fragment in ORDER_EXEMPT)
                if exempt:
                    continue
                offenders.append(f'{path.name}:{lineno} {source[:110]}')
        self.assertFalse(offenders, 'Unordered iterated querysets:\n' +
                         '\n'.join(offenders))

    def test_resolution_services_declare_their_order(self):
        """The same rule, applied where the engine reaches outside itself.

        `ENGINE_ROOT` stops at `core/engine`, but resolution calls into
        `core/services`, and Stage 4 moved the round-correct platform lookup
        there. An unordered scan in `product_platform.missing_platform_
        resolutions` survived that move precisely because this scan did not
        reach it -- the refusal list it builds was ordered by whatever the
        database returned.
        """
        offenders = []
        for name in sorted(RESOLUTION_SERVICES):
            path = SERVICES_ROOT / name
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for lineno, node in _iterators(tree):
                source = ast.unparse(node)
                if not any(marker in source for marker in QUERYSET_MARKERS):
                    continue
                if '.order_by(' in source:
                    continue
                offenders.append(f'{name}:{lineno} {source[:110]}')
        self.assertFalse(offenders, 'Unordered iterated querysets:\n' +
                         '\n'.join(offenders))

    def test_the_scanned_service_list_is_what_the_engine_actually_calls(self):
        """The allowlist above is derived, not remembered.

        A scan scoped by a hand-kept list decays the first time someone adds
        an engine import. This fails when the engine reaches a service the
        scan does not cover, so the scope follows the code.
        """
        imported = set()
        for path in sorted(ENGINE_ROOT.rglob('*.py')):
            if '__pycache__' in str(path) or 'tests' in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                if node.module.startswith('core.services.'):
                    imported.add(node.module.split('.')[-1] + '.py')
                elif node.module == 'core.services':
                    for alias in node.names:
                        if (SERVICES_ROOT / f'{alias.name}.py').exists():
                            imported.add(f'{alias.name}.py')
        unscanned = imported - RESOLUTION_SERVICES - NARRATIVE_MODULES
        self.assertFalse(
            unscanned,
            'The engine calls these services, but the ordering scan above '
            'does not cover them. Add them to RESOLUTION_SERVICES (and fix '
            f'what that surfaces), or mark them narrative: {sorted(unscanned)}')

    def test_exemptions_are_all_still_reachable(self):
        """An exemption that no longer matches anything is stale documentation."""
        seen = set()
        for path in ENGINE_ROOT.rglob('*.py'):
            if '__pycache__' in str(path) or 'tests' in path.parts:
                continue
            for _lineno, node in _iterators(ast.parse(path.read_text(encoding='utf-8'))):
                seen.add((path.name, ast.unparse(node)))
        for module, fragment in ORDER_EXEMPT:
            self.assertTrue(
                any(name == module and fragment in source for name, source in seen),
                f'Exemption {module}:{fragment!r} no longer matches any loop')

    def test_agent_execution_order_is_fixed_by_registration(self):
        """Agent order decides ties when two actions share a priority."""
        from core.engine.agents.registry import AgentRegistry
        import core.engine.agents  # noqa: F401  (registers the four agents)
        self.assertEqual([agent.agent_class for agent in AgentRegistry.get_all()],
                         ['competitor', 'investor', 'alliance', 'government'])


# ---------------------------------------------------------------------------
# 4. Snapshots against a real game
# ---------------------------------------------------------------------------

FIXTURE_GAME = 'Determinism Fixture'
FIXTURE_SECTION_ID = 4242
FIXTURE_LOCKED_AT = datetime.datetime(2026, 8, 28, 9, 0, 0,
                                     tzinfo=datetime.timezone.utc)


class ManifestSnapshotIntegrationTests(TestCase):
    """Insertion order, corruption detection and the schema gate, on real rows."""

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        from core.models.scenario import Scenario
        import io as _io
        call_command('load_scenario', file='scenarios/consumer_electronics_2026.yaml',
                     stdout=_io.StringIO())
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')
        # initialize_game attributes the new game to a superuser.
        DjangoUser.objects.create_superuser('determinism-fixture-owner',
                                            'fixture@example.com', 'x')

    def setUp(self):
        import io
        from django.core.management import call_command
        from core.models import Game, Round, Team
        call_command('initialize_game', scenario=self.scenario.id, teams=3,
                     name=FIXTURE_GAME, stdout=io.StringIO())
        self.game = Game.objects.filter(name=FIXTURE_GAME).order_by('-id').first()
        # The engine seeds every RNG stream on ``game.section_id or game.id``.
        # Pinning it keeps the fixture's draws stable no matter what id the
        # game row happened to receive.
        self.game.section_id = FIXTURE_SECTION_ID
        self.game.save(update_fields=['section_id'])
        self.round = Round.objects.get(game=self.game, round_number=1)
        self.teams = list(Team.objects.filter(game=self.game).order_by('id'))

    # -- fixture decisions --------------------------------------------------

    def _decision_rows(self):
        """One marketing row per team-product-market, plus a budget row.

        Returned as callables so the same logical state can be written in
        either order.
        """
        from decimal import Decimal as D
        from core.models.cc31_models import ComplianceInvestment
        from core.models.decisions import (
            DecisionBudgetAllocation, DecisionMarketEntry, DecisionMarketing,
            DecisionPlant, DecisionRDInvestment, DecisionSubmission)
        from core.models.scenario import PlatformGenerationDefinition
        from core.models.scenario import (
            EntryModeDefinition, FeatureDefinition, MarketDefinition)
        from core.models.sc_decisions import SourcingAllocation
        from core.models.sc_models import Supplier
        from core.models import TalentAllocation
        from core.models.team_state import TeamPlatform, TeamProduct

        markets = list(MarketDefinition.objects.filter(
            scenario=self.scenario).order_by('code')[:3])
        features = list(FeatureDefinition.objects.filter(
            scenario=self.scenario).order_by('code')[:3])
        entry_mode = EntryModeDefinition.objects.filter(
            scenario=self.scenario).order_by('code').first()
        suppliers = list(Supplier.objects.filter(
            scenario=self.scenario).order_by('supplier_id')[:2])
        rows = []
        for index, team in enumerate(self.teams):
            submission, _ = DecisionSubmission.objects.get_or_create(
                team=team, round=self.round, defaults={'status': 'draft'})
            rows.append(lambda s=submission, i=index: DecisionBudgetAllocation
                        .objects.update_or_create(
                            submission=s, defaults=dict(
                                rd_budget=D(1_000_000 * (i + 1)),
                                marketing_budget=D(2_000_000 * (i + 1)),
                                strategy_budget=D(500_000),
                                research_budget=D(0))))
            products = list(TeamProduct.objects.filter(team=team).order_by('id'))
            for product in products:
                for offset, market in enumerate(markets):
                    rows.append(
                        lambda s=submission, p=product, m=market, i=index, o=offset:
                        DecisionMarketing.objects.update_or_create(
                            submission=s, team_product=p, market=m,
                            defaults=dict(
                                retail_price=D(500 + 10 * i + o),
                                promotion_budget=D(100_000 * (i + 1)),
                                campaign_focus_feature_ids=[],
                                channel_digital_pct=D('1'),
                                channel_traditional_pct=D('0'),
                                channel_trade_pct=D('0'),
                                distribution_strategy='hybrid',
                                distribution_investment=D('0'),
                                sales_team_count=5 + i,
                                production_volume=1000 * (i + 1),
                                demand_estimate=1000 * (i + 1),
                                production_source_market=m)))

            # R&D rows still populate their manifest section, so they stay in
            # the envelope. They no longer bind a feature-level or pending-gain
            # mutation loop -- Ruling 1 retired both -- and they must not target
            # a ready platform, which the engine now refuses outright. A
            # platform still in development is the one legal target left.
            # Its own generation: one non-retired platform per team per
            # generation, or the duplicate-generation precondition refuses.
            base_gen = (TeamPlatform.objects.filter(team=team)
                        .order_by('id').first().platform_generation)
            draft_gen, _ = PlatformGenerationDefinition.objects.get_or_create(
                scenario=base_gen.scenario, generation_order=90,
                defaults=dict(name='Drafting Gen', description='d',
                              unlock_round=0,
                              development_cost=D('1000000'),
                              license_cost=D('2000000'),
                              development_rounds=1))
            drafting, _ = TeamPlatform.objects.get_or_create(
                team=team, platform_generation=draft_gen,
                defaults=dict(
                    name=f'{team.name} Drafting Platform',
                    status='unfunded_draft', development_method='in_house',
                    development_started_round=0, funded_round=None,
                    development_rounds_remaining=1))
            for platform in [drafting]:
                for offset, feature in enumerate(features):
                    rows.append(
                        lambda s=submission, p=platform, f=feature, i=index, o=offset:
                        DecisionRDInvestment.objects.update_or_create(
                            submission=s, team_platform=p, feature=f,
                            method='in_house',
                            defaults=dict(amount=D(200_000 + 1_000 * o + 100 * i),
                                          calculated_cost=D(200_000))))

            # Market entry and plant build: both mutate carried team state.
            for offset, market in enumerate(markets[1:], start=1):
                rows.append(
                    lambda s=submission, m=market, i=index:
                    DecisionMarketEntry.objects.update_or_create(
                        submission=s, market=m, action='enter',
                        defaults=dict(entry_mode=entry_mode,
                                      initial_investment=D(1_000_000 + 1_000 * i))))
                rows.append(
                    lambda s=submission, m=market, i=index:
                    DecisionPlant.objects.update_or_create(
                        submission=s, market=m, action='contract',
                        defaults=dict(capacity_units=0,
                                      contract_mfg_volume=500 + 10 * i)))
                rows.append(
                    lambda s=submission, m=market, i=index:
                    ComplianceInvestment.objects.update_or_create(
                        submission=s, market=m,
                        defaults=dict(investment_amount=D(50_000 * (i + 1)))))

            # Talent: accumulated per pool across markets.
            for pool in ('rd', 'commercial', 'operations'):
                rows.append(
                    lambda s=submission, pl=pool, i=index:
                    TalentAllocation.objects.update_or_create(
                        submission=s, talent_pool=pl,
                        defaults=dict(hq_count=5 + i,
                                      market_allocation={m.code: 2 + i
                                                         for m in markets})))

            # Sourcing: read by the supply-chain capacity loop.
            for offset, supplier in enumerate(suppliers):
                rows.append(
                    lambda t=team, sup=supplier, o=offset:
                    SourcingAllocation.objects.update_or_create(
                        team=t, round=self.round,
                        critical_input_category='semiconductor', supplier=sup,
                        defaults=dict(allocation_pct=100 // max(len(suppliers), 1),
                                      volume_commitment_units=0,
                                      payment_terms='')))
        return rows

    def _write_decisions(self, reverse=False):
        from core.models.cc31_models import ComplianceInvestment
        from core.models.decisions import (
            DecisionBudgetAllocation, DecisionMarketEntry, DecisionMarketing,
            DecisionPlant, DecisionRDInvestment)
        from core.models import DecisionSubmission
        from core.models.sc_decisions import SourcingAllocation
        from core.models import TalentAllocation
        submissions = DecisionSubmission.objects.filter(round=self.round)
        for model in (DecisionMarketing, DecisionBudgetAllocation,
                      DecisionRDInvestment, DecisionMarketEntry, DecisionPlant,
                      ComplianceInvestment, TalentAllocation):
            model.objects.filter(submission__in=submissions).delete()
        SourcingAllocation.objects.filter(round=self.round).delete()
        rows = self._decision_rows()
        for write in (reversed(rows) if reverse else rows):
            write()
        # A fixed lock timestamp: the point of the reordering test is the row
        # order, not the clock, and locked_at is inside the input envelope.
        submissions.update(status='locked', locked_at=FIXTURE_LOCKED_AT)

    def _input_body(self):
        from core.services.resolution_manifest import build_input_manifest
        body, _snapshot = build_input_manifest(self.game, self.round)
        return body

    def _resolve_and_capture(self):
        """Run Phase 1, capture the competitive hash, then undo the mutations."""
        from django.db import transaction
        from core.engine.advance_round import _run_phase_1
        from core.services.resolution_manifest import build_output_manifest
        with transaction.atomic():
            _run_phase_1(self.game.id)
            body, narrative = build_output_manifest(self.round)
            captured = (cj.canonical_sha256(body), cj.canonical_sha256(narrative),
                        body)
            transaction.set_rollback(True)
        self.round.refresh_from_db()
        return captured

    # -- tests --------------------------------------------------------------

    def test_natural_keys_are_unique_across_every_populated_section(self):
        """A duplicate token would silently merge two rows in the manifest."""
        body = self._input_body()
        for name, rows in body['sections'].items():
            keys = [row['_key'] for row in rows]
            self.assertEqual(len(keys), len(set(keys)),
                             f'Section {name} produced duplicate natural keys')

    def test_no_surrogate_primary_key_reaches_the_manifest(self):
        rendered = cj.canonical_dumps(self._input_body()['sections'])
        self.assertNotIn('"id":', rendered)
        self.assertNotIn('#surrogate:', rendered)

    def test_input_manifest_carries_the_accepted_decision_payloads(self):
        """V2-002: the payload itself, not a hash of it."""
        self._write_decisions()
        sections = self._input_body()['sections']
        self.assertTrue(sections['decision_marketing'],
                        'marketing decisions missing from the input manifest')
        self.assertTrue(sections['decision_budget'])
        row = sections['decision_marketing'][0]
        for column in ('retail_price', 'promotion_budget', 'production_volume',
                       'channel_digital_pct'):
            self.assertIn(column, row)
        self.assertTrue(sections['scenario_config'], 'engine configuration missing')
        self.assertTrue(sections['segment_preference'], 'fit inputs missing')
        self.assertTrue(sections['team'], 'starting team state missing')

    def test_row_insertion_order_does_not_change_the_input_manifest(self):
        self._write_decisions(reverse=False)
        forward = cj.canonical_sha256(self._input_body())
        self._write_decisions(reverse=True)
        reverse = cj.canonical_sha256(self._input_body())
        self.assertEqual(forward, reverse)

    def test_row_insertion_order_does_not_change_the_competitive_hash(self):
        """The whole Phase-1 pipeline, replayed over reordered rows.

        The rows are deleted and rewritten backwards between the two runs, so
        every decision row carries a different primary key the second time and
        the physical row order in the table is reversed.
        """
        self._write_decisions(reverse=False)
        forward_hash, _forward_narrative, forward_body = self._resolve_and_capture()
        self._write_decisions(reverse=True)
        reverse_hash, _reverse_narrative, reverse_body = self._resolve_and_capture()
        if forward_hash != reverse_hash:
            from core.services.resolution_manifest import diff_sections
            diff = diff_sections(forward_body['sections'], reverse_body['sections'])
            self.fail(f'Insertion order changed the competitive hash: '
                      f'{sorted(diff)}')

    def test_corrupted_decision_payload_fails_verification_before_processing(self):
        self._assert_corruption_detected(
            'decision_marketing', self._corrupt_decision)

    def test_corrupted_scenario_value_fails_verification_before_processing(self):
        self._assert_corruption_detected(
            'segment_preference', self._corrupt_scenario)

    def test_corrupted_carried_state_fails_verification_before_processing(self):
        self._assert_corruption_detected('team', self._corrupt_carried_state)

    def _assert_corruption_detected(self, expected_section, corrupt):
        from core.services.resolution_manifest import prepare_manifest, verify_input_state
        self._write_decisions()
        manifest = prepare_manifest(self.game, self.round, 'test://no-backup')
        clean = verify_input_state(manifest)
        self.assertTrue(clean['matches'], clean.get('section_diffs'))

        corrupt()
        report = verify_input_state(manifest)
        self.assertFalse(report['matches'],
                         'Tampering was not detected before processing')
        self.assertIn(expected_section, report['section_diffs'])
        self.assertEqual(report['section_diffs'][expected_section]['changed_count'], 1)

    def _corrupt_decision(self):
        from decimal import Decimal as D
        from core.models.decisions import DecisionMarketing
        row = DecisionMarketing.objects.filter(
            submission__round=self.round).order_by('id').first()
        row.retail_price = D(row.retail_price) + D('1.00')
        row.save(update_fields=['retail_price'])

    def _corrupt_scenario(self):
        from core.models.scenario import SegmentPreference
        row = SegmentPreference.objects.filter(
            segment__scenario=self.scenario).order_by('id').first()
        row.weight = (row.weight or 0) + 1
        row.save(update_fields=['weight'])

    def _corrupt_carried_state(self):
        from decimal import Decimal as D
        team = self.teams[0]
        team.cash_on_hand = D(team.cash_on_hand) + D('1000000.00')
        team.save(update_fields=['cash_on_hand'])

    def test_no_surrogate_reference_reaches_the_output_or_narrative_envelope(self):
        """A competitive row points at configuration the output snapshot does
        not itself contain — a team's starter profile, a game's scenario. Those
        foreign keys must still resolve to natural-key tokens, or the hash moves
        with unrelated sequence activity."""
        from core.services.resolution_manifest import build_output_manifest
        self._write_decisions()
        competitive, narrative = build_output_manifest(self.round)
        for name, body in (('output', competitive), ('narrative', narrative)):
            rendered = cj.canonical_dumps(body)
            self.assertNotIn('#surrogate:', rendered,
                             f'{name} envelope carries a surrogate reference')
        team = competitive['sections']['team'][0]
        self.assertTrue(team['firm_starter_profile_id'].startswith(
            'firm_starter_profile('))
        self.assertTrue(team['game_id'].startswith('game('))

    def test_narrative_envelope_carries_the_prose_itself(self):
        """Hashing a narrative section's metadata and calling it the narrative
        hash would make "the prose differed" untestable."""
        from django.apps import apps
        from core.services.resolution_manifest import build_output_manifest
        StrategicBriefing = apps.get_model('core', 'StrategicBriefing')
        briefing = StrategicBriefing.objects.create(
            game=self.game, team=self.teams[0], round_number=1,
            executive_summary='ORIGINAL PROSE from the recorded model.',
            performance_analysis='p', investment_returns='i',
            investor_sentiment='s', competitive_landscape='c',
            strategic_recommendations='r', risk_alerts='a')

        _competitive, narrative = build_output_manifest(self.round)
        rows = narrative['prose']['strategic_briefing']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['executive_summary'],
                         'ORIGINAL PROSE from the recorded model.')
        before = cj.canonical_sha256(narrative)

        briefing.executive_summary = 'DIFFERENT PROSE from another model.'
        briefing.save(update_fields=['executive_summary'])
        _competitive, changed = build_output_manifest(self.round)
        self.assertNotEqual(cj.canonical_sha256(changed), before)

    def test_changed_prose_leaves_the_competitive_hash_alone(self):
        """The other half of the same claim: prose moves, the result does not."""
        from django.apps import apps
        from core.services.resolution_manifest import build_output_manifest
        StrategicBriefing = apps.get_model('core', 'StrategicBriefing')
        briefing = StrategicBriefing.objects.create(
            game=self.game, team=self.teams[0], round_number=1,
            executive_summary='first', performance_analysis='p',
            investment_returns='i', investor_sentiment='s',
            competitive_landscape='c', strategic_recommendations='r',
            risk_alerts='a')
        competitive_before, _ = build_output_manifest(self.round)
        briefing.executive_summary = 'a completely different narrative'
        briefing.save(update_fields=['executive_summary'])
        competitive_after, _ = build_output_manifest(self.round)
        self.assertEqual(cj.canonical_sha256(competitive_before),
                         cj.canonical_sha256(competitive_after))

    def test_version_1_manifests_are_readable_but_never_read_as_version_2(self):
        from core.models import ResolutionManifest
        from core.services.resolution_manifest import (
            ManifestSchemaError, require_schema_version, verify_input_state)
        legacy = ResolutionManifest.objects.create(
            game=self.game, round=self.round, schema_version=1, seed='s' * 64,
            input_manifest={'game_id': self.game.id, 'decision_events': []},
            input_sha256='i' * 64, output_manifest={'financials': []},
            output_sha256='o' * 64)
        # Still readable exactly as stored.
        self.assertEqual(legacy.input_manifest['game_id'], self.game.id)
        self.assertEqual(legacy.output_sha256, 'o' * 64)
        with self.assertRaisesRegex(ManifestSchemaError, 'schema version 1'):
            require_schema_version(legacy)
        with self.assertRaises(ManifestSchemaError):
            verify_input_state(legacy)

    def test_prepare_and_complete_write_a_version_2_envelope(self):
        from core.services.resolution_manifest import (
            MANIFEST_SCHEMA_VERSION, complete_manifest, prepare_manifest)
        self._write_decisions()
        manifest = prepare_manifest(self.game, self.round, 'test://no-backup')
        self.assertEqual(manifest.schema_version, MANIFEST_SCHEMA_VERSION)
        from core.services.resolution_manifest import envelope_schema_version
        self.assertEqual(envelope_schema_version(manifest.input_manifest),
                         MANIFEST_SCHEMA_VERSION)
        self.assertEqual(len(manifest.input_sha256), 64)
        # The build that resolved the round must be identifiable by content,
        # not only by a commit hash that a dirty tree renders ambiguous.
        self.assertEqual(len(manifest.source_tree_sha256), 64)
        self.assertEqual(manifest.source_tree_sha256,
                         manifest.environment['source_tree_sha256'])
        self.assertTrue(manifest.environment['python'])
        self.assertEqual(set(manifest.input_section_digests),
                         set(manifest.input_manifest['sections']))

        from django.db import transaction
        from core.engine.advance_round import _run_phase_1
        with transaction.atomic():
            _run_phase_1(self.game.id)
            completed = complete_manifest(self.round)
            self.assertEqual(completed.schema_version, MANIFEST_SCHEMA_VERSION)
            self.assertEqual(len(completed.output_sha256), 64)
            self.assertEqual(len(completed.narrative_sha256), 64)
            self.assertNotEqual(completed.output_sha256, completed.narrative_sha256)
            self.assertEqual(set(completed.output_manifest['sections']),
                             EXPECTED_OUTPUT_SECTIONS)
            # Resolution must not have rewritten its own configuration.
            for name, digest in completed.output_manifest['config_digests'].items():
                self.assertEqual(digest, manifest.input_section_digests[name],
                                 f'Resolution mutated configuration section {name}')
            transaction.set_rollback(True)


# ---------------------------------------------------------------------------
# 5. Build identity
# ---------------------------------------------------------------------------

class BuildIdentityTests(SimpleTestCase):
    """A `-dirty` suffix names the commit but not the code on top of it.

    Two different uncommitted patches on one HEAD produce the same revision
    string, so a manifest carrying only that string cannot prove which code
    computed its hashes. The source digest is what closes that gap.
    """

    def _tree(self, files):
        import tempfile
        root = pathlib.Path(tempfile.mkdtemp())
        for relative, body in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding='utf-8')
        return root

    def test_identical_trees_digest_identically(self):
        from core.services.build_identity import source_tree_digest
        files = {'a.py': 'x = 1\n', 'pkg/b.py': 'y = 2\n'}
        first = source_tree_digest(self._tree(files), refresh=True)
        second = source_tree_digest(self._tree(files), refresh=True)
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual(first['file_count'], 2)

    def test_a_one_byte_content_change_changes_the_digest(self):
        from core.services.build_identity import source_tree_digest
        before = source_tree_digest(self._tree({'a.py': 'x = 1\n'}), refresh=True)
        after = source_tree_digest(self._tree({'a.py': 'x = 2\n'}), refresh=True)
        self.assertNotEqual(before['sha256'], after['sha256'])

    def test_moving_a_file_changes_the_digest(self):
        from core.services.build_identity import source_tree_digest
        before = source_tree_digest(self._tree({'a.py': 'x = 1\n'}), refresh=True)
        after = source_tree_digest(self._tree({'pkg/a.py': 'x = 1\n'}), refresh=True)
        self.assertNotEqual(before['sha256'], after['sha256'])

    def test_caches_and_operator_data_are_not_part_of_the_build(self):
        """A resolution writes into competition_backups; that must not change
        the identity of the code that wrote it."""
        from core.services.build_identity import source_tree_digest
        base = {'a.py': 'x = 1\n'}
        clean = source_tree_digest(self._tree(base), refresh=True)
        noisy = source_tree_digest(self._tree({
            **base,
            '__pycache__/a.cpython-310.pyc': 'compiled',
            'competition_backups/manifests/round-1.json': '{"big": "body"}',
            'staticfiles/app.json': '{}',
        }), refresh=True)
        self.assertEqual(clean['sha256'], noisy['sha256'])

    def test_untracked_source_is_included(self):
        """The digest is content-derived, so it does not care about git at all
        — which is the point: it survives a dirty tree and a .git-less export."""
        from core.services.build_identity import source_tree_digest
        base = source_tree_digest(self._tree({'a.py': 'x = 1\n'}), refresh=True)
        plus = source_tree_digest(
            self._tree({'a.py': 'x = 1\n', 'new_module.py': 'z = 3\n'}),
            refresh=True)
        self.assertNotEqual(base['sha256'], plus['sha256'])
        self.assertEqual(plus['file_count'], 2)

    def test_clean_build_gate_refuses_an_uncommitted_tree(self):
        from django.test import override_settings
        from core.services.build_identity import require_identified_build
        dirty = {'code_revision': 'abc123-dirty', 'code_revision_is_dirty': True,
                 'source_tree_sha256': 'd' * 64, 'source_file_count': 1,
                 'source_root': '/tmp'}
        with override_settings(COMPETITION_REQUIRE_CLEAN_BUILD=True):
            with self.assertRaisesRegex(RuntimeError, 'uncommitted working tree'):
                require_identified_build(dirty)
        with override_settings(COMPETITION_REQUIRE_CLEAN_BUILD=False):
            self.assertEqual(require_identified_build(dirty), dirty)

    def test_clean_build_gate_accepts_a_named_revision(self):
        from django.test import override_settings
        from core.services.build_identity import require_identified_build
        clean = {'code_revision': 'abc123', 'code_revision_is_dirty': False,
                 'source_tree_sha256': 'c' * 64, 'source_file_count': 1,
                 'source_root': '/tmp'}
        with override_settings(COMPETITION_REQUIRE_CLEAN_BUILD=True):
            self.assertEqual(require_identified_build(clean), clean)

    def test_environment_fingerprint_carries_the_source_digest(self):
        from core.services.resolution_manifest import environment_fingerprint
        fingerprint = environment_fingerprint()
        self.assertEqual(len(fingerprint['source_tree_sha256']), 64)
        self.assertGreater(fingerprint['source_file_count'], 0)
        # The fields a cross-environment replay asserts on must be present.
        for key in ('tz_env', 'lc_all', 'python', 'system_timezone', 'locale'):
            self.assertIn(key, fingerprint)


class ReplayCommandGuardTests(SimpleTestCase):
    """The replay command's fail-closed gates, independent of a database."""

    def _command(self):
        from core.management.commands.replay_round import Command
        return Command()

    def test_required_environment_mismatch_is_refused(self):
        from django.core.management.base import CommandError
        observed = {'tz_env': 'UTC', 'lc_all': ''}
        with self.assertRaisesRegex(CommandError, 'not the environment'):
            self._command()._check_required_env(
                ['tz_env=Asia/Kolkata'], observed)

    def test_required_environment_match_is_reported(self):
        observed = {'tz_env': 'Asia/Kolkata', 'locale': ['de_DE', 'UTF-8']}
        report = self._command()._check_required_env(
            ['tz_env=Asia/Kolkata', 'locale=de_DE,UTF-8'], observed)
        self.assertTrue(all(item['matches'] for item in report))

    def test_unknown_required_environment_key_is_refused(self):
        from django.core.management.base import CommandError
        with self.assertRaisesRegex(CommandError, 'not an environment'):
            self._command()._check_required_env(['nonsense=1'], {'tz_env': 'UTC'})

    def test_malformed_requirement_is_refused(self):
        from django.core.management.base import CommandError
        with self.assertRaisesRegex(CommandError, 'KEY=VALUE'):
            self._command()._check_required_env(['tz_env'], {'tz_env': 'UTC'})

    def test_exported_manifest_reads_plain_and_gzipped(self):
        """The stored evidence is gzipped; the documented command must read it
        without an undocumented decompression step."""
        import gzip
        import tempfile
        body = {'schema_version': '2', 'input_sha256': 'a' * 64}
        directory = pathlib.Path(tempfile.mkdtemp())
        plain = directory / 'expected-manifest.json'
        plain.write_text(json.dumps(body), encoding='utf-8')
        gzipped = directory / 'other-manifest.json.gz'
        with gzip.open(gzipped, 'wt', encoding='utf-8') as stream:
            json.dump(body, stream)

        command = self._command()
        self.assertEqual(command._read_manifest_file(plain), body)
        self.assertEqual(command._read_manifest_file(gzipped), body)
        # A path naming the uncompressed file resolves to the .gz beside it.
        self.assertEqual(
            command._read_manifest_file(directory / 'other-manifest.json'), body)

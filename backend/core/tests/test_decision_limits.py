"""GSP-CRV2-06 Stage 1 — the legal decision space, enforced the same way
everywhere.

Two write surfaces accept decisions: the whole-submission endpoint and the
per-type PATCH endpoint. A rule that only one of them applies is not a rule, and
a rule that lives in two places is one edit away from being a rule that only one
of them applies.

These tests go through the real endpoints. An earlier probe in this handoff
compared the *serializers* in isolation and reported that the per-type path
accepted a duplicate R&D payload the whole-submission path refused. The view
turned out to call the cross-row rule itself, so the endpoints agreed and the
serializers did not — a difference the probe could not see because it never made
a request. What follows asks the API.
"""
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import (DecisionSubmission, Game, Round, Scenario, Team,
                         TeamMember, User)
from core.models.scenario import FirmStarterProfile, MarketDefinition
from core.serializers import decision_limits


class DecisionApiBase(TestCase):
    def setUp(self):
        owner = DjangoUser.objects.create(username=f'owner-{id(self)}')
        self.user = User.objects.create(
            username=f'student-{id(self)}', role='student', password_hash='x')
        self.scenario = Scenario.objects.create(
            name=f'Limits {id(self)}', industry_label='T', description='d',
            starting_cash=1000, num_rounds=4)
        market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=market, starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Limits game', current_round=1,
            status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.team = Team.objects.create(
            game=self.game, name='T', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000)
        # Membership is read by user id through `Enrollment` or `TeamMember`;
        # `TeamMember.user` points at Django's auth user, so the id is what
        # matters rather than the model the row was built from.
        TeamMember.objects.create(team_id=self.team.id, user_id=self.user.user_id)

        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.user)}')

    def partial_url(self, decision_type):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/decisions/round/{self.round.round_number}/{decision_type}/')

    def full_url(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/decisions/round/{self.round.round_number}/')

    def submission(self):
        return DecisionSubmission.objects.filter(
            team=self.team, round=self.round).first()


class NonNegativeTableTests(TestCase):
    """The table is the coverage claim, so it has to describe reality."""

    def test_every_named_field_exists_on_its_serializer(self):
        import core.serializers.decisions  # noqa: F401  (registers the classes)
        import core.serializers.sc_serializers  # noqa: F401
        from rest_framework import serializers as drf

        found = {}
        for module in ('core.serializers.decisions',
                       'core.serializers.sc_serializers'):
            import importlib
            mod = importlib.import_module(module)
            for name in dir(mod):
                obj = getattr(mod, name)
                if isinstance(obj, type) and issubclass(obj, drf.Serializer):
                    found[name] = obj

        for serializer_name, fields in decision_limits.NON_NEGATIVE_FIELDS.items():
            self.assertIn(serializer_name, found,
                          f'{serializer_name} is in the table but not defined')
            available = found[serializer_name]().get_fields()
            for field in fields:
                self.assertIn(field, available,
                              f'{serializer_name}.{field} is in the table but '
                              'the serializer has no such field')

    def test_the_guard_is_attached_to_each_named_field(self):
        import importlib
        from rest_framework import serializers as drf
        for module in ('core.serializers.decisions',
                       'core.serializers.sc_serializers'):
            mod = importlib.import_module(module)
            for serializer_name, fields in decision_limits.NON_NEGATIVE_FIELDS.items():
                cls = getattr(mod, serializer_name, None)
                if cls is None:
                    continue
                built = cls().get_fields()
                for field in fields:
                    validators = built[field].validators
                    self.assertIn(
                        decision_limits._NonNegative(field), validators,
                        f'{serializer_name}.{field} has no non-negative guard')

    def test_nothing_is_allowed_to_be_negative_without_a_reason(self):
        # The escape hatch exists so that adding one is deliberate. If it ever
        # has an entry, that entry must carry a reason.
        for field, reason in decision_limits.NEGATIVE_ALLOWED.items():
            self.assertTrue(reason and len(reason) > 20,
                            f'{field} is exempt without a reason')


class NegativeInvestmentApiTests(DecisionApiBase):
    """A negative investment was income. Both endpoints must refuse it."""

    # (decision type, payload, the field the refusal must name)
    NEGATIVE_CASES = [
        ('esg', {'environmental_investment': '-5000000', 'social_investment': '0'},
         'environmental_investment'),
        ('esg', {'environmental_investment': '0', 'social_investment': '-5000000'},
         'social_investment'),
        ('talent', {'rd_headcount': -5, 'commercial_headcount': 1,
                    'operations_headcount': 1, 'rd_salary_level': 3,
                    'commercial_salary_level': 3, 'operations_salary_level': 3,
                    'rd_training_budget': '0', 'commercial_training_budget': '0',
                    'operations_training_budget': '0'}, 'rd_headcount'),
        ('talent', {'rd_headcount': 1, 'commercial_headcount': -5,
                    'operations_headcount': 1, 'rd_salary_level': 3,
                    'commercial_salary_level': 3, 'operations_salary_level': 3,
                    'rd_training_budget': '0', 'commercial_training_budget': '0',
                    'operations_training_budget': '0'}, 'commercial_headcount'),
        ('talent', {'rd_headcount': 1, 'commercial_headcount': 1,
                    'operations_headcount': -5, 'rd_salary_level': 3,
                    'commercial_salary_level': 3, 'operations_salary_level': 3,
                    'rd_training_budget': '0', 'commercial_training_budget': '0',
                    'operations_training_budget': '0'}, 'operations_headcount'),
        ('talent', {'rd_headcount': 1, 'commercial_headcount': 1,
                    'operations_headcount': 1, 'rd_salary_level': 3,
                    'commercial_salary_level': 3, 'operations_salary_level': 3,
                    'rd_training_budget': '-5000000',
                    'commercial_training_budget': '0',
                    'operations_training_budget': '0'}, 'rd_training_budget'),
    ]

    def test_the_partial_api_refuses_every_negative_investment(self):
        for decision_type, payload, field in self.NEGATIVE_CASES:
            with self.subTest(field=field):
                response = self.client.patch(
                    self.partial_url(decision_type), payload, format='json')
                self.assertEqual(response.status_code, 400,
                                 f'{field} was accepted: {response.data}')
                self.assertIn(field, str(response.data))
                self.assertIn('>= 0', str(response.data))

    def test_a_refused_payload_writes_nothing(self):
        """The engine must never see the row. A 400 that still stored the
        decision would be a validation message, not a validation."""
        from core.models.decisions import DecisionESG
        response = self.client.patch(
            self.partial_url('esg'),
            {'environmental_investment': '-5000000', 'social_investment': '0'},
            format='json')
        self.assertEqual(response.status_code, 400)
        submission = self.submission()
        if submission is not None:
            self.assertFalse(
                DecisionESG.objects.filter(submission=submission).exists(),
                'the refused ESG row was written anyway')

    def test_zero_and_positive_are_still_accepted(self):
        """The control. A guard that refuses everything is not a guard."""
        from core.models.decisions import DecisionESG
        for amount in ('0', '1', '5000000.00'):
            with self.subTest(amount=amount):
                response = self.client.patch(
                    self.partial_url('esg'),
                    {'environmental_investment': amount,
                     'social_investment': '0'},
                    format='json')
                self.assertEqual(response.status_code, 200,
                                 f'{amount} was refused: {response.data}')
                row = DecisionESG.objects.get(submission=self.submission())
                self.assertEqual(row.environmental_investment, Decimal(amount))

    def test_the_whole_submission_api_refuses_the_negatives_it_accepts(self):
        """Only for decision types the whole-submission serializer nests.

        `talent` is reachable through the per-type endpoint alone — it is not a
        field of `DecisionSubmissionSerializer` — so for those fields there is
        no second path to disagree with. That asymmetry is recorded in the
        legal-space inventory rather than asserted as agreement here.
        """
        from core.serializers.decisions import DecisionSubmissionSerializer
        nested = set(DecisionSubmissionSerializer().get_fields())
        checked = 0
        for decision_type, payload, field in self.NEGATIVE_CASES:
            if decision_type not in nested:
                continue
            checked += 1
            with self.subTest(field=field):
                response = self.client.put(
                    self.full_url(),
                    {'team': self.team.id, 'round': self.round.id,
                     decision_type: payload},
                    format='json')
                self.assertEqual(response.status_code, 400,
                                 f'{field} was accepted: {response.data}')
                self.assertIn(field, str(response.data))
        self.assertGreater(checked, 0, 'no case exercised the whole-submission path')

    def test_talent_is_reachable_on_one_path_only(self):
        """Recorded because it shapes what "both APIs agree" can mean.

        The whole-submission serializer has no `talent` field, so a `talent`
        key in that payload is ignored rather than validated. The per-type
        endpoint is the only way to submit it, and the only place its rules can
        be enforced.
        """
        from core.models.talent import DecisionTalent
        from core.serializers.decisions import DecisionSubmissionSerializer
        self.assertNotIn('talent', DecisionSubmissionSerializer().get_fields())

        negative = dict(self.NEGATIVE_CASES[2][1])
        response = self.client.put(
            self.full_url(),
            {'team': self.team.id, 'round': self.round.id, 'talent': negative},
            format='json')
        # Ignored, not stored: the danger would be silent acceptance.
        submission = self.submission()
        if submission is not None:
            self.assertFalse(
                DecisionTalent.objects.filter(submission=submission).exists(),
                'the whole-submission path stored a talent row it never validated')


class DuplicateRdRowApiTests(DecisionApiBase):
    """Two R&D rows naming the same platform feature.

    The rule exists because the outcome would otherwise depend on row order —
    the V2-012 class. What matters is that both endpoints refuse it *for that
    reason*, and that the distinct-feature control still succeeds.
    """

    def setUp(self):
        super().setUp()
        from core.models.team_state import TeamPlatform
        from core.models.scenario import (FeatureDefinition,
                                          PlatformFeatureCeiling,
                                          PlatformGenerationDefinition)
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen 1', description='d',
            generation_order=1, unlock_round=1, development_cost=0,
            development_rounds=1, license_cost=0, annual_maintenance_cost=0,
            is_starting_platform=True)
        self.platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation, name='P1',
            status='active')
        self.feature_a = FeatureDefinition.objects.create(
            scenario=self.scenario, name='Feature A', code='FA',
            description='d', layer='core', category='performance',
            min_value=0, max_value=10, default_value=0,
            cost_curve_type='linear', cost_base=1)
        self.feature_b = FeatureDefinition.objects.create(
            scenario=self.scenario, name='Feature B', code='FB',
            description='d', layer='core', category='performance',
            min_value=0, max_value=10, default_value=0,
            cost_curve_type='linear', cost_base=1)
        # An R&D row is only legal for a feature the platform generation can
        # actually reach.
        for feature in (self.feature_a, self.feature_b):
            PlatformFeatureCeiling.objects.create(
                platform_generation=generation, feature=feature,
                ceiling_value=10, starting_value=0)

    def row(self, feature):
        return {'team_platform': self.platform.pk, 'feature': feature.pk,
                'method': 'in_house', 'amount': '1000.00', 'target_level': 1}

    def test_the_partial_api_refuses_a_duplicate_platform_feature(self):
        response = self.client.patch(
            self.partial_url('rd'),
            [self.row(self.feature_a), self.row(self.feature_a)],
            format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('Only one R&D investment per platform feature',
                      str(response.data))

    def test_the_whole_submission_api_refuses_it_too(self):
        response = self.client.put(
            self.full_url(),
            {'team': self.team.id, 'round': self.round.id,
             'rd_investments': [self.row(self.feature_a),
                                self.row(self.feature_a)]},
            format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('Only one R&D investment per platform feature',
                      str(response.data))

    def test_distinct_features_are_still_accepted_on_both_paths(self):
        """The control both refusals are meaningless without."""
        from core.models.decisions import DecisionRDInvestment
        response = self.client.patch(
            self.partial_url('rd'),
            [self.row(self.feature_a), self.row(self.feature_b)],
            format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            DecisionRDInvestment.objects.filter(
                submission=self.submission()).count(), 2)

    def test_a_refused_duplicate_writes_nothing(self):
        from core.models.decisions import DecisionRDInvestment
        self.client.patch(
            self.partial_url('rd'),
            [self.row(self.feature_a), self.row(self.feature_a)],
            format='json')
        submission = self.submission()
        if submission is not None:
            self.assertEqual(
                DecisionRDInvestment.objects.filter(submission=submission).count(),
                0, 'a refused duplicate payload was stored')


class PersistedRowEngineGuardTests(TestCase):
    """The engine scores rows, not payloads.

    The serializer guards stop a negative value entering through either
    supported API. A row can still arrive from a data migration, an import, the
    admin, `manage.py shell` or a restore, and scoring would read it. So the
    same policy is applied to what is about to be scored, and scoring refuses
    rather than correcting: a clamped value is a team's decision silently
    replaced with a different one, scored as though it were theirs.
    """

    def setUp(self):
        from core.models.core import TeamMember  # noqa: F401
        owner = DjangoUser.objects.create(username=f'owner-eng-{id(self)}')
        self.scenario = Scenario.objects.create(
            name=f'Engine {id(self)}', industry_label='T', description='d',
            starting_cash=1000, num_rounds=4)
        market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=market, starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Engine game', current_round=1,
            status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.team = Team.objects.create(
            game=self.game, name='T1', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000)
        self.submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='locked',
            locked_at=timezone.now())

    def esg(self, amount):
        """Straight to the database, exactly as a bypass would."""
        from core.models.decisions import DecisionESG
        DecisionESG.objects.filter(submission=self.submission).delete()
        return DecisionESG.objects.create(
            submission=self.submission,
            environmental_investment=Decimal(amount),
            social_investment=Decimal('0'))

    def resolve(self):
        from core.engine.advance_round import _run_phase_1
        return _run_phase_1(self.game.id)

    def test_a_negative_row_written_past_the_serializers_is_refused(self):
        from core.engine.advance_round import InvalidPersistedDecisionError
        row = self.esg('-5000000')
        # The row exists: the ORM wrote it without asking a serializer.
        self.assertEqual(row.environmental_investment, Decimal('-5000000'))
        with self.assertRaises(InvalidPersistedDecisionError):
            self.resolve()

    def test_the_refusal_names_the_row_and_the_field(self):
        from core.engine.advance_round import InvalidPersistedDecisionError
        row = self.esg('-5000000')
        with self.assertRaises(InvalidPersistedDecisionError) as caught:
            self.resolve()
        message = str(caught.exception)
        self.assertIn('DecisionESG', message)
        self.assertIn(str(row.pk), message)
        self.assertIn('environmental_investment', message)
        self.assertIn('-5000000', message)

    def test_a_refused_round_leaves_no_competitive_result(self):
        from core.engine.advance_round import InvalidPersistedDecisionError
        from core.models import (RoundResultFinancials,
                                 RoundResultPerformanceIndex)
        self.esg('-5000000')
        with self.assertRaises(InvalidPersistedDecisionError):
            self.resolve()

        self.assertFalse(
            RoundResultFinancials.objects.filter(game=self.game).exists())
        self.assertFalse(
            RoundResultPerformanceIndex.objects.filter(game=self.game).exists())
        # The round must not be left mid-flight either.
        self.round.refresh_from_db()
        self.assertNotEqual(self.round.processing_status, 'PROCESSING')
        self.assertNotEqual(self.round.status, 'processed')
        self.team.refresh_from_db()
        self.assertEqual(self.team.cash_on_hand, 1000)

    def test_zero_and_positive_persisted_values_still_resolve(self):
        """The control. A precondition that refuses everything is not a guard."""
        for amount in ('0', '250000'):
            with self.subTest(amount=amount):
                Round.objects.filter(pk=self.round.pk).update(
                    status='open', processing_status='')
                self.round.refresh_from_db()
                self.esg(amount)
                # Resolution may still fail for unrelated scenario reasons; what
                # must not happen is a refusal about this policy.
                from core.engine.advance_round import InvalidPersistedDecisionError
                try:
                    self.resolve()
                except InvalidPersistedDecisionError as error:
                    self.fail(f'{amount} was refused by the decision policy: {error}')
                except Exception:
                    pass

    def test_the_scan_covers_every_protected_model(self):
        """The precondition is only worth what it looks at."""
        from core.serializers import decision_limits
        mapping = decision_limits.protected_model_fields()
        names = {m.__name__ for m in mapping}
        for expected in ('DecisionESG', 'DecisionTalent', 'DecisionMarketing',
                         'DecisionRDInvestment', 'DecisionPlant',
                         'DecisionPartnership', 'DecisionMarketEntry',
                         'DecisionPlatformDevelopment', 'SourcingAllocation'):
            self.assertIn(expected, names)
        total = sum(len(f) for f in mapping.values())
        self.assertEqual(total, 21, f'expected 21 protected fields, found {total}')

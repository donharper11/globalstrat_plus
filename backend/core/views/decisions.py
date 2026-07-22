"""
Decision Submission API views (CC-04).

Endpoints:
- GET/POST/PUT full decision submission
- PATCH partial update by decision type
- POST lock / unlock
- GET summary (checklist for submit page)
- GET context endpoints (R&D, products, marketing, strategy, finance)
"""
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team, TeamMember, Round
from core.models.decisions import (
    DecisionSubmission, DecisionBudgetAllocation, DecisionRDInvestment,
    DecisionPlatformDevelopment, DecisionProductCreate, DecisionProductRetire,
    DecisionMarketing, DecisionMarketEntry, DecisionFinancing,
    DecisionPlant, DecisionPartnership, DecisionAcquisition,
    DecisionESG, DecisionEventResponse, DecisionResearchAllocation,
)
from core.models.team_state import (
    TeamPlatform, TeamPlatformFeatureLevel, PendingFeatureGain,
    TeamProduct, TeamProductMarket,
    TeamMarketPresence, TeamPlant, TeamPartnership as TeamPartnershipState,
    TeamStrategyFeatureLevel, TeamAcquisition,
)
from core.models.scenario import (
    Scenario, FeatureDefinition, PlatformGenerationDefinition,
    PlatformFeatureCeiling, MarketDefinition, EntryModeDefinition,
    StrategyOptionDefinition, ScenarioConfig, AICompetitorDefinition,
    FeatureLevelCost, AcquisitionTarget,
)
from core.models.results_financials import RoundResultFinancials
from core.utils.localization import get_localized_field, get_user_language
from core.serializers.decisions import (
    DecisionSubmissionSerializer,
    DecisionBudgetAllocationSerializer,
    DecisionRDInvestmentSerializer,
    DecisionPlatformDevelopmentSerializer,
    DecisionProductCreateSerializer,
    DecisionProductRetireSerializer,
    DecisionMarketingSerializer,
    DecisionMarketEntrySerializer,
    DecisionFinancingSerializer,
    DecisionPlantSerializer,
    DecisionPartnershipSerializer,
    DecisionAcquisitionSerializer,
    DecisionESGSerializer,
    DecisionEventResponseSerializer,
    DecisionResearchAllocationSerializer,
    DecisionTalentSerializer,
)


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def _get_user_from_header(request):
    """
    Look up our custom User model for the authenticated caller.

    Name kept for back-compat; identity now comes only from the signed JWT.
    The X-User-Id header is no longer trusted (it allowed impersonation).
    """
    from core.utils.auth_context import get_request_user
    return get_request_user(request)


class IsTeamMember(permissions.BasePermission):
    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, view):
        team_id = view.kwargs.get('team_id')
        user = _get_user_from_header(request)
        if not user:
            return False
        role = (user.role or '').lower()
        # Instructors / admins always allowed
        if role in ('instructor', 'admin'):
            return True
        # Students: check enrollment team or TeamMember
        from core.models import Enrollment
        if Enrollment.objects.filter(
            user_id=user.user_id, team_id=team_id, is_active=True,
        ).exists():
            return True
        return TeamMember.objects.filter(
            team_id=team_id, user_id=user.user_id,
        ).exists()


class IsRoundOpen(permissions.BasePermission):
    """
    Block writes unless the round is genuinely open for submissions.

    Three gates, all previously missing or unenforced:
      1. the round's status must be 'open';
      2. the round's deadline must not have passed — checked here rather than
         trusting cron alone, so a stalled cron can't hand students extra time;
      3. the game must not be paused/completed/archived.

    Instructors are exempt so they can still fix a team's decisions.
    """
    message = 'The round is not currently open for submissions.'

    def has_permission(self, request, view):
        # Read-only methods always allowed
        if request.method in permissions.SAFE_METHODS:
            return True

        from core.utils.auth_context import get_request_role
        if get_request_role(request) in ('instructor', 'admin'):
            return True

        round_number = view.kwargs.get('round_number')
        game_id = view.kwargs.get('game_id')

        from core.models import Game
        game = Game.objects.filter(pk=game_id).only('status').first()
        if game:
            if game.status == 'paused':
                self.message = ('The game is paused by your instructor. '
                                'No changes can be made right now.')
                return False
            if game.status in ('completed', 'archived'):
                self.message = f'This game is {game.status}.'
                return False

        round_obj = Round.objects.filter(
            game_id=game_id, round_number=round_number,
        ).only('status', 'deadline').first()
        if not round_obj:
            return False

        if round_obj.status != 'open':
            self.message = (f'Round {round_number} is {round_obj.status} — '
                            f'it is no longer accepting decisions.')
            return False

        if round_obj.deadline:
            from django.utils import timezone
            if timezone.now() >= round_obj.deadline:
                self.message = ('The deadline for this round has passed. '
                                'Your decisions are locked.')
                return False

        return True


class IsInstructor(permissions.BasePermission):
    message = 'Instructor or Admin access required.'

    def has_permission(self, request, view):
        user = _get_user_from_header(request)
        if not user:
            return False
        return (user.role or '').lower() in ('instructor', 'admin')


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_submission_or_none(team_id, game_id, round_number):
    """Get the DecisionSubmission for a team/round, or None."""
    try:
        rnd = Round.objects.get(game_id=game_id, round_number=round_number)
    except Round.DoesNotExist:
        return None
    return DecisionSubmission.objects.filter(
        team_id=team_id, round=rnd,
    ).first()


def _get_round(game_id, round_number):
    return get_object_or_404(Round, game_id=game_id, round_number=round_number)


def _get_team(team_id):
    return get_object_or_404(Team, pk=team_id)


# ---------------------------------------------------------------------------
# Decision CRUD Views
# ---------------------------------------------------------------------------

class DecisionSubmissionView(APIView):
    """
    GET  — retrieve full decision submission
    POST — create or update (upsert) draft submission
    PUT  — full replacement of draft submission
    """
    permission_classes = [IsTeamMember, IsRoundOpen]

    def get(self, request, game_id, team_id, round_number):
        rnd = _get_round(game_id, round_number)
        submission = DecisionSubmission.objects.filter(
            team_id=team_id, round=rnd,
        ).first()
        if not submission:
            # GSP-R1-01: the normal no-draft state is not an error. Return a
            # typed empty 200 so it does not read as a browser-visible failure
            # during play. Frontend (DecisionContext) already treats an empty
            # body as a fresh draft.
            return Response({}, status=status.HTTP_200_OK)
        serializer = DecisionSubmissionSerializer(submission)
        return Response(serializer.data)

    def post(self, request, game_id, team_id, round_number):
        return self._upsert(request, game_id, team_id, round_number)

    def put(self, request, game_id, team_id, round_number):
        return self._upsert(request, game_id, team_id, round_number)

    def _upsert(self, request, game_id, team_id, round_number):
        rnd = _get_round(game_id, round_number)
        team = _get_team(team_id)
        submission = DecisionSubmission.objects.filter(
            team=team, round=rnd,
        ).first()

        data = request.data.copy()
        data['team'] = team.id
        data['round'] = rnd.id

        if submission:
            if submission.status == 'locked':
                return Response(
                    {'detail': 'Submission is locked. Unlock before editing.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer = DecisionSubmissionSerializer(
                submission, data=data, partial=True,
            )
        else:
            serializer = DecisionSubmissionSerializer(data=data)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        resp_status = status.HTTP_200_OK if submission else status.HTTP_201_CREATED
        return Response(serializer.data, status=resp_status)


# ---------------------------------------------------------------------------
# Partial Update by Decision Type
# ---------------------------------------------------------------------------

# Map decision_type URL param → (related_name, serializer, is_one_to_one)
_TYPE_MAP = {
    'budget':           ('budget_allocation',     DecisionBudgetAllocationSerializer,     True),
    'rd':               ('rd_investments',         DecisionRDInvestmentSerializer,          False),
    'platforms':        ('platform_developments',  DecisionPlatformDevelopmentSerializer,   False),
    'products':         ('product_creates',        DecisionProductCreateSerializer,         False),
    'product-retires':  ('product_retires',        DecisionProductRetireSerializer,         False),
    'marketing':        ('marketing_decisions',    DecisionMarketingSerializer,             False),
    'market-entry':     ('market_entries',         DecisionMarketEntrySerializer,           False),
    'financing':        ('financing',              DecisionFinancingSerializer,             True),
    'plants':           ('plant_decisions',        DecisionPlantSerializer,                 False),
    'partnerships':     ('partnerships',           DecisionPartnershipSerializer,           False),
    'acquisitions':     ('acquisitions',           DecisionAcquisitionSerializer,           False),
    'esg':              ('esg',                    DecisionESGSerializer,                   True),
    'event-responses':  ('event_responses',        DecisionEventResponseSerializer,         False),
    'talent':           ('talent',                 DecisionTalentSerializer,                True),
}


class DecisionPartialUpdateView(APIView):
    """
    PATCH — update a single decision type within a submission.
    """
    permission_classes = [IsTeamMember, IsRoundOpen]

    def patch(self, request, game_id, team_id, round_number, decision_type):
        if decision_type not in _TYPE_MAP:
            return Response(
                {'detail': f'Unknown decision type: {decision_type}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rnd = _get_round(game_id, round_number)
        team = _get_team(team_id)
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd,
            defaults={'status': 'draft'},
        )
        if submission.status == 'locked':
            return Response(
                {'detail': 'Submission is locked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        related_name, serializer_cls, is_one_to_one = _TYPE_MAP[decision_type]

        # Build the nested data dict with just this one type
        payload_key = related_name
        if isinstance(request.data, list):
            # Raw list sent directly as body
            nested_data = request.data
        else:
            nested_data = request.data.get(payload_key)
            if nested_data is None:
                # Also accept the data directly without wrapping
                nested_data = request.data

        # Validate
        if is_one_to_one:
            ser = serializer_cls(data=nested_data)
            ser.is_valid(raise_exception=True)
            validated = ser.validated_data
            model_cls = serializer_cls.Meta.model
            model_cls.objects.filter(submission=submission).delete()
            model_cls.objects.create(submission=submission, **validated)
        else:
            if not isinstance(nested_data, list):
                nested_data = [nested_data]
            validated_items = []
            for item in nested_data:
                ser = serializer_cls(data=item)
                ser.is_valid(raise_exception=True)
                validated_items.append(ser.validated_data)
            model_cls = serializer_cls.Meta.model
            model_cls.objects.filter(submission=submission).delete()
            if validated_items:
                objs = [model_cls(submission=submission, **v) for v in validated_items]
                model_cls.objects.bulk_create(objs)

        # Log the change for team notifications
        try:
            from core.utils.auth_context import get_request_user_id
            user_id = get_request_user_id(request)
            if user_id:
                from core.models.cc21_models import DecisionChangeLog
                from core.models.core import User as UserModel
                u = UserModel.objects.filter(id=user_id).first()
                if u:
                    _PG = {
                        'budget': 'Finance', 'rd': 'R&D', 'platforms': 'R&D',
                        'products': 'Products', 'product-retires': 'Products',
                        'marketing': 'Marketing', 'market-entry': 'Market Strategy',
                        'financing': 'Finance', 'plants': 'Market Strategy',
                        'partnerships': 'Corporate Strategy', 'acquisitions': 'Corporate Strategy',
                        'esg': 'Corporate Strategy', 'event-responses': 'Events',
                        'research': 'Research', 'talent': 'Corporate Strategy',
                    }
                    pg = _PG.get(decision_type, decision_type)
                    DecisionChangeLog.objects.create(
                        team=team, user=u, round_number=round_number,
                        page=pg,
                        change_description=f'Updated {pg} decisions',
                        change_data={'decision_type': decision_type},
                    )
        except Exception:
            pass

        # Return updated submission
        submission.refresh_from_db()
        return Response(DecisionSubmissionSerializer(submission).data)


# ---------------------------------------------------------------------------
# Lock / Unlock
# ---------------------------------------------------------------------------

class DecisionLockView(APIView):
    """POST — lock the submission after full validation."""
    permission_classes = [IsTeamMember, IsRoundOpen]

    def post(self, request, game_id, team_id, round_number):
        rnd = _get_round(game_id, round_number)
        submission = DecisionSubmission.objects.filter(
            team_id=team_id, round=rnd,
        ).first()

        if not submission:
            return Response(
                {'detail': 'No submission exists.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if submission.status == 'locked':
            return Response(
                {'detail': 'Already locked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Run full validation
        errors = self._full_validate(submission)
        if errors:
            return Response(
                {'detail': 'Validation failed.', 'errors': errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submission.status = 'locked'
        submission.locked_at = timezone.now()
        # locked_by left null — our auth uses X-User-Id, not Django auth
        submission.save()

        # Generate pre-lock instructor alerts
        try:
            from core.engine.instructor_alerts import generate_pre_lock_alerts
            game = Game.objects.get(id=game_id)
            team = Team.objects.get(id=team_id)
            generate_pre_lock_alerts(game, team, submission)
        except Exception:
            pass  # Don't block locking if alert generation fails

        return Response(DecisionSubmissionSerializer(submission).data)

    def _full_validate(self, submission):
        """
        Run hard validation for locking. Returns list of error strings.
        """
        errors = []
        team = submission.team
        game = team.game
        scenario = game.scenario

        # Budget allocation must exist
        try:
            budget = submission.budget_allocation
        except DecisionBudgetAllocation.DoesNotExist:
            errors.append('Budget allocation is required before locking.')
            return errors

        # Budget fields >= 0
        for field in ('rd_budget', 'marketing_budget', 'strategy_budget'):
            if getattr(budget, field) < 0:
                errors.append(f'{field} must be >= 0.')

        # Total budget vs available cash (hard limit — can't spend money you don't have)
        total_budget = budget.rd_budget + budget.marketing_budget + budget.strategy_budget
        if total_budget > team.cash_on_hand:
            errors.append(
                f'Total budget (${total_budget:,.2f}) exceeds available cash (${team.cash_on_hand:,.2f}).'
            )

        # R&D investments: total <= rd_budget
        rd_total = sum(
            inv.amount for inv in submission.rd_investments.all()
        )
        if rd_total > budget.rd_budget:
            errors.append(
                f'R&D investments (${rd_total:,.2f}) exceed R&D budget (${budget.rd_budget:,.2f}).'
            )

        # R&D: validate team_platform belongs to team
        for inv in submission.rd_investments.all():
            if inv.team_platform.team_id != team.id:
                errors.append(f'R&D investment references a platform not owned by this team.')
            if inv.team_platform.status != 'active':
                errors.append(f'R&D investment on inactive platform "{inv.team_platform}".')
            if inv.feature.layer != 'platform':
                errors.append(f'R&D feature "{inv.feature.name}" is not a platform-layer feature.')
            if inv.method == 'license' and hasattr(inv.feature, 'is_licensable') and not inv.feature.is_licensable:
                errors.append(f'Feature "{inv.feature.name}" cannot be licensed.')
            # Check ceiling
            ceiling = PlatformFeatureCeiling.objects.filter(
                platform_generation=inv.team_platform.platform_generation,
                feature=inv.feature,
            ).first()
            if ceiling:
                current_level = TeamPlatformFeatureLevel.objects.filter(
                    team_platform=inv.team_platform, feature=inv.feature,
                ).values_list('current_level', flat=True).first() or Decimal('0')
                if current_level >= ceiling.ceiling_value:
                    errors.append(
                        f'Feature "{inv.feature.name}" is already at ceiling '
                        f'({ceiling.ceiling_value}) on this platform generation.'
                    )

        # Platform development: validate generation
        for pd in submission.platform_developments.all():
            if pd.platform_generation.scenario_id != scenario.id:
                errors.append(f'Platform generation "{pd.platform_generation.name}" is not in this scenario.')
            if pd.platform_generation.unlock_round > game.current_round:
                errors.append(
                    f'Platform "{pd.platform_generation.name}" not unlocked yet '
                    f'(unlocks round {pd.platform_generation.unlock_round}).'
                )
            existing = TeamPlatform.objects.filter(
                team=team, platform_generation=pd.platform_generation,
            ).exclude(status='retired')
            if existing.exists():
                errors.append(f'Team already has platform "{pd.platform_generation.name}".')

        # Product creates: validate platform and limits
        active_products = TeamProduct.objects.filter(team=team, status='active').count()
        for pc in submission.product_creates.all():
            if pc.team_platform.team_id != team.id:
                errors.append('Product create references a platform not owned by this team.')
            if pc.team_platform.status != 'active':
                errors.append(f'Cannot create product on inactive platform.')
            # Check max products
            if active_products + 1 > scenario.max_products_total:
                errors.append(f'Would exceed max products ({scenario.max_products_total}).')
            # Check target markets have presence
            for mid in (pc.target_market_ids or []):
                if not TeamMarketPresence.objects.filter(
                    team=team, market_id=mid, status='active',
                ).exists():
                    errors.append(f'Product "{pc.product_name}" targets market {mid} where team has no active presence.')

        # Product retires: validate ownership
        for pr in submission.product_retires.all():
            if pr.team_product.team_id != team.id:
                errors.append('Product retire references a product not owned by this team.')
            if pr.team_product.status != 'active':
                errors.append(f'Product "{pr.team_product.name}" is not active.')

        # Marketing: channel pcts, budget
        marketing_total = Decimal('0')
        for md in submission.marketing_decisions.all():
            if md.team_product.team_id != team.id:
                errors.append(f'Marketing decision references product not owned by team.')
            ch_sum = md.channel_digital_pct + md.channel_traditional_pct + md.channel_trade_pct
            if abs(ch_sum - Decimal('1.0')) > Decimal('0.001'):
                errors.append(
                    f'Marketing for "{md.team_product.name}" in {md.market.name}: '
                    f'channel percentages sum to {ch_sum}, must be 1.0.'
                )
            if md.retail_price <= 0:
                errors.append(f'Retail price must be > 0 for "{md.team_product.name}" in {md.market.name}.')
            marketing_total += md.promotion_budget + md.distribution_investment

        if marketing_total > budget.marketing_budget:
            errors.append(
                f'Marketing spend (${marketing_total:,.2f}) exceeds marketing budget (${budget.marketing_budget:,.2f}).'
            )

        # Market entry: validate actions
        for me in submission.market_entries.all():
            presence = TeamMarketPresence.objects.filter(
                team=team, market=me.market,
            ).exclude(status='exited').first()
            if me.action == 'enter' and presence:
                errors.append(f'Already have presence in {me.market.name}; cannot enter again.')
            if me.action in ('change_mode', 'exit') and not presence:
                errors.append(f'No active presence in {me.market.name}; cannot {me.action}.')
            if me.action == 'enter' and me.initial_investment < me.entry_mode.capital_requirement:
                errors.append(
                    f'Entry investment for {me.market.name} (${me.initial_investment:,.2f}) is below '
                    f'minimum (${me.entry_mode.capital_requirement:,.2f}).'
                )

        # Core Round 1 decisions must be explicit before locking.
        if submission.product_creates.count() == 0 and submission.product_retires.count() == 0:
            errors.append('Product Portfolio is required before locking.')

        active_product_markets = TeamProductMarket.objects.filter(
            team_product__team=team, team_product__status='active', is_active=True,
        ).count()
        marketing_count = submission.marketing_decisions.count()
        if active_product_markets > 0 and marketing_count < active_product_markets:
            errors.append('Marketing Mix is required for all active product-market combinations before locking.')
        elif active_product_markets == 0:
            errors.append('Marketing Mix requires at least one active product-market combination before locking.')

        strategy_configured = (
            submission.market_entries.count()
            + submission.plant_decisions.count()
            + submission.partnerships.count()
            + submission.acquisitions.count()
        ) > 0
        try:
            submission.esg
            strategy_configured = True
        except DecisionESG.DoesNotExist:
            pass
        if not strategy_configured:
            errors.append('Strategy Mix is required before locking.')

        # Financing: debt ceiling
        try:
            fin = submission.financing
            max_ratio = Decimal('2.0')
            cfg = ScenarioConfig.objects.filter(
                scenario=scenario, config_key='max_debt_to_equity_ratio',
            ).first()
            if cfg:
                max_ratio = Decimal(cfg.config_value)
            projected_debt = team.total_debt + fin.new_debt - fin.debt_repayment
            if fin.debt_repayment > team.total_debt:
                errors.append(
                    f'Debt repayment (${fin.debt_repayment:,.2f}) exceeds outstanding debt (${team.total_debt:,.2f}).'
                )
            projected_equity = team.total_equity + fin.new_equity
            if projected_equity > 0 and projected_debt / projected_equity > max_ratio:
                errors.append(
                    f'Projected debt-to-equity ratio ({projected_debt/projected_equity:.2f}) '
                    f'exceeds max ({max_ratio}).'
                )
            total_dividends = fin.dividend_per_share * team.shares_outstanding
            # Simple check: dividends shouldn't exceed equity
            if total_dividends > projected_equity:
                errors.append(
                    f'Total dividends (${total_dividends:,.2f}) exceed projected equity.'
                )
        except DecisionFinancing.DoesNotExist:
            pass  # Financing is optional

        # (Research budget removed — research queries are free)

        # ESG: total <= strategy_budget (shared with other strategy items)
        try:
            esg = submission.esg
            esg_total = esg.environmental_investment + esg.social_investment
            # Strategy budget is shared — don't validate in isolation here,
            # but flag obvious overspend
        except DecisionESG.DoesNotExist:
            pass

        # Projected ending cash check
        projected_cash = team.cash_on_hand - total_budget
        try:
            fin = submission.financing
            projected_cash += fin.new_debt + fin.new_equity - fin.debt_repayment
            projected_cash -= fin.dividend_per_share * team.shares_outstanding
        except DecisionFinancing.DoesNotExist:
            pass
        if projected_cash < 0:
            errors.append(
                f'Projected ending cash is negative (${projected_cash:,.2f}). '
                f'Increase revenue or raise financing.'
            )

        # CC-32A: Check mandatory communication assignments
        try:
            from core.models.cc32_models import CommunicationAssignment, TeamCommunication
            game = submission.round.game
            scenario = game.scenario
            current_round = submission.round.round_number

            for ca in CommunicationAssignment.objects.filter(scenario=scenario, is_mandatory=True):
                triggered = False
                if ca.trigger_type == 'ROUND_MILESTONE':
                    triggered = (ca.trigger_condition or {}).get('round') == current_round
                elif ca.trigger_type == 'EVENT_BASED':
                    categories = (ca.trigger_condition or {}).get('event_category', [])
                    if isinstance(categories, str):
                        categories = [categories]
                    from core.models.results import EventInstance
                    triggered = EventInstance.objects.filter(
                        game=game, round_number=current_round,
                        event_template__category__in=categories,
                    ).exists()

                if triggered:
                    submitted = TeamCommunication.objects.filter(
                        game=game, team=submission.team, round=submission.round,
                        assignment=ca, is_draft=False,
                    ).exists()
                    if not submitted:
                        errors.append(
                            f'Mandatory communication "{ca.name}" must be submitted before locking.'
                        )
        except Exception:
            pass  # Don't block locking if communication check fails

        return errors


class DecisionUnlockView(APIView):
    """POST — instructor-only unlock of a locked submission."""
    permission_classes = [IsInstructor]

    def post(self, request, game_id, team_id, round_number):
        rnd = _get_round(game_id, round_number)
        submission = get_object_or_404(
            DecisionSubmission, team_id=team_id, round=rnd,
        )
        if submission.status != 'locked':
            return Response(
                {'detail': 'Submission is not locked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        submission.status = 'draft'
        submission.locked_at = None
        submission.locked_by = None
        submission.save()
        return Response(DecisionSubmissionSerializer(submission).data)


# ---------------------------------------------------------------------------
# Decision Summary
# ---------------------------------------------------------------------------

class DecisionSummaryView(APIView):
    """GET — checklist status for the Decision Summary page."""
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id, round_number):
        language = get_user_language(request)
        rnd = _get_round(game_id, round_number)

        # Supply-chain categories are independent of the main decision draft (UX #7).
        from core.models.sc_decisions import (
            SourcingAllocation as _SA, LogisticsDecision as _LD,
            TradeFinanceDecision as _TF, SinosureEnrollment as _SE,
            FXHedgeDecision as _FX, InventoryDecision as _INV, ContingencyPlan as _CP,
        )

        def _sc_cfg(exists):
            return {'status': 'configured' if exists else 'empty', 'warnings': []}
        sc_categories = {
            'sourcing': _sc_cfg(_SA.objects.filter(team_id=team_id, round=rnd).exists()),
            'logistics': _sc_cfg(_LD.objects.filter(team_id=team_id, round=rnd).exists()),
            'trade_finance': _sc_cfg(
                _TF.objects.filter(team_id=team_id, round=rnd).exists()
                or _SE.objects.filter(team_id=team_id, round=rnd).exists()
                or _FX.objects.filter(team_id=team_id, round=rnd).exists()),
            'inventory': _sc_cfg(
                _INV.objects.filter(team_id=team_id, round=rnd).exists()
                or _CP.objects.filter(team_id=team_id, round=rnd).exists()),
        }

        submission = DecisionSubmission.objects.filter(
            team_id=team_id, round=rnd,
        ).first()

        if not submission:
            return Response({
                'submission_status': None,
                'categories': sc_categories,
                'can_lock': False,
                'lock_blockers': ['No submission created yet.'],
                'budget_summary': None,
            })

        team = _get_team(team_id)
        categories = dict(sc_categories)
        lock_blockers = []

        # Budget
        try:
            budget = submission.budget_allocation
            total_budget = budget.rd_budget + budget.marketing_budget + budget.strategy_budget
            budget_warnings = []
            budget_errors = []
            if total_budget > team.cash_on_hand:
                budget_errors.append(f'Total budget exceeds available cash.')
            for f in ('rd_budget', 'marketing_budget', 'strategy_budget'):
                if getattr(budget, f) == 0:
                    budget_warnings.append(f'{f} is 0.')
            if budget_errors:
                categories['budget'] = {'status': 'error', 'errors': budget_errors, 'warnings': budget_warnings}
                lock_blockers.extend(budget_errors)
            else:
                categories['budget'] = {'status': 'configured', 'warnings': budget_warnings}
        except DecisionBudgetAllocation.DoesNotExist:
            categories['budget'] = {'status': 'empty', 'warnings': []}
            lock_blockers.append('Budget allocation required.')

        # R&D
        rd_count = submission.rd_investments.count()
        pd_count = submission.platform_developments.count()
        if rd_count > 0 or pd_count > 0:
            rd_warnings = []
            if rd_count == 0:
                rd_warnings.append('No R&D investment this round.')
            categories['rd'] = {'status': 'configured', 'warnings': rd_warnings}
        else:
            categories['rd'] = {'status': 'empty', 'warnings': ['No R&D investment this round.']}

        # Products
        pc_count = submission.product_creates.count()
        pr_count = submission.product_retires.count()
        if pc_count > 0 or pr_count > 0:
            categories['products'] = {'status': 'configured', 'warnings': []}
        else:
            categories['products'] = {'status': 'empty', 'warnings': []}

        # Marketing
        mkt_count = submission.marketing_decisions.count()
        active_product_markets = TeamProductMarket.objects.filter(
            team_product__team=team, team_product__status='active', is_active=True,
        ).count()
        if mkt_count > 0:
            if mkt_count < active_product_markets:
                categories['marketing'] = {
                    'status': 'partial',
                    'warnings': [f'{active_product_markets - mkt_count} product-market(s) not configured.'],
                    'configured_count': mkt_count,
                    'total_required': active_product_markets,
                }
            else:
                categories['marketing'] = {'status': 'configured', 'warnings': []}
        else:
            categories['marketing'] = {
                'status': 'empty',
                'warnings': [],
                'configured_count': 0,
                'total_required': active_product_markets,
            }

        # Strategy
        me_count = submission.market_entries.count()
        pl_count = submission.plant_decisions.count()
        pa_count = submission.partnerships.count()
        acq_count = submission.acquisitions.count()
        strategy_configured = me_count + pl_count + pa_count + acq_count > 0
        try:
            submission.esg
            strategy_configured = True
        except DecisionESG.DoesNotExist:
            pass

        strategy_warnings = []

        # Check for markets with presence but no products or marketing decisions
        active_presences = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).select_related('market')
        # Also include markets being entered this round
        entering_market_ids = set(
            me.market_id for me in submission.market_entries.filter(action='enter')
        ) if me_count > 0 else set()

        marketed_market_ids = set(
            md.market_id for md in submission.marketing_decisions.all()
        )
        product_market_ids = set(
            tpm.market_id for tpm in TeamProductMarket.objects.filter(
                team_product__team=team, team_product__status='active', is_active=True,
            )
        )

        for presence in active_presences:
            mid = presence.market_id
            mname = presence.market.name
            has_products = mid in product_market_ids
            has_marketing = mid in marketed_market_ids
            if not has_products:
                strategy_warnings.append(
                    f"You're operating in {mname} but have no products assigned there. "
                    f"Go to Product Portfolio to add a target market."
                )
            elif not has_marketing:
                strategy_warnings.append(
                    f"You have products in {mname} but no marketing decisions configured. "
                    f"Go to Marketing Mix to set pricing, production, and promotion."
                )

        for mid in entering_market_ids:
            if mid not in product_market_ids and mid not in set(p.market_id for p in active_presences):
                mkt = MarketDefinition.objects.filter(pk=mid).first()
                mname = get_localized_field(mkt, 'name', language) if mkt else f"Market {mid}"
                strategy_warnings.append(
                    f"You're entering {mname} this round but have no products assigned there yet."
                )

        categories['strategy'] = {
            'status': 'configured' if strategy_configured else 'empty',
            'warnings': strategy_warnings,
        }

        # Financing is optional unless a saved financing decision creates a hard error.
        try:
            fin = submission.financing
            fin_errors = []
            # Projected cash check
            try:
                budget = submission.budget_allocation
                total_budget = budget.rd_budget + budget.marketing_budget + budget.strategy_budget + budget.research_budget
                projected_cash = team.cash_on_hand - total_budget
                projected_cash += fin.new_debt + fin.new_equity - fin.debt_repayment
                projected_cash -= fin.dividend_per_share * team.shares_outstanding
                if projected_cash < 0:
                    fin_errors.append(
                        f'Projected ending cash is negative (${float(projected_cash):,.0f}). '
                        f'Increase revenue or raise financing.'
                    )
            except DecisionBudgetAllocation.DoesNotExist:
                pass
            if fin_errors:
                categories['financing'] = {'status': 'error', 'errors': fin_errors}
                lock_blockers.extend(fin_errors)
            else:
                categories['financing'] = {'status': 'configured', 'warnings': []}
        except DecisionFinancing.DoesNotExist:
            categories['financing'] = {
                'status': 'configured',
                'warnings': ['No financing changes this round.'],
                'optional': True,
            }

        required_lock_categories = {
            'products': 'Product Portfolio is required before locking.',
            'marketing': 'Marketing Mix is required before locking.',
            'strategy': 'Strategy Mix is required before locking.',
        }
        for key, message in required_lock_categories.items():
            if categories.get(key, {}).get('status') != 'configured':
                lock_blockers.append(message)

        can_lock = len(lock_blockers) == 0

        # Budget summary
        budget_summary = None
        try:
            budget = submission.budget_allocation
            rd_spent = sum(i.amount for i in submission.rd_investments.all())
            mkt_spent = sum(
                m.promotion_budget + m.distribution_investment
                for m in submission.marketing_decisions.all()
            )
            strategy_spent = sum(me.initial_investment for me in submission.market_entries.all())
            strategy_spent += sum(p.annual_investment for p in submission.partnerships.all())
            strategy_spent += sum(a.acquisition_target.base_acquisition_cost for a in submission.acquisitions.select_related('acquisition_target').all())
            try:
                esg = submission.esg
                strategy_spent += esg.environmental_investment + esg.social_investment
            except DecisionESG.DoesNotExist:
                pass
            total_allocated = budget.rd_budget + budget.marketing_budget + budget.strategy_budget

            budget_summary = {
                'rd_allocated': float(budget.rd_budget),
                'rd_spent': float(rd_spent),
                'marketing_allocated': float(budget.marketing_budget),
                'marketing_spent': float(mkt_spent),
                'strategy_allocated': float(budget.strategy_budget),
                'strategy_spent': float(strategy_spent),
                'total_available': float(team.cash_on_hand),
                'total_allocated': float(total_allocated),
                'unallocated': float(team.cash_on_hand - total_allocated),
            }
        except DecisionBudgetAllocation.DoesNotExist:
            pass

        return Response({
            'submission_status': submission.status,
            'categories': categories,
            'can_lock': can_lock,
            'lock_blockers': lock_blockers,
            'budget_summary': budget_summary,
        })


# ---------------------------------------------------------------------------
# Context Endpoints (Read-Only)
# ---------------------------------------------------------------------------

class RDContextView(APIView):
    """GET — data needed for the R&D decision page (CC-17 slot-based UI)."""
    permission_classes = [IsTeamMember]

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_config(scenario, key, default):
        try:
            return ScenarioConfig.objects.get(scenario=scenario, config_key=key).config_value
        except ScenarioConfig.DoesNotExist:
            return str(default)

    def _calculate_rd_budget(self, team, game):
        prev_round = game.current_round - 1
        profit_share = Decimal('0')
        prev_net_income = Decimal('0')
        if prev_round >= 0:
            prev_fin = RoundResultFinancials.objects.filter(
                game=game, team=team, round_number=prev_round,
            ).first()
            if prev_fin and prev_fin.net_income and prev_fin.net_income > 0:
                prev_net_income = prev_fin.net_income
                profit_share = prev_fin.net_income * Decimal('0.20')
        base_allocation = Decimal(self._get_config(game.scenario, 'rd_base_budget', '1500000'))
        total = profit_share + base_allocation
        return total, profit_share, base_allocation, prev_net_income

    @staticmethod
    def _build_cost_schedule(feature, platform_generation, current_level, ceiling_value):
        """Cost schedule for levels above current up to ceiling."""
        current = int(float(current_level))
        ceiling = int(float(ceiling_value))
        schedule = []
        level_costs = FeatureLevelCost.objects.filter(
            feature=feature,
            platform_generation=platform_generation,
            level__gt=current,
            level__lte=ceiling,
        ).order_by('level')
        cumulative = Decimal('0')
        for lc in level_costs:
            cumulative += lc.incremental_cost
            schedule.append({
                'level': lc.level,
                'incremental_cost': float(lc.incremental_cost),
                'cumulative_from_current': float(cumulative),
            })
        return schedule

    @staticmethod
    def _check_generation_prerequisites(team, target_gen, game, scenario):
        """Return (all_met: bool, details: list[dict])."""
        details = []
        all_met = True
        prev_gen_order = target_gen.generation_order - 1

        # 1. Round requirement
        round_met = game.current_round >= target_gen.unlock_round
        details.append({
            'requirement': f'Round {target_gen.unlock_round} or later',
            'met': round_met,
            'detail': f'Current round: {game.current_round}',
        })
        if not round_met:
            all_met = False

        # 2. Previous generation must be active (can't skip)
        if prev_gen_order > 1:
            has_prev = TeamPlatform.objects.filter(
                team=team,
                platform_generation__generation_order=prev_gen_order,
                status='active',
            ).exists()
            details.append({
                'requirement': f'Gen {prev_gen_order} must be active',
                'met': has_prev,
                'detail': 'Active' if has_prev else 'Not yet developed',
            })
            if not has_prev:
                all_met = False

        # 3. Technology capability threshold
        if target_gen.generation_order == 2:
            min_feats = int(RDContextView._get_config_static(scenario, 'gen2_min_features_at_level', 3))
            min_lvl = int(RDContextView._get_config_static(scenario, 'gen2_min_feature_level', 4))
        elif target_gen.generation_order == 3:
            min_feats = int(RDContextView._get_config_static(scenario, 'gen3_min_features_at_level', 4))
            min_lvl = int(RDContextView._get_config_static(scenario, 'gen3_min_feature_level', 6))
        else:
            min_feats, min_lvl = 0, 0

        if min_feats > 0:
            prev_platform = TeamPlatform.objects.filter(
                team=team,
                platform_generation__generation_order=prev_gen_order,
                status='active',
            ).first()
            qualifying = 0
            if prev_platform:
                for fl in TeamPlatformFeatureLevel.objects.filter(team_platform=prev_platform):
                    ceil = PlatformFeatureCeiling.objects.filter(
                        platform_generation=prev_platform.platform_generation,
                        feature=fl.feature,
                    ).first()
                    if ceil and ceil.ceiling_value > 0 and float(fl.current_level) >= min_lvl:
                        qualifying += 1
            tech_met = qualifying >= min_feats
            details.append({
                'requirement': f'At least {min_feats} features at level {min_lvl}+',
                'met': tech_met,
                'detail': f'{qualifying} of {min_feats} features qualify',
            })
            if not tech_met:
                all_met = False

        return all_met, details

    @staticmethod
    def _get_config_static(scenario, key, default):
        try:
            return ScenarioConfig.objects.get(scenario=scenario, config_key=key).config_value
        except ScenarioConfig.DoesNotExist:
            return str(default)

    # ------------------------------------------------------------------
    # main view
    # ------------------------------------------------------------------

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        team = _get_team(team_id)
        game = get_object_or_404(Game, pk=game_id)
        scenario = game.scenario

        # === OWNED PLATFORMS ===
        owned_platforms = []
        for tp in TeamPlatform.objects.filter(team=team).exclude(status='retired').select_related('platform_generation'):
            pdata = {
                'id': tp.id,
                'platform_generation_id': tp.platform_generation_id,
                'generation_name': get_localized_field(tp.platform_generation, 'name', language),
                'platform_name': tp.name or get_localized_field(tp.platform_generation, 'name', language),
                'generation_order': tp.platform_generation.generation_order,
                'status': tp.status,
            }

            if tp.status == 'in_development':
                pdata['development_method'] = tp.development_method
                pdata['rounds_remaining'] = tp.development_rounds_remaining
                pdata['completion_round'] = game.current_round + (tp.development_rounds_remaining or 0)
                # No feature details for in-development platforms
            elif tp.status == 'active':
                features = []
                for fl in tp.feature_levels.select_related('feature').all():
                    ceil_obj = PlatformFeatureCeiling.objects.filter(
                        platform_generation=tp.platform_generation,
                        feature=fl.feature,
                    ).first()
                    ceil_val = float(ceil_obj.ceiling_value) if ceil_obj else 0
                    if ceil_val <= 0:
                        continue  # skip locked features (ceiling=0)
                    features.append({
                        'feature_id': fl.feature_id,
                        'code': fl.feature.code,
                        'name': get_localized_field(fl.feature, 'name', language),
                        'current_level': float(fl.current_level),
                        'ceiling': ceil_val,
                        'is_licensable': getattr(fl.feature, 'is_licensable', True),
                        'license_cost_multiplier': float(fl.feature.license_cost_multiplier),
                        'cost_schedule': self._build_cost_schedule(
                            fl.feature, tp.platform_generation, fl.current_level, ceil_val
                        ),
                    })
                pdata['features'] = sorted(features, key=lambda f: f.get('code', ''))

            owned_platforms.append(pdata)

        # === LOCKED FEATURES (on current active platform) ===
        locked_features = []
        active_tp = TeamPlatform.objects.filter(team=team, status='active').select_related('platform_generation').first()
        if active_tp:
            current_gen_order = active_tp.platform_generation.generation_order
            # Find all features with ceiling=0 on current gen
            zero_ceilings = PlatformFeatureCeiling.objects.filter(
                platform_generation=active_tp.platform_generation,
                ceiling_value=0,
            ).select_related('feature')
            for zc in zero_ceilings:
                # Find which generation unlocks this feature
                unlock_gen = PlatformFeatureCeiling.objects.filter(
                    feature=zc.feature,
                    ceiling_value__gt=0,
                    platform_generation__scenario=scenario,
                    platform_generation__generation_order__gt=current_gen_order,
                ).select_related('platform_generation').order_by('platform_generation__generation_order').first()
                locked_features.append({
                    'name': get_localized_field(zc.feature, 'name', language),
                    'code': zc.feature.code,
                    'unlocked_at': get_localized_field(unlock_gen.platform_generation, 'name', language) if unlock_gen else 'Future generation',
                    'unlock_generation_order': unlock_gen.platform_generation.generation_order if unlock_gen else None,
                    'starting_level': float(unlock_gen.starting_value) if unlock_gen else 0,
                    'ceiling': float(unlock_gen.ceiling_value) if unlock_gen else 0,
                })

        # === UPGRADE OPTIONS (next generation only) ===
        upgrade_options = []
        current_gen_orders = set(
            tp.platform_generation.generation_order
            for tp in TeamPlatform.objects.filter(team=team).exclude(status='retired')
        )
        highest_owned_gen = max(current_gen_orders) if current_gen_orders else 1

        # Only show next gen, never skip
        next_gen = PlatformGenerationDefinition.objects.filter(
            scenario=scenario,
            generation_order=highest_owned_gen + 1,
        ).first()

        if next_gen:
            prereqs_met, prereq_details = self._check_generation_prerequisites(
                team, next_gen, game, scenario
            )

            # Determine new vs improved features
            current_gen_def = PlatformGenerationDefinition.objects.filter(
                scenario=scenario, generation_order=highest_owned_gen,
            ).first()
            new_features_unlocked = []
            improved_features = []
            if current_gen_def:
                for ceil in PlatformFeatureCeiling.objects.filter(
                    platform_generation=next_gen,
                ).select_related('feature'):
                    if ceil.ceiling_value <= 0:
                        continue
                    cur_ceil = PlatformFeatureCeiling.objects.filter(
                        platform_generation=current_gen_def,
                        feature=ceil.feature,
                    ).first()
                    if not cur_ceil or cur_ceil.ceiling_value == 0:
                        new_features_unlocked.append({
                            'name': get_localized_field(ceil.feature, 'name', language),
                            'code': ceil.feature.code,
                            'starting_level': float(ceil.starting_value),
                            'ceiling': float(ceil.ceiling_value),
                        })
                    elif ceil.ceiling_value > cur_ceil.ceiling_value:
                        improved_features.append({
                            'name': get_localized_field(ceil.feature, 'name', language),
                            'code': ceil.feature.code,
                            'current_ceiling': float(cur_ceil.ceiling_value),
                            'new_ceiling': float(ceil.ceiling_value),
                        })

            upgrade_options.append({
                'generation_id': next_gen.id,
                'name': get_localized_field(next_gen, 'name', language),
                'description': get_localized_field(next_gen, 'description', language),
                'generation_order': next_gen.generation_order,
                'prerequisites_met': prereqs_met,
                'prerequisites': prereq_details,
                'development_cost': float(next_gen.development_cost),
                'development_rounds': next_gen.development_rounds,
                'license_cost': float(next_gen.license_cost),
                'new_features_unlocked': new_features_unlocked,
                'improved_features': improved_features,
            })

        # === R&D BUDGET ===
        rd_budget, profit_share, base_allocation, prev_net_income = self._calculate_rd_budget(team, game)

        # === CURRENT INVESTMENTS (from draft submission) ===
        rd_spent = Decimal('0')
        current_investments = []
        max_slots = int(self._get_config(scenario, 'max_rd_investments_per_round', '5'))
        rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
        current_submission = None
        if rnd:
            current_submission = DecisionSubmission.objects.filter(team=team, round=rnd).first()
            if current_submission:
                for inv in current_submission.rd_investments.select_related('feature', 'team_platform').all():
                    cost = inv.calculated_cost if inv.calculated_cost else inv.amount
                    rd_spent += cost
                    current_investments.append({
                        'id': inv.id,
                        'feature_id': inv.feature_id,
                        'feature_name': get_localized_field(inv.feature, 'name', language),
                        'feature_code': inv.feature.code,
                        'team_platform_id': inv.team_platform_id,
                        'target_level': inv.target_level,
                        'method': inv.method if hasattr(inv, 'method') else 'in_house',
                        'cost': float(cost),
                    })

        used_slots = len(set(i['feature_id'] for i in current_investments))

        # === PENDING FEATURE GAINS ===
        pending = [
            {
                'feature_id': pg.feature_id,
                'feature_name': get_localized_field(pg.feature, 'name', language),
                'gain_amount': float(pg.gain_amount),
                'applies_round': pg.applies_round,
            }
            for pg in PendingFeatureGain.objects.filter(
                team_platform__team=team, applied=False,
            ).select_related('feature')
        ]

        # === AVAILABLE GENERATIONS (for Create Platform modal) ===
        # Show all generations the team could build on.
        # Gen 1 always available. Higher gens need prerequisites.
        available_generations = []
        owned_gen_orders = set(
            tp.platform_generation.generation_order
            for tp in TeamPlatform.objects.filter(team=team).exclude(status='retired')
        )
        for gen_def in PlatformGenerationDefinition.objects.filter(
            scenario=scenario,
        ).order_by('generation_order'):
            # Gen 3 hidden until Gen 2 is active
            if gen_def.generation_order == 3:
                has_gen2_active = TeamPlatform.objects.filter(
                    team=team,
                    platform_generation__generation_order=2,
                    status='active',
                ).exists()
                if not has_gen2_active:
                    continue

            # Check prerequisites for Gen 2+
            prereqs_met = True
            prereq_details = []
            if gen_def.generation_order > 1:
                prereqs_met, prereq_details = self._check_generation_prerequisites(
                    team, gen_def, game, scenario
                )

            # Features with ceiling > 0 and their cost schedules
            gen_features = []
            for pc in PlatformFeatureCeiling.objects.filter(
                platform_generation=gen_def,
            ).select_related('feature').order_by('feature__display_order', 'feature__id'):
                if pc.ceiling_value <= 0:
                    continue
                # Full cost schedule from level 1 to ceiling
                cost_schedule = []
                cumulative = Decimal('0')
                for lc in FeatureLevelCost.objects.filter(
                    feature=pc.feature,
                    platform_generation=gen_def,
                ).order_by('level'):
                    cumulative += lc.incremental_cost
                    cost_schedule.append({
                        'level': lc.level,
                        'incremental_cost': float(lc.incremental_cost),
                        'cumulative_cost': float(cumulative),
                    })
                gen_features.append({
                    'feature_id': pc.feature.id,
                    'code': pc.feature.code,
                    'name': get_localized_field(pc.feature, 'name', language),
                    'ceiling': int(pc.ceiling_value),
                    'starting_value': int(pc.starting_value),
                    'cost_schedule': cost_schedule,
                })

            team_already_owns = gen_def.generation_order in owned_gen_orders
            available_generations.append({
                'id': gen_def.id,
                'name': get_localized_field(gen_def, 'name', language),
                'generation_order': gen_def.generation_order,
                'description': get_localized_field(gen_def, 'description', language),
                'development_cost': float(gen_def.development_cost),
                'development_rounds': gen_def.development_rounds,
                'license_cost': float(gen_def.license_cost),
                'team_already_owns': team_already_owns,
                'prerequisites_met': prereqs_met,
                'prerequisites': prereq_details,
                'features': gen_features,
            })

        # Existing platform creation decisions in current draft
        platform_dev_decisions = []
        if current_submission:
            for pd in current_submission.platform_developments.select_related('platform_generation').all():
                platform_dev_decisions.append({
                    'id': pd.id,
                    'platform_name': pd.platform_name,
                    'generation_id': pd.platform_generation_id,
                    'generation_name': get_localized_field(pd.platform_generation, 'name', language),
                    'method': pd.method,
                    'committed_cost': float(pd.committed_cost),
                    'feature_levels': pd.feature_levels or {},
                })

        return Response({
            'owned_platforms': owned_platforms,
            'locked_features': locked_features,
            'upgrade_options': upgrade_options,
            'available_generations': available_generations,
            'platform_dev_decisions': platform_dev_decisions,
            'investment_slots': {
                'max': max_slots,
                'used': used_slots,
                'remaining': max_slots - used_slots,
            },
            'max_platform_features': int(self._get_config(scenario, 'max_platform_features', '5')),
            'current_investments': current_investments,
            'rd_budget': float(rd_budget),
            'rd_budget_remaining': float(rd_budget - rd_spent),
            'rd_spent': float(rd_spent),
            'budget_source': f"20% of previous round net profit ({float(prev_net_income):,.0f}) + base allocation ({float(base_allocation):,.0f})",
            'pending_feature_gains': pending,
        })


class ProductContextView(APIView):
    """GET — data needed for the Product Portfolio page."""
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        team = _get_team(team_id)
        game = get_object_or_404(Game, pk=game_id)
        scenario = game.scenario

        # Active platforms
        active_platforms = [
            {
                'id': tp.id,
                'name': tp.name or get_localized_field(tp.platform_generation, 'name', language),
                'status': tp.status,
            }
            for tp in TeamPlatform.objects.filter(
                team=team, status='active',
            ).select_related('platform_generation')
        ]

        # Base unit cost from scenario config
        from core.models.scenario import ScenarioConfig
        try:
            base_cost_cfg = float(ScenarioConfig.objects.get(
                scenario=scenario, config_key='base_unit_cost',
            ).config_value)
        except ScenarioConfig.DoesNotExist:
            base_cost_cfg = 50.0

        # Current round submission for retail prices
        current_prices = {}
        rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
        if rnd:
            sub = DecisionSubmission.objects.filter(team=team, round=rnd).first()
            if sub:
                for md in sub.marketing_decisions.all():
                    current_prices.setdefault(md.team_product_id, {})[md.market_id] = float(md.retail_price)

        # Existing products
        products = []
        for p in TeamProduct.objects.filter(team=team).select_related('team_platform__platform_generation'):
            markets = list(
                TeamProductMarket.objects.filter(
                    team_product=p,
                ).select_related('market').values('market_id', 'market__name', 'is_active')
            )
            # Feature levels inherited from parent platform (only features with ceiling > 0)
            feature_levels = []
            for fl in TeamPlatformFeatureLevel.objects.filter(
                team_platform=p.team_platform,
            ).select_related('feature'):
                ceil_obj = PlatformFeatureCeiling.objects.filter(
                    platform_generation=p.team_platform.platform_generation,
                    feature=fl.feature,
                ).first()
                if ceil_obj and ceil_obj.ceiling_value > 0:
                    feature_levels.append({
                        'feature_id': fl.feature_id,
                        'feature_name': get_localized_field(fl.feature, 'name', language),
                        'feature_code': fl.feature.code,
                        'current_level': float(fl.current_level),
                    })
            # Estimated unit cost: base × generation factor
            gen_order = p.team_platform.platform_generation.generation_order
            gen_factor = 1.0 + (gen_order - 1) * 0.20
            est_unit_cost = round(base_cost_cfg * gen_factor, 2)
            # Retail prices from current round decisions
            prices = current_prices.get(p.id, {})
            products.append({
                'id': p.id,
                'name': p.name,
                'platform_id': p.team_platform_id,
                'platform_name': p.team_platform.name or get_localized_field(p.team_platform.platform_generation, 'name', language),
                'positioning': p.positioning,
                'status': p.status,
                'markets': markets,
                'feature_levels': feature_levels,
                'est_unit_cost': est_unit_cost,
                'retail_prices': prices,
            })

        # Product limits
        active_count = TeamProduct.objects.filter(team=team, status='active').count()

        # Markets with active presence
        active_markets = [
            {
                'id': mp.market_id,
                'name': get_localized_field(mp.market, 'name', language),
            }
            for mp in TeamMarketPresence.objects.filter(
                team=team, status='active',
            ).select_related('market')
        ]

        return Response({
            'active_platforms': active_platforms,
            'products': products,
            'active_product_count': active_count,
            'max_products_total': scenario.max_products_total,
            'max_products_per_platform': scenario.max_products_per_platform,
            'active_markets': active_markets,
        })


class MarketingContextView(APIView):
    """GET — data needed for the Marketing Mix page."""
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        team = _get_team(team_id)
        game = get_object_or_404(Game, pk=game_id)

        # Active products with their markets
        product_markets = []
        for p in TeamProduct.objects.filter(team=team, status='active').select_related('team_platform__platform_generation'):
            markets = [
                {
                    'market_id': tpm.market_id,
                    'market__name': get_localized_field(tpm.market, 'name', language),
                }
                for tpm in TeamProductMarket.objects.filter(
                    team_product=p, is_active=True,
                ).select_related('market')
            ]
            # Feature levels for campaign focus selection (only features with ceiling > 0)
            feature_levels = []
            for fl in TeamPlatformFeatureLevel.objects.filter(
                team_platform=p.team_platform,
            ).select_related('feature'):
                ceil_obj = PlatformFeatureCeiling.objects.filter(
                    platform_generation=p.team_platform.platform_generation,
                    feature=fl.feature,
                ).first()
                if ceil_obj and ceil_obj.ceiling_value > 0:
                    feature_levels.append({
                        'feature_id': fl.feature_id,
                        'feature__name': get_localized_field(fl.feature, 'name', language),
                        'current_level': float(fl.current_level),
                    })
            product_markets.append({
                'product_id': p.id,
                'product_name': p.name,
                'positioning': p.positioning,
                'platform_name': p.team_platform.name or get_localized_field(p.team_platform.platform_generation, 'name', language),
                'markets': markets,
                'feature_levels': feature_levels,
            })

        # Platform features for campaign focus — only those with ceiling > 0 on team's active platform
        active_tp = TeamPlatform.objects.filter(team=team, status='active').select_related('platform_generation').first()
        if active_tp:
            available_feat_ids = set(
                PlatformFeatureCeiling.objects.filter(
                    platform_generation=active_tp.platform_generation,
                    ceiling_value__gt=0,
                ).values_list('feature_id', flat=True)
            )
            features = [
                {'id': f.id, 'name': get_localized_field(f, 'name', language), 'code': f.code}
                for f in FeatureDefinition.objects.filter(
                    scenario=game.scenario, layer='platform', id__in=available_feat_ids,
                ).order_by('display_order', 'id')
            ]
        else:
            features = [
                {'id': f.id, 'name': get_localized_field(f, 'name', language), 'code': f.code}
                for f in FeatureDefinition.objects.filter(
                    scenario=game.scenario, layer='platform',
                ).order_by('display_order', 'id')
            ]

        # Production capacity by market — combined plant + contract mfg
        capacity_map = {}
        for plant in TeamPlant.objects.filter(team=team, status='operational').select_related('market'):
            mid = plant.market_id
            if mid not in capacity_map:
                capacity_map[mid] = {
                    'market_id': mid,
                    'market_name': get_localized_field(plant.market, 'name', language),
                    'own_capacity': 0,
                    'contract_mfg_capacity': 0,
                    'contract_mfg_available': False,
                    'contract_mfg_cost_multiplier': 1.25,
                }
            capacity_map[mid]['own_capacity'] += plant.capacity_units

        for mkt in MarketDefinition.objects.filter(scenario=game.scenario, contract_mfg_available=True):
            mid = mkt.id
            if mid not in capacity_map:
                capacity_map[mid] = {
                    'market_id': mid,
                    'market_name': get_localized_field(mkt, 'name', language),
                    'own_capacity': 0,
                    'contract_mfg_capacity': 0,
                    'contract_mfg_available': False,
                    'contract_mfg_cost_multiplier': 1.25,
                }
            capacity_map[mid]['contract_mfg_available'] = True
            capacity_map[mid]['contract_mfg_capacity'] = mkt.contract_mfg_capacity_cap or 0
            capacity_map[mid]['contract_mfg_cost_multiplier'] = float(mkt.contract_mfg_cost_multiplier or 1.25)

        capacity = list(capacity_map.values())

        # Marketing budget remaining
        marketing_budget_remaining = None
        rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
        if rnd:
            sub = DecisionSubmission.objects.filter(team=team, round=rnd).first()
            if sub:
                try:
                    budget = sub.budget_allocation
                    mkt_spent = sum(
                        m.promotion_budget + m.distribution_investment
                        for m in sub.marketing_decisions.all()
                    )
                    marketing_budget_remaining = float(budget.marketing_budget - mkt_spent)
                except DecisionBudgetAllocation.DoesNotExist:
                    pass

        # Sales rep cost from scenario config
        try:
            sales_rep_cost = float(ScenarioConfig.objects.get(
                scenario=game.scenario, config_key='sales_rep_cost_per_round',
            ).config_value)
        except ScenarioConfig.DoesNotExist:
            sales_rep_cost = 100000

        # Previous round sales for revenue impact preview
        prev_round_sales = {}
        prev_round_decisions = {}
        prev_round_number = game.current_round - 1
        if prev_round_number >= 1:
            from core.models.results_financials import RoundResultProductMarket
            for r in RoundResultProductMarket.objects.filter(
                game=game, round_number=prev_round_number, team=team,
            ):
                key = f"{r.team_product_id}_{r.market_id}"
                prev_round_sales[key] = {
                    'units_sold': float(r.units_sold),
                    'units_produced': r.units_produced or 0,
                    'units_unsold': float(r.units_unsold) if r.units_unsold else 0,
                    'revenue': float(r.local_revenue),
                    'retail_price': float(r.retail_price),
                    'inventory_holding_cost': float(r.inventory_holding_cost) if r.inventory_holding_cost else 0,
                }

            # Previous round marketing decisions
            prev_rnd = Round.objects.filter(game=game, round_number=prev_round_number).first()
            if prev_rnd:
                prev_sub = DecisionSubmission.objects.filter(team=team, round=prev_rnd).first()
                if prev_sub:
                    for md in prev_sub.marketing_decisions.all():
                        key = f"{md.team_product_id}_{md.market_id}"
                        prev_round_decisions[key] = {
                            'retail_price': float(md.retail_price),
                            'promotion_budget': float(md.promotion_budget),
                            'production_volume': md.production_volume or 0,
                            'distribution_strategy': md.distribution_strategy,
                            'sales_team_count': md.sales_team_count or 0,
                            'channel_digital_pct': float(md.channel_digital_pct) if md.channel_digital_pct else 0.34,
                            'channel_traditional_pct': float(md.channel_traditional_pct) if md.channel_traditional_pct else 0.33,
                            'channel_trade_pct': float(md.channel_trade_pct) if md.channel_trade_pct else 0.33,
                        }

        return Response({
            'product_markets': product_markets,
            'production_capacity': capacity,
            'features': features,
            'marketing_budget_remaining': marketing_budget_remaining,
            'sales_rep_cost_per_round': sales_rep_cost,
            'prev_round_sales': prev_round_sales,
            'prev_round_decisions': prev_round_decisions,
        })


class StrategyContextView(APIView):
    """GET — data needed for the Strategy Mix page."""
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        team = _get_team(team_id)
        game = get_object_or_404(Game, pk=game_id)
        scenario = game.scenario

        # All markets with entry status
        markets = []
        for mkt in MarketDefinition.objects.filter(scenario=scenario):
            presence = TeamMarketPresence.objects.filter(
                team=team, market=mkt,
            ).exclude(status='exited').first()
            markets.append({
                'id': mkt.id,
                'code': mkt.code,
                'name': get_localized_field(mkt, 'name', language),
                'is_home_market': team.home_market_id == mkt.id if team.home_market_id else False,
                'entry_status': presence.status if presence else 'not_entered',
                'entry_mode': get_localized_field(presence.entry_mode, 'name', language) if presence else None,
                'allows_manufacturing': mkt.allows_manufacturing,
                'contract_mfg_available': mkt.contract_mfg_available,
            })

        # Active partnerships
        partnerships = [
            {
                'id': p.id,
                'market_id': p.market_id,
                'market_name': get_localized_field(p.market, 'name', language),
                'strategy_option_name': get_localized_field(p.strategy_option, 'name', language),
                'annual_investment': float(p.annual_investment),
                'status': p.status,
            }
            for p in TeamPartnershipState.objects.filter(
                team=team, status='active',
            ).select_related('market', 'strategy_option')
        ]

        # Plant status
        plants = [
            {
                'id': p.id,
                'market_id': p.market_id,
                'market_name': get_localized_field(p.market, 'name', language),
                'status': p.status,
                'capacity_units': p.capacity_units,
            }
            for p in TeamPlant.objects.filter(team=team).exclude(
                status='decommissioned',
            ).select_related('market')
        ]

        # Available entry modes and strategy options
        entry_modes = [
            {
                'id': em.id, 'name': get_localized_field(em, 'name', language),
                'code': em.code, 'capital_requirement': em.capital_requirement,
                'setup_rounds': em.setup_rounds, 'control_level': em.control_level,
                'risk_level': em.risk_level,
            }
            for em in EntryModeDefinition.objects.filter(scenario=scenario)
        ]
        strategy_options = [
            {
                'id': so.id, 'name': get_localized_field(so, 'name', language),
                'category': so.category, 'code': so.code,
                'capital_cost_base': so.capital_cost_base, 'is_reversible': so.is_reversible,
            }
            for so in StrategyOptionDefinition.objects.filter(scenario=scenario)
        ]

        # Financial summary
        financial = {
            'cash_on_hand': float(team.cash_on_hand),
            'total_debt': float(team.total_debt),
            'total_equity': float(team.total_equity),
            'shares_outstanding': team.shares_outstanding,
        }

        # Strategy budget remaining
        strategy_budget_remaining = None
        rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
        if rnd:
            sub = DecisionSubmission.objects.filter(team=team, round=rnd).first()
            if sub:
                try:
                    budget = sub.budget_allocation
                    strat_spent = sum(me.initial_investment for me in sub.market_entries.all())
                    strat_spent += sum(p.annual_investment for p in sub.partnerships.all())
                    strat_spent += sum(a.acquisition_target.base_acquisition_cost for a in sub.acquisitions.select_related('acquisition_target').all())
                    try:
                        esg = sub.esg
                        strat_spent += esg.environmental_investment + esg.social_investment
                    except DecisionESG.DoesNotExist:
                        pass
                    strategy_budget_remaining = float(budget.strategy_budget - strat_spent)
                except DecisionBudgetAllocation.DoesNotExist:
                    pass

        # Acquisition targets
        current_round = game.current_round
        acquisition_targets = []
        for target in AcquisitionTarget.objects.filter(scenario=scenario).select_related('market'):
            # Check if already acquired by anyone
            acquired_by = TeamAcquisition.objects.filter(
                acquisition_target=target,
            ).select_related('team').first()

            # Check prerequisites for this team
            has_presence = TeamMarketPresence.objects.filter(
                team=team, market=target.market,
            ).exclude(status='exited').exists()
            round_available = current_round >= target.min_round_available
            meets_presence = (not target.requires_market_presence) or has_presence

            acquisition_targets.append({
                'id': target.id,
                'target_name': get_localized_field(target, 'target_name', language),
                'description': get_localized_field(target, 'description', language),
                'market_id': target.market_id,
                'market_name': get_localized_field(target.market, 'name', language),
                'base_acquisition_cost': float(target.base_acquisition_cost),
                'market_share_gained': float(target.market_share_gained),
                'includes_plant': target.includes_plant,
                'plant_capacity': target.plant_capacity,
                'includes_distribution': target.includes_distribution,
                'distribution_reach_bonus': float(target.distribution_reach_bonus),
                'talent_bonus': target.talent_bonus,
                'min_round_available': target.min_round_available,
                'requires_market_presence': target.requires_market_presence,
                'integration_rounds': target.integration_rounds,
                'integration_cost_per_round': float(target.integration_cost_per_round),
                'available': round_available and meets_presence and not acquired_by,
                'locked_reasons': [
                    reason for reason in [
                        f'Available from Round {target.min_round_available}' if not round_available else None,
                        f'Requires presence in {get_localized_field(target.market, "name", language)}' if not meets_presence else None,
                        f'Already acquired by {acquired_by.team.name}' if acquired_by else None,
                    ] if reason
                ],
                'acquired_by_team': acquired_by.team.name if acquired_by else None,
                'acquired_by_self': acquired_by.team_id == team.id if acquired_by else False,
            })

        # Team's own acquisitions
        team_acquisitions = [
            {
                'id': acq.id,
                'target_name': get_localized_field(acq.acquisition_target, 'target_name', language),
                'market_name': get_localized_field(acq.acquisition_target.market, 'name', language),
                'acquired_round': acq.acquired_round,
                'integration_complete': acq.integration_complete,
                'integration_rounds_remaining': acq.integration_rounds_remaining,
                'total_cost_paid': float(acq.total_cost_paid),
                'integration_cost_per_round': float(acq.acquisition_target.integration_cost_per_round),
                'includes_plant': acq.acquisition_target.includes_plant,
                'plant_capacity': acq.acquisition_target.plant_capacity,
                'market_share_gained': float(acq.acquisition_target.market_share_gained),
            }
            for acq in TeamAcquisition.objects.filter(
                team=team,
            ).select_related('acquisition_target__market')
        ]

        return Response({
            'markets': markets,
            'partnerships': partnerships,
            'plants': plants,
            'entry_modes': entry_modes,
            'strategy_options': strategy_options,
            'financial': financial,
            'strategy_budget_remaining': strategy_budget_remaining,
            'acquisition_targets': acquisition_targets,
            'team_acquisitions': team_acquisitions,
        })


class FinanceContextView(APIView):
    """GET — data needed for the Finance Dashboard page."""
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id):
        team = _get_team(team_id)
        game = get_object_or_404(Game, pk=game_id)

        # Basic financial position
        financial = {
            'cash_on_hand': float(team.cash_on_hand),
            'total_debt': float(team.total_debt),
            'total_equity': float(team.total_equity),
            'shares_outstanding': team.shares_outstanding,
            'performance_index': float(team.performance_index),
        }

        # Auto-calculated budget: 20% of prior round profit + base amount
        from core.engine.utils import get_config
        budget_base = float(get_config(game.scenario, 'budget_base_amount', default=5000000))
        budget_profit_pct = float(get_config(game.scenario, 'budget_profit_pct', default=0.20))

        prev_financials = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=game.current_round - 1,
        ).first()
        prev_profit = float(prev_financials.net_income) if prev_financials else 0
        profit_share = max(prev_profit * budget_profit_pct, 0)
        auto_budget = budget_base + profit_share
        # Operating budget is formula-driven, independent of cash on hand.
        # Teams CAN spend over budget but receive a coherence penalty.
        total_budget_available = auto_budget

        # Budget allocation status
        budget_status = {
            'total_budget_available': total_budget_available,
            'auto_budget': auto_budget,
            'budget_base': budget_base,
            'profit_share': profit_share,
        }
        rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
        if rnd:
            sub = DecisionSubmission.objects.filter(team=team, round=rnd).first()
            if sub:
                try:
                    budget = sub.budget_allocation
                    rd_spent = sum(i.amount for i in sub.rd_investments.all())
                    mkt_spent = sum(
                        m.promotion_budget + m.distribution_investment
                        for m in sub.marketing_decisions.all()
                    )
                    strat_spent = sum(me.initial_investment for me in sub.market_entries.all())
                    strat_spent += sum(p.annual_investment for p in sub.partnerships.all())
                    strat_spent += sum(a.acquisition_target.base_acquisition_cost for a in sub.acquisitions.select_related('acquisition_target').all())
                    try:
                        esg = sub.esg
                        strat_spent += esg.environmental_investment + esg.social_investment
                    except DecisionESG.DoesNotExist:
                        pass
                    total_allocated = budget.rd_budget + budget.marketing_budget + budget.strategy_budget

                    # Projected cash
                    projected_cash = team.cash_on_hand - total_allocated
                    try:
                        fin = sub.financing
                        projected_cash += fin.new_debt + fin.new_equity - fin.debt_repayment
                        projected_cash -= fin.dividend_per_share * team.shares_outstanding
                    except DecisionFinancing.DoesNotExist:
                        pass

                    total_spent = float(rd_spent + mkt_spent + strat_spent)
                    over_budget = total_spent > total_budget_available

                    budget_status.update({
                        'rd_allocated': float(budget.rd_budget),
                        'rd_spent': float(rd_spent),
                        'marketing_allocated': float(budget.marketing_budget),
                        'marketing_spent': float(mkt_spent),
                        'strategy_allocated': float(budget.strategy_budget),
                        'strategy_spent': float(strat_spent),
                        'total_allocated': float(total_allocated),
                        'total_spent': total_spent,
                        'over_budget': over_budget,
                        'remaining': total_budget_available - total_spent,
                        'unallocated': float(team.cash_on_hand - total_allocated),
                        'projected_ending_cash': float(projected_cash),
                    })
                except DecisionBudgetAllocation.DoesNotExist:
                    pass

        # Key ratios
        debt_to_equity = float(team.total_debt / team.total_equity) if team.total_equity > 0 else None

        # Capital management data (CC-19)
        try:
            interest_rate = float(ScenarioConfig.objects.get(
                scenario=game.scenario, config_key='debt_interest_rate',
            ).config_value)
        except ScenarioConfig.DoesNotExist:
            interest_rate = 0.06
        try:
            max_de_ratio = float(ScenarioConfig.objects.get(
                scenario=game.scenario, config_key='max_debt_to_equity_ratio',
            ).config_value)
        except ScenarioConfig.DoesNotExist:
            max_de_ratio = 2.0

        equity_val = float(team.total_equity) if team.total_equity > 0 else 0
        max_total_debt = equity_val * max_de_ratio
        available_credit = max(max_total_debt - float(team.total_debt), 0)
        interest_per_round = float(team.total_debt) * interest_rate
        # Last round financials for share price and net income
        last_fin = RoundResultFinancials.objects.filter(
            game=game, team=team,
        ).order_by('-round_number').first()
        share_price = float(last_fin.share_price) if last_fin else 0
        last_net_income = float(last_fin.net_income) if last_fin else 0

        # Current financing decisions
        financing_draft = None
        if rnd:
            sub_fin = DecisionSubmission.objects.filter(team=team, round=rnd).first()
            if sub_fin:
                try:
                    fin = sub_fin.financing
                    financing_draft = {
                        'new_debt': float(fin.new_debt),
                        'debt_repayment': float(fin.debt_repayment),
                        'new_equity': float(fin.new_equity),
                        'dividend_per_share': float(fin.dividend_per_share),
                    }
                except DecisionFinancing.DoesNotExist:
                    pass

        capital = {
            'interest_rate': interest_rate,
            'max_de_ratio': max_de_ratio,
            'max_total_debt': max_total_debt,
            'available_credit': available_credit,
            'interest_per_round': interest_per_round,
            'share_price': share_price,
            'last_net_income': last_net_income,
            'financing_draft': financing_draft,
        }

        return Response({
            'financial': financial,
            'budget_status': budget_status,
            'key_ratios': {
                'debt_to_equity': debt_to_equity,
            },
            'capital': capital,
        })


class TalentContextView(APIView):
    """GET — current talent state and cost projections for the Talent & Workforce section."""
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id):
        from core.models.talent import TeamTalentState, DecisionTalent
        team = _get_team(team_id)
        game = get_object_or_404(Game, pk=game_id)

        current_round = game.current_round
        prev_round = current_round - 1

        pools = {}
        for pool in ['rd', 'commercial', 'operations']:
            state = TeamTalentState.objects.filter(
                team=team, talent_pool=pool, round_number=prev_round,
            ).first()
            pools[pool] = {
                'headcount': state.headcount if state else 0,
                'salary_level': state.salary_level if state else 3,
                'talent_level': float(state.talent_level) if state else 3.0,
                'turnover_rate': float(state.turnover_rate) if state else 0.10,
                'cumulative_training': float(state.cumulative_training) if state else 0,
            }

        # Check for existing draft decisions
        rnd = Round.objects.filter(game=game, round_number=current_round).first()
        draft = None
        if rnd:
            sub = DecisionSubmission.objects.filter(team=team, round=rnd).first()
            if sub:
                try:
                    td = sub.talent
                    draft = {
                        'rd_headcount': td.rd_headcount,
                        'rd_salary_level': td.rd_salary_level,
                        'rd_training_budget': float(td.rd_training_budget),
                        'commercial_headcount': td.commercial_headcount,
                        'commercial_salary_level': td.commercial_salary_level,
                        'commercial_training_budget': float(td.commercial_training_budget),
                        'operations_headcount': td.operations_headcount,
                        'operations_salary_level': td.operations_salary_level,
                        'operations_training_budget': float(td.operations_training_budget),
                    }
                except DecisionTalent.DoesNotExist:
                    pass

        # Salary cost table for UI cost calculator
        salary_table = {1: 15000, 2: 22500, 3: 30000, 4: 40000, 5: 55000}

        return Response({
            'pools': pools,
            'draft': draft,
            'salary_table': salary_table,
            'recruitment_cost_per_head': 10000,
            'layoff_cost_per_head': 20000,
        })

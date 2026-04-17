from django.contrib import admin

from core.models.scenario import (
    Scenario, ScenarioConfig,
    FeatureDefinition, PlatformGenerationDefinition,
    PlatformFeatureCeiling, MarketDefinition, MarketReadiness,
    SegmentDefinition, SegmentPreference,
    EntryModeDefinition, StrategyOptionDefinition, StrategyOptionEffect,
    EventTemplateDefinition, EventImpactDefinition, EventResponseDefinition,
    MarketConditionByRound,
    FirmStarterProfile, FirmStarterPlatformConfig, FirmStarterProduct,
    AICompetitorDefinition, AICompetitorFitByRound,
)
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
    TeamMarketPresence, TeamPlant, TeamPartnership,
    TeamStrategyFeatureLevel,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class ScenarioConfigInline(admin.TabularInline):
    model = ScenarioConfig
    extra = 1


class PlatformFeatureCeilingInline(admin.TabularInline):
    model = PlatformFeatureCeiling
    extra = 1


class MarketReadinessInline(admin.TabularInline):
    model = MarketReadiness
    extra = 1


class MarketConditionByRoundInline(admin.TabularInline):
    model = MarketConditionByRound
    extra = 1


class SegmentPreferenceInline(admin.TabularInline):
    model = SegmentPreference
    extra = 1


class StrategyOptionEffectInline(admin.TabularInline):
    model = StrategyOptionEffect
    extra = 1


class EventImpactDefinitionInline(admin.TabularInline):
    model = EventImpactDefinition
    extra = 1


class EventResponseDefinitionInline(admin.TabularInline):
    model = EventResponseDefinition
    extra = 1


class FirmStarterPlatformConfigInline(admin.TabularInline):
    model = FirmStarterPlatformConfig
    extra = 1


class FirmStarterProductInline(admin.TabularInline):
    model = FirmStarterProduct
    extra = 1


class AICompetitorFitByRoundInline(admin.TabularInline):
    model = AICompetitorFitByRound
    extra = 1


# ---------------------------------------------------------------------------
# Model Admins
# ---------------------------------------------------------------------------

@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ['name', 'industry_label', 'num_rounds', 'starting_cash', 'currency_code', 'is_active']
    list_filter = ['is_active', 'currency_code']
    search_fields = ['name', 'industry_label', 'description']
    list_per_page = 50
    inlines = [ScenarioConfigInline]


@admin.register(ScenarioConfig)
class ScenarioConfigAdmin(admin.ModelAdmin):
    list_display = ['scenario', 'config_key', 'config_value']
    list_filter = ['scenario']
    search_fields = ['config_key', 'config_value', 'description']
    list_per_page = 50


@admin.register(FeatureDefinition)
class FeatureDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'scenario', 'layer', 'category', 'code', 'max_value', 'cost_curve_type']
    list_filter = ['scenario', 'layer', 'category', 'cost_curve_type']
    search_fields = ['name', 'code', 'description']
    list_per_page = 50
    ordering = ['scenario', 'layer', 'display_order']


@admin.register(PlatformGenerationDefinition)
class PlatformGenerationDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'scenario', 'generation_order', 'unlock_round', 'development_cost', 'is_starting_platform']
    list_filter = ['scenario', 'is_starting_platform']
    search_fields = ['name', 'description']
    list_per_page = 50
    ordering = ['scenario', 'generation_order']
    inlines = [PlatformFeatureCeilingInline]


@admin.register(PlatformFeatureCeiling)
class PlatformFeatureCeilingAdmin(admin.ModelAdmin):
    list_display = ['platform_generation', 'feature', 'ceiling_value', 'starting_value']
    list_filter = ['platform_generation__scenario']
    search_fields = ['feature__name', 'platform_generation__name']
    list_per_page = 50


@admin.register(MarketDefinition)
class MarketDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'scenario', 'code', 'currency_code', 'base_growth_rate', 'allows_manufacturing']
    list_filter = ['scenario', 'allows_manufacturing', 'contract_mfg_available']
    search_fields = ['name', 'code', 'description']
    list_per_page = 50
    ordering = ['scenario', 'display_order']
    inlines = [MarketReadinessInline, MarketConditionByRoundInline]


@admin.register(MarketReadiness)
class MarketReadinessAdmin(admin.ModelAdmin):
    list_display = ['market', 'platform_generation', 'round_number', 'readiness_pct']
    list_filter = ['market__scenario', 'market']
    list_per_page = 50


@admin.register(SegmentDefinition)
class SegmentDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'scenario', 'market', 'segment_type', 'population_size', 'performance_index_weight']
    list_filter = ['scenario', 'segment_type', 'market']
    search_fields = ['name', 'description']
    list_per_page = 50
    ordering = ['scenario', 'display_order']
    inlines = [SegmentPreferenceInline]


@admin.register(SegmentPreference)
class SegmentPreferenceAdmin(admin.ModelAdmin):
    list_display = ['segment', 'feature', 'ideal_value', 'weight', 'tolerance']
    list_filter = ['segment__scenario', 'feature__layer']
    search_fields = ['segment__name', 'feature__name']
    list_per_page = 50


@admin.register(EntryModeDefinition)
class EntryModeDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'scenario', 'code', 'capital_requirement', 'setup_rounds', 'control_level', 'risk_level']
    list_filter = ['scenario', 'tariff_applies']
    search_fields = ['name', 'code', 'description']
    list_per_page = 50


@admin.register(StrategyOptionDefinition)
class StrategyOptionDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'scenario', 'category', 'code', 'capital_cost_base', 'is_reversible']
    list_filter = ['scenario', 'category', 'is_reversible']
    search_fields = ['name', 'code', 'description']
    list_per_page = 50
    inlines = [StrategyOptionEffectInline]


@admin.register(StrategyOptionEffect)
class StrategyOptionEffectAdmin(admin.ModelAdmin):
    list_display = ['strategy_option', 'feature', 'effect_type', 'effect_value', 'market_specific']
    list_filter = ['effect_type', 'market_specific']
    search_fields = ['strategy_option__name', 'feature__name']
    list_per_page = 50


@admin.register(EventTemplateDefinition)
class EventTemplateDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'scenario', 'category', 'severity', 'probability_per_round', 'earliest_round']
    list_filter = ['scenario', 'severity', 'category', 'affects_all_markets', 'response_required']
    search_fields = ['name', 'description_template', 'category']
    list_per_page = 50
    inlines = [EventImpactDefinitionInline, EventResponseDefinitionInline]


@admin.register(EventImpactDefinition)
class EventImpactDefinitionAdmin(admin.ModelAdmin):
    list_display = ['event_template', 'impact_type', 'target_segment', 'target_feature', 'impact_value', 'duration_rounds']
    list_filter = ['impact_type', 'is_cumulative', 'event_template__scenario']
    search_fields = ['event_template__name']
    list_per_page = 50


@admin.register(EventResponseDefinition)
class EventResponseDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'event_template', 'cost']
    list_filter = ['event_template__scenario']
    search_fields = ['name', 'description']
    list_per_page = 50


@admin.register(MarketConditionByRound)
class MarketConditionByRoundAdmin(admin.ModelAdmin):
    list_display = ['market', 'round_number', 'growth_rate_modifier', 'demand_multiplier', 'exchange_rate_modifier']
    list_filter = ['market__scenario', 'market']
    list_per_page = 50


@admin.register(FirmStarterProfile)
class FirmStarterProfileAdmin(admin.ModelAdmin):
    list_display = ['profile_name', 'scenario', 'home_market', 'starting_cash', 'starting_debt']
    list_filter = ['scenario']
    search_fields = ['profile_name', 'description']
    list_per_page = 50
    inlines = [FirmStarterPlatformConfigInline, FirmStarterProductInline]


@admin.register(FirmStarterPlatformConfig)
class FirmStarterPlatformConfigAdmin(admin.ModelAdmin):
    list_display = ['firm_starter_profile', 'platform_generation', 'feature', 'starting_level']
    list_filter = ['firm_starter_profile__scenario']
    search_fields = ['firm_starter_profile__profile_name', 'feature__name']
    list_per_page = 50


@admin.register(FirmStarterProduct)
class FirmStarterProductAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'firm_starter_profile', 'positioning_label', 'base_price', 'market', 'unit_volume']
    list_filter = ['firm_starter_profile__scenario', 'positioning_label']
    search_fields = ['product_name']
    list_per_page = 50


@admin.register(AICompetitorDefinition)
class AICompetitorDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'scenario']
    list_filter = ['scenario']
    search_fields = ['name', 'description']
    list_per_page = 50
    inlines = [AICompetitorFitByRoundInline]


@admin.register(AICompetitorFitByRound)
class AICompetitorFitByRoundAdmin(admin.ModelAdmin):
    list_display = ['ai_competitor', 'segment', 'market', 'round_number', 'fit_score']
    list_filter = ['ai_competitor__scenario', 'market']
    search_fields = ['ai_competitor__name', 'segment__name']
    list_per_page = 50


# ---------------------------------------------------------------------------
# Group 3: Game Instance Admin
# ---------------------------------------------------------------------------

class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 1


class RoundInline(admin.TabularInline):
    model = Round
    extra = 0
    fields = ['round_number', 'status', 'opened_at', 'deadline', 'processed_at']
    readonly_fields = ['opened_at', 'processed_at']


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['name', 'scenario', 'current_round', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'scenario']
    search_fields = ['name']
    list_per_page = 50
    inlines = [RoundInline]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'game', 'firm_starter_profile', 'performance_index', 'cash_on_hand', 'is_in_distress']
    list_filter = ['game', 'is_in_distress']
    search_fields = ['name']
    list_per_page = 50
    inlines = [TeamMemberInline]


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['team', 'user', 'role', 'joined_at']
    list_filter = ['role']
    search_fields = ['team__name']
    list_per_page = 50


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ['game', 'round_number', 'status', 'opened_at', 'deadline', 'processed_at']
    list_filter = ['status', 'game']
    list_per_page = 50


# ---------------------------------------------------------------------------
# Group 4: Team State Admin
# ---------------------------------------------------------------------------

class TeamPlatformFeatureLevelInline(admin.TabularInline):
    model = TeamPlatformFeatureLevel
    extra = 0


class PendingFeatureGainInline(admin.TabularInline):
    model = PendingFeatureGain
    extra = 0


class TeamProductMarketInline(admin.TabularInline):
    model = TeamProductMarket
    extra = 1


@admin.register(TeamPlatform)
class TeamPlatformAdmin(admin.ModelAdmin):
    list_display = ['team', 'platform_generation', 'status', 'development_method', 'activated_round']
    list_filter = ['status', 'development_method']
    search_fields = ['team__name']
    list_per_page = 50
    inlines = [TeamPlatformFeatureLevelInline, PendingFeatureGainInline]


@admin.register(TeamPlatformFeatureLevel)
class TeamPlatformFeatureLevelAdmin(admin.ModelAdmin):
    list_display = ['team_platform', 'feature', 'current_level']
    list_filter = ['feature__layer']
    list_per_page = 50


@admin.register(PendingFeatureGain)
class PendingFeatureGainAdmin(admin.ModelAdmin):
    list_display = ['team_platform', 'feature', 'gain_amount', 'applies_round', 'applied']
    list_filter = ['applied', 'applies_round']
    list_per_page = 50


@admin.register(TeamProduct)
class TeamProductAdmin(admin.ModelAdmin):
    list_display = ['team', 'name', 'team_platform', 'positioning', 'status', 'created_round']
    list_filter = ['positioning', 'status']
    search_fields = ['name', 'team__name']
    list_per_page = 50
    inlines = [TeamProductMarketInline]


@admin.register(TeamProductMarket)
class TeamProductMarketAdmin(admin.ModelAdmin):
    list_display = ['team_product', 'market', 'is_active', 'first_offered_round']
    list_filter = ['is_active']
    list_per_page = 50


@admin.register(TeamMarketPresence)
class TeamMarketPresenceAdmin(admin.ModelAdmin):
    list_display = ['team', 'market', 'entry_mode', 'status', 'established_round']
    list_filter = ['status', 'entry_mode']
    search_fields = ['team__name']
    list_per_page = 50


@admin.register(TeamPlant)
class TeamPlantAdmin(admin.ModelAdmin):
    list_display = ['team', 'market', 'status', 'capacity_units', 'completion_round', 'cumulative_production']
    list_filter = ['status', 'market']
    list_per_page = 50


@admin.register(TeamPartnership)
class TeamPartnershipAdmin(admin.ModelAdmin):
    list_display = ['team', 'market', 'strategy_option', 'annual_investment', 'status']
    list_filter = ['status', 'market']
    list_per_page = 50


@admin.register(TeamStrategyFeatureLevel)
class TeamStrategyFeatureLevelAdmin(admin.ModelAdmin):
    list_display = ['team', 'feature', 'market', 'current_level', 'round_number']
    list_filter = ['feature', 'market', 'round_number']
    list_per_page = 50


# ---------------------------------------------------------------------------
# Group 5: Decision Admin
# ---------------------------------------------------------------------------

class DecisionBudgetAllocationInline(admin.TabularInline):
    model = DecisionBudgetAllocation
    extra = 0


class DecisionRDInvestmentInline(admin.TabularInline):
    model = DecisionRDInvestment
    extra = 0


class DecisionPlatformDevelopmentInline(admin.TabularInline):
    model = DecisionPlatformDevelopment
    extra = 0


class DecisionProductCreateInline(admin.TabularInline):
    model = DecisionProductCreate
    extra = 0


class DecisionProductRetireInline(admin.TabularInline):
    model = DecisionProductRetire
    extra = 0


class DecisionMarketingInline(admin.StackedInline):
    model = DecisionMarketing
    extra = 0


class DecisionMarketEntryInline(admin.TabularInline):
    model = DecisionMarketEntry
    extra = 0


class DecisionFinancingInline(admin.TabularInline):
    model = DecisionFinancing
    extra = 0


class DecisionPlantInline(admin.TabularInline):
    model = DecisionPlant
    extra = 0


class DecisionPartnershipInline(admin.TabularInline):
    model = DecisionPartnership
    extra = 0


class DecisionAcquisitionInline(admin.TabularInline):
    model = DecisionAcquisition
    extra = 0


class DecisionESGInline(admin.TabularInline):
    model = DecisionESG
    extra = 0


class DecisionEventResponseInline(admin.TabularInline):
    model = DecisionEventResponse
    extra = 0


class DecisionResearchAllocationInline(admin.TabularInline):
    model = DecisionResearchAllocation
    extra = 0


class CC31TalentAllocationInline(admin.TabularInline):
    from core.models.cc31_models import TalentAllocation
    model = TalentAllocation
    extra = 0


class CC31ComplianceInvestmentInline(admin.TabularInline):
    from core.models.cc31_models import ComplianceInvestment
    model = ComplianceInvestment
    extra = 0


@admin.register(DecisionSubmission)
class DecisionSubmissionAdmin(admin.ModelAdmin):
    list_display = ['team', 'round', 'status', 'locked_at']
    list_filter = ['status', 'round__round_number']
    search_fields = ['team__name']
    list_per_page = 50
    inlines = [
        DecisionBudgetAllocationInline,
        DecisionRDInvestmentInline,
        DecisionPlatformDevelopmentInline,
        DecisionProductCreateInline,
        DecisionProductRetireInline,
        DecisionMarketingInline,
        DecisionMarketEntryInline,
        DecisionFinancingInline,
        DecisionPlantInline,
        DecisionPartnershipInline,
        DecisionAcquisitionInline,
        DecisionESGInline,
        DecisionEventResponseInline,
        DecisionResearchAllocationInline,
        CC31TalentAllocationInline,
        CC31ComplianceInvestmentInline,
    ]


@admin.register(DecisionMarketing)
class DecisionMarketingAdmin(admin.ModelAdmin):
    list_display = ['submission', 'team_product', 'market', 'retail_price', 'promotion_budget', 'production_volume']
    list_filter = ['distribution_strategy', 'market']
    list_per_page = 50


@admin.register(DecisionRDInvestment)
class DecisionRDInvestmentAdmin(admin.ModelAdmin):
    list_display = ['submission', 'team_platform', 'feature', 'method', 'amount']
    list_per_page = 50


@admin.register(DecisionMarketEntry)
class DecisionMarketEntryAdmin(admin.ModelAdmin):
    list_display = ['submission', 'market', 'entry_mode', 'action', 'initial_investment']
    list_per_page = 50


@admin.register(DecisionBudgetAllocation)
class DecisionBudgetAllocationAdmin(admin.ModelAdmin):
    list_display = ['submission', 'rd_budget', 'marketing_budget', 'strategy_budget']
    list_per_page = 50


@admin.register(DecisionPlatformDevelopment)
class DecisionPlatformDevelopmentAdmin(admin.ModelAdmin):
    list_display = ['submission', 'platform_generation', 'method', 'committed_cost']
    list_per_page = 50


@admin.register(DecisionProductCreate)
class DecisionProductCreateAdmin(admin.ModelAdmin):
    list_display = ['submission', 'team_platform', 'product_name', 'positioning']
    list_per_page = 50


@admin.register(DecisionProductRetire)
class DecisionProductRetireAdmin(admin.ModelAdmin):
    list_display = ['submission', 'team_product', 'timing']
    list_per_page = 50


@admin.register(DecisionFinancing)
class DecisionFinancingAdmin(admin.ModelAdmin):
    list_display = ['submission', 'new_debt', 'debt_repayment', 'new_equity', 'dividend_per_share']
    list_per_page = 50


@admin.register(DecisionPlant)
class DecisionPlantAdmin(admin.ModelAdmin):
    list_display = ['submission', 'market', 'action', 'capacity_units', 'contract_mfg_volume']
    list_per_page = 50


@admin.register(DecisionPartnership)
class DecisionPartnershipAdmin(admin.ModelAdmin):
    list_display = ['submission', 'market', 'strategy_option', 'annual_investment', 'action']
    list_per_page = 50


@admin.register(DecisionAcquisition)
class DecisionAcquisitionAdmin(admin.ModelAdmin):
    list_display = ['submission', 'acquisition_target']
    list_per_page = 50


@admin.register(DecisionESG)
class DecisionESGAdmin(admin.ModelAdmin):
    list_display = ['submission', 'environmental_investment', 'social_investment']
    list_per_page = 50


@admin.register(DecisionEventResponse)
class DecisionEventResponseAdmin(admin.ModelAdmin):
    list_display = ['submission', 'event_instance', 'response']
    list_per_page = 50


@admin.register(DecisionResearchAllocation)
class DecisionResearchAllocationAdmin(admin.ModelAdmin):
    list_display = ['submission', 'market', 'allocation_amount']
    list_per_page = 50


# ---------------------------------------------------------------------------
# Group 6: Engine Result Admin
# ---------------------------------------------------------------------------

from core.models.results import EventInstance, ActiveModifier, RoundResultAdoption


@admin.register(EventInstance)
class EventInstanceAdmin(admin.ModelAdmin):
    list_display = ['event_template', 'game', 'round_number', 'target_market', 'created_at']
    list_filter = ['game', 'round_number']
    list_per_page = 50


@admin.register(ActiveModifier)
class ActiveModifierAdmin(admin.ModelAdmin):
    list_display = ['modifier_type', 'game', 'modifier_value', 'started_round', 'expires_round']
    list_filter = ['modifier_type', 'game']
    list_per_page = 50


@admin.register(RoundResultAdoption)
class RoundResultAdoptionAdmin(admin.ModelAdmin):
    list_display = ['team', 'segment', 'market', 'round_number', 'fit_score', 'adjusted_fit_score', 'new_adopters', 'cumulative_adopters']
    list_filter = ['game', 'round_number', 'market']
    list_per_page = 50


# ---------------------------------------------------------------------------
# CC-06: Group 6 Financial Result Models
# ---------------------------------------------------------------------------

from core.models.results_financials import (
    RoundResultProductMarket, RoundResultFinancials, RoundResultMarketRevenue,
    RoundResultPerformanceIndex, RoundResultCoherence, LeaderboardEntry,
    MarketIntelligenceBrief,
)


@admin.register(RoundResultProductMarket)
class RoundResultProductMarketAdmin(admin.ModelAdmin):
    list_display = ['team', 'team_product', 'market', 'round_number', 'units_sold', 'home_revenue', 'total_cogs']
    list_filter = ['game', 'round_number', 'market']
    list_per_page = 50


@admin.register(RoundResultFinancials)
class RoundResultFinancialsAdmin(admin.ModelAdmin):
    list_display = ['team', 'round_number', 'total_revenue', 'net_income', 'cash_closing', 'roe', 'debt_to_equity']
    list_filter = ['game', 'round_number']
    list_per_page = 50


@admin.register(RoundResultMarketRevenue)
class RoundResultMarketRevenueAdmin(admin.ModelAdmin):
    list_display = ['team', 'market', 'round_number', 'home_revenue', 'market_profit', 'market_share_pct']
    list_filter = ['game', 'round_number', 'market']
    list_per_page = 50


@admin.register(RoundResultPerformanceIndex)
class RoundResultPerformanceIndexAdmin(admin.ModelAdmin):
    list_display = ['team', 'round_number', 'satisfaction_score', 'index_change', 'index_value']
    list_filter = ['game', 'round_number']
    list_per_page = 50


@admin.register(RoundResultCoherence)
class RoundResultCoherenceAdmin(admin.ModelAdmin):
    list_display = ['team', 'round_number', 'formula_score', 'rag_score', 'blended_score']
    list_filter = ['game', 'round_number']
    list_per_page = 50


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ['rank', 'team', 'round_number', 'performance_index', 'total_revenue', 'net_income']
    list_filter = ['game', 'round_number']
    list_per_page = 50


@admin.register(MarketIntelligenceBrief)
class MarketIntelligenceBriefAdmin(admin.ModelAdmin):
    list_display = ['market', 'round_number', 'team', 'brief_level', 'generated_at']
    list_filter = ['game', 'round_number', 'brief_level']
    list_per_page = 50


# ---------------------------------------------------------------------------
# CC-7: RAG models
# ---------------------------------------------------------------------------

from core.models.rag import ResearchQueryLog


@admin.register(ResearchQueryLog)
class ResearchQueryLogAdmin(admin.ModelAdmin):
    list_display = ['team', 'round_number', 'query_text', 'queried_at']
    list_filter = ['round_number']
    list_per_page = 50


# ---------------------------------------------------------------------------
# CC-31A: Origin-Trust Framework models
# ---------------------------------------------------------------------------

from core.models.cc31_models import (
    CulturalDistanceMatrix, OriginTrustModifier,
    TalentAllocation, ComplianceInvestment, TeamMarketCompliance,
)


class CulturalDistanceMatrixInline(admin.TabularInline):
    model = CulturalDistanceMatrix
    extra = 1


class OriginTrustModifierInline(admin.TabularInline):
    model = OriginTrustModifier
    extra = 1


class TalentAllocationInline(admin.TabularInline):
    model = TalentAllocation
    extra = 0


# Add inlines to existing Scenario admin
ScenarioAdmin.inlines = ScenarioAdmin.inlines + [CulturalDistanceMatrixInline, OriginTrustModifierInline]


@admin.register(CulturalDistanceMatrix)
class CulturalDistanceMatrixAdmin(admin.ModelAdmin):
    list_display = ['scenario', 'from_market', 'to_market', 'distance_level', 'base_effectiveness']
    list_filter = ['scenario', 'distance_level']
    list_per_page = 50


@admin.register(OriginTrustModifier)
class OriginTrustModifierAdmin(admin.ModelAdmin):
    list_display = ['scenario', 'origin_market', 'host_market', 'customer_trust_multiplier', 'regulator_origin_modifier']
    list_filter = ['scenario']
    list_per_page = 50


@admin.register(TalentAllocation)
class TalentAllocationAdmin(admin.ModelAdmin):
    list_display = ['submission', 'talent_pool', 'hq_count']
    list_filter = ['talent_pool']
    list_per_page = 50


@admin.register(ComplianceInvestment)
class ComplianceInvestmentAdmin(admin.ModelAdmin):
    list_display = ['submission', 'market', 'investment_amount']
    list_per_page = 50


@admin.register(TeamMarketCompliance)
class TeamMarketComplianceAdmin(admin.ModelAdmin):
    list_display = ['team', 'market', 'compliance_level', 'current_trust_multiplier', 'rounds_present']
    list_filter = ['game']
    list_per_page = 50

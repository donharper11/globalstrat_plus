"""Declared inventory of every table that carries competitive state.

GSP-CRV2-01 requirements 1 and 2. A resolution manifest is only sufficient if
someone holding it — and nothing else — can say what went into a round and
what came out. That means the registry below has to be a *complete*, reviewed
enumeration rather than a convenient subset, and every field that is left out
has to carry a reason a disputing team can read.

How a section is snapshotted
----------------------------
``scope``/``lookup`` say how the section's rows are found from the game, round
or scenario being resolved. ``key`` is the section's **natural key**: the
surrogate primary key never appears in a manifest, because sequence values
depend on unrelated inserts and would make two byte-identical competitions
hash differently. Every row is instead identified by a token built from its
natural key, with foreign keys replaced by the referenced row's token
(``core.services.manifest_snapshot``). When a table has no natural key the
token is derived from the row's own canonical content, which is still free of
sequence values.

``key`` defaults to the model's single ``unique_together`` when it has exactly
one, so the natural key tracks the schema instead of drifting from it.

What is excluded
----------------
Three global rules, then per-section exceptions:

* the surrogate primary key and every foreign-key id — replaced by tokens, so
  the information is preserved in a sequence-independent form;
* the fields in ``MEASURED_TIME_FIELDS`` are dropped from the **output**
  (competitive) manifest because they record when the machine did something,
  not what it computed. They are kept in the **input** manifest: there they
  are frozen facts about the state resolution started from, they are what a
  dispute about "when was this accepted" is settled with, and a replay reads
  them back from the restored snapshot unchanged;
* ``narrative_fields`` are LLM- or template-authored prose. They are hashed
  separately (``narrative_sha256``) and reported separately, exactly as the
  acceptance criteria require.

Anything else that is excluded is listed in the section's ``exclude`` mapping
with its justification, and ``test_manifest_determinism`` fails if a model
grows a field that no rule and no justification covers.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


SCENARIO = 'scenario'
GAME = 'game'


# Wall-clock values written by the code at the moment it mutates a row. They
# differ between two correct runs of the same round, so they cannot be in the
# competitive hash. See the module docstring for why the input manifest keeps
# them.
MEASURED_TIME_FIELDS = {
    'created_at': 'Row-creation wall clock, set by auto_now_add.',
    'updated_at': 'Row-update wall clock, set by auto_now.',
    'generated_at': 'Narrative-generation wall clock (Phase 2).',
    'joined_at': 'Roster wall clock; participation itself is captured.',
    'opened_at': 'Round lifecycle wall clock.',
    'closed_at': 'Round lifecycle wall clock.',
    'processed_at': 'Round lifecycle wall clock.',
    'started_at': 'Agent-cycle lifecycle wall clock.',
    'completed_at': 'Agent-cycle lifecycle wall clock.',
    'locked_at': 'Submission lifecycle wall clock.',
    'withdrawn_at': 'Participation lifecycle wall clock.',
}


@dataclass(frozen=True)
class Section:
    name: str
    model: str
    scope: str
    lookup: str
    key: Optional[Tuple[str, ...]] = None
    # Extra ORM filter, for the case where one table holds rows on both sides
    # of a boundary — engine-written and narrative-written instructor alerts
    # live together and must be hashed differently.
    filters: Optional[Dict[str, object]] = None
    exclude: Dict[str, str] = field(default_factory=dict)
    narrative_fields: Tuple[str, ...] = ()
    in_output: bool = True
    why: str = ''


# --------------------------------------------------------------------------
# Scenario and engine configuration.
#
# Immutable during resolution, but a manifest that omits it cannot explain a
# single number: every price curve, adoption parameter and event probability
# lives here. Captured in full in the input manifest; carried into the output
# manifest as per-section digests so a replay proves the engine did not
# rewrite its own configuration mid-round.
# --------------------------------------------------------------------------
CONFIG_SECTIONS = (
    Section('scenario', 'core.Scenario', SCENARIO, 'id', key=('name',),
            exclude={'is_active': 'Catalogue visibility flag; not read by the '
                                  'scoring call graph.'},
            in_output=False, why='Scenario-level engine constants.'),
    Section('scenario_config', 'core.ScenarioConfig', SCENARIO, 'scenario_id',
            exclude={'description': 'Author-facing help text; the config value is hashed.'},
            in_output=False, why='Keyed engine configuration values.'),
    Section('feature_definition', 'core.FeatureDefinition', SCENARIO, 'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.',
                     'display_order': 'Display ordering for the UI; not read by scoring.',
                     'icon_key': 'UI icon asset reference; not read by scoring.'},
            in_output=False, why='Feature cost curves, lags and bounds.'),
    Section('platform_generation', 'core.PlatformGenerationDefinition', SCENARIO,
            'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.'},
            in_output=False, why='Platform costs and unlock schedule.'),
    Section('market_definition', 'core.MarketDefinition', SCENARIO, 'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'display_name_zh': 'Localised display label; the code is hashed.',
                     'description': 'Author-facing prose; carries no engine input.',
                     'market_description_zh': 'Localised author-facing prose; no engine input.',
                     'display_order': 'Display ordering for the UI; not read by scoring.'},
            in_output=False, why='Tax, tariff, FX and manufacturing constants.'),
    Section('entry_mode', 'core.EntryModeDefinition', SCENARIO, 'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.'},
            in_output=False, why='Market-entry capital and cost multipliers.'),
    Section('strategy_option', 'core.StrategyOptionDefinition', SCENARIO, 'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.'},
            in_output=False, why='Strategy costs, lags and exclusivity rules.'),
    Section('strategy_option_effect', 'core.StrategyOptionEffect', SCENARIO,
            'strategy_option__scenario_id',
            in_output=False, why='Feature deltas each strategy option grants.'),
    Section('ai_competitor', 'core.AICompetitorDefinition', SCENARIO, 'scenario_id',
            key=('scenario_id', 'name'),
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.'},
            in_output=False, why='Non-team competitors present in every market.'),
    Section('ai_competitor_behavior', 'core.AICompetitorBehavior', SCENARIO,
            'ai_competitor__scenario_id', key=('ai_competitor',),
            in_output=False, why='AI competitor pricing and entry behaviour.'),
    Section('ai_competitor_fit', 'core.AICompetitorFitByRound', SCENARIO,
            'ai_competitor__scenario_id',
            in_output=False, why='Per-round AI competitor fit scores.'),
    Section('platform_feature_ceiling', 'core.PlatformFeatureCeiling', SCENARIO,
            'platform_generation__scenario_id',
            in_output=False, why='Per-generation feature ceilings.'),
    Section('market_readiness', 'core.MarketReadiness', SCENARIO, 'market__scenario_id',
            in_output=False, why='Per-round readiness gating of adoption.'),
    Section('segment_definition', 'core.SegmentDefinition', SCENARIO, 'scenario_id',
            key=('scenario_id', 'market_id', 'name'),
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.',
                     'display_order': 'Display ordering for the UI; not read by scoring.'},
            in_output=False, why='Bass parameters and segment demand pools.'),
    Section('segment_preference', 'core.SegmentPreference', SCENARIO,
            'segment__scenario_id',
            in_output=False, why='Ideal points driving every fit score.'),
    Section('event_template', 'core.EventTemplateDefinition', SCENARIO, 'scenario_id',
            key=('scenario_id', 'name'),
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.',
                     'description_template_zh': 'Localised narrative template; prose only.',
                     'rag_source_tags': 'Retrieval hints for Phase-2 prose only.'},
            narrative_fields=('description_template',),
            in_output=False, why='Event probabilities, windows and SC effects.'),
    Section('event_impact', 'core.EventImpactDefinition', SCENARIO,
            'event_template__scenario_id',
            in_output=False, why='Numeric impact each event applies.'),
    Section('event_response', 'core.EventResponseDefinition', SCENARIO,
            'event_template__scenario_id',
            key=('event_template_id', 'name'),
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.',
                     'rag_alignment_tags': 'Retrieval hints for Phase-2 prose only.'},
            in_output=False, why='Costs and effects of each event response.'),
    Section('firm_starter_profile', 'core.FirmStarterProfile', SCENARIO, 'scenario_id',
            key=('scenario_id', 'profile_name'),
            exclude={'profile_name_zh': 'Localised display label; the profile name is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.'},
            in_output=False, why='Starting balance sheet each team inherited.'),
    Section('firm_starter_platform_config', 'core.FirmStarterPlatformConfig', SCENARIO,
            'firm_starter_profile__scenario_id',
            in_output=False, why='Starting feature levels.'),
    Section('firm_starter_product', 'core.FirmStarterProduct', SCENARIO,
            'firm_starter_profile__scenario_id',
            key=('firm_starter_profile_id', 'product_name', 'market_id'),
            in_output=False, why='Starting products and volumes.'),
    Section('feature_level_cost', 'core.FeatureLevelCost', SCENARIO, 'feature__scenario_id',
            in_output=False, why='R&D cost table for every feature level.'),
    Section('market_condition_by_round', 'core.MarketConditionByRound', SCENARIO,
            'market__scenario_id',
            exclude={'rag_source_tags': 'Retrieval hints for Phase-2 prose only.'},
            narrative_fields=('market_outlook_narrative',),
            in_output=False, why='Scheduled per-round market modifiers.'),
    Section('acquisition_target', 'core.AcquisitionTarget', SCENARIO, 'scenario_id',
            key=('scenario_id', 'market_id', 'target_name'),
            exclude={'target_name_zh': 'Localised display label; the target name is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.'},
            in_output=False, why='Acquisition costs and granted assets.'),
    Section('cultural_distance', 'core.CulturalDistanceMatrix', SCENARIO, 'scenario_id',
            in_output=False, why='Cross-market effectiveness and repatriation cost.'),
    Section('origin_trust', 'core.OriginTrustModifier', SCENARIO, 'scenario_id',
            in_output=False, why='Origin-country trust multipliers.'),
    Section('government_profile', 'core.GovernmentProfile', SCENARIO, 'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.'},
            in_output=False, why='Government agent thresholds and budgets.'),
    Section('compliance_regime', 'core.ComplianceRegime', SCENARIO, 'scenario_id',
            in_output=False, why='Enforcement probabilities and penalties.'),
    Section('supplier', 'core.Supplier', SCENARIO, 'scenario_id',
            in_output=False, why='Supplier price, quality and lead time.'),
    Section('shipping_lane', 'core.ShippingLane', SCENARIO, 'scenario_id',
            in_output=False, why='Lane modes, chokepoints and exposure.'),
    Section('trade_finance_instrument', 'core.TradeFinanceInstrument', SCENARIO,
            'scenario_id',
            in_output=False, why='Trade-finance costs and rejection rates.'),
    Section('tax_structure_type', 'core.TaxStructureType', SCENARIO, 'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.',
                     'display_order': 'Display ordering for the UI; not read by scoring.'},
            in_output=False, why='Tax structure savings and audit odds.'),
    Section('governance_commitment_type', 'core.GovernanceCommitmentType', SCENARIO,
            'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.',
                     'display_order': 'Display ordering for the UI; not read by scoring.'},
            in_output=False, why='Governance commitment costs and benefits.'),
    Section('org_structure_type', 'core.OrganizationalStructureType', SCENARIO,
            'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.',
                     'display_order': 'Display ordering for the UI; not read by scoring.'},
            in_output=False, why='Organisational overhead and modifiers.'),
    Section('alliance_partner_profile', 'core.AlliancePartnerProfile', SCENARIO,
            'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.'},
            in_output=False, why='Alliance satisfaction curves and thresholds.'),
    Section('ai_investor_fund', 'core.AIInvestorFund', SCENARIO, 'scenario_id',
            exclude={'name_zh': 'Localised display label; the machine-readable code is hashed.', 'description': 'Author-facing prose; carries no engine input.',
                     'description_zh': 'Localised author-facing prose; carries no engine input.'},
            in_output=False, why='Investor holdings policy driving share price.'),
    Section('ai_investor_preference', 'core.AIInvestorPreference', SCENARIO,
            'fund__scenario_id',
            exclude={'feature_label': 'Display label for the preference row.'},
            in_output=False, why='Investor ideal points.'),
    Section('resilience_parameters', 'core.ResilienceParameters', SCENARIO, 'scenario_id',
            key=('scenario',),
            in_output=False, why='Resilience score weights and thresholds.'),
    Section('freight_market', 'core.FreightMarket', SCENARIO, 'scenario_id',
            key=('scenario',),
            in_output=False, why='Freight rate dynamics constants.'),
)


# --------------------------------------------------------------------------
# Per-class configuration overrides. Instructor-set, game-scoped, and read by
# the engine, so they belong with the configuration rather than with results.
# --------------------------------------------------------------------------
OVERRIDE_SECTIONS = (
    Section('class_disclosure_override', 'core.ClassProgressiveDisclosureOverride',
            GAME, 'game_id',
            exclude={'reason': 'Operator free text; the effective value is hashed.'},
            in_output=False, why='Per-class unlock-round overrides.'),
    Section('class_resilience_weight_override', 'core.ClassResilienceWeightOverride',
            GAME, 'game_id',
            exclude={'reason': 'Operator free text; the effective value is hashed.'},
            in_output=False, why='Per-class resilience weight overrides.'),
)


# --------------------------------------------------------------------------
# Game, roster and lifecycle.
# --------------------------------------------------------------------------
GAME_SECTIONS = (
    Section('game', 'core.Game', GAME, 'id', key=('name',),
            exclude={'round_deadline': 'Operator deadline; not read by scoring.'},
            why='Scenario binding, current round and RNG cohort.'),
    Section('round', 'core.Round', GAME, 'game_id',
            exclude={'deadline': 'Operator deadline; not read by scoring.',
                     'lock_reason': 'Operator free text; the resulting lock state is hashed.',
                     'close_reason': 'Operator free text; the resulting status is hashed.',
                     'processing_status': 'Phase-1/Phase-2 lifecycle state.',
                     'narrative_generated': 'Phase-2 lifecycle flag.',
                     'narrative_error': 'Phase-2 error text.',
                     'phase_1_duration': 'Measured wall-clock duration.',
                     'phase_2_duration': 'Measured wall-clock duration.'},
            why='Round status and lock state.'),
    Section('team', 'core.Team', GAME, 'game_id', key=('game_id', 'name'),
            exclude={'withdrawal_reason': 'Operator free text; the status is hashed.'},
            why='Carried balance sheet, index, distress and participation.'),
    Section('team_member', 'core.TeamMember', GAME, 'team__game_id',
            in_output=False, why='Roster: who could submit for each team.'),
    Section('decision_audit_event', 'core.DecisionAuditEvent', GAME, 'game_id',
            key=None,
            exclude={'payload': 'The accepted payload is snapshotted in full by '
                                'the decision_* sections; the event keeps its '
                                'hash so tampering with either side is visible.'},
            in_output=False,
            why='Ordered provenance of every accepted or defaulted save.'),
)


# --------------------------------------------------------------------------
# Accepted decisions. The payload itself, not a hash of it — this is the half
# of V2-002 that made the old manifest unable to explain an input.
# --------------------------------------------------------------------------
DECISION_SECTIONS = (
    Section('decision_submission', 'core.DecisionSubmission', GAME, 'team__game_id',
            exclude={'team_notes': 'Student free text; carries no engine input.'},
            why='Lock state of each team-round submission.'),
    Section('decision_budget', 'core.DecisionBudgetAllocation', GAME,
            'submission__team__game_id', key=('submission',),
            why='R&D / marketing / strategy / research budgets.'),
    Section('decision_rd', 'core.DecisionRDInvestment', GAME,
            'submission__team__game_id',
            key=('submission_id', 'team_platform_id', 'feature_id', 'method'),
            why='Per-feature R&D spend and target levels.'),
    Section('decision_platform', 'core.DecisionPlatformDevelopment', GAME,
            'submission__team__game_id',
            key=('submission_id', 'platform_generation_id', 'platform_name'),
            why='Platform development commitments.'),
    Section('decision_product_create', 'core.DecisionProductCreate', GAME,
            'submission__team__game_id',
            key=('submission_id', 'product_name'),
            why='New products and their target markets.'),
    Section('decision_product_retire', 'core.DecisionProductRetire', GAME,
            'submission__team__game_id',
            key=('submission_id', 'team_product_id'),
            why='Product retirements.'),
    Section('decision_marketing', 'core.DecisionMarketing', GAME,
            'submission__team__game_id',
            exclude={'distribution_channel_detail': 'Student free text; the '
                                                    'percentages are hashed.'},
            why='Price, promotion, channels and production volume.'),
    Section('decision_market_entry', 'core.DecisionMarketEntry', GAME,
            'submission__team__game_id',
            key=('submission_id', 'market_id', 'action'),
            why='Market entry and exit.'),
    Section('decision_financing', 'core.DecisionFinancing', GAME,
            'submission__team__game_id', key=('submission',),
            why='Debt, equity and dividend decisions.'),
    Section('decision_plant', 'core.DecisionPlant', GAME, 'submission__team__game_id',
            key=('submission_id', 'market_id', 'action'),
            why='Plant build/contract manufacturing and emissions.'),
    Section('decision_partnership', 'core.DecisionPartnership', GAME,
            'submission__team__game_id',
            key=('submission_id', 'market_id', 'strategy_option_id', 'action'),
            why='Partnership commitments.'),
    Section('decision_acquisition', 'core.DecisionAcquisition', GAME,
            'submission__team__game_id',
            key=('submission_id', 'acquisition_target_id'),
            why='Acquisition attempts.'),
    Section('decision_esg', 'core.DecisionESG', GAME, 'submission__team__game_id',
            key=('submission',), why='ESG and compliance investment.'),
    Section('decision_event_response', 'core.DecisionEventResponse', GAME,
            'submission__team__game_id',
            key=('submission_id', 'event_instance_id'),
            why='Chosen responses to fired events.'),
    Section('decision_research', 'core.DecisionResearchAllocation', GAME,
            'submission__team__game_id', key=('submission_id', 'market_id'),
            why='Market research spend.'),
    Section('decision_talent', 'core.DecisionTalent', GAME, 'submission__team__game_id',
            key=('submission',), why='Headcount, salary and training decisions.'),
    Section('talent_allocation', 'core.TalentAllocation', GAME,
            'submission__team__game_id', why='Talent split across markets.'),
    Section('compliance_investment', 'core.ComplianceInvestment', GAME,
            'submission__team__game_id', why='Per-market compliance investment.'),
    Section('sc_sourcing', 'core.SourcingDecision', GAME, 'team__game_id',
            why='Sourcing strategy and tier-2/3 visibility.'),
    Section('sc_sourcing_allocation', 'core.SourcingAllocation', GAME, 'team__game_id',
            why='Per-supplier allocation percentages.'),
    Section('sc_logistics', 'core.LogisticsDecision', GAME, 'team__game_id',
            why='Mode split per lane.'),
    Section('sc_inventory', 'core.InventoryDecision', GAME, 'team__game_id',
            why='Buffer days and safety-stock triggers.'),
    Section('sc_incoterms', 'core.IncotermsDecision', GAME, 'team__game_id',
            why='Incoterms and insurance coverage.'),
    Section('sc_customs', 'core.CustomsClassificationDecision', GAME, 'team__game_id',
            why='Customs classification and reverse logistics.'),
    Section('sc_trade_finance', 'core.TradeFinanceDecision', GAME, 'team__game_id',
            why='Buyer payment instruments.'),
    Section('sc_sinosure', 'core.SinosureEnrollment', GAME, 'team__game_id',
            why='Export credit insurance coverage.'),
    Section('sc_fx_hedge', 'core.FXHedgeDecision', GAME, 'team__game_id',
            why='Hedge ratio and tenor per currency pair.'),
    Section('sc_contingency', 'core.ContingencyPlan', GAME, 'team__game_id',
            exclude={'disruption_response_playbook': 'Student free text; the '
                                                     'machine-readable rules are hashed.'},
            why='Alternate-supplier and mode-switch rules.'),
)


# --------------------------------------------------------------------------
# Market, event and modifier state carried into and out of the round.
# --------------------------------------------------------------------------
WORLD_STATE_SECTIONS = (
    Section('event_instance', 'core.EventInstance', GAME, 'game_id', key=None,
            narrative_fields=('narrative',),
            why='Which events fired, when and where.'),
    Section('active_modifier', 'core.ActiveModifier', GAME, 'game_id', key=None,
            why='Live numeric modifiers applied to segments/features/markets.'),
    Section('sc_event_instance', 'core.SCEventInstance', GAME, 'round__game_id',
            key=None, narrative_fields=('narrative',),
            why='Supply-chain events fired this game.'),
    Section('supplier_state', 'core.SupplierState', GAME, 'round__game_id',
            why='Per-round supplier capacity, quality and recovery.'),
    Section('lane_state', 'core.LaneState', GAME, 'round__game_id',
            why='Per-round lane disruption and rate modifiers.'),
    Section('government_action', 'core.GovernmentAction', GAME, 'game_id', key=None,
            narrative_fields=('narrative',),
            why='Government agent actions taken against teams and origins.'),
    Section('government_satisfaction', 'core.GovernmentSatisfaction', GAME, 'game_id',
            why='Per-market government standing carried forward.'),
    Section('compliance_enforcement', 'core.ComplianceEnforcementEvent', GAME,
            'team__game_id', key=None, narrative_fields=('narrative',),
            why='Detentions, freezes and penalties.'),
    Section('ai_investor_holding', 'core.AIInvestorHolding', GAME, 'game_id',
            exclude={'trade_reason': 'Template-authored explanation of the trade.'},
            why='Investor holdings feeding share price.'),
)


# --------------------------------------------------------------------------
# Per-team carried state. Everything the next round reads back.
# --------------------------------------------------------------------------
TEAM_STATE_SECTIONS = (
    Section('team_platform', 'core.TeamPlatform', GAME, 'team__game_id',
            key=('team_id', 'name'),
            why='Platform development progress and capitalised cost.'),
    Section('team_platform_feature_level', 'core.TeamPlatformFeatureLevel', GAME,
            'team_platform__team__game_id',
            exclude={'updated_at': 'Row-update wall clock, set by auto_now.'},
            why='Achieved feature levels per platform.'),
    Section('pending_feature_gain', 'core.PendingFeatureGain', GAME,
            'team_platform__team__game_id',
            key=('team_platform_id', 'feature_id', 'applies_round'),
            why='Lagged R&D gains not yet applied.'),
    Section('team_product', 'core.TeamProduct', GAME, 'team__game_id',
            key=('team_id', 'name'), why='Products, positioning and lifecycle.'),
    Section('team_product_platform_history', 'core.TeamProductPlatformHistory',
            GAME, 'team_product__team__game_id',
            key=('team_product_id', 'effective_from_round'),
            exclude={'switched_at': 'Row-write wall clock.'},
            why='Which platform a product was based on in each round. In the '
                'envelope because it decides how a round resolves: without it '
                'a re-based product would replay against the platform its team '
                'moved to afterwards.'),
    Section('team_product_market', 'core.TeamProductMarket', GAME,
            'team_product__team__game_id', why='Where each product is offered.'),
    Section('team_market_presence', 'core.TeamMarketPresence', GAME, 'team__game_id',
            key=('team_id', 'market_id'),
            why='Entry mode, setup progress and IP exposure.'),
    Section('team_market_modifier', 'core.TeamMarketModifier', GAME, 'team__game_id',
            key=None, why='Per-team market modifiers with expiry.'),
    Section('team_strategy_feature_level', 'core.TeamStrategyFeatureLevel', GAME,
            'team__game_id', why='Strategy-granted feature levels by round.'),
    Section('team_talent_state', 'core.TeamTalentState', GAME, 'team__game_id',
            why='Headcount, talent level and turnover by round.'),
    Section('team_plant', 'core.TeamPlant', GAME, 'team__game_id',
            key=('team_id', 'market_id', 'construction_started_round'),
            why='Plant capacity and construction progress.'),
    Section('team_partnership', 'core.TeamPartnership', GAME, 'team__game_id',
            key=('team_id', 'market_id', 'strategy_option_id', 'established_round'),
            why='Active partnerships and their investment.'),
    Section('team_acquisition', 'core.TeamAcquisition', GAME, 'team__game_id',
            why='Completed acquisitions and integration progress.'),
    Section('team_alliance_state', 'core.TeamAllianceState', GAME, 'game_id',
            exclude={'renegotiation_demands': 'Template-authored demand text; the '
                                              'satisfaction numbers are hashed.'},
            why='Alliance satisfaction and dissolution counters.'),
    Section('team_governance_commitment', 'core.TeamGovernanceCommitment', GAME,
            'game_id', why='Active governance commitments and penalties.'),
    Section('team_market_compliance', 'core.TeamMarketCompliance', GAME, 'game_id',
            why='Compliance level and the multipliers it grants.'),
    Section('team_tax_structure', 'core.TeamTaxStructure', GAME, 'game_id',
            why='Tax structure, audit history and cumulative savings.'),
    Section('team_org_structure', 'core.TeamOrganizationalStructure', GAME, 'game_id',
            why='Organisational structure and transition progress.'),
    Section('hedge_position', 'core.HedgePosition', GAME, 'team__game_id', key=None,
            why='Open and settled FX hedges.'),
)


# --------------------------------------------------------------------------
# Published results. The scoreboard a disputing team is arguing about.
# --------------------------------------------------------------------------
RESULT_SECTIONS = (
    Section('financials', 'core.RoundResultFinancials', GAME, 'game_id',
            why='Full income statement, balance sheet and cash flow.'),
    Section('market_revenue', 'core.RoundResultMarketRevenue', GAME, 'game_id',
            why='Revenue, profit and share by market.'),
    Section('product_market', 'core.RoundResultProductMarket', GAME, 'game_id',
            why='Units, price and cost by product-market.'),
    Section('adoption', 'core.RoundResultAdoption', GAME, 'game_id',
            why='Bass adoption pools, fit and share by segment.'),
    Section('performance', 'core.RoundResultPerformanceIndex', GAME, 'game_id',
            why='Performance index and its change.'),
    Section('coherence', 'core.RoundResultCoherence', GAME, 'game_id',
            why='Coherence formula, RAG and blended score.'),
    Section('resilience', 'core.ResilienceScoreHistory', GAME, 'round__game_id',
            why='Supply-chain resilience score and its components.'),
    Section('share_price', 'core.SharePriceHistory', GAME, 'game_id',
            why='Share price and the sentiment that produced it.'),
    Section('leaderboard', 'core.LeaderboardEntry', GAME, 'game_id',
            why='Published rank and the values it was ranked on.'),
    Section('esg_impact', 'core.ESGEconomicImpact', GAME, 'game_id', key=None,
            exclude={'description': 'Template-authored explanation of the benefit.'},
            why='ESG savings booked into the financials.'),
    Section('talent_impact', 'core.TalentEconomicImpact', GAME, 'game_id',
            why='Talent modifiers booked into the financials.'),
    Section('partnership_impact', 'core.PartnershipEconomicImpact', GAME, 'game_id',
            key=None,
            exclude={'description': 'Template-authored explanation of the benefit.'},
            why='Partnership benefits booked into the financials.'),
    Section('agent_cycle', 'core.AgentCycleLog', GAME, 'game_id',
            exclude={'errors': 'Diagnostic error strings from the agent cycle.'},
            narrative_fields=('narrative_items', 'agent_summary'),
            why='Deterministic agent actions and convergence.'),
    Section('instructor_alert', 'core.InstructorAlert', GAME, 'game_id', key=None,
            filters={'source': 'engine'},
            exclude={'acknowledged': 'Operator UI state set after publication.',
                     'teaching_note': 'Template-authored coaching text.',
                     'detail': 'Template-authored alert body.'},
            why='Alerts raised by the deterministic alert pass.'),
)


# --------------------------------------------------------------------------
# Phase-2 prose. Never part of the competitive hash; hashed and reported on
# its own so a narrative difference is visible but not disqualifying.
# --------------------------------------------------------------------------
NARRATIVE_SECTIONS = (
    Section('strategic_briefing', 'core.StrategicBriefing', GAME, 'game_id',
            narrative_fields=('executive_summary', 'performance_analysis',
                              'investment_returns', 'investor_sentiment',
                              'competitive_landscape', 'strategic_recommendations',
                              'risk_alerts'),
            in_output=False, why='Phase-2 team briefing prose.'),
    Section('market_intelligence', 'core.MarketIntelligenceBrief', GAME, 'game_id',
            narrative_fields=('brief_content',),
            in_output=False, why='Phase-2 market intelligence prose.'),
    Section('narrative_alert', 'core.InstructorAlert', GAME, 'game_id', key=None,
            filters={'source': 'narrative'},
            narrative_fields=('title', 'detail', 'teaching_note'),
            exclude={'acknowledged': 'Operator UI state set after publication.'},
            in_output=False,
            why='Phase-2 coaching notes and RAG commentary for instructors.'),
)


INPUT_SECTIONS = (CONFIG_SECTIONS + OVERRIDE_SECTIONS + GAME_SECTIONS +
                  DECISION_SECTIONS + WORLD_STATE_SECTIONS +
                  TEAM_STATE_SECTIONS + RESULT_SECTIONS)

OUTPUT_SECTIONS = tuple(s for s in INPUT_SECTIONS if s.in_output)

CONFIG_SECTION_NAMES = tuple(s.name for s in CONFIG_SECTIONS + OVERRIDE_SECTIONS)

ALL_SECTIONS = INPUT_SECTIONS + NARRATIVE_SECTIONS


# Natural keys for models that a manifest references but does not snapshot, so
# a foreign key to them still resolves without a sequence value.
EXTERNAL_KEYS = {
    'core.User': ('username',),
    'core.Section': ('section_code',),
    # Scenario.created_by / Game.created_by point at Django's own auth user.
    'auth.User': ('username',),
}


def sections_by_name(sections=ALL_SECTIONS):
    return {section.name: section for section in sections}


def duplicate_models(sections):
    """Model labels claimed by more than one section in the same snapshot."""
    seen, duplicates = {}, set()
    for section in sections:
        if section.model in seen:
            duplicates.add(section.model)
        seen[section.model] = section.name
    return duplicates

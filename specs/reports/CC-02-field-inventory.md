# CC-02 Field Inventory Report

**Database:** globalstrat_plus @ 192.168.50.38
**Source branch:** cc-02-decision-taxonomy
**Django models registered:** 155
**Physical tables in public schema:** 119

This report is the CC-02 §2 verification artifact. Section A is the
per-model field inventory for every coverage-required model that
physically exists as a table. Section B is the ghost model roster.
Section C reports the §5 EXTEND collision check.

## Section A — Per-model field inventory (physically-existing tables)

### core.DecisionAcquisition

- **File:** `backend/core/models/decisions.py:329`
- **Managed:** True
- **Physical table:** `decision_acquisition` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - acquisition_target | ForeignKey | related=core.AcquisitionTarget

**PostgreSQL `\d decision_acquisition`:**

  - id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL
  - acquisition_target_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionBudgetAllocation

- **File:** `backend/core/models/decisions.py:48`
- **Managed:** True
- **Physical table:** `decision_budget_allocation` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | OneToOneField | unique=True | related=core.DecisionSubmission
  - rd_budget | DecimalField
  - marketing_budget | DecimalField
  - strategy_budget | DecimalField
  - research_budget | DecimalField

**PostgreSQL `\d decision_budget_allocation`:**

  - id | bigint | NOT NULL
  - rd_budget | numeric | NOT NULL
  - marketing_budget | numeric | NOT NULL
  - strategy_budget | numeric | NOT NULL
  - research_budget | numeric | NOT NULL
  - submission_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionChangeLog

- **File:** `backend/core/models/cc21_models.py:40`
- **Managed:** True
- **Physical table:** `decision_change_log` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - team | ForeignKey | related=core.Team
  - user | ForeignKey | related=core.User
  - round_number | IntegerField
  - page | CharField | max_length=50
  - change_description | CharField | max_length=500
  - change_data | JSONField | null=True | blank=True
  - created_at | DateTimeField | blank=True

**PostgreSQL `\d decision_change_log`:**

  - id | bigint | NOT NULL
  - round_number | integer | NOT NULL
  - page | character varying | len=50 | NOT NULL
  - change_description | character varying | len=500 | NOT NULL
  - change_data | jsonb
  - created_at | timestamp with time zone | NOT NULL
  - team_id | bigint | NOT NULL
  - user_id | integer | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionESG

- **File:** `backend/core/models/decisions.py:345`
- **Managed:** True
- **Physical table:** `decision_esg` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | OneToOneField | unique=True | related=core.DecisionSubmission
  - environmental_investment | DecimalField
  - social_investment | DecimalField
  - governance_commitments | JSONField | null=True | blank=True

**PostgreSQL `\d decision_esg`:**

  - id | bigint | NOT NULL
  - environmental_investment | numeric | NOT NULL
  - social_investment | numeric | NOT NULL
  - governance_commitments | jsonb
  - submission_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionEventResponse

- **File:** `backend/core/models/decisions.py:361`
- **Managed:** True
- **Physical table:** `decision_event_response` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - event_instance | ForeignKey | null=True | blank=True | related=core.EventInstance
  - response | ForeignKey | related=core.EventResponseDefinition

**PostgreSQL `\d decision_event_response`:**

  - id | bigint | NOT NULL
  - response_id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL
  - event_instance_id | bigint

**Field-registry vs. DB delta:** none.

### core.DecisionFinancing

- **File:** `backend/core/models/decisions.py:259`
- **Managed:** True
- **Physical table:** `decision_financing` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | OneToOneField | unique=True | related=core.DecisionSubmission
  - new_debt | DecimalField
  - debt_repayment | DecimalField
  - new_equity | DecimalField
  - dividend_per_share | DecimalField

**PostgreSQL `\d decision_financing`:**

  - id | bigint | NOT NULL
  - new_debt | numeric | NOT NULL
  - debt_repayment | numeric | NOT NULL
  - new_equity | numeric | NOT NULL
  - dividend_per_share | numeric | NOT NULL
  - submission_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionMarketEntry

- **File:** `backend/core/models/decisions.py:221`
- **Managed:** True
- **Physical table:** `decision_market_entry` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - market | ForeignKey | related=core.MarketDefinition
  - entry_mode | ForeignKey | related=core.EntryModeDefinition
  - initial_investment | DecimalField
  - action | CharField | max_length=20 | choices=3
  - integration_strategy | CharField | max_length=20 | null=True | blank=True | choices=3

**PostgreSQL `\d decision_market_entry`:**

  - id | bigint | NOT NULL
  - initial_investment | numeric | NOT NULL
  - action | character varying | len=20 | NOT NULL
  - entry_mode_id | bigint | NOT NULL
  - market_id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL
  - integration_strategy | character varying | len=20

**Field-registry vs. DB delta:** none.

### core.DecisionMarketing

- **File:** `backend/core/models/decisions.py:174`
- **Managed:** True
- **Physical table:** `decision_marketing` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - team_product | ForeignKey | related=core.TeamProduct
  - market | ForeignKey | related=core.MarketDefinition
  - retail_price | DecimalField
  - promotion_budget | DecimalField
  - campaign_focus_feature_ids | JSONField
  - channel_digital_pct | DecimalField
  - channel_traditional_pct | DecimalField
  - channel_trade_pct | DecimalField
  - distribution_strategy | CharField | max_length=30 | choices=5
  - distribution_investment | DecimalField
  - sales_team_count | IntegerField
  - distribution_channel_detail | JSONField | blank=True
  - production_volume | IntegerField
  - production_source_market | ForeignKey | related=core.MarketDefinition
  - demand_estimate | IntegerField

**PostgreSQL `\d decision_marketing`:**

  - id | bigint | NOT NULL
  - retail_price | numeric | NOT NULL
  - promotion_budget | numeric | NOT NULL
  - campaign_focus_feature_ids | jsonb | NOT NULL
  - channel_digital_pct | numeric | NOT NULL
  - channel_traditional_pct | numeric | NOT NULL
  - channel_trade_pct | numeric | NOT NULL
  - distribution_strategy | character varying | len=30 | NOT NULL
  - distribution_investment | numeric | NOT NULL
  - production_volume | integer | NOT NULL
  - demand_estimate | integer | NOT NULL
  - market_id | bigint | NOT NULL
  - production_source_market_id | bigint | NOT NULL
  - team_product_id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL
  - sales_team_count | integer | NOT NULL
  - distribution_channel_detail | jsonb | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionPartnership

- **File:** `backend/core/models/decisions.py:301`
- **Managed:** True
- **Physical table:** `decision_partnership` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - market | ForeignKey | related=core.MarketDefinition
  - strategy_option | ForeignKey | related=core.StrategyOptionDefinition
  - annual_investment | DecimalField
  - action | CharField | max_length=20 | choices=3

**PostgreSQL `\d decision_partnership`:**

  - id | bigint | NOT NULL
  - annual_investment | numeric | NOT NULL
  - action | character varying | len=20 | NOT NULL
  - market_id | bigint | NOT NULL
  - strategy_option_id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionPlant

- **File:** `backend/core/models/decisions.py:276`
- **Managed:** True
- **Physical table:** `decision_plant` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - market | ForeignKey | related=core.MarketDefinition
  - action | CharField | max_length=20 | choices=3
  - capacity_units | IntegerField | null=True | blank=True
  - contract_mfg_volume | IntegerField | null=True | blank=True

**PostgreSQL `\d decision_plant`:**

  - id | bigint | NOT NULL
  - action | character varying | len=20 | NOT NULL
  - capacity_units | integer
  - contract_mfg_volume | integer
  - market_id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionPlatformDevelopment

- **File:** `backend/core/models/decisions.py:95`
- **Managed:** True
- **Physical table:** `decision_platform_development` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - platform_generation | ForeignKey | related=core.PlatformGenerationDefinition
  - method | CharField | max_length=20 | choices=3
  - committed_cost | DecimalField
  - platform_name | CharField | max_length=100 | blank=True
  - feature_levels | JSONField | blank=True

**PostgreSQL `\d decision_platform_development`:**

  - id | bigint | NOT NULL
  - method | character varying | len=20 | NOT NULL
  - committed_cost | numeric | NOT NULL
  - platform_generation_id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL
  - feature_levels | jsonb | NOT NULL
  - platform_name | character varying | len=100 | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionProductCreate

- **File:** `backend/core/models/decisions.py:126`
- **Managed:** True
- **Physical table:** `decision_product_create` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - team_platform | ForeignKey | related=core.TeamPlatform
  - product_name | CharField | max_length=200
  - positioning | CharField | max_length=20 | choices=4
  - target_market_ids | JSONField

**PostgreSQL `\d decision_product_create`:**

  - id | bigint | NOT NULL
  - product_name | character varying | len=200 | NOT NULL
  - positioning | character varying | len=20 | NOT NULL
  - target_market_ids | jsonb | NOT NULL
  - team_platform_id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionProductRetire

- **File:** `backend/core/models/decisions.py:152`
- **Managed:** True
- **Physical table:** `decision_product_retire` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - team_product | ForeignKey | related=core.TeamProduct
  - timing | CharField | max_length=20 | choices=2

**PostgreSQL `\d decision_product_retire`:**

  - id | bigint | NOT NULL
  - timing | character varying | len=20 | NOT NULL
  - team_product_id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionRDInvestment

- **File:** `backend/core/models/decisions.py:65`
- **Managed:** True
- **Physical table:** `decision_rd_investment` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - team_platform | ForeignKey | related=core.TeamPlatform
  - feature | ForeignKey | related=core.FeatureDefinition
  - method | CharField | max_length=20 | choices=2
  - amount | DecimalField
  - target_level | IntegerField | null=True | blank=True
  - calculated_cost | DecimalField

**PostgreSQL `\d decision_rd_investment`:**

  - id | bigint | NOT NULL
  - method | character varying | len=20 | NOT NULL
  - amount | numeric | NOT NULL
  - feature_id | bigint | NOT NULL
  - team_platform_id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL
  - calculated_cost | numeric | NOT NULL
  - target_level | integer

**Field-registry vs. DB delta:** none.

### core.DecisionResearchAllocation

- **File:** `backend/core/models/decisions.py:382`
- **Managed:** True
- **Physical table:** `decision_research_allocation` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | ForeignKey | related=core.DecisionSubmission
  - market | ForeignKey | related=core.MarketDefinition
  - allocation_amount | DecimalField

**PostgreSQL `\d decision_research_allocation`:**

  - id | bigint | NOT NULL
  - allocation_amount | numeric | NOT NULL
  - market_id | bigint | NOT NULL
  - submission_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionSubmission

- **File:** `backend/core/models/decisions.py:15`
- **Managed:** True
- **Physical table:** `decision_submission` (verified present)

**Django `_meta.get_fields()`:**

  - budget_allocation | OneToOneRel | null=True | related=core.DecisionBudgetAllocation
  - rd_investments | ManyToOneRel | null=True | related=core.DecisionRDInvestment
  - platform_developments | ManyToOneRel | null=True | related=core.DecisionPlatformDevelopment
  - product_creates | ManyToOneRel | null=True | related=core.DecisionProductCreate
  - product_retires | ManyToOneRel | null=True | related=core.DecisionProductRetire
  - marketing_decisions | ManyToOneRel | null=True | related=core.DecisionMarketing
  - market_entries | ManyToOneRel | null=True | related=core.DecisionMarketEntry
  - financing | OneToOneRel | null=True | related=core.DecisionFinancing
  - plant_decisions | ManyToOneRel | null=True | related=core.DecisionPlant
  - partnerships | ManyToOneRel | null=True | related=core.DecisionPartnership
  - acquisitions | ManyToOneRel | null=True | related=core.DecisionAcquisition
  - esg | OneToOneRel | null=True | related=core.DecisionESG
  - event_responses | ManyToOneRel | null=True | related=core.DecisionEventResponse
  - research_allocations | ManyToOneRel | null=True | related=core.DecisionResearchAllocation
  - talent | OneToOneRel | null=True | related=core.DecisionTalent
  - talent_allocations | ManyToOneRel | null=True | related=core.TalentAllocation
  - compliance_investments | ManyToOneRel | null=True | related=core.ComplianceInvestment
  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - team | ForeignKey | related=core.Team
  - round | ForeignKey | related=core.Round
  - status | CharField | max_length=20 | choices=2
  - locked_at | DateTimeField | null=True | blank=True
  - locked_by | ForeignKey | null=True | blank=True | related=auth.User
  - team_notes | TextField | null=True | blank=True

**PostgreSQL `\d decision_submission`:**

  - id | bigint | NOT NULL
  - status | character varying | len=20 | NOT NULL
  - locked_at | timestamp with time zone
  - team_notes | text
  - locked_by_id | integer
  - round_id | bigint | NOT NULL
  - team_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.DecisionTalent

- **File:** `backend/core/models/talent.py:10`
- **Managed:** True
- **Physical table:** `decision_talent` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - submission | OneToOneField | unique=True | related=core.DecisionSubmission
  - rd_headcount | IntegerField
  - rd_salary_level | IntegerField | choices=5
  - rd_training_budget | DecimalField
  - commercial_headcount | IntegerField
  - commercial_salary_level | IntegerField | choices=5
  - commercial_training_budget | DecimalField
  - operations_headcount | IntegerField
  - operations_salary_level | IntegerField | choices=5
  - operations_training_budget | DecimalField

**PostgreSQL `\d decision_talent`:**

  - id | bigint | NOT NULL
  - rd_headcount | integer | NOT NULL
  - rd_salary_level | integer | NOT NULL
  - rd_training_budget | numeric | NOT NULL
  - commercial_headcount | integer | NOT NULL
  - commercial_salary_level | integer | NOT NULL
  - commercial_training_budget | numeric | NOT NULL
  - operations_headcount | integer | NOT NULL
  - operations_salary_level | integer | NOT NULL
  - operations_training_budget | numeric | NOT NULL
  - submission_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.ESGEconomicImpact

- **File:** `backend/core/models/cc24_models.py:10`
- **Managed:** True
- **Physical table:** `esg_economic_impact` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - game | ForeignKey | related=core.Game
  - team | ForeignKey | related=core.Team
  - round_number | IntegerField
  - market | ForeignKey | null=True | blank=True | related=core.MarketDefinition
  - benefit_type | CharField | max_length=50 | choices=4
  - base_value | DecimalField
  - effective_value | DecimalField
  - savings | DecimalField
  - esg_level | DecimalField
  - description | CharField | max_length=500 | blank=True

**PostgreSQL `\d esg_economic_impact`:**

  - id | bigint | NOT NULL
  - round_number | integer | NOT NULL
  - benefit_type | character varying | len=50 | NOT NULL
  - base_value | numeric | NOT NULL
  - effective_value | numeric | NOT NULL
  - savings | numeric | NOT NULL
  - esg_level | numeric | NOT NULL
  - description | character varying | len=500 | NOT NULL
  - game_id | bigint | NOT NULL
  - market_id | bigint
  - team_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.CommunicationAssignment

- **File:** `backend/core/models/cc32_models.py:11`
- **Managed:** True
- **Physical table:** `communication_assignment` (verified present)

**Django `_meta.get_fields()`:**

  - submissions | ManyToOneRel | null=True | related=core.TeamCommunication
  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - scenario | ForeignKey | related=core.Scenario
  - code | CharField | max_length=50
  - name | CharField | max_length=200
  - name_zh | CharField | max_length=200 | blank=True
  - trigger_type | CharField | max_length=30 | choices=3
  - trigger_condition | JSONField
  - audience | CharField | max_length=50 | choices=6
  - prompt_text | TextField
  - prompt_text_zh | TextField | blank=True
  - word_limit | IntegerField
  - evaluation_criteria | JSONField
  - is_mandatory | BooleanField
  - coherence_weight | DecimalField
  - display_order | IntegerField

**PostgreSQL `\d communication_assignment`:**

  - id | bigint | NOT NULL
  - code | character varying | len=50 | NOT NULL
  - name | character varying | len=200 | NOT NULL
  - trigger_type | character varying | len=30 | NOT NULL
  - trigger_condition | jsonb | NOT NULL
  - audience | character varying | len=50 | NOT NULL
  - prompt_text | text | NOT NULL
  - word_limit | integer | NOT NULL
  - evaluation_criteria | jsonb | NOT NULL
  - is_mandatory | boolean | NOT NULL
  - coherence_weight | numeric | NOT NULL
  - display_order | integer | NOT NULL
  - scenario_id | bigint | NOT NULL
  - name_zh | character varying | len=200 | NOT NULL
  - prompt_text_zh | text | NOT NULL

**Field-registry vs. DB delta:** none.

### core.TeamCommunication

- **File:** `backend/core/models/cc32_models.py:72`
- **Managed:** True
- **Physical table:** `team_communication` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - game | ForeignKey | related=core.Game
  - team | ForeignKey | related=core.Team
  - round | ForeignKey | related=core.Round
  - assignment | ForeignKey | related=core.CommunicationAssignment
  - content | TextField
  - word_count | IntegerField
  - submitted_at | DateTimeField | null=True | blank=True
  - is_draft | BooleanField
  - evaluation | JSONField | null=True | blank=True
  - coherence_contribution | DecimalField

**PostgreSQL `\d team_communication`:**

  - id | bigint | NOT NULL
  - content | text | NOT NULL
  - word_count | integer | NOT NULL
  - submitted_at | timestamp with time zone
  - is_draft | boolean | NOT NULL
  - evaluation | jsonb
  - coherence_contribution | numeric | NOT NULL
  - assignment_id | bigint | NOT NULL
  - game_id | bigint | NOT NULL
  - team_id | bigint | NOT NULL
  - round_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.OrganizationalStructureType

- **File:** `backend/core/models/cc32b_models.py:11`
- **Managed:** True
- **Physical table:** `core_organizationalstructuretype` (verified present)

**Django `_meta.get_fields()`:**

  - current_teams | ManyToOneRel | null=True | related=core.TeamOrganizationalStructure
  - transitioning_from | ManyToOneRel | null=True | related=core.TeamOrganizationalStructure
  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - scenario | ForeignKey | related=core.Scenario
  - code | CharField | max_length=30
  - name | CharField | max_length=100
  - name_zh | CharField | max_length=200 | blank=True
  - description | TextField
  - description_zh | TextField | blank=True
  - base_overhead_per_round | DecimalField
  - per_market_coordination_cost | DecimalField
  - hq_talent_effectiveness_modifier | DecimalField
  - local_talent_effectiveness_modifier | DecimalField
  - innovation_modifier | DecimalField
  - coordination_efficiency | DecimalField
  - decision_speed_modifier | DecimalField
  - optimal_market_range_min | IntegerField
  - optimal_market_range_max | IntegerField
  - overextension_cost_per_market | DecimalField
  - overextension_effectiveness_penalty | DecimalField
  - transition_cost | DecimalField
  - transition_disruption_rounds | IntegerField
  - display_order | IntegerField

**PostgreSQL `\d core_organizationalstructuretype`:**

  - id | bigint | NOT NULL
  - code | character varying | len=30 | NOT NULL
  - name | character varying | len=100 | NOT NULL
  - description | text | NOT NULL
  - base_overhead_per_round | numeric | NOT NULL
  - per_market_coordination_cost | numeric | NOT NULL
  - hq_talent_effectiveness_modifier | numeric | NOT NULL
  - local_talent_effectiveness_modifier | numeric | NOT NULL
  - innovation_modifier | numeric | NOT NULL
  - coordination_efficiency | numeric | NOT NULL
  - decision_speed_modifier | numeric | NOT NULL
  - optimal_market_range_min | integer | NOT NULL
  - optimal_market_range_max | integer | NOT NULL
  - overextension_cost_per_market | numeric | NOT NULL
  - overextension_effectiveness_penalty | numeric | NOT NULL
  - transition_cost | numeric | NOT NULL
  - transition_disruption_rounds | integer | NOT NULL
  - display_order | integer | NOT NULL
  - scenario_id | bigint | NOT NULL
  - description_zh | text | NOT NULL
  - name_zh | character varying | len=200 | NOT NULL

**Field-registry vs. DB delta:** none.

### core.TeamOrganizationalStructure

- **File:** `backend/core/models/cc32b_models.py:87`
- **Managed:** True
- **Physical table:** `core_teamorganizationalstructure` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - game | ForeignKey | related=core.Game
  - team | ForeignKey | related=core.Team
  - current_structure | ForeignKey | null=True | related=core.OrganizationalStructureType
  - adopted_round | IntegerField
  - transitioning_from | ForeignKey | null=True | blank=True | related=core.OrganizationalStructureType
  - transition_rounds_remaining | IntegerField

**PostgreSQL `\d core_teamorganizationalstructure`:**

  - id | bigint | NOT NULL
  - adopted_round | integer | NOT NULL
  - transition_rounds_remaining | integer | NOT NULL
  - current_structure_id | bigint
  - game_id | bigint | NOT NULL
  - team_id | bigint | NOT NULL
  - transitioning_from_id | bigint

**Field-registry vs. DB delta:** none.

### core.TaxStructureType

- **File:** `backend/core/models/cc32c_models.py:6`
- **Managed:** True
- **Physical table:** `tax_structure_type` (verified present)

**Django `_meta.get_fields()`:**

  - teamtaxstructure | ManyToOneRel | null=True | related=core.TeamTaxStructure
  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - scenario | ForeignKey | related=core.Scenario
  - code | CharField | max_length=30
  - name | CharField | max_length=100
  - name_zh | CharField | max_length=200 | blank=True
  - description | TextField
  - description_zh | TextField | blank=True
  - setup_cost | DecimalField
  - annual_maintenance_cost | DecimalField
  - effective_tax_reduction_pct | DecimalField
  - repatriation_cost_reduction_pct | DecimalField
  - audit_probability_per_round | DecimalField
  - audit_penalty_multiplier | DecimalField
  - value_investor_modifier | DecimalField
  - esg_investor_modifier | DecimalField
  - regulator_modifier | DecimalField
  - anti_corruption_conflict | BooleanField
  - display_order | IntegerField

**PostgreSQL `\d tax_structure_type`:**

  - id | bigint | NOT NULL
  - code | character varying | len=30 | NOT NULL
  - name | character varying | len=100 | NOT NULL
  - description | text | NOT NULL
  - setup_cost | numeric | NOT NULL
  - annual_maintenance_cost | numeric | NOT NULL
  - effective_tax_reduction_pct | numeric | NOT NULL
  - repatriation_cost_reduction_pct | numeric | NOT NULL
  - audit_probability_per_round | numeric | NOT NULL
  - audit_penalty_multiplier | numeric | NOT NULL
  - value_investor_modifier | numeric | NOT NULL
  - esg_investor_modifier | numeric | NOT NULL
  - regulator_modifier | numeric | NOT NULL
  - anti_corruption_conflict | boolean | NOT NULL
  - display_order | integer | NOT NULL
  - scenario_id | bigint | NOT NULL
  - description_zh | text | NOT NULL
  - name_zh | character varying | len=200 | NOT NULL

**Field-registry vs. DB delta:** none.

### core.TeamTaxStructure

- **File:** `backend/core/models/cc32c_models.py:64`
- **Managed:** True
- **Physical table:** `team_tax_structure` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - game | ForeignKey | related=core.Game
  - team | ForeignKey | related=core.Team
  - current_structure | ForeignKey | null=True | blank=True | related=core.TaxStructureType
  - adopted_round | IntegerField
  - setup_cost_paid | BooleanField
  - times_audited | IntegerField
  - cumulative_audit_penalties | DecimalField
  - cumulative_tax_savings | DecimalField
  - last_audit_round | IntegerField | null=True | blank=True

**PostgreSQL `\d team_tax_structure`:**

  - id | bigint | NOT NULL
  - adopted_round | integer | NOT NULL
  - setup_cost_paid | boolean | NOT NULL
  - times_audited | integer | NOT NULL
  - cumulative_audit_penalties | numeric | NOT NULL
  - cumulative_tax_savings | numeric | NOT NULL
  - last_audit_round | integer
  - current_structure_id | bigint
  - game_id | bigint | NOT NULL
  - team_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.AlliancePartnerProfile

- **File:** `backend/core/models/cc32d_models.py:11`
- **Managed:** True
- **Physical table:** `alliance_partner_profile` (verified present)

**Django `_meta.get_fields()`:**

  - alliance_states | ManyToOneRel | null=True | related=core.TeamAllianceState
  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - scenario | ForeignKey | related=core.Scenario
  - partnership_code | CharField | max_length=50
  - market | ForeignKey | related=core.MarketDefinition
  - name | CharField | max_length=100
  - name_zh | CharField | max_length=200 | blank=True
  - partner_type | CharField | max_length=30 | choices=5
  - description | TextField
  - description_zh | TextField | blank=True
  - preferences | JSONField
  - satisfaction_floor | DecimalField
  - renegotiation_threshold | DecimalField
  - patience_rounds | IntegerField
  - benefit_curve | CharField | max_length=20 | choices=3

**PostgreSQL `\d alliance_partner_profile`:**

  - id | bigint | NOT NULL
  - partnership_code | character varying | len=50 | NOT NULL
  - name | character varying | len=100 | NOT NULL
  - partner_type | character varying | len=30 | NOT NULL
  - description | text | NOT NULL
  - preferences | jsonb | NOT NULL
  - satisfaction_floor | numeric | NOT NULL
  - renegotiation_threshold | numeric | NOT NULL
  - patience_rounds | integer | NOT NULL
  - benefit_curve | character varying | len=20 | NOT NULL
  - market_id | bigint | NOT NULL
  - scenario_id | bigint | NOT NULL
  - description_zh | text | NOT NULL
  - name_zh | character varying | len=200 | NOT NULL

**Field-registry vs. DB delta:** none.

### core.TeamAllianceState

- **File:** `backend/core/models/cc32d_models.py:81`
- **Managed:** True
- **Physical table:** `team_alliance_state` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - game | ForeignKey | related=core.Game
  - team | ForeignKey | related=core.Team
  - partner_profile | ForeignKey | related=core.AlliancePartnerProfile
  - market | ForeignKey | related=core.MarketDefinition
  - satisfaction | DecimalField
  - feature_satisfaction | JSONField
  - rounds_below_renegotiation | IntegerField
  - rounds_below_dissolution | IntegerField
  - status | CharField | max_length=20 | choices=5
  - benefit_delivery_pct | DecimalField
  - renegotiation_demands | JSONField | null=True | blank=True
  - established_round | IntegerField
  - dissolved_round | IntegerField | null=True | blank=True

**PostgreSQL `\d team_alliance_state`:**

  - id | bigint | NOT NULL
  - satisfaction | numeric | NOT NULL
  - feature_satisfaction | jsonb | NOT NULL
  - rounds_below_renegotiation | integer | NOT NULL
  - rounds_below_dissolution | integer | NOT NULL
  - status | character varying | len=20 | NOT NULL
  - benefit_delivery_pct | numeric | NOT NULL
  - renegotiation_demands | jsonb
  - established_round | integer | NOT NULL
  - dissolved_round | integer
  - game_id | bigint | NOT NULL
  - market_id | bigint | NOT NULL
  - partner_profile_id | bigint | NOT NULL
  - team_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.GovernanceCommitmentType

- **File:** `backend/core/models/cc31_models.py:223`
- **Managed:** True
- **Physical table:** `governance_commitment_type` (verified present)

**Django `_meta.get_fields()`:**

  - team_commitments | ManyToOneRel | null=True | related=core.TeamGovernanceCommitment
  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - scenario | ForeignKey | related=core.Scenario
  - code | CharField | max_length=30
  - name | CharField | max_length=100
  - name_zh | CharField | max_length=200 | blank=True
  - description | TextField
  - description_zh | TextField | blank=True
  - ongoing_cost_per_round | DecimalField
  - benefits | JSONField
  - interactions | JSONField
  - revocation_penalty | JSONField
  - prerequisite | JSONField | null=True | blank=True
  - amplifier | JSONField | null=True | blank=True
  - display_order | IntegerField

**PostgreSQL `\d governance_commitment_type`:**

  - id | bigint | NOT NULL
  - code | character varying | len=30 | NOT NULL
  - name | character varying | len=100 | NOT NULL
  - description | text | NOT NULL
  - ongoing_cost_per_round | numeric | NOT NULL
  - benefits | jsonb | NOT NULL
  - interactions | jsonb | NOT NULL
  - revocation_penalty | jsonb | NOT NULL
  - prerequisite | jsonb
  - amplifier | jsonb
  - display_order | integer | NOT NULL
  - scenario_id | bigint | NOT NULL
  - description_zh | text | NOT NULL
  - name_zh | character varying | len=200 | NOT NULL

**Field-registry vs. DB delta:** none.

### core.GovernmentAction

- **File:** `backend/core/models/cc32f_models.py:131`
- **Managed:** True
- **Physical table:** `government_action` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - game | ForeignKey | related=core.Game
  - round | ForeignKey | related=core.Round
  - market | ForeignKey | related=core.MarketDefinition
  - action_type | CharField | max_length=30 | choices=9
  - target_team | ForeignKey | null=True | blank=True | related=core.Team
  - target_origin | ForeignKey | null=True | blank=True | related=core.MarketDefinition
  - parameters | JSONField
  - narrative | TextField | blank=True
  - created_at | DateTimeField | blank=True

**PostgreSQL `\d government_action`:**

  - id | bigint | NOT NULL
  - action_type | character varying | len=30 | NOT NULL
  - parameters | jsonb | NOT NULL
  - narrative | text | NOT NULL
  - created_at | timestamp with time zone | NOT NULL
  - game_id | bigint | NOT NULL
  - market_id | bigint | NOT NULL
  - round_id | bigint | NOT NULL
  - target_origin_id | bigint
  - target_team_id | bigint

**Field-registry vs. DB delta:** none.

### core.GovernmentProfile

- **File:** `backend/core/models/cc32f_models.py:11`
- **Managed:** True
- **Physical table:** `government_profile` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - scenario | ForeignKey | related=core.Scenario
  - market | ForeignKey | related=core.MarketDefinition
  - name | CharField | max_length=100
  - name_zh | CharField | max_length=200 | blank=True
  - description | TextField
  - description_zh | TextField | blank=True
  - policy_priorities | JSONField
  - incentive_threshold | DecimalField
  - warning_threshold | DecimalField
  - restriction_threshold | DecimalField
  - max_incentive_value_per_round | DecimalField
  - procurement_budget_per_round | DecimalField
  - procurement_frequency | IntegerField
  - policy_volatility | DecimalField
  - patience_rounds | IntegerField

**PostgreSQL `\d government_profile`:**

  - id | bigint | NOT NULL
  - name | character varying | len=100 | NOT NULL
  - description | text | NOT NULL
  - policy_priorities | jsonb | NOT NULL
  - incentive_threshold | numeric | NOT NULL
  - warning_threshold | numeric | NOT NULL
  - restriction_threshold | numeric | NOT NULL
  - max_incentive_value_per_round | numeric | NOT NULL
  - procurement_budget_per_round | numeric | NOT NULL
  - procurement_frequency | integer | NOT NULL
  - policy_volatility | numeric | NOT NULL
  - patience_rounds | integer | NOT NULL
  - market_id | bigint | NOT NULL
  - scenario_id | bigint | NOT NULL
  - description_zh | text | NOT NULL
  - name_zh | character varying | len=200 | NOT NULL

**Field-registry vs. DB delta:** none.

### core.GovernmentSatisfaction

- **File:** `backend/core/models/cc32f_models.py:85`
- **Managed:** True
- **Physical table:** `government_satisfaction` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - game | ForeignKey | related=core.Game
  - team | ForeignKey | related=core.Team
  - market | ForeignKey | related=core.MarketDefinition
  - satisfaction | DecimalField
  - objective_scores | JSONField
  - rounds_below_warning | IntegerField
  - rounds_below_restriction | IntegerField
  - status | CharField | max_length=20 | choices=5
  - active_incentive | JSONField | null=True | blank=True
  - active_restriction | JSONField | null=True | blank=True

**PostgreSQL `\d government_satisfaction`:**

  - id | bigint | NOT NULL
  - satisfaction | numeric | NOT NULL
  - objective_scores | jsonb | NOT NULL
  - rounds_below_warning | integer | NOT NULL
  - rounds_below_restriction | integer | NOT NULL
  - status | character varying | len=20 | NOT NULL
  - active_incentive | jsonb
  - active_restriction | jsonb
  - game_id | bigint | NOT NULL
  - market_id | bigint | NOT NULL
  - team_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.TeamGovernanceCommitment

- **File:** `backend/core/models/cc31_models.py:275`
- **Managed:** True
- **Physical table:** `team_governance_commitment` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - game | ForeignKey | related=core.Game
  - team | ForeignKey | related=core.Team
  - commitment_type | ForeignKey | related=core.GovernanceCommitmentType
  - is_active | BooleanField
  - activated_round | IntegerField | null=True | blank=True
  - revoked_round | IntegerField | null=True | blank=True
  - penalty_rounds_remaining | IntegerField

**PostgreSQL `\d team_governance_commitment`:**

  - id | bigint | NOT NULL
  - is_active | boolean | NOT NULL
  - activated_round | integer
  - revoked_round | integer
  - penalty_rounds_remaining | integer | NOT NULL
  - commitment_type_id | bigint | NOT NULL
  - game_id | bigint | NOT NULL
  - team_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.AcquisitionTarget

- **File:** `backend/core/models/scenario.py:615`
- **Managed:** True
- **Physical table:** `acquisition_target` (verified present)

**Django `_meta.get_fields()`:**

  - acquisition_decisions | ManyToOneRel | null=True | related=core.DecisionAcquisition
  - team_acquisitions | ManyToOneRel | null=True | related=core.TeamAcquisition
  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - scenario | ForeignKey | related=core.Scenario
  - market | ForeignKey | related=core.MarketDefinition
  - target_name | CharField | max_length=200
  - target_name_zh | CharField | max_length=200 | blank=True
  - description | TextField
  - description_zh | TextField | blank=True
  - base_acquisition_cost | DecimalField
  - market_share_gained | DecimalField
  - includes_plant | BooleanField
  - plant_capacity | IntegerField
  - includes_distribution | BooleanField
  - distribution_reach_bonus | DecimalField
  - talent_bonus | JSONField
  - min_round_available | IntegerField
  - requires_market_presence | BooleanField
  - integration_rounds | IntegerField
  - integration_cost_per_round | DecimalField

**PostgreSQL `\d acquisition_target`:**

  - id | bigint | NOT NULL
  - target_name | character varying | len=200 | NOT NULL
  - description | text | NOT NULL
  - base_acquisition_cost | numeric | NOT NULL
  - market_share_gained | numeric | NOT NULL
  - includes_plant | boolean | NOT NULL
  - plant_capacity | integer | NOT NULL
  - includes_distribution | boolean | NOT NULL
  - distribution_reach_bonus | numeric | NOT NULL
  - talent_bonus | jsonb | NOT NULL
  - min_round_available | integer | NOT NULL
  - requires_market_presence | boolean | NOT NULL
  - integration_rounds | integer | NOT NULL
  - integration_cost_per_round | numeric | NOT NULL
  - market_id | bigint | NOT NULL
  - scenario_id | bigint | NOT NULL
  - description_zh | text | NOT NULL
  - target_name_zh | character varying | len=200 | NOT NULL

**Field-registry vs. DB delta:** none.

### core.TeamAcquisition

- **File:** `backend/core/models/team_state.py:292`
- **Managed:** True
- **Physical table:** `team_acquisition` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - team | ForeignKey | related=core.Team
  - acquisition_target | ForeignKey | related=core.AcquisitionTarget
  - acquired_round | IntegerField
  - integration_complete | BooleanField
  - integration_rounds_remaining | IntegerField
  - total_cost_paid | DecimalField

**PostgreSQL `\d team_acquisition`:**

  - id | bigint | NOT NULL
  - acquired_round | integer | NOT NULL
  - integration_complete | boolean | NOT NULL
  - integration_rounds_remaining | integer | NOT NULL
  - total_cost_paid | numeric | NOT NULL
  - acquisition_target_id | bigint | NOT NULL
  - team_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.FirmStarterProduct

- **File:** `backend/core/models/scenario.py:545`
- **Managed:** True
- **Physical table:** `firm_starter_product` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - firm_starter_profile | ForeignKey | related=core.FirmStarterProfile
  - product_name | CharField | max_length=200
  - positioning_label | CharField | max_length=50
  - base_price | DecimalField
  - market | ForeignKey | related=core.MarketDefinition
  - unit_volume | IntegerField
  - market_share_pct | DecimalField
  - platform_label | CharField | max_length=20

**PostgreSQL `\d firm_starter_product`:**

  - id | bigint | NOT NULL
  - product_name | character varying | len=200 | NOT NULL
  - positioning_label | character varying | len=50 | NOT NULL
  - base_price | numeric | NOT NULL
  - unit_volume | integer | NOT NULL
  - market_share_pct | numeric | NOT NULL
  - firm_starter_profile_id | bigint | NOT NULL
  - market_id | bigint | NOT NULL
  - platform_label | character varying | len=20 | NOT NULL

**Field-registry vs. DB delta:** none.

### core.TeamProduct

- **File:** `backend/core/models/team_state.py:211`
- **Managed:** True
- **Physical table:** `team_product` (verified present)

**Django `_meta.get_fields()`:**

  - retire_decisions | ManyToOneRel | null=True | related=core.DecisionProductRetire
  - marketing_decisions | ManyToOneRel | null=True | related=core.DecisionMarketing
  - markets | ManyToOneRel | null=True | related=core.TeamProductMarket
  - adoption_results | ManyToOneRel | null=True | related=core.RoundResultAdoption
  - round_results | ManyToOneRel | null=True | related=core.RoundResultProductMarket
  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - team | ForeignKey | related=core.Team
  - team_platform | ForeignKey | related=core.TeamPlatform
  - name | CharField | max_length=200
  - positioning | CharField | max_length=20 | choices=4
  - status | CharField | max_length=20 | choices=2
  - created_round | IntegerField
  - retired_round | IntegerField | null=True | blank=True

**PostgreSQL `\d team_product`:**

  - id | bigint | NOT NULL
  - name | character varying | len=200 | NOT NULL
  - positioning | character varying | len=20 | NOT NULL
  - status | character varying | len=20 | NOT NULL
  - created_round | integer | NOT NULL
  - retired_round | integer
  - team_id | bigint | NOT NULL
  - team_platform_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

### core.TeamProductMarket

- **File:** `backend/core/models/team_state.py:272`
- **Managed:** True
- **Physical table:** `team_product_market` (verified present)

**Django `_meta.get_fields()`:**

  - id | BigAutoField | blank=True | unique=True | primary_key=True
  - team_product | ForeignKey | related=core.TeamProduct
  - market | ForeignKey | related=core.MarketDefinition
  - is_active | BooleanField
  - first_offered_round | IntegerField

**PostgreSQL `\d team_product_market`:**

  - id | bigint | NOT NULL
  - is_active | boolean | NOT NULL
  - first_offered_round | integer | NOT NULL
  - market_id | bigint | NOT NULL
  - team_product_id | bigint | NOT NULL

**Field-registry vs. DB delta:** none.

**Section A model count:** 36

## Section B — Ghost model roster (registered in Django, no physical table)

- **core.Achievement** (`backend/core/models/gamification.py:4`) — db_table=`achievements`, managed=False
- **core.AdminAction** (`backend/core/models/instructor.py:88`) — db_table=`admin_actions`, managed=False
- **core.ComponentStatus** (`backend/core/models/core.py:221`) — db_table=`component_status`, managed=False
- **core.CumulativeSales** (`backend/core/models/financials.py:113`) — db_table=`cumulative_sales`, managed=False
- **core.Decision** (`backend/core/models/programs.py:84`) — db_table=`decisions`, managed=False
- **core.Feedback** (`backend/core/models/messaging.py:103`) — db_table=`feedback`, managed=False
- **core.FinancialExpense** (`backend/core/models/financials.py:96`) — db_table=`financial_expenses`, managed=False
- **core.FinancialRevenue** (`backend/core/models/financials.py:79`) — db_table=`financial_revenue`, managed=False
- **core.GamificationBadge** (`backend/core/models/gamification.py:19`) — db_table=`gamification_badges`, managed=False
- **core.InstructorAction** (`backend/core/models/instructor.py:4`) — db_table=`instructor_actions`, managed=False
- **core.InstructorEvaluation** (`backend/core/models/instructor.py:21`) — db_table=`instructor_evaluations`, managed=False
- **core.InstructorFeedbackTemplate** (`backend/core/models/instructor.py:58`) — db_table=`instructor_feedback_templates`, managed=False
- **core.InstructorNote** (`backend/core/models/instructor.py:41`) — db_table=`instructor_notes`, managed=False
- **core.InstructorScenarioCustomization** (`backend/core/models/instructor.py:73`) — db_table=`instructor_scenario_customization`, managed=False
- **core.LeaderboardMetric** (`backend/core/models/scoring.py:36`) — db_table=`leaderboard_metrics`, managed=False
- **core.LeaderboardScore** (`backend/core/models/scoring.py:50`) — db_table=`leaderboard_scores`, managed=False
- **core.Message** (`backend/core/models/messaging.py:4`) — db_table=`messages`, managed=False
- **core.MessageResponse** (`backend/core/models/messaging.py:33`) — db_table=`message_responses`, managed=False
- **core.MessageThread** (`backend/core/models/messaging.py:52`) — db_table=`message_threads`, managed=False
- **core.NewSalesByRound** (`backend/core/models/financials.py:129`) — db_table=`new_sales_by_round`, managed=False
- **core.NotificationLog** (`backend/core/models/messaging.py:86`) — db_table=`notification_logs`, managed=False
- **core.PlayerProgress** (`backend/core/models/gamification.py:34`) — db_table=`player_progress`, managed=False
- **core.Program** (`backend/core/models/programs.py:21`) — db_table=`programs`, managed=False
- **core.ProgramFeature** (`backend/core/models/programs.py:68`) — db_table=`program_features`, managed=False
- **core.ProgramPortfolio** (`backend/core/models/programs.py:49`) — db_table=`program_portfolio`, managed=False
- **core.ProgramType** (`backend/core/models/programs.py:4`) — db_table=`program_types`, managed=False
- **core.Score** (`backend/core/models/scoring.py:18`) — db_table=`scores`, managed=False
- **core.ScoreType** (`backend/core/models/scoring.py:4`) — db_table=`score_types`, managed=False
- **core.SimulationParameters** (`backend/core/models/core.py:206`) — db_table=`simulation_parameters`, managed=False
- **core.SimulationSettings** (`backend/core/models/core.py:192`) — db_table=`simulation_settings`, managed=False
- **core.SimulationState** (`backend/core/models/core.py:177`) — db_table=`simulation_state`, managed=False
- **core.TeamAchievement** (`backend/core/models/gamification.py:51`) — db_table=`team_achievements`, managed=False
- **core.TeamBadge** (`backend/core/models/gamification.py:67`) — db_table=`team_badges`, managed=False
- **core.TeamBalanceSheet** (`backend/core/models/financials.py:23`) — db_table=`team_balance_sheets`, managed=False
- **core.TeamCashFlow** (`backend/core/models/financials.py:42`) — db_table=`team_cash_flows`, managed=False
- **core.TeamIncomeStatement** (`backend/core/models/financials.py:4`) — db_table=`team_income_statements`, managed=False
- **core.TeamNotification** (`backend/core/models/messaging.py:69`) — db_table=`team_notifications`, managed=False
- **core.TeamPerformance** (`backend/core/models/scoring.py:66`) — db_table=`team_performance`, managed=False
- **core.TeamResources** (`backend/core/models/financials.py:62`) — db_table=`team_resources`, managed=False
- **core.TriggeredEvent** (`backend/core/models/events.py:4`) — db_table=`triggered_events`, managed=False

**Total ghosts:** 40

## Section C — CC-02 §5 EXTEND collision check

### core.DecisionPlant (§5.1 EXTEND target)

- Existing field names: ['action', 'capacity_units', 'contract_mfg_volume', 'id', 'market', 'submission']
- Proposed new fields: ['reverse_logistics_enabled', 'scope_1_co2_per_unit_kg', 'scope_2_co2_per_unit_kg', 'sourcing_node_role', 'upstream_suppliers_required']
- No collisions.

### core.DecisionESG (§5.2 EXTEND target — primary)

- Existing field names: ['environmental_investment', 'governance_commitments', 'id', 'social_investment', 'submission']
- Proposed new fields: ['cbam_reporting_readiness', 'scope_3_emissions_tracking', 'scope_3_investment_usd', 'supplier_audit_program', 'uflpa_tier_mapping_investment']
- No collisions.

### core.ESGEconomicImpact (§5.2 EXTEND target — secondary candidate)

- Existing field names: ['base_value', 'benefit_type', 'description', 'effective_value', 'esg_level', 'game', 'id', 'market', 'round_number', 'savings', 'team']
- Proposed new fields: ['cbam_reporting_readiness', 'scope_3_emissions_tracking', 'scope_3_investment_usd', 'supplier_audit_program', 'uflpa_tier_mapping_investment']
- No collisions.

## Halt-condition summary (CC-02 §2.2)

1. **Field name mismatch in §5 targets:** none.
2. **Field collision on proposed EXTEND fields:** see Section C.
3. **Ghost EXTEND target:** DecisionPlant=non-ghost, DecisionESG=non-ghost, ESGEconomicImpact=non-ghost. No halt.
4. **Field-registry vs. DB drift:** see per-model delta lines in Section A.


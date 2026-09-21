/**
 * The largest number each student decision input will accept.
 *
 * Why this exists: an `InputNumber` with no `max` lets a student type a
 * sixteen-digit amount, and the server then refuses it in the storage layer's
 * own words. Every bound here is the most the SERVER will accept for that field
 * today -- a storage limit, or a business validator where one exists -- and
 * never anything tighter, so no bound refuses a decision the server would have
 * taken. A bound is not a business rule and must not become one: budget caps,
 * the price band and the funding-need limit stay where they are, on the server,
 * with sentences of their own.
 *
 * Each entry is keyed by the backend field it is sent as, and names the
 * declaration it was read from. `decisionInputLimits.test.js` re-reads those
 * declarations from the backend source, so an entry cannot drift from its
 * field, and fails when a student page gains an `InputNumber` with no `max`.
 *
 * antd's `InputNumber` does not pass an out-of-range value to `onChange` while
 * the student types, and settles on `max` when the input loses focus, so a
 * bounded input cannot send a number past its bound.
 */

/** `models.DecimalField(max_digits=15, decimal_places=2)`: 13 whole digits. */
export const MONEY_MAX = 9999999999999.99;

/** `models.DecimalField(max_digits=10, decimal_places=4)`: 6 whole digits. */
export const DIVIDEND_PER_SHARE_MAX = 999999.9999;

/**
 * `models.IntegerField()`: PostgreSQL `integer`. DRF reads the range off the
 * model field and refuses anything above it (`max_value`).
 */
export const INTEGER_MAX = 2147483647;

/**
 * `ComplianceInvestmentSerializer.validate_investment_amount`
 * (`core/serializers/decisions.py`): "cannot exceed $10M per market in one
 * round". The one bound here that is a business validator, and equal to it.
 */
export const COMPLIANCE_INVESTMENT_MAX = 10000000;

export const DECISION_INPUT_LIMITS = {
  // core/models/decisions.py -- DecisionBudgetAllocation
  rd_budget: MONEY_MAX,
  marketing_budget: MONEY_MAX,
  strategy_budget: MONEY_MAX,

  // core/models/decisions.py -- DecisionFinancing
  new_debt: MONEY_MAX,
  new_equity: MONEY_MAX,
  dividend_per_share: DIVIDEND_PER_SHARE_MAX,

  // core/models/decisions.py -- DecisionESG
  environmental_investment: MONEY_MAX,
  social_investment: MONEY_MAX,

  // core/models/decisions.py -- DecisionMarketing. `retail_price` is bounded by
  // storage only: the price band ALERTS on an out-of-band price and accepts it
  // (Ruling 2), so the band must not be enforced here.
  retail_price: MONEY_MAX,
  promotion_budget: MONEY_MAX,
  production_volume: INTEGER_MAX,
  demand_estimate: INTEGER_MAX,

  // core/models/talent.py -- DecisionTalent. One input serves all three pools
  // (`rd_`, `commercial_`, `operations_training_budget`); the three fields are
  // declared identically.
  training_budget: MONEY_MAX,

  // core/models/cc31_models.py -- ComplianceInvestment.investment_amount
  investment_amount: COMPLIANCE_INVESTMENT_MAX,

  // core/models/sc_decisions.py -- SourcingAllocation, LogisticsDecision,
  // InventoryDecision
  volume_commitment_units: INTEGER_MAX,
  volume_commitment_teu: INTEGER_MAX,
  buffer_days: INTEGER_MAX,

  // core/models/sc_decisions.py -- ContingencyPlan. The two rule lists are
  // JSON, so the server states no limit for a rule's threshold at all. They
  // are bounded at the integer range their sibling fields have, which refuses
  // nothing a contingency rule could mean.
  contingency_threshold: INTEGER_MAX,
  contingency_threshold_days: INTEGER_MAX,
};

/**
 * For the one money entry that is a text box rather than an `InputNumber`
 * (`MoneyTextInput` on the finance page, which accepts "2.5M"): there is no
 * `max` prop to set, so the parsed amount is held to the bound instead.
 */
export const boundTo = (field, value) => {
  const limit = DECISION_INPUT_LIMITS[field];
  return typeof value === 'number' && value > limit ? limit : value;
};

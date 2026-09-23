/**
 * Labels the Market Strategy page derives from stored tokens and authored
 * numbers (W-CE-22, 2026-09-22).
 *
 * Three things reached the screen unlabelled: the cultural-distance level as
 * its enum (`VERY_HIGH`), a plant's status as its token (`operational`), and
 * a plant cost of "$0" for every market because the context never carried the
 * authored cost at all. Each is decided here, with one literal `t()` key per
 * value so the string gate can see every key, and a stored token this table
 * does not know is shown as itself rather than hidden.
 */

export const distanceLabel = (level, t) => {
  switch (level) {
    case 'HOME': return t('market_strategy.distance_home');
    case 'LOW': return t('market_strategy.distance_low');
    case 'MEDIUM': return t('market_strategy.distance_medium');
    case 'HIGH': return t('market_strategy.distance_high');
    case 'VERY_HIGH':
    case 'VERY HIGH': return t('market_strategy.distance_very_high');
    case 'UNKNOWN': return t('market_strategy.distance_unknown');
    default: return level || '—';
  }
};

export const plantStatusLabel = (status, t) => {
  switch (status) {
    case 'operational': return t('market_strategy.plant_operational');
    case 'under_construction': return t('market_strategy.under_construction');
    case 'decommissioned': return t('market_strategy.plant_decommissioned');
    default: return status || '—';
  }
};

/** "$2.0M/round": the charge as the engine levies it, every active round. */
export const perRoundCharge = (amount, t, fmt) => (
  t('market_strategy.per_round_charge', { amount: fmt(amount) })
);

/**
 * "Build Plant — $12.0M, 2 rounds, 80000 units". The cost is the scenario's
 * authored `plant_build_cost`; when none is authored the label says so rather
 * than showing $0, and no figure is invented for it.
 */
export const plantCostLabel = (market, t, fmt) => (
  market.plant_build_cost == null
    ? t('market_strategy.plant_cost_not_available')
    : fmt(market.plant_build_cost)
);

export const plantBuildLabel = (market, t, fmt) => {
  const cost = plantCostLabel(market, t, fmt);
  const rounds = market.plant_build_rounds == null ? '—' : market.plant_build_rounds;
  const detail = market.plant_capacity_units
    ? t('market_strategy.build_plant_detail', { rounds, units: market.plant_capacity_units })
    : t('market_strategy.round_setup', { rounds });
  return `${t('market_strategy.build_plant')} — ${cost}, ${detail}`;
};

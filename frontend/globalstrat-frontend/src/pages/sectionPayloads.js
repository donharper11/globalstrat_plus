/**
 * What two decision sections are sent as, and read back from.
 *
 * Kept out of the pages so it can be tested without rendering them. The rows
 * built here are the rows `core/tests/test_silent_section_saves.py` drives
 * through the real route: `TalentAllocationSerializer` and
 * `ComplianceInvestmentSerializer` each take a LIST of rows, and the pages had
 * been sending a dict keyed by pool / by market code.
 *
 * On screen a pool's allocation is `{ hq: n, <market code>: n, ... }`.
 */

export const TALENT_POOLS = ['rd', 'commercial', 'operations'];

const count = (value) => Math.max(0, Math.trunc(Number(value) || 0));

const marketCounts = (allocation) => Object.fromEntries(
  Object.entries(allocation || {})
    .filter(([key, value]) => key !== 'hq' && count(value) > 0)
    .map(([key, value]) => [key, count(value)]),
);

const hasAllocation = (allocation) => Object.values(allocation || {})
  .some(value => count(value) > 0);

/**
 * A pool nobody has allocated is shown with everyone at headquarters, which is
 * what the engine takes "no allocation" to mean. Nothing is stored for it.
 */
export const effectiveAllocation = (allocation, headcount) => (
  hasAllocation(allocation) ? allocation : { hq: count(headcount) }
);

/**
 * After a market count is edited, headquarters gives up or takes back the
 * difference. The server requires each pool to total its headcount, so a
 * screen that only ever added staff would be refused on its first keystroke.
 * Headquarters stops at zero; past that the total is over and the screen (and
 * the server) says so. An edit to headquarters itself is left as typed.
 */
export const rebalanceAfterEdit = (allocation, editedKey, headcount) => {
  if (editedKey === 'hq') return allocation;
  const inMarkets = Object.values(marketCounts(allocation))
    .reduce((sum, value) => sum + value, 0);
  return { ...allocation, hq: Math.max(0, count(headcount) - inMarkets) };
};

/** A change of headcount is absorbed at headquarters, never below zero. */
export const followHeadcount = (allocation, previousHeadcount, nextHeadcount) => {
  if (!hasAllocation(allocation)) return allocation || {};
  const delta = count(nextHeadcount) - count(previousHeadcount);
  return { ...allocation, hq: Math.max(0, count(allocation.hq) + delta) };
};

export const allocationTotals = (allocations) => Object.fromEntries(
  TALENT_POOLS.map(pool => [
    pool,
    Object.values(allocations?.[pool] || {})
      .reduce((sum, value) => sum + count(value), 0),
  ]),
);

/** The rows `talent_allocations` is sent as: one per allocated pool. */
export const allocationRows = (allocations) => TALENT_POOLS
  .filter(pool => hasAllocation(allocations?.[pool]))
  .map(pool => ({
    talent_pool: pool,
    hq_count: count(allocations[pool].hq),
    market_allocation: marketCounts(allocations[pool]),
  }));

/**
 * Staffing and allocation in ONE request to the staffing section.
 *
 * An allocation must total its pool's headcount, so neither can change first;
 * the server judges and stores the pair together and refuses a staffing change
 * that would strand a stored allocation. Sending them together also means a
 * team that has only ever touched the allocation still has a staffing decision
 * for it to total against.
 *
 * `allocationsLoaded` is false when the page could not read the stored
 * allocation. The key is then left out, because an empty list would delete
 * rows the page has never seen.
 */
export const staffingPayload = (talent, allocations, allocationsLoaded) => {
  const payload = {
    talent: Object.fromEntries(TALENT_POOLS.flatMap(pool => [
      [`${pool}_headcount`, talent[pool].headcount],
      [`${pool}_salary_level`, talent[pool].salary_level],
      [`${pool}_training_budget`, talent[pool].training_budget],
    ])),
  };
  if (allocationsLoaded) payload.talent_allocations = allocationRows(allocations);
  return payload;
};

/** The rows `compliance_investments` is sent as. `markets` carry code and id. */
export const complianceRows = (byCode, markets) => (markets || [])
  .filter(market => Number(byCode?.[market.code]) > 0)
  .map(market => ({
    market: market.market_id,
    investment_amount: Number(byCode[market.code]),
  }));

/** The reverse: the server's rows, as the per-market amounts the page shows. */
export const complianceByCode = (rows, markets) => {
  const byMarketId = new Map(
    (rows || []).map(row => [row.market, Number(row.investment_amount) || 0]),
  );
  return Object.fromEntries((markets || []).map(
    market => [market.code, byMarketId.get(market.market_id) || 0],
  ));
};

/**
 * The income statement as the Financial Reports page shows it.
 *
 * Pure functions, so the set of lines a student reads can be asserted without
 * rendering. R47: compliance investment is its own line, by owner ruling
 * ("show its own line on the income statement"), and research -- which has
 * had its own statement column since paid research landed (schema v6) and
 * was never rendered -- rides the same pattern.
 *
 * W-CE3-03: the page printed Revenue, COGS, Gross Profit, R&D, Marketing,
 * Strategy, Research, Compliance, Admin, Net Income and Margin, and nothing
 * else. It printed neither interest, tax, logistics/tariff nor inventory --
 * all four of which the same API serves on the same row -- so gross profit
 * less the lines shown differed from the net income printed beside them by
 * $0.36M to $2.80M, on every team in every round. Every served charge is now
 * a line, and `INCOME_STATEMENT_SUM` below states the identity the printed
 * lines satisfy; `incomeStatementRows.test.js` asserts it on a served row
 * rather than trusting the list.
 */

// Column key -> the statement field it reads and the locale key of its title.
export const INCOME_STATEMENT_LINES = [
  { key: 'revenue', field: 'total_revenue', label: 'financial_reports.revenue', kind: 'money' },
  { key: 'cogs', field: 'total_cogs', label: 'financial_reports.cogs', kind: 'money' },
  { key: 'gross_profit', field: 'gross_profit', label: 'financial_reports.gross_profit', kind: 'money' },
  { key: 'rd', field: 'rd_expense', label: 'financial_reports.rd_label', kind: 'money' },
  { key: 'marketing', field: 'marketing_expense', label: 'financial_reports.marketing_label', kind: 'money' },
  { key: 'strategy', field: 'strategy_expense', label: 'financial_reports.strategy_label', kind: 'money' },
  { key: 'research', field: 'research_expense', label: 'financial_reports.research_label', kind: 'money' },
  { key: 'compliance', field: 'compliance_expense', label: 'financial_reports.compliance_label', kind: 'money' },
  { key: 'admin', field: 'admin_overhead', label: 'financial_reports.admin', kind: 'money' },
  { key: 'logistics', field: 'logistics_tariff_expense', label: 'financial_reports.logistics_label', kind: 'money' },
  { key: 'inventory_cost', field: 'inventory_expense', label: 'financial_reports.inventory_cost_label', kind: 'money' },
  { key: 'platform_amortization', field: 'platform_amortization', label: 'financial_reports.platform_amortization_label', kind: 'money' },
  { key: 'platform_write_off', field: 'platform_switch_write_off', label: 'financial_reports.platform_write_off_label', kind: 'money' },
  { key: 'other_operating', field: 'other_operating_expense', label: 'financial_reports.other_operating_label', kind: 'money' },
  { key: 'operating_income', field: 'operating_income', label: 'financial_reports.operating_income', kind: 'money' },
  { key: 'interest', field: 'interest_expense', label: 'financial_reports.interest_label', kind: 'money' },
  { key: 'tax', field: 'tax_expense', label: 'financial_reports.tax_label', kind: 'money' },
  { key: 'other_non_operating', field: 'other_non_operating_expense', label: 'financial_reports.other_non_operating_label', kind: 'money' },
  { key: 'net_income', field: 'net_income', label: 'financial_reports.net_income', kind: 'money' },
  { key: 'margin', field: 'net_margin_pct', label: 'financial_reports.margin', kind: 'pct' },
];

/**
 * The identity the printed lines satisfy, stated once.
 *
 * `gross_profit` less every expense line printed between it and Net Income
 * equals `net_income`. `operating_income` is a subtotal the page also prints,
 * so it is excluded from the subtraction rather than counted twice.
 */
export const INCOME_STATEMENT_SUM = {
  from: 'gross_profit',
  to: 'net_income',
  subtotals: ['operating_income'],
  revenue: ['revenue', 'cogs'],
  ratio: ['margin'],
};

export function incomeStatementExpenseKeys() {
  const skip = new Set([
    ...INCOME_STATEMENT_SUM.revenue,
    ...INCOME_STATEMENT_SUM.subtotals,
    INCOME_STATEMENT_SUM.from,
    INCOME_STATEMENT_SUM.to,
    ...INCOME_STATEMENT_SUM.ratio,
  ]);
  return INCOME_STATEMENT_LINES.map(line => line.key).filter(key => !skip.has(key));
}

export function incomeStatementRow(round) {
  const row = { key: round.round_number, round: `R${round.round_number}` };
  INCOME_STATEMENT_LINES.forEach(line => { row[line.key] = round[line.field]; });
  return row;
}

export function incomeStatementColumns(t, { money, pct, roundTitle }) {
  return [
    { title: roundTitle, dataIndex: 'round', key: 'round', width: 70 },
    ...INCOME_STATEMENT_LINES.map(line => ({
      title: t(line.label),
      dataIndex: line.key,
      key: line.key,
      render: line.kind === 'pct' ? pct : money,
    })),
  ];
}

/**
 * The income statement as the Financial Reports page shows it.
 *
 * Pure functions, so the set of lines a student reads can be asserted without
 * rendering. R47: compliance investment is its own line, by owner ruling
 * ("show its own line on the income statement"), and research -- which has
 * had its own statement column since paid research landed (schema v6) and
 * was never rendered -- rides the same pattern.
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
  { key: 'net_income', field: 'net_income', label: 'financial_reports.net_income', kind: 'money' },
  { key: 'margin', field: 'net_margin_pct', label: 'financial_reports.margin', kind: 'pct' },
];

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

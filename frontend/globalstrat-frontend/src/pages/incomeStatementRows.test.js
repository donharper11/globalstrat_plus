import {
  INCOME_STATEMENT_LINES,
  INCOME_STATEMENT_SUM,
  incomeStatementColumns,
  incomeStatementExpenseKeys,
  incomeStatementRow,
} from './incomeStatementRows';
import en from '../locales/en.json';
import zh from '../locales/zh-CN.json';

/**
 * R47: compliance investment is charged from cash and shown as its own line
 * on the income statement. Each test fails without the line.
 *
 * W-CE3-03: the statement on the page did not add up. It printed neither
 * interest, tax, logistics/tariff nor inventory -- all four of which the same
 * API serves on the same row -- so gross profit less the lines shown differed
 * from the net income printed beside them by $0.36M to $2.80M, on every team
 * in every round. `a served row adds up` below is that measurement, run on a
 * row shaped like the one the API returns.
 */

const lookup = (catalogue, key) => key.split('.').reduce((node, part) => (node ? node[part] : undefined), catalogue);

// A round as `/financial-reports/history/` serves it, with every charge the
// engine books present. The figures are arbitrary but internally consistent:
// gross profit less every expense equals net income.
const servedRound = () => ({
  round_number: 4,
  total_revenue: 20000000,
  total_cogs: 12000000,
  gross_profit: 8000000,
  rd_expense: 1000000,
  marketing_expense: 1500000,
  strategy_expense: 900000,
  research_expense: 100000,
  compliance_expense: 400000,
  admin_overhead: 700000,
  logistics_tariff_expense: 350000,
  inventory_expense: 250000,
  platform_amortization: 200000,
  platform_switch_write_off: 50000,
  other_operating_expense: 615289,
  operating_income: 1934711,
  interest_expense: 300000,
  tax_expense: 250000,
  other_non_operating_expense: 84711,
  net_income: 1300000,
  net_margin_pct: 0.065,
});

describe('the income statement a student reads (R47)', () => {
  test('compliance investment is its own line, after strategy and before admin', () => {
    const keys = INCOME_STATEMENT_LINES.map(line => line.key);
    expect(keys.indexOf('compliance')).toBeGreaterThan(keys.indexOf('strategy'));
    expect(keys.indexOf('compliance')).toBeLessThan(keys.indexOf('admin'));
    const line = INCOME_STATEMENT_LINES.find(l => l.key === 'compliance');
    expect(line.field).toBe('compliance_expense');
  });

  test('research, which had a statement column and no row, is rendered too', () => {
    const line = INCOME_STATEMENT_LINES.find(l => l.key === 'research');
    expect(line).toBeDefined();
    expect(line.field).toBe('research_expense');
  });

  test('every line has a title in both catalogues, and the new ones are named', () => {
    INCOME_STATEMENT_LINES.forEach(line => {
      expect(typeof lookup(en, line.label)).toBe('string');
      expect(typeof lookup(zh, line.label)).toBe('string');
    });
    expect(lookup(en, 'financial_reports.compliance_label')).toBe('Compliance investment');
    expect(lookup(zh, 'financial_reports.compliance_label')).toBe('合规投入');
    expect(lookup(en, 'financial_reports.research_label')).toBe('Research');
  });

  test('a row carries the server field under the column key', () => {
    const row = incomeStatementRow({
      round_number: 3, total_revenue: 10, compliance_expense: 600000,
      research_expense: 50000, strategy_expense: 7, net_margin_pct: 0.1,
    });
    expect(row.round).toBe('R3');
    expect(row.compliance).toBe(600000);
    expect(row.research).toBe(50000);
    expect(row.strategy).toBe(7);
  });

  test('the columns are built from the same lines, with the right formatter', () => {
    const t = key => `<${key}>`;
    const money = v => `$${v}`;
    const pct = v => `${v}%`;
    const columns = incomeStatementColumns(t, { money, pct, roundTitle: 'Round' });
    const compliance = columns.find(c => c.key === 'compliance');
    expect(compliance.title).toBe('<financial_reports.compliance_label>');
    expect(compliance.dataIndex).toBe('compliance');
    expect(compliance.render).toBe(money);
    expect(columns.find(c => c.key === 'margin').render).toBe(pct);
    expect(columns[0].dataIndex).toBe('round');
  });
});

describe('the statement adds up (W-CE3-03)', () => {
  test('a served row adds up: gross profit less every printed line is net income', () => {
    const row = incomeStatementRow(servedRound());
    const expenses = incomeStatementExpenseKeys()
      .reduce((total, key) => total + Number(row[key] || 0), 0);

    expect(row[INCOME_STATEMENT_SUM.from] - expenses)
      .toBe(row[INCOME_STATEMENT_SUM.to]);
  });

  test('the subtotal the page prints is consistent with the lines above it', () => {
    const row = incomeStatementRow(servedRound());
    const keys = INCOME_STATEMENT_LINES.map(l => l.key);
    const above = incomeStatementExpenseKeys()
      .filter(key => keys.indexOf(key) < keys.indexOf('operating_income'))
      .reduce((total, key) => total + Number(row[key] || 0), 0);

    expect(row.gross_profit - above).toBe(row.operating_income);
  });

  test('every charge the API serves is printed, none twice', () => {
    const fields = INCOME_STATEMENT_LINES.map(l => l.field);
    [
      'logistics_tariff_expense', 'inventory_expense', 'interest_expense',
      'tax_expense', 'platform_amortization', 'platform_switch_write_off',
      'other_operating_expense', 'other_non_operating_expense',
    ].forEach(field => expect(fields).toContain(field));
    expect(new Set(fields).size).toBe(fields.length);
  });

  test('the residual lines are named in both languages', () => {
    expect(lookup(en, 'financial_reports.other_operating_label'))
      .toBe('Other operating charges');
    expect(lookup(zh, 'financial_reports.other_operating_label'))
      .toBe('其他营业费用');
    expect(lookup(en, 'financial_reports.interest_label')).toBe('Interest');
    expect(lookup(zh, 'financial_reports.tax_label')).toBe('所得税');
  });
});

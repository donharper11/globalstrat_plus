import { INCOME_STATEMENT_LINES, incomeStatementColumns, incomeStatementRow } from './incomeStatementRows';
import en from '../locales/en.json';
import zh from '../locales/zh-CN.json';

/**
 * R47: compliance investment is charged from cash and shown as its own line
 * on the income statement. Each test fails without the line.
 */

const lookup = (catalogue, key) => key.split('.').reduce((node, part) => (node ? node[part] : undefined), catalogue);

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

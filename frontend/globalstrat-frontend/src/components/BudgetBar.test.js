import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import BudgetBar from './BudgetBar';
import en from '../locales/en.json';
import zh from '../locales/zh-CN.json';

/**
 * R48 item 12. Compliance investment is charged from cash (R47) and the
 * Summary, Finance and dashboard payloads carry it as `compliance_committed`
 * beside the other committed lines, but no row read it: a charge a student
 * could feel in the cash check without seeing the line. The row is rendered
 * from the payload, here, by the one component all three pages share.
 *
 * `t` is stubbed to print its key and values, so the assertions name
 * catalogue keys; the catalogues themselves are checked for the sentence.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));

const budgets = (overrides = {}) => ({
  rd_allocated: 1000000, rd_spent: 250000,
  marketing_allocated: 500000, marketing_spent: 100000,
  strategy_allocated: 200000, strategy_spent: 0,
  research_allocated: 50000, research_spent: 0,
  platform_development_committed: 0,
  compliance_committed: 600000,
  platform_development_committed: 15000000,
  committed_total: 2350000,
  unallocated: 7650000,
  ...overrides,
});

test('the compliance investment committed this round is its own row', () => {
  render(<BudgetBar budgets={budgets()} />);
  expect(screen.getByText('budget.compliance_committed')).toBeInTheDocument();
  expect(screen.getByText('budget.platform_development_committed')).toBeInTheDocument();
  expect(screen.getByText('$600K')).toBeInTheDocument();
});

test('the row reads the payload, not a constant', () => {
  render(<BudgetBar budgets={budgets({ compliance_committed: 1250000 })} />);
  expect(screen.getByText('$1.3M')).toBeInTheDocument();
  expect(screen.queryByText('$600K')).not.toBeInTheDocument();
});

test('a payload without the figure (an older server) shows no row', () => {
  render(<BudgetBar budgets={budgets({ compliance_committed: undefined })} />);
  expect(screen.queryByText('budget.compliance_committed')).not.toBeInTheDocument();
});

test('nothing committed is still a row, at zero', () => {
  // A team that committed nothing sees the line at $0, as it sees R&D at
  // $0: the line exists whether or not it was used this round.
  render(<BudgetBar budgets={budgets({ compliance_committed: 0 })} />);
  expect(screen.getByText('budget.compliance_committed')).toBeInTheDocument();
});

test('the row is shown, not summed: unallocated is still the server figure', () => {
  render(<BudgetBar budgets={budgets()} />);
  expect(screen.getByText(/budget\.committed_of_cash.*\$7\.7M/)).toBeInTheDocument();
});

/**
 * W-CE2-09 (second walkthrough). The Summary showed two round totals and the
 * line below them was unformatted: `Unallocated: $-12553689`, where every
 * other figure on the page is `$28.5M`-style. The formatter tested only
 * `n >= 1e6`, so a negative fell through to `toFixed(0)`.
 */
test('a negative figure is formatted like every other figure on the page', () => {
  render(<BudgetBar budgets={budgets({ unallocated: -12553689 })} />);
  const text = document.body.textContent;
  expect(text).toContain('$-12.6M');
  expect(text).not.toContain('-12553689');
});

test('a negative thousands figure is formatted too', () => {
  render(<BudgetBar budgets={budgets({ unallocated: -45000 })} />);
  expect(document.body.textContent).toContain('$-45K');
});

/**
 * W-CE2-09, the other half: one total per concept. The panel now states the
 * authoritative committed total -- the same figure the lock blocker quotes,
 * from `rd_costs.budget_assessment` -- beside the cash it is committed
 * against, so "unallocated" can no longer read as headroom on its own.
 */
test('the panel states the one authoritative total, against cash', () => {
  render(<BudgetBar budgets={budgets({
    committed_total: 38000000, total_available: 25446311, unallocated: -12553689,
  })} />);
  const text = document.body.textContent;
  expect(text).toContain('budget.committed_of_cash');
  expect(text).toContain('$38.0M');
  expect(text).toContain('$25.4M');
  expect(text).toContain('$-12.6M');
});

test('an older server without the committed total falls back to the plain line', () => {
  render(<BudgetBar budgets={budgets({ committed_total: undefined })} />);
  expect(screen.getByText(/budget\.unallocated.*\$7\.7M/)).toBeInTheDocument();
});

test('both budget sentences exist in both catalogues and name their own concept', () => {
  expect(en.budget.committed_of_cash).toBeTruthy();
  expect(zh.budget.committed_of_cash).toBeTruthy();
  // The banner compares the declared budget lines with the operating budget;
  // it must not call that figure the round's total spending, because the
  // blocker on the same screen quotes a different, larger total.
  expect(en.budget.over_budget).not.toMatch(/total spending/i);
  expect(en.budget.over_budget).toMatch(/operating budget/i);
  expect(zh.budget.over_budget).not.toContain('总支出');
});

test('the label exists in both catalogues, worded as the income statement line', () => {
  expect(en.budget.compliance_committed).toBe('Compliance investment');
  expect(zh.budget.compliance_committed).toBe('合规投入');
  expect(en.budget.compliance_committed).toBe(en.financial_reports.compliance_label);
  expect(zh.budget.compliance_committed).toBe(zh.financial_reports.compliance_label);
});

// W-CE-18: payroll and a plant build are charged from cash under no budget
// line; the Summary and Finance payloads carry them as `talent_committed`
// and `plant_committed`, and the one shared bar shows them as rows.
test('payroll and plant construction committed this round are rows too', () => {
  render(<BudgetBar budgets={budgets({ talent_committed: 6250000, plant_committed: 0 })} />);
  expect(screen.getByText('budget.talent_committed')).toBeInTheDocument();
  expect(screen.getByText('$6.3M')).toBeInTheDocument();
  expect(screen.getByText('budget.plant_committed')).toBeInTheDocument();
  expect(en.budget.talent_committed).toBeTruthy();
  expect(zh.budget.talent_committed).toBeTruthy();
  expect(en.budget.plant_committed).toBeTruthy();
  expect(zh.budget.plant_committed).toBeTruthy();
});

test('an older server without the two figures shows neither row', () => {
  render(<BudgetBar budgets={budgets()} />);
  expect(screen.queryByText('budget.talent_committed')).not.toBeInTheDocument();
  expect(screen.queryByText('budget.plant_committed')).not.toBeInTheDocument();
});

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
  expect(screen.getByText(/budget\.unallocated.*\$7\.7M/)).toBeInTheDocument();
});

test('the label exists in both catalogues, worded as the income statement line', () => {
  expect(en.budget.compliance_committed).toBe('Compliance investment');
  expect(zh.budget.compliance_committed).toBe('合规投入');
  expect(en.budget.compliance_committed).toBe(en.financial_reports.compliance_label);
  expect(zh.budget.compliance_committed).toBe(zh.financial_reports.compliance_label);
});

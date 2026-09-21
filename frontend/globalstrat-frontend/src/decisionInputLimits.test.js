import fs from 'fs';
import path from 'path';
import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import { InputNumber } from 'antd';
import {
  DECISION_INPUT_LIMITS, MONEY_MAX, DIVIDEND_PER_SHARE_MAX, INTEGER_MAX,
  COMPLIANCE_INVESTMENT_MAX, boundTo,
} from './decisionInputLimits';

/**
 * 21 of the 37 `InputNumber`s on student pages had no `max`, so a student could
 * type a sixteen-digit amount and be answered by the storage layer ("Ensure
 * that there are no more than 15 digits in total."). Two guards:
 *
 *   - a source scan, so a student page cannot gain an unbounded `InputNumber`;
 *   - a re-reading of the backend declarations each bound was taken from, so a
 *     bound cannot drift away from -- above all, below -- what the server takes.
 */

const SRC = __dirname;
const BACKEND = path.join(SRC, '..', '..', '..', 'backend', 'core');

// Everything under src/ is a student surface unless it is named here. Listing
// the exceptions rather than the pages means a new page is scanned by default.
const INSTRUCTOR_ONLY = [
  path.join('pages', 'InstructorDashboard.js'),
  path.join('pages', 'InstructorLoginPage.js'),
  `components${path.sep}instructor${path.sep}`,
];

const sourceFiles = (dir) => fs.readdirSync(dir, { withFileTypes: true })
  .flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.jsx?$/.test(entry.name) && !/\.test\.jsx?$/.test(entry.name)
      ? [full] : [];
  });

const studentFiles = () => sourceFiles(SRC).filter((file) => {
  const relative = path.relative(SRC, file);
  return !INSTRUCTOR_ONLY.some((name) => relative.startsWith(name));
});

/** Every `<InputNumber ... />` in a file, as {line, text}. */
const inputNumbers = (file) => {
  const source = fs.readFileSync(file, 'utf8');
  const found = [];
  const opening = /<InputNumber\b/g;
  let match = opening.exec(source);
  while (match) {
    const end = source.indexOf('/>', match.index);
    found.push({
      where: `${path.relative(SRC, file)}:${source.slice(0, match.index).split('\n').length}`,
      text: source.slice(match.index, end === -1 ? undefined : end + 2),
    });
    match = opening.exec(source);
  }
  return found;
};

describe('student number inputs are bounded', () => {
  const all = studentFiles().flatMap(inputNumbers);

  test('the scan is reading the pages it is meant to', () => {
    expect(all.length).toBeGreaterThanOrEqual(37);
    const files = new Set(all.map((item) => item.where.split(':')[0]));
    ['FinancePage.js', 'MarketingPage.js', 'CorporateStrategyPage.js',
      'InventoryPage.js'].forEach((page) => {
      expect(files).toContain(path.join('pages', page));
    });
  });

  test('no InputNumber is without a max', () => {
    const unbounded = all.filter((item) => !/\bmax=\{/.test(item.text))
      .map((item) => item.where);
    expect(unbounded).toEqual([]);
  });

  test('no InputNumber is without a min', () => {
    // No decision a team submits is a negative quantity of anything
    // (`NEGATIVE_ALLOWED` in core/serializers/decision_limits.py is empty).
    const unbounded = all.filter((item) => !/\bmin=\{/.test(item.text))
      .map((item) => item.where);
    expect(unbounded).toEqual([]);
  });

  test('the finance page holds its text-box budgets to the same bound', () => {
    const source = fs.readFileSync(
      path.join(SRC, 'pages', 'FinancePage.js'), 'utf8');
    expect(source).toMatch(/boundTo\(field, normalizeMoneyInput\(value\)\)/);
  });
});

describe('each bound is what the server accepts, not less', () => {
  const read = (relative) => fs.readFileSync(
    path.join(BACKEND, relative), 'utf8');

  const largestDecimal = (source, field) => {
    const declared = new RegExp(
      `\\b${field} = models\\.DecimalField\\(\\s*max_digits=(\\d+),\\s*decimal_places=(\\d+)`)
      .exec(source);
    if (!declared) throw new Error(`${field} is not declared as a DecimalField`);
    const [digits, places] = [Number(declared[1]), Number(declared[2])];
    return Number(`${'9'.repeat(digits - places)}.${'9'.repeat(places)}`);
  };

  const isInteger = (source, field) => new RegExp(
    `\\b${field} = models\\.IntegerField\\(`).test(source);

  test('money and dividend bounds equal the declared decimal capacity', () => {
    const decisions = read(path.join('models', 'decisions.py'));
    ['rd_budget', 'marketing_budget', 'strategy_budget', 'new_debt',
      'new_equity', 'dividend_per_share', 'environmental_investment',
      'social_investment', 'retail_price', 'promotion_budget',
    ].forEach((field) => {
      expect([field, DECISION_INPUT_LIMITS[field]])
        .toEqual([field, largestDecimal(decisions, field)]);
    });
    const talent = read(path.join('models', 'talent.py'));
    ['rd', 'commercial', 'operations'].forEach((pool) => {
      expect(largestDecimal(talent, `${pool}_training_budget`))
        .toBe(DECISION_INPUT_LIMITS.training_budget);
    });
    expect(MONEY_MAX).toBe(9999999999999.99);
    expect(DIVIDEND_PER_SHARE_MAX).toBe(999999.9999);
  });

  test('integer bounds belong to fields that are still integers', () => {
    const decisions = read(path.join('models', 'decisions.py'));
    const supplyChain = read(path.join('models', 'sc_decisions.py'));
    ['production_volume', 'demand_estimate'].forEach((field) => {
      expect([field, isInteger(decisions, field)]).toEqual([field, true]);
      expect(DECISION_INPUT_LIMITS[field]).toBe(INTEGER_MAX);
    });
    ['volume_commitment_units', 'volume_commitment_teu', 'buffer_days',
    ].forEach((field) => {
      expect([field, isInteger(supplyChain, field)]).toEqual([field, true]);
      expect(DECISION_INPUT_LIMITS[field]).toBe(INTEGER_MAX);
    });
    expect(INTEGER_MAX).toBe(2 ** 31 - 1);
  });

  test('the compliance bound is the server’s own $10M validator', () => {
    const serializers = read(path.join('serializers', 'decisions.py'));
    const rule = /def validate_investment_amount[\s\S]*?if value > (\d+):/
      .exec(serializers);
    expect(Number(rule[1])).toBe(COMPLIANCE_INVESTMENT_MAX);
    expect(DECISION_INPUT_LIMITS.investment_amount)
      .toBe(COMPLIANCE_INVESTMENT_MAX);
  });

  test('a bound survives the trip to the server as the digits it names', () => {
    // The server reads a JSON number through str(); a bound that serialised as
    // 1e13 or grew a digit would itself be refused.
    expect(JSON.stringify(MONEY_MAX)).toBe('9999999999999.99');
    expect(JSON.stringify(DIVIDEND_PER_SHARE_MAX)).toBe('999999.9999');
  });
});

describe('boundTo', () => {
  test('holds an over-long amount to the bound and leaves the rest alone', () => {
    expect(boundTo('rd_budget', 99999999999999999)).toBe(MONEY_MAX);
    expect(boundTo('rd_budget', 2500000)).toBe(2500000);
    expect(boundTo('rd_budget', 0)).toBe(0);
    expect(boundTo('rd_budget', MONEY_MAX)).toBe(MONEY_MAX);
  });
});

describe('what a bound does to the number a page is handed', () => {
  // The claim the whole repair rests on, checked against the installed antd
  // rather than remembered: an out-of-range entry never reaches `onChange`.
  test('sixteen typed numerals never reach onChange, and blur settles on max', () => {
    const onChange = jest.fn();
    const { container } = render(
      <InputNumber min={0} max={DECISION_INPUT_LIMITS.new_debt} onChange={onChange} />);
    const input = container.querySelector('input');

    fireEvent.change(input, { target: { value: '1234567890123456' } });
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.blur(input);
    expect(onChange.mock.calls.map(([value]) => value)).toEqual([MONEY_MAX]);
  });

  test('a legitimate large amount passes through untouched', () => {
    const onChange = jest.fn();
    const { container } = render(
      <InputNumber min={0} max={DECISION_INPUT_LIMITS.new_debt} onChange={onChange} />);
    fireEvent.change(container.querySelector('input'),
      { target: { value: '250000000.75' } });
    expect(onChange).toHaveBeenLastCalledWith(250000000.75);
  });
});

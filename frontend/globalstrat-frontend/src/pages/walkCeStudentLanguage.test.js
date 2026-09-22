import fs from 'fs';
import path from 'path';

import en from '../locales/en.json';
import zh from '../locales/zh-CN.json';
import {
  everythingSpoken, keysUsed, computedKeys, exists, withoutComments,
} from '../englishLiteralScan';

/**
 * The student screens after the 2026-09-22 walkthrough (W-CE-16, W-CE-11).
 *
 * Two strengths of guard. A screen this pass cleaned completely is held to
 * the whole scan: no JSX text, bare line, spoken prop or fallback in English,
 * every key in both catalogues, no key picked at run time. A screen another
 * builder is editing at the same time (finance, R&D, marketing) is held only
 * to the literals this pass removed, by name, so their work is not failed by
 * a guard they did not write.
 */

const read = (relative) => fs.readFileSync(path.join(__dirname, relative), 'utf8');

const CLEANED = {
  'SummaryPage.js': read('SummaryPage.js'),
};

describe.each(Object.entries(CLEANED))('%s', (name, source) => {
  test('renders no hard-coded words', () => {
    expect(everythingSpoken(source)).toEqual([]);
  });

  test('picks no key at run time', () => {
    expect(computedKeys(source)).toEqual([]);
  });

  test('every key it asks for exists in both languages', () => {
    const missing = keysUsed(source).filter((key) => !exists(en, key) || !exists(zh, key));
    expect(missing).toEqual([]);
  });
});

describe('LoginPage.js: the two taglines under the form', () => {
  // The demo buttons reach their labels through a label map
  // (`t(account.labelKey)`), inventoried with the owner; the page is held to
  // the literals this pass removed and to its keys existing, not to the whole scan.
  const source = withoutComments(read('LoginPage.js'));

  test.each(['Built for Real Work', 'Clarity. Capability.'])('no longer says %s', (literal) => {
    expect(source).not.toContain(literal);
  });

  test('every key it asks for exists in both languages', () => {
    const missing = keysUsed(source).filter((key) => !exists(en, key) || !exists(zh, key));
    expect(missing).toEqual([]);
    expect(keysUsed(source)).toEqual(expect.arrayContaining(['login.tagline', 'login.brand_line']));
  });
});

// Pages another builder is editing at the same time: held to the literals
// this pass removed, by name, and to their keys existing.
describe.each([
  ['RDPage.js', [
    "push('Saving...')", "'Cost exceeds R&D budget'", 'message="Choose one R&D action',
    'Upgrade an existing feature when', 'Invest next level\n', 'title="CURRENT R&D DRAFT"',
    "{ title: 'Feature'", "{ title: 'Method'", "{ title: 'Cost'",
  ]],
  ['FinancePage.js', [
    "'Unsaved budget changes'", "'Saving budget...'", "'Budget saved'", "'Budget save failed'",
    "'Unsaved financing changes'", "'Saving financing...'", "'Financing saved'",
    "'Financing save failed'", '| Round {currentRound} budget remaining',
    'Enter dollar amounts directly', 'Setup: {fmt(switchCost)}', 'Regulators: {',
    '`Allocated budget ${', "'net positive'", "'net negative if audited'",
  ]],
  // The remaining-literal sweep (2026-09-22): what it found on the visited
  // screens and this pass could fix.
  ['GameDashboard.js', ["label: 'Supply Chain'"]],
  ['ProductsPage.js', ['placeholder="e.g. Nexus Pro"']],
  ['CorporateStrategyPage.js', ['`Revoking triggers a', '`Revocation penalty active:', '`HQ: ${']],
  ['MarketingPage.js', ['{d.positioning}\n']],
  ['../components/TeamActivityBanner.js', ["|| 'a decision'"]],
])('%s: the literals W-CE-16 removed', (name, literals) => {
  const source = withoutComments(read(name));

  test.each(literals)('no longer says %s', (literal) => {
    expect(source).not.toContain(literal);
  });

  test('every key it asks for exists in both languages', () => {
    const missing = keysUsed(source).filter((key) => !exists(en, key) || !exists(zh, key));
    expect(missing).toEqual([]);
  });
});

describe('GameDashboard.js: the next-action card and the checklist', () => {
  const source = withoutComments(read('GameDashboard.js'));

  test.each([
    'NEXT REQUIRED ACTION',
    'Continue here first',
    'Continue to {',
    'Open Review & Submit',
    "'Needs review'",
    "'Not started'",
  ])('no longer says %s', (literal) => {
    expect(source).not.toContain(literal);
  });

  test('every key it asks for exists in both languages', () => {
    const missing = keysUsed(source).filter((key) => !exists(en, key) || !exists(zh, key));
    expect(missing).toEqual([]);
  });
});

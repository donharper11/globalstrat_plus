import fs from 'fs';
import path from 'path';

import { withoutComments } from '../englishLiteralScan';

/**
 * Third Consumer Electronics walkthrough (2026-09-23): the screens whose
 * defect is *what the source does*, not what one render happens to produce.
 *
 * A source scan rather than a render test, following
 * `walkCe2MoneyFormat.test.js`: each of these was a single line that a later
 * edit can quietly restore, and the render that would catch it needs a game
 * context, an API mock and a round of data. Comments are stripped first,
 * because every repaired file explains the defect by quoting it.
 */

const SRC = path.join(__dirname, '..');
const read = (relative) => withoutComments(
  fs.readFileSync(path.join(SRC, relative), 'utf8'));

// W-CE3-15 -----------------------------------------------------------------
// Round 6 read `1 Nova Circuit 54.59 … 4 Meridian Tech 60.34`: R32 places a
// commercially inactive firm below every firm that competed, and the
// leaderboard said nothing about it. The marker and the rule are the server's
// own sentences, so the page must read them rather than invent wording.
describe('the leaderboard explains an inversion it shows', () => {
  const source = () => read('pages/LeaderboardPage.js');

  test('the row marker is read from the payload', () => {
    expect(source()).toMatch(/commercially_inactive/);
    expect(source()).toMatch(/rank_marker/);
  });

  test('the rule is stated under the table', () => {
    expect(source()).toMatch(/rank_rule_note/);
  });

  test('neither sentence is written in the page', () => {
    expect(source()).not.toMatch(/did not compete/i);
    expect(source()).not.toMatch(/未参与竞争/);
  });
});

// W-CE3-19 -----------------------------------------------------------------
// The end-of-game team export read `Status: No decisions saved` for every
// team, including four that played all six rounds: the column reads the
// currently open round, which the advance past round 6 had just created.
describe('the team summary export says which round its status describes', () => {
  const source = () => read('pages/InstructorDashboard.js');

  test('the status header names the round', () => {
    expect(source()).toMatch(/export_status_round/);
  });

  test('the bare status label is no longer the export header', () => {
    const exportBlock = source().split('const exportAllTeams')[1]
      .split('const statusColor')[0];
    expect(exportBlock).not.toMatch(/t\('instructor\.status'\)/);
  });

  test('the sentence exists in both catalogues, with the same placeholder', () => {
    const en = JSON.parse(fs.readFileSync(
      path.join(SRC, 'locales/en.json'), 'utf8'));
    const zh = JSON.parse(fs.readFileSync(
      path.join(SRC, 'locales/zh-CN.json'), 'utf8'));
    expect(en.instructor.export_status_round).toMatch(/\{\{round\}\}/);
    expect(zh.instructor.export_status_round).toMatch(/\{\{round\}\}/);
  });
});

const catalogues = () => [
  JSON.parse(fs.readFileSync(path.join(SRC, 'locales/en.json'), 'utf8')),
  JSON.parse(fs.readFileSync(path.join(SRC, 'locales/zh-CN.json'), 'utf8')),
];

// W-CE3-12 -----------------------------------------------------------------
// One tab of nine carried a hard-coded English literal where every sibling
// used the catalogue, so it read `Trade Finance & FX` on a Chinese screen.
describe('the Financial Reports tab bar is wholly in the catalogue', () => {
  const source = () => read('pages/FinancialReportsPage.js');

  test('no tab label is a bare string literal', () => {
    const labels = source().match(/^ *label: .*$/gm) || [];
    expect(labels.length).toBeGreaterThan(5);
    labels.forEach((line) => expect(line).toMatch(/t\(/));
  });

  test('the tab name exists in both catalogues and differs between them', () => {
    const [en, zh] = catalogues();
    expect(en.financial_reports.trade_finance_fx).toBe('Trade Finance & FX');
    expect(zh.financial_reports.trade_finance_fx).toBeTruthy();
    expect(zh.financial_reports.trade_finance_fx)
      .not.toBe(en.financial_reports.trade_finance_fx);
  });
});

// W-CE3-17 -----------------------------------------------------------------
// The evaluation's criterion names were `criteria_scores`' own storage keys,
// prettified, and the weight beside them a hard-coded English literal.
describe('the communication evaluation names its criteria', () => {
  const source = () => read('pages/CommunicationsPage.js');

  test('the authored label is preferred over the prettified token', () => {
    expect(source()).toMatch(/criterion_label/);
  });

  test('both call sites go through one helper, and the token is the fallback', () => {
    expect(source()).toMatch(/criterionLabelFor/);
    // One definition of the prettifier, reached through the helpers -- not a
    // label computed inline at each of the two call sites, as before.
    const prettifiers = source().match(/\.replace\(\/\\b\\w\/g/g) || [];
    expect(prettifiers.length).toBe(1);
    expect(source()).not.toMatch(/c\.criterion\.replace/);
  });

  test('the weight comes from the catalogue', () => {
    expect(source()).not.toMatch(/\(weight:/);
    const [en, zh] = catalogues();
    expect(en.communications_page.criterion_weight).toMatch(/\{\{weight\}\}/);
    expect(zh.communications_page.criterion_weight).toMatch(/\{\{weight\}\}/);
  });
});

// W-CE3-18 -----------------------------------------------------------------
// *Refused: …requires a written reason of at least 10 characters.
// **reason_required***: the code ran onto the end of the sentence, because
// only a CSS margin stood between them and the row's own text has no margins.
describe('the operator log keeps the refusal code off the sentence', () => {
  const source = () => read('components/instructor/OperatorEventsPanel.js');
  const refusalBlock = () => source().split('oplog_refused_because')[1]
    .split('const rows =')[0];

  test('the code is labelled and outside the sentence it followed', () => {
    expect(refusalBlock()).toMatch(/oplog_refusal_code/);
    // The sentence's own div closes before the code is rendered.
    expect(refusalBlock().indexOf('</div>'))
      .toBeLessThan(refusalBlock().indexOf('oplog_refusal_code'));
  });

  test('the label exists in both catalogues', () => {
    const [en, zh] = catalogues();
    expect(en.instructor.oplog_refusal_code).toBeTruthy();
    expect(zh.instructor.oplog_refusal_code).toBeTruthy();
  });
});

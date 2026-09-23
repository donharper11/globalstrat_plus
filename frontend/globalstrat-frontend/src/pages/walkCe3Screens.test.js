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

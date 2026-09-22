import fs from 'fs';
import path from 'path';

import en from '../locales/en.json';
import zh from '../locales/zh-CN.json';

/**
 * The instructor console after the 2026-09-22 walkthrough (W-CE-08, W-CE-17,
 * W-CE-20). Each block names the defect it keeps fixed.
 *
 * Reads the source, as `instructorDashboardMessages.test.js` does: the
 * dashboard is a 2,000-line component that cannot be rendered without the
 * whole console behind it, and what these defects were about is visible in
 * the source -- a stored token rendered as its own label, an English literal
 * where a `t()` key belongs, a table placed before the content it explains.
 */

const read = (relative) => fs.readFileSync(path.join(__dirname, relative), 'utf8');
const DASHBOARD = read('InstructorDashboard.js');

const lookup = (catalogue, key) => key.split('.')
  .reduce((node, part) => (node == null ? node : node[part]), catalogue);
const inBoth = (key) => typeof lookup(en, key) === 'string' && typeof lookup(zh, key) === 'string';

describe('W-CE-08: a submission status is a translated label, never the stored token', () => {
  test('the drill-down does not print `drillData.status` as its own label', () => {
    expect(DASHBOARD).not.toMatch(/>\{drillData\.status\}</);
  });

  test('the team overview does not print `decision_status` as its own label', () => {
    // `render: (v, r) => ... <Tag ...>{v}</Tag>` was the raw token.
    const column = DASHBOARD.slice(
      DASHBOARD.indexOf("dataIndex: 'decision_status'"),
      DASHBOARD.indexOf("dataIndex: 'coherence_score'"));
    expect(column).not.toMatch(/>\{v\}</);
    expect(column).toMatch(/submissionStatusLabel\(v\)/);
  });

  test('every status the server can send has a label in both languages', () => {
    ['instructor.submission_status_locked', 'instructor.submission_status_draft',
      'instructor.submission_status_empty'].forEach((key) => {
      expect(inBoth(key)).toBe(true);
      expect(DASHBOARD).toContain(`t('${key}')`);
    });
  });

  test('a team with no submission is not given two tags for one fact', () => {
    expect(DASHBOARD).toMatch(/drillData\.status !== 'no_submission' &&/);
  });
});

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

describe('W-CE-17: the console’s English on a Chinese screen', () => {
  const source = DASHBOARD.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

  test.each([
    "label: 'Students & Logins'",
    'title="Decision round"',
    'title="Round status"',
    'title="Game status"',
    "text: 'Open for student decisions'",
    "text: 'Not open yet'",
    '`Monitoring ${',
    'Latest processed results round: ${',
    'addonAfter="hours"',
    'CSV format: student_id',
    '} student(s)</Text>',
    "} student(s)`",
    '} students assigned',
    'placeholder="Category name',
    'placeholder="Description"',
    "['Team', 'Index', 'Cash'",
    "'Select a section first'",
    "'No simulation linked to this section'",
    'placeholder="e.g. Spring 2026 Simulation"',
    'John Doe,john@university.edu',
  ])('no longer says %s', (literal) => {
    expect(source).not.toContain(literal);
  });

  test('the stored game status is never its own label', () => {
    expect(source).not.toMatch(/>\{displayGameStatus\}</);
    expect(source).not.toMatch(/value=\{displayGameStatus\}/);
  });

  test('every key the console asks for exists in both languages', () => {
    const keys = [...new Set([...source.matchAll(/\bt\(\s*'([\w.]+)'/g)].map((m) => m[1]))];
    expect(keys.length).toBeGreaterThan(300);
    expect(keys.filter((key) => !inBoth(key))).toEqual([]);
  });

  test('the audit table and the supply-chain panel are whole-scan clean', () => {
    // Held to the same scan as the round-control card; see
    // consolePanelsLanguage.test.js (InstructorSCPanel) and the render test
    // AuditEvidenceTable.test.js. Here: no computed key and every key exists.
    ['../components/instructor/AuditEvidenceTable.js', '../components/instructor/InstructorSCPanel.js']
      .forEach((relative) => {
        const panel = read(relative).replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
        expect(panel.match(/\bt\(\s*(?!['"])/g) || []).toEqual([]);
        const keys = [...panel.matchAll(/\bt\(\s*'([\w.]+)'/g)].map((m) => m[1]);
        expect(keys.filter((key) => !inBoth(key))).toEqual([]);
      });
  });
});

describe('W-CE-11: the console header carries the language switch', () => {
  test('the instructor header renders LanguageSwitcher', () => {
    const header = DASHBOARD.slice(
      DASHBOARD.indexOf('const instructorHeader = ('),
      DASHBOARD.indexOf('if (loading && gameId) return'));
    expect(header).toContain('<LanguageSwitcher');
  });
});

describe('W-CE-20: the drill-down leads with the decisions, not the audit table', () => {
  const modal = DASHBOARD.slice(
    DASHBOARD.indexOf('{/* Team Decisions Drill-Down Modal */}'),
    DASHBOARD.indexOf('export default InstructorDashboard'));

  test('the audit table is rendered once, after every decision block, collapsed', () => {
    const audit = modal.indexOf('<AuditEvidenceTable');
    expect(audit).toBeGreaterThan(-1);
    expect(modal.indexOf('<AuditEvidenceTable', audit + 1)).toBe(-1);
    ['drillData.budget &&', 'drillData.rd?.investments', 'drillData.marketing?.length',
      'drillData.financing &&', 'drillData.esg &&', 'drillData.talent &&']
      .forEach((block) => {
        expect(modal.indexOf(block)).toBeGreaterThan(-1);
        expect(modal.indexOf(block)).toBeLessThan(audit);
      });
    expect(modal.slice(audit, modal.indexOf('/>', audit))).toContain('collapsed');
  });
});

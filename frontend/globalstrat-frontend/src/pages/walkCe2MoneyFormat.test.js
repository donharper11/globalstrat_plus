import fs from 'fs';
import path from 'path';

import { withoutComments } from '../englishLiteralScan';

/**
 * W-CE2-09 (second Consumer Electronics walkthrough). The Summary printed
 * `Unallocated: $-12553689` beside figures written `$28.5M`: eight copies of
 * the same short money formatter tested `n >= 1e6` and `n >= 1e3`, so every
 * negative amount fell past both branches into `toFixed(0)`.
 *
 * A source scan rather than a render test, because the defect is the shape of
 * the branch and the copies are spread across eight files: a ninth copy
 * written the old way fails here the moment it is added.
 *
 * The directories are listed rather than walked, following
 * `walkCeStudentLanguage.test.js`: every copy of this formatter lives in a
 * page, a component or the design system, and a bounded read keeps this suite
 * from starving the timing-sensitive suites beside it.
 */

const SRC = path.join(__dirname, '..');
const SCANNED_DIRS = ['pages', 'components', 'components/design-system',
                      'components/instructor', 'pages/instructor'];

const scannedFiles = () => SCANNED_DIRS.flatMap((relativeDir) => {
  const dir = path.join(SRC, relativeDir);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((name) => /\.(js|jsx)$/.test(name) && !/\.test\.(js|jsx)$/.test(name))
    .map((name) => path.join(relativeDir, name));
});

// A money formatter's unit branch. `Math.abs(n) >= 1e6` is the correct shape;
// `n >= 1e6` is the defect.
const UNGUARDED = /(?<!Math\.abs\()\bn\s*>=\s*1e[36]\b/;

// The files the repair touched, named so a "fix" that deletes the branch
// rather than guarding it is still a failure here.
const REPAIRED = [
  'components/BudgetBar.js',
  'components/BudgetAlert.js',
  'components/GameStatusBar.js',
  'components/design-system/DSBudgetBar.jsx',
  'pages/StrategyPage.js',
  'pages/CommunicationsPage.js',
  'pages/MarketStrategyPage.js',
  'pages/RDPage.js',
  'pages/MarketingPage.js',
  'pages/CorporateStrategyPage.js',
];

describe('every money formatter carries the sign', () => {
  test('no scanned source decides a unit from an unsigned comparison', () => {
    // Comments are stripped first: the repaired files explain the defect by
    // quoting the branch that caused it.
    const offenders = scannedFiles()
      .filter((relative) => UNGUARDED.test(withoutComments(
        fs.readFileSync(path.join(SRC, relative), 'utf8'))));
    expect(offenders).toEqual([]);
  });

  test('the guarded shape is present in every file the repair touched', () => {
    REPAIRED.forEach((relative) => {
      const source = fs.readFileSync(path.join(SRC, relative), 'utf8');
      expect(source).toMatch(/Math\.abs\(n\)\s*>=\s*1e6/);
      expect(source).toMatch(/Math\.abs\(n\)\s*>=\s*1e3/);
    });
  });
});

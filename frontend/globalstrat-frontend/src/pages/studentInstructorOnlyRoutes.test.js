import fs from 'fs';
import path from 'path';

/**
 * W-CE-09 (walkthrough of 2026-09-22). The student sidebar offered "Team
 * Activity", whose page's only data call was
 * `GET /games/<g>/teams/<t>/changes/` -- `IsInstructor` since the V2-035
 * hardening -- so every visit was answered 403 "This area is open to
 * instructors only" and the console logged the error each time. V2-106 had
 * already found the same route polled by `TeamActivityBanner` and stopped
 * that poll for students; the page itself was left in the sidebar.
 *
 * There is no student route for the team change log, so the page, its
 * route and its sidebar entry are gone from the student shell (the change
 * log is still written on every save and still readable by an instructor).
 * This reads the source so no student page can call the instructor-only
 * route again.
 */

const SRC = path.join(__dirname, '..');
const read = (relative) => fs.readFileSync(path.join(SRC, relative), 'utf8');

const sourceFiles = (dir) => fs.readdirSync(dir, { withFileTypes: true })
  .flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.jsx?$/.test(entry.name) && !/\.test\.jsx?$/.test(entry.name)
      ? [full] : [];
  });

describe('the instructor-only team-changes route', () => {
  test('is called by no student page', () => {
    const callers = sourceFiles(path.join(SRC, 'pages'))
      .filter((file) => /\bgetTeamChanges\(/.test(fs.readFileSync(file, 'utf8')))
      .map((file) => path.relative(SRC, file));
    expect(callers).toEqual([]);
  });

  test('the only remaining caller asks first whether it may', () => {
    // TeamActivityBanner (V2-106): instructors and admins only.
    const callers = sourceFiles(SRC)
      .filter((file) => /(?<!const )\bgetTeamChanges\(/.test(fs.readFileSync(file, 'utf8')))
      .map((file) => path.relative(SRC, file));
    expect(callers).toEqual([path.join('components', 'TeamActivityBanner.js')]);
    expect(read('components/TeamActivityBanner.js')).toMatch(/if \(!mayReadTeamChanges\) return;/);
  });
});

describe('the student shell', () => {
  test('has no Team Activity route or sidebar entry', () => {
    expect(fs.existsSync(path.join(SRC, 'pages', 'TeamActivityPage.js'))).toBe(false);
    expect(read('App.js')).not.toMatch(/team-activity|TeamActivityPage/);
    expect(read('components/Sidebar.js')).not.toMatch(/team-activity|team_activity/);
  });
});

import fs from 'fs';
import path from 'path';

/**
 * D6, the guard. The defect was two call sites that read `res.data.created`
 * and nothing else, so the per-row `errors` the server returned were dropped
 * and a partly refused upload was announced as a success. This reads the
 * source so a call site cannot discard the response again: every
 * `uploadRoster()` call anywhere under `src/` must hand its response straight
 * to the one shared reading.
 */

const SRC = path.join(__dirname, '..');

const sourceFiles = (dir) => fs.readdirSync(dir, { withFileTypes: true })
  .flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.jsx?$/.test(entry.name) && !/\.test\.jsx?$/.test(entry.name)
      ? [full] : [];
  });

const READ = /announceRosterUpload\(\s*rosterUploadOutcome\(\(await uploadRoster\(/g;

describe('every roster upload call site', () => {
  const callers = sourceFiles(SRC)
    .map((file) => ({ file, source: fs.readFileSync(file, 'utf8') }))
    // The definition in api/instructor.js is `export const uploadRoster =`.
    .map(({ file, source }) => ({
      file: path.relative(SRC, file),
      calls: (source.match(/(?<!const )\buploadRoster\(/g) || []).length,
      read: (source.match(READ) || []).length,
      source,
    }))
    .filter((entry) => entry.calls > 0);

  test('the scan finds the call sites it exists to police', () => {
    expect(callers.map((entry) => entry.file)).toEqual(
      [path.join('pages', 'InstructorDashboard.js')]);
    expect(callers[0].calls).toBe(2);
  });

  test('reads the response through rosterUploadOutcome, none is discarded', () => {
    for (const entry of callers) {
      expect({ file: entry.file, read: entry.read })
        .toEqual({ file: entry.file, read: entry.calls });
    }
  });

  test('no call site reads the created count on its own any more', () => {
    for (const entry of callers) {
      expect(entry.source).not.toMatch(/res\.data\?\.created/);
      expect(entry.source).not.toMatch(/msg_roster_uploaded/);
    }
  });

  test('the scanner itself tells a read response from a discarded one', () => {
    const good = 'announceRosterUpload(\n  rosterUploadOutcome((await uploadRoster(a, b)).data), ui);';
    const bad = 'const res = await uploadRoster(a, b); message.success(res.data.created);';
    expect((good.match(READ) || []).length).toBe(1);
    expect((bad.match(READ) || []).length).toBe(0);
    expect(('export const uploadRoster = (a) =>'.match(/(?<!const )\buploadRoster\(/g) || []).length).toBe(0);
  });
});

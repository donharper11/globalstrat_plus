import fs from 'fs';
import path from 'path';

/**
 * V2-104, the guard. The defect was a call site that did not read the response
 * of `assignStudents()`. Two of the three were repaired at 1855b25; the third
 * -- removing a student from a team -- still discarded it, and announced its
 * failure in hard-coded English. This reads the dashboard's source so that a
 * fourth call site cannot be added without going through the shared reading.
 */

describe('the dashboard’s call sites', () => {
  const source = fs.readFileSync(
    path.join(__dirname, 'InstructorDashboard.js'), 'utf8');

  test('every assignStudents() response is read, none is discarded', () => {
    const calls = source.match(/await assignStudents\(/g) || [];
    const read = source.match(
      /announceAssignment\(\s*assignmentOutcome\(\(await assignStudents\(/g) || [];
    expect(calls.length).toBeGreaterThan(0);
    expect(read.length).toBe(calls.length);
  });

  test('every call site hands the short-team report to the roster notice', () => {
    // `under_minimum` was returned by the server and read by nobody. A call
    // site that omits `onUnderMinimum` silently drops it again.
    const announced = source.match(/announceAssignment\(/g) || [];
    const handed = source.match(/onUnderMinimum: setUnderMinimum/g) || [];
    expect(announced.length).toBeGreaterThan(0);
    expect(handed.length).toBe(announced.length);
    expect(source).toMatch(/<UnderMinimumNotice notices=\{underMinimum\} t=\{t\} \/>/);
  });

  test('no assignment failure is announced in hard-coded English', () => {
    expect(source).not.toMatch(/Failed to unassign/);
  });
});

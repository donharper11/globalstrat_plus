import fs from 'fs';
import path from 'path';

/**
 * The instructor console announces in the instructor's language.
 *
 * `InstructorDashboard.js` had 42 `message.success/error/warning/info(...)`
 * calls whose text was an English literal -- `'Failed to create game'`,
 * `'Round schedule saved'`, `err.response?.data?.error || 'Failed to reset'` --
 * so an instructor working in Chinese was told in English. The string gate
 * (`check-participant-strings`) never saw them: it reads `t()` calls, and these
 * were not `t()` calls at all.
 *
 * This reads the source. Every `message.*(` call is cut out with its balanced
 * argument list, the keys handed to `t()` are set aside, and whatever
 * string or template literal is left must carry no letters. That catches a
 * call that OPENS on a literal and one that falls back to a literal after
 * `||`, which is how most of the 42 were written.
 */

const SOURCE = fs.readFileSync(
  path.join(__dirname, 'InstructorDashboard.js'), 'utf8');

const CALL = /\bmessage\.(success|error|warning|info|loading|open)\(/g;

/** The text between a call's opening parenthesis and its matching close. */
const argumentsAt = (source, open) => {
  let depth = 1;
  let quote = null;
  for (let i = open; i < source.length; i += 1) {
    const ch = source[i];
    if (quote) {
      if (ch === '\\') i += 1;
      else if (ch === quote) quote = null;
      continue;
    }
    if (ch === '\'' || ch === '"' || ch === '`') quote = ch;
    else if (ch === '(') depth += 1;
    else if (ch === ')') {
      depth -= 1;
      if (depth === 0) return source.slice(open, i);
    }
  }
  throw new Error(`unbalanced message call at offset ${open}`);
};

const messageCalls = (source) => {
  const calls = [];
  let match;
  CALL.lastIndex = 0;
  while ((match = CALL.exec(source)) !== null) {
    const open = match.index + match[0].length;
    calls.push({
      line: source.slice(0, match.index).split('\n').length,
      args: argumentsAt(source, open),
    });
  }
  return calls;
};

/** Literals that would reach the screen: everything except a `t()` key. */
const spokenLiterals = (args) => {
  const withoutKeys = args.replace(/\bt\(\s*(['"])[\w.]+\1/g, 't[KEY]');
  const literals = withoutKeys.match(
    /'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`/g) || [];
  return literals.filter((literal) => /\p{L}/u.test(
    // `${...}` holes are code, not wording.
    literal.replace(/\$\{[^}]*\}/g, '')));
};

describe('the scanner itself', () => {
  test.each([
    ["message.error('Failed to save');", 1],
    ["message.error(err.response?.data?.error || 'Failed to save');", 1],
    ['message.success(`Created ${n} students`);', 1],
    ["message.warning(\n  'Weights must sum to 100%'\n);", 1],
    ["message.error(t('instructor.msg_upload_failed'));", 0],
    ["message.error(err.response?.data?.error || t('instructor.msg_upload_failed'));", 0],
    ["message.success(t('instructor.msg_roster_uploaded', { count: n, file: `${a}` }), 10);", 0],
  ])('%s', (snippet, expected) => {
    const calls = messageCalls(snippet);
    expect(calls).toHaveLength(1);
    expect(spokenLiterals(calls[0].args)).toHaveLength(expected);
  });
});

describe('InstructorDashboard announcements', () => {
  const calls = messageCalls(SOURCE);

  test('the scan found the calls it is meant to police', () => {
    // A rename of the antd import would make the guard pass by finding nothing.
    expect(calls.length).toBeGreaterThanOrEqual(50);
  });

  test('no message.*( call speaks a hard-coded literal', () => {
    const offenders = calls
      .map((call) => ({ line: call.line, literals: spokenLiterals(call.args) }))
      .filter((call) => call.literals.length > 0)
      .map((call) => `line ${call.line}: ${call.literals.join(' ')}`);
    expect(offenders).toEqual([]);
  });

  test('no message.*( call picks its key at run time', () => {
    // The string gate cannot resolve a key chosen by a ternary or a variable;
    // write two t() calls instead.
    const computed = calls
      .filter((call) => /\bt\(\s*(?!['"])/.test(call.args))
      .map((call) => `line ${call.line}: ${call.args.trim()}`);
    expect(computed).toEqual([]);
  });
});

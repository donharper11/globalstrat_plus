import fs from 'fs';
import path from 'path';

import en from '../locales/en.json';
import zh from '../locales/zh-CN.json';

/**
 * The round-control card and the student-accounts panel speak the
 * instructor's language (V2-080, and D3's remainder of 2026-09-21).
 *
 * `RoundControlCard.js` -- close, reopen, process, advance, deadline: the most
 * destructive controls in the product -- was hard-coded English apart from the
 * eight confirmation titles Stage 6 routed through the catalogue, and
 * `StudentAccountsPanel.js` had no `t()` call at all. Both also fell back to an
 * English sentence whenever the server sent no reason (`|| 'Action failed'`).
 *
 * This reads the source, the same way `instructorDashboardMessages.test.js`
 * does for the dashboard: what a person would read must come from `t()` with a
 * literal key that exists in both catalogues.
 */

const read = (relative) => fs.readFileSync(path.join(__dirname, relative), 'utf8');

const PANELS = {
  'RoundControlCard.js': read('RoundControlCard.js'),
  'StudentAccountsPanel.js': read('StudentAccountsPanel.js'),
};
// Only its announcements are policed: the rest of this panel is still English
// (reported, not part of this item).
const ANNOUNCEMENTS_ONLY = {
  'instructor/InstructorSCPanel.js': read('instructor/InstructorSCPanel.js'),
};

const withoutComments = (source) => source
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '');

/** JSX text: letters sitting between a `>` and a `<` on the way to the screen. */
const jsxText = (source) => {
  const found = [];
  const pattern = />([^<>{}]*\p{L}{2,}[^<>{}]*)</gu;
  withoutComments(source).split('\n').forEach((line, index) => {
    // A line of code (arrow functions, comparisons) is not markup.
    if (/=>|&&|\|\||[=!]==|\breturn\b|\bconst\b/.test(line)) return;
    let match;
    while ((match = pattern.exec(line)) !== null) {
      found.push(`line ${index + 1}: ${match[1].trim()}`);
    }
  });
  return found;
};

/** A line of markup that is nothing but words. */
const bareTextLines = (source) => withoutComments(source).split('\n')
  .map((line, index) => ({ line: line.trim(), number: index + 1 }))
  .filter(({ line }) => /^[A-Z][\p{L}\p{N} ,.'’—–\-:;()&]*[\p{L}.]$/u.test(line)
    && /\s/.test(line))
  .map(({ line, number }) => `line ${number}: ${line}`);

/** `title="Deadline"`, `placeholder='…'`, `okText="…"`: a prop set to words. */
const SPOKEN_PROPS = ['title', 'label', 'message', 'description', 'placeholder',
  'okText', 'cancelText', 'emptyText', 'tooltip'];
const literalProps = (source) => {
  const found = [];
  const pattern = new RegExp(
    `\\b(${SPOKEN_PROPS.join('|')})\\s*[=:]\\s*\\{?\\s*(['"\`])((?:\\\\.|(?!\\2).)*)\\2`, 'g');
  const text = withoutComments(source);
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (/\p{L}/u.test(match[3].replace(/\$\{[^}]*\}/g, ''))) {
      found.push(`${match[1]}: ${match[3]}`);
    }
  }
  return found;
};

/** A `message.*(` call, or an `||` / `??` fallback, that ends in words. */
const spokenFallbacks = (source) => {
  const found = [];
  const text = withoutComments(source);
  const patterns = [
    /\bmessage\.(?:success|error|warning|info)\(\s*(['"`])((?:\\.|(?!\1).)*)\1/g,
    /(?:\|\||\?\?|\?|:)\s*(['"`])((?:\\.|(?!\1).)*\p{L}{3,}(?:\\.|(?!\1).)*)\1/gu,
  ];
  patterns.forEach((pattern) => {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      const words = match[2].replace(/\$\{[^}]*\}/g, '');
      // A word with a space or a capital is a sentence; `'descend'`,
      // `'success'`, `'danger'` are antd tokens.
      if (/\p{L}/u.test(words) && (/\s/.test(words) || /^[A-Z]/.test(words))) {
        found.push(match[2]);
      }
    }
  });
  return found;
};

const keysUsed = (source) => {
  const keys = new Set();
  const pattern = /\bt\(\s*(['"])([\w.]+)\1/g;
  let match;
  while ((match = pattern.exec(source)) !== null) keys.add(match[2]);
  return [...keys];
};

const lookup = (catalogue, key) => key.split('.')
  .reduce((node, part) => (node == null ? node : node[part]), catalogue);

const exists = (catalogue, key) => (
  typeof lookup(catalogue, key) === 'string'
  // i18next plural: `key` is asked for, `key_other` is what is stored.
  || typeof lookup(catalogue, `${key}_other`) === 'string');

describe('the scanner itself', () => {
  test('finds each way a panel can speak English', () => {
    expect(jsxText('<Text>Not set</Text>')).toHaveLength(1);
    expect(jsxText('<Button>{t(\'a.b\')}</Button>')).toHaveLength(0);
    expect(bareTextLines('  <Paragraph>\n    This unlocks every team.\n  </Paragraph>'))
      .toHaveLength(1);
    expect(literalProps('<Card title="Round Control" />')).toHaveLength(1);
    expect(literalProps('{ title: \'Student\', key: \'name\' }')).toHaveLength(1);
    expect(literalProps('<Card title={t(\'a.b\')} key="name" />')).toHaveLength(0);
    expect(spokenFallbacks('message.error(x?.error || \'Action failed\');'))
      .toHaveLength(1);
    expect(spokenFallbacks('message.error(\'Pick a new deadline.\');'))
      .toHaveLength(1);
    expect(spokenFallbacks('const a = b ? \'Change deadline\' : \'Set deadline\';'))
      .toHaveLength(2);
    expect(spokenFallbacks('message.error(x?.error || t(\'a.b\')); f(y ? \'danger\' : \'secondary\');'))
      .toHaveLength(0);
  });
});

describe.each(Object.entries(PANELS))('%s', (name, source) => {
  test('uses the catalogue at all', () => {
    expect(source).toMatch(/useTranslation\(\)/);
    expect(keysUsed(source).length).toBeGreaterThanOrEqual(30);
  });

  test('renders no hard-coded words', () => {
    expect([
      ...jsxText(source), ...bareTextLines(source), ...literalProps(source),
      ...spokenFallbacks(source),
    ]).toEqual([]);
  });

  test('picks no key at run time', () => {
    // The string gate cannot resolve a computed key; write one t() per key.
    expect(withoutComments(source).match(/\bt\(\s*(?!['"])/g) || []).toEqual([]);
  });

  test('every key it asks for exists in both languages', () => {
    const missing = keysUsed(source).filter(
      (key) => !exists(en, key) || !exists(zh, key));
    expect(missing).toEqual([]);
  });
});

describe.each(Object.entries(ANNOUNCEMENTS_ONLY))('%s announcements', (name, source) => {
  test('no message.*( call falls back to, or opens on, English', () => {
    const calls = withoutComments(source).split('\n')
      .filter((line) => /\bmessage\.(success|error|warning|info)\(/.test(line));
    expect(calls.length).toBeGreaterThanOrEqual(4);
    expect(calls.filter((line) => spokenFallbacks(line).length > 0)).toEqual([]);
  });

  test('every key it asks for exists in both languages', () => {
    const missing = keysUsed(source).filter(
      (key) => !exists(en, key) || !exists(zh, key));
    expect(missing).toEqual([]);
  });
});

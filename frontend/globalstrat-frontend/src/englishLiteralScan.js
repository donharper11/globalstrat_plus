/**
 * The source scan the language guards share (2026-09-22).
 *
 * `consolePanelsLanguage.test.js` wrote these for the round-control card and
 * the student-accounts panel; the walkthrough's language guards
 * (`walkCeStudentLanguage.test.js`, `walkCeConsoleLanguage.test.js`) read the
 * same four shapes of English out of a React source: JSX text between tags, a
 * line of markup that is nothing but words, a spoken prop set to a literal,
 * and an announcement or fallback that ends in words. What a person would read
 * must come from `t()` with a literal key that exists in both catalogues.
 *
 * Not imported by the application; only by tests.
 */

export const withoutComments = (source) => source
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '');

/** JSX text: letters sitting between a `>` and a `<` on the way to the screen. */
export const jsxText = (source) => {
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
export const bareTextLines = (source) => withoutComments(source).split('\n')
  .map((line, index) => ({ line: line.trim(), number: index + 1 }))
  .filter(({ line }) => /^[A-Z][\p{L}\p{N} ,.'’—–\-:;()&]*[\p{L}.]$/u.test(line)
    && /\s/.test(line))
  .map(({ line, number }) => `line ${number}: ${line}`);

/** `title="Deadline"`, `placeholder='…'`, `okText="…"`: a prop set to words. */
export const SPOKEN_PROPS = ['title', 'label', 'message', 'description', 'placeholder',
  'okText', 'cancelText', 'emptyText', 'tooltip'];

export const literalProps = (source) => {
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
export const spokenFallbacks = (source) => {
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

/** Every literal key handed to `t()`. */
export const keysUsed = (source) => {
  const keys = new Set();
  const pattern = /\bt\(\s*(['"])([\w.]+)\1/g;
  let match;
  while ((match = pattern.exec(source)) !== null) keys.add(match[2]);
  return [...keys];
};

/** `t(` with anything but a quoted literal: a key decided at run time. */
export const computedKeys = (source) => (
  withoutComments(source).match(/\bt\(\s*(?!['"])/g) || []);

export const lookup = (catalogue, key) => key.split('.')
  .reduce((node, part) => (node == null ? node : node[part]), catalogue);

export const exists = (catalogue, key) => (
  typeof lookup(catalogue, key) === 'string'
  // i18next plural: `key` is asked for, `key_other` is what is stored.
  || typeof lookup(catalogue, `${key}_other`) === 'string');

/** Everything the scan can find, in one list, for one source. */
export const everythingSpoken = (source) => [
  ...jsxText(source), ...bareTextLines(source), ...literalProps(source),
  ...spokenFallbacks(source),
];

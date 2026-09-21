import fs from 'fs';
import path from 'path';

/**
 * Nobody is told anything in a hard-coded sentence, anywhere under `src/`.
 *
 * `instructorDashboardMessages.test.js` polices `message.*(` calls in one file.
 * The remainder of 2026-09-21 found the same defect outside it: the R&D page
 * -- a student page -- announced "All R&D investment slots are already used
 * this round." in English to everyone, and three instructor panels fell back
 * to English whenever the server sent no reason. `check-participant-strings`
 * cannot see these: it reads `t()` calls, and these are not `t()` calls.
 *
 * Two shapes are caught, in every non-test source file:
 *   message.error('Words')  /  message.success(`Saved ${x}`)
 *   anything || 'Words that form a sentence'   (also ??)
 */

const ROOT = __dirname;

const sources = (dir) => fs.readdirSync(dir, { withFileTypes: true })
  .flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sources(full);
    if (!/\.jsx?$/.test(entry.name) || /\.test\.jsx?$/.test(entry.name)) return [];
    return [full];
  });

const withoutComments = (source) => source
  .replace(/\/\*[\s\S]*?\*\//g, (block) => block.replace(/[^\n]/g, ' '))
  .replace(/^(\s*)\/\/.*$/gm, '$1');

const OPENS_ON_WORDS = /\bmessage\.(?:success|error|warning|info)\(\s*(['"`])((?:\\.|(?!\1).)*)\1/g;
const FALLS_BACK_TO_WORDS = /(?:\|\||\?\?)\s*(['"`])((?:\\.|(?!\1).)*)\1/g;

const isSentence = (text) => {
  const words = text.replace(/\$\{[^}]*\}/g, '').trim();
  // A capitalised word or more: `'en'`, `'default'`, `'descend'` and CSS
  // values are tokens; `'Sourcing'` and `'Not set'` are read by a person.
  return /^[A-Z][a-z]{2,}/.test(words);
};

const offences = (source) => {
  const text = withoutComments(source);
  const found = [];
  [OPENS_ON_WORDS, FALLS_BACK_TO_WORDS].forEach((pattern) => {
    pattern.lastIndex = 0;
    let match;
    while ((match = pattern.exec(text)) !== null) {
      if (isSentence(match[2])) {
        found.push({
          line: text.slice(0, match.index).split('\n').length,
          text: match[2],
        });
      }
    }
  });
  return found;
};

describe('the scanner itself', () => {
  test.each([
    ["message.warning('All R&D investment slots are already used this round.');", 1],
    ['message.success(`Saved R&D investment: ${feature.name} to level ${n}`);', 1],
    ["setError(e?.response?.data?.detail || 'Failed to load the panel.');", 1],
    ["const name = record.home_market_name ?? 'Not set';", 1],
    ["label: <span>{sidebarLabels?.sourcing_page || 'Sourcing'}</span>,", 1],
    ["message.error(err.response?.data?.error || t('instructor.rc_load_failed'));", 0],
    ["const lang = stored || 'en'; const kind = x || 'default';", 0],
    ["// message.error('Commented out words');", 0],
  ])('%s', (snippet, expected) => {
    expect(offences(snippet)).toHaveLength(expected);
  });
});

describe('every source file', () => {
  const files = sources(ROOT);

  test('the scan reads the tree it is meant to police', () => {
    expect(files.length).toBeGreaterThan(80);
    expect(files.some((file) => file.endsWith('pages/RDPage.js'))).toBe(true);
  });

  test('announces, and falls back, through the catalogue only', () => {
    const offenders = files.flatMap((file) => offences(fs.readFileSync(file, 'utf8'))
      .map((hit) => `${path.relative(ROOT, file)}:${hit.line}: ${hit.text}`));
    expect(offenders).toEqual([]);
  });
});

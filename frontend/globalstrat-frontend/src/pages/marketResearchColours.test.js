import fs from 'fs';
import path from 'path';

/**
 * W-CE-16: the research reports' rating words now arrive in the reader's
 * language, so the page must colour by the server's code, not by the English
 * word. Reads the source: every fitColor() and importancePct() call takes
 * the `_code` field first.
 */
const source = fs.readFileSync(path.join(__dirname, 'MarketResearchPage.js'), 'utf8');

test('every fit colour is taken from a code, with the word as the fallback', () => {
  const calls = source.match(/fitColor\(([^)]*)\)/g).filter((c) => !c.startsWith('fitColor(codeOrLabel'));
  expect(calls.length).toBeGreaterThanOrEqual(5);
  calls.forEach((call) => {
    expect(call).toMatch(/_code \|\| /);
  });
});

test('importance is measured and coloured by its code', () => {
  expect(source).toMatch(/importancePct\(f\.importance_code \|\| f\.importance\)/);
  expect(source).not.toMatch(/f\.importance === 'Critical'/);
});

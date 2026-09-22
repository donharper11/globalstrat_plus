import { countWords } from './communicationWords';

/**
 * R48 item 7. The live count on the communications page and the count the
 * server refuses on are one rule: CJK letters at 1.5 per word, added to the
 * space-split count of the rest. This table is the one in
 * `backend/core/tests/test_communication_word_limit.py`, row for row, so a
 * change to either side without the other fails here.
 */
const CASES = [
  ['', 0],
  ['   ', 0],
  ['one two three', 3],
  ['  spaced\tout\nwords  ', 3],
  ['中文字', 2],
  ['中文字中文字', 4],
  ['中', 1],
  ['市'.repeat(600), 400],
  ['我们。他们', 3],
  ['市场，产品；价格。', 4],
  ['第１季度', 3],
  ['Q3 memo 我们将进入欧洲市场 end', 3 + 6],
  ['ひらがな', 3],
  ['カタカナ', 3],
  ['한국어', 2],
  ['\u{20000}\u{20001}\u{20002}', 2],
];

test.each(CASES)('%j counts %i words', (text, expected) => {
  expect(countWords(text)).toBe(expected);
});

test('a missing value is empty, not an error', () => {
  expect(countWords(undefined)).toBe(0);
  expect(countWords(null)).toBe(0);
});

test('English is what the page always counted', () => {
  const memo = 'word '.repeat(300);
  expect(countWords(memo)).toBe(memo.trim().split(/\s+/).length);
});

test('the rule is a pure function of the text', () => {
  expect(countWords('市'.repeat(450))).toBe(300);
  expect(countWords('市'.repeat(450))).toBe(300);
});

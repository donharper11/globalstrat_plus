/**
 * How many words a communication has, in either language (R48 item 7).
 *
 * The communications page shows a live "N / limit" count while a student
 * writes, and disables Submit past the limit. It counted by splitting on
 * spaces, so a Chinese memo counted as one word and the limit never bound
 * for a Chinese team. This is the screen's half of one rule; the server's
 * half is `backend/core/services/communication_words.py`, with the same
 * letter ranges and the same integer arithmetic, and the two tests share one
 * table of cases. Change both or neither.
 *
 * The rule:
 *  - a CJK letter is a Han ideograph (unified block, extension A, the
 *    supplementary-plane extensions, compatibility ideographs, and 々〆〇),
 *    a Hiragana or Katakana letter (with the phonetic extensions and the
 *    half-width forms), or a Hangul syllable or jamo;
 *  - every 1.5 CJK letters are one word, rounded up: ceil(letters * 2 / 3);
 *  - CJK punctuation and full-width symbols separate words and are not
 *    counted; full-width digits and Latin letters are words;
 *  - everything else is split on whitespace, as before.
 */

const CJK_LETTER = new RegExp(
  '['
  + '\\u3400-\\u4dbf'      // CJK Unified Ideographs Extension A
  + '\\u4e00-\\u9fff'      // CJK Unified Ideographs
  + '\\uf900-\\ufaff'      // CJK Compatibility Ideographs
  + '\\u{20000}-\\u{2fa1f}' // Extensions B..F and the supplementary compat block
  + '\\u3005-\\u3007'      // 々 〆 〇
  + '\\u3040-\\u309f'      // Hiragana
  + '\\u30a0-\\u30ff'      // Katakana
  + '\\u31f0-\\u31ff'      // Katakana Phonetic Extensions
  + '\\uff66-\\uff9f'      // Half-width Katakana
  + '\\u1100-\\u11ff'      // Hangul Jamo
  + '\\u3130-\\u318f'      // Hangul Compatibility Jamo
  + '\\uac00-\\ud7af'      // Hangul Syllables
  + ']',
  'gu',
);

const CJK_SEPARATOR = new RegExp(
  '['
  + '\\u3000-\\u3004\\u3008-\\u303f' // CJK symbols and punctuation, less 々〆〇
  + '\\uff01-\\uff0f\\uff1a-\\uff20' // full-width punctuation, not digits/letters
  + '\\uff3b-\\uff40\\uff5b-\\uff65'
  + ']',
  'gu',
);

export const CJK_LETTERS_PER_WORD = 1.5;

/** The number of words in `text` under the rule above; a missing value is 0. */
export function countWords(text) {
  const source = text || '';
  const letters = (source.match(CJK_LETTER) || []).length;
  const rest = source.replace(CJK_LETTER, ' ').replace(CJK_SEPARATOR, ' ').trim();
  const spaced = rest ? rest.split(/\s+/).length : 0;
  // ceil(letters / 1.5) in integers, as the server does it.
  const cjkWords = Math.floor((letters * 2 + 2) / 3);
  return spaced + cjkWords;
}

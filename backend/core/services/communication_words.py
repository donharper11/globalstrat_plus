"""How many words a communication has, in either language (R48 item 7).

A communication assignment carries a `word_limit`, and the submit route
refused a memo over it by counting `len(content.split())`. Chinese is written
without spaces, so a Chinese memo of any length counted as one word and the
limit never bound for a Chinese team. The integrator's decision under R48:
count CJK letters at 1.5 letters per word, added to the space-split count of
the rest, so a Chinese team is limited like an English one.

This is the only place the server counts, and
`frontend/globalstrat-frontend/src/communicationWords.js` is the only place
the screen counts; the two carry the same letter ranges and the same integer
arithmetic, and their tests share one table of cases, so the live count a
student watches is the count the server refuses on.

The rule:

* a CJK letter is a Han ideograph (the unified block, extensions A and the
  supplementary-plane extensions, the compatibility ideographs, and the
  iteration marks 々〆〇), a Hiragana or Katakana letter (including the
  phonetic extensions and the half-width forms), or a Hangul syllable or
  jamo;
* every 1.5 CJK letters are one word, rounded up, so a single letter is one
  word and never zero: `ceil(letters * 2 / 3)`, in integers;
* CJK punctuation and full-width symbols (。，、「」！？ and the like) separate
  words and are not counted; full-width digits and Latin letters are words
  like their ASCII forms;
* everything else is split on whitespace, exactly as before.
"""
import re

CJK_LETTER = re.compile(
    '['
    '㐀-䶿'          # CJK Unified Ideographs Extension A
    '一-鿿'          # CJK Unified Ideographs
    '豈-﫿'          # CJK Compatibility Ideographs
    '\U00020000-\U0002fa1f'  # Extensions B..F and the supplementary compat block
    '々-〇'          # 々 〆 〇
    '぀-ゟ'          # Hiragana
    '゠-ヿ'          # Katakana
    'ㇰ-ㇿ'          # Katakana Phonetic Extensions
    'ｦ-ﾟ'          # Half-width Katakana
    'ᄀ-ᇿ'          # Hangul Jamo
    '㄰-㆏'          # Hangul Compatibility Jamo
    '가-힯'          # Hangul Syllables
    ']')

CJK_SEPARATOR = re.compile(
    '['
    '　-〄〈-〿'  # CJK symbols and punctuation, less 々〆〇
    '！-／：-＠'  # full-width punctuation, not digits/letters
    '［-｀｛-･'
    ']')

CJK_LETTERS_PER_WORD = 1.5


def count_words(text):
    """The number of words in `text` under the rule above; `None` is empty."""
    source = text or ''
    letters = len(CJK_LETTER.findall(source))
    rest = CJK_SEPARATOR.sub(' ', CJK_LETTER.sub(' ', source))
    # ceil(letters / 1.5) without a float, so the screen cannot disagree by a
    # rounding: 1 -> 1, 2 -> 2, 3 -> 2, 600 -> 400.
    cjk_words = (letters * 2 + 2) // 3
    return len(rest.split()) + cjk_words

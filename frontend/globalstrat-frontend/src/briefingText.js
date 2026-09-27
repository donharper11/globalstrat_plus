/** Plain-text briefing surfaces must not print Markdown control characters. */
export const briefingDisplayText = (text) => {
  if (typeof text !== 'string') return text;
  return text.replace(/\*\*([^*\n]+)\*\*/g, '$1');
};

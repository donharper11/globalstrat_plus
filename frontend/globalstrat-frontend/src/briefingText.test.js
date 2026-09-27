import { briefingDisplayText } from './briefingText';

test.each([
  ['**Quarter 3 Results**\n\nRevenue declined.', 'Quarter 3 Results\n\nRevenue declined.'],
  ['**第 2 回合业绩**\n\n收入增长。', '第 2 回合业绩\n\n收入增长。'],
])('removes Markdown emphasis from a plain-text briefing', (stored, displayed) => {
  expect(briefingDisplayText(stored)).toBe(displayed);
});

test('leaves prose without Markdown unchanged', () => {
  expect(briefingDisplayText('Quarter 4 Results')).toBe('Quarter 4 Results');
});

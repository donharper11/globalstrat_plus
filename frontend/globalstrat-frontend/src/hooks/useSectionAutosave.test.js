/**
 * The autosave two decision pages share.
 *
 * Both pages had a private copy of it that (1) ended in a catch block which
 * discarded the error, and (2) kept ONE debounce timer for every section on
 * the page -- so choosing an entry mode and then typing a compliance amount
 * within two seconds cancelled the entry-mode save without a word. The choice
 * stayed highlighted on screen and was never sent.
 */
import React from 'react';
import { render, act } from '@testing-library/react';
import useSectionAutosave from './useSectionAutosave';
import { patchDecision } from '../api/decisions';
import { subscribeToSaves, resetSaveFailures } from '../api/saveFailures';

jest.mock('../api/decisions', () => ({ patchDecision: jest.fn() }));

let hook;
const Probe = (props) => { hook = useSectionAutosave(props); return null; };

const mount = (overrides = {}) => render(
  <Probe gameId={1} teamId={2} currentRound={3} locked={false} {...overrides} />,
);

const flush = async (ms) => {
  await act(async () => { jest.advanceTimersByTime(ms); });
  await act(async () => { await Promise.resolve(); });
};

beforeEach(() => {
  jest.useFakeTimers();
  patchDecision.mockReset();
  patchDecision.mockResolvedValue({ data: {} });
  resetSaveFailures();
});

afterEach(() => jest.useRealTimers());

test('two sections edited inside one debounce are BOTH saved', async () => {
  mount();
  act(() => {
    hook.autoSave('market-entry', { market_entries: [{ market: 5 }] });
    hook.autoSave('compliance-investments', { compliance_investments: [] });
  });
  await flush(2000);

  expect(patchDecision.mock.calls.map(call => call[3]).sort())
    .toEqual(['compliance-investments', 'market-entry']);
});

test('a second edit to the same section replaces the first, as before', async () => {
  mount();
  act(() => {
    hook.autoSave('esg', { esg: { social_investment: 1 } });
    hook.autoSave('esg', { esg: { social_investment: 2 } });
  });
  await flush(2000);

  expect(patchDecision).toHaveBeenCalledTimes(1);
  expect(patchDecision).toHaveBeenCalledWith(1, 2, 3, 'esg', { esg: { social_investment: 2 } });
});

test('nothing is sent once the submission is locked', async () => {
  mount({ locked: true });
  act(() => { hook.autoSave('esg', { esg: {} }); });
  await flush(2000);
  expect(patchDecision).not.toHaveBeenCalled();
});

test('a refused save is remembered against its section, not discarded', async () => {
  const refusal = {
    config: { method: 'patch', url: '/games/1/teams/2/decisions/round/3/esg/' },
    response: { status: 400, data: { detail: 'No.' } },
  };
  patchDecision.mockRejectedValueOnce(refusal);
  mount();
  act(() => { hook.autoSave('esg', { esg: {} }); });
  await flush(2000);

  expect(hook.failedSections).toEqual(['esg']);

  // ...and a later accepted save of that section clears it.
  act(() => { hook.autoSave('esg', { esg: {} }); });
  await flush(2000);
  expect(hook.failedSections).toEqual([]);
});

test('a failure that never became a request is still announced', async () => {
  // The interceptor cannot see an error thrown before axios sends anything.
  const seen = [];
  subscribeToSaves(event => seen.push(event.type));
  patchDecision.mockRejectedValueOnce(new TypeError('could not build the request'));
  mount();
  act(() => { hook.autoSave('esg', { esg: {} }); });
  await flush(2000);

  expect(seen).toEqual(['failed']);
});

test('the page is told when a save lands, so it can re-read what it needs', async () => {
  const onSaved = jest.fn();
  mount({ onSaved });
  act(() => { hook.autoSave('acquisitions', { acquisitions: [] }); });
  await flush(2000);
  expect(onSaved).toHaveBeenCalledWith('acquisitions');
});

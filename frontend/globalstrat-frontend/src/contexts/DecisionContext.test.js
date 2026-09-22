/**
 * V2-064 / R17: a contended save must refuse fast AND tell the student.
 *
 * Each test names the finding it covers and fails without the repair. Before
 * it, `saveDraft` was `catch (err) { console.error(...) }` -- the edit was
 * discarded, nothing was shown, and the indicator went on reporting the last
 * successful save.
 *
 * i18n is not initialised under test, so a lookup renders its key itself and
 * the assertions below are on keys. The SERVER's sentences are asserted
 * verbatim, which is the point: the screen must not restate the rule in its
 * own words.
 *
 * (An earlier draft of this comment quoted a translation call with a made-up
 * key as an example. The string check reads every line of every .js file
 * under src without stripping comments, so it reported the example as a real
 * uncatalogued key and failed the build -- the same false positive that made
 * V2-080 look open. Describe the shape; do not spell out the call.)
 */
import React from 'react';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { DecisionProvider, useDecisions } from './DecisionContext';
import DecisionSaveAlert from '../components/DecisionSaveAlert';
import GameStatusBar from '../components/GameStatusBar';
import { saveDecisions, getDecisions } from '../api/decisions';
import client from '../api/client';
import {
  publishSaveFailure, publishSaveSuccess, resetSaveFailures,
} from '../api/saveFailures';

jest.mock('../api/decisions', () => ({
  getDecisions: jest.fn(() => Promise.resolve({ data: {} })),
  saveDecisions: jest.fn(),
}));

jest.mock('../api/client', () => ({
  __esModule: true,
  default: { request: jest.fn(() => Promise.resolve({ data: {} })) },
}));

jest.mock('./GameContext', () => ({
  useGame: () => ({
    gameId: 1, teamId: 2, currentRound: 3, refreshBudgets: jest.fn(),
    team: { name: 'Atlas' }, totalRounds: 4, roundStatus: 'open', budgets: null,
  }),
}));

jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { is_demo: false } }),
}));

/** The refusal the decision-write boundary returns, verbatim in shape. */
const LIFECYCLE_REFUSAL = {
  response: {
    status: 409,
    data: {
      detail: 'This round is being processed. Refresh shortly to see the results.',
      code: 'lifecycle_in_progress',
    },
  },
};

/** A DRF field refusal: the server read the edit and objected to it. */
const VALIDATION_REFUSAL = {
  response: {
    status: 400,
    data: { retail_price: ['Set a unit price above zero for Atlas in Germany.'] },
  },
};

let ctx;
const Probe = () => { ctx = useDecisions(); return null; };

const mount = async () => {
  await act(async () => {
    render(
      <DecisionProvider>
        <DecisionSaveAlert />
        <GameStatusBar />
        <Probe />
      </DecisionProvider>,
    );
  });
};

const save = async () => { await act(async () => { await ctx.saveDraft(); }); };

beforeEach(() => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  resetSaveFailures();
  ctx = undefined;
});

afterEach(() => { jest.useRealTimers(); resetSaveFailures(); });

describe('a refused autosave is surfaced and retried (V2-064, R17)', () => {
  test('a lifecycle conflict tells the student nothing was saved', async () => {
    saveDecisions.mockRejectedValue(LIFECYCLE_REFUSAL);
    await mount();
    await save();

    expect(screen.getByText('decision_save.not_saved_title')).toBeInTheDocument();
    // The operator wording, not the validation wording.
    expect(screen.getByText('decision_save.lifecycle_conflict')).toBeInTheDocument();
    expect(screen.queryByText('decision_save.refused')).not.toBeInTheDocument();
  });

  test('a lifecycle conflict is retried rather than dropped', async () => {
    saveDecisions.mockRejectedValue(LIFECYCLE_REFUSAL);
    await mount();
    await save();

    expect(screen.getByText('decision_save.retrying')).toBeInTheDocument();
    expect(saveDecisions).toHaveBeenCalledTimes(1);

    await act(async () => { jest.advanceTimersByTime(2000); });
    expect(saveDecisions).toHaveBeenCalledTimes(2);
  });

  test('a validation refusal shows the server sentence and is NOT retried', async () => {
    saveDecisions.mockRejectedValue(VALIDATION_REFUSAL);
    await mount();
    await save();

    expect(screen.getByText('decision_save.refused')).toBeInTheDocument();
    // The server's own sentence, verbatim -- no field name, no restatement.
    expect(screen.getByText(
      'Set a unit price above zero for Atlas in Germany.')).toBeInTheDocument();
    // A timer will never fix an edit the server objected to.
    expect(screen.queryByText('decision_save.retrying')).not.toBeInTheDocument();

    await act(async () => { jest.advanceTimersByTime(30000); });
    expect(saveDecisions).toHaveBeenCalledTimes(1);
  });

  test('a 409 without the lifecycle code is a refusal, not an operator action', async () => {
    // The classifier keys on `code`, never on the status alone: some other
    // conflict must not be retried as though an instructor caused it.
    saveDecisions.mockRejectedValue({
      response: { status: 409, data: { detail: 'This submission is locked.' } },
    });
    await mount();
    await save();

    expect(screen.getByText('decision_save.refused')).toBeInTheDocument();
    expect(screen.queryByText('decision_save.lifecycle_conflict')).not.toBeInTheDocument();
    expect(screen.getByText('This submission is locked.')).toBeInTheDocument();
  });

  test('pressing Retry now re-sends the refused edit and clears the notice', async () => {
    saveDecisions
      .mockRejectedValueOnce(LIFECYCLE_REFUSAL)
      .mockResolvedValueOnce({ data: {} });
    await mount();
    await save();
    expect(screen.getByText('decision_save.not_saved_title')).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'decision_save.retry_now' }));
    });

    expect(screen.queryByText('decision_save.not_saved_title')).not.toBeInTheDocument();
    expect(ctx.lastSaved).not.toBeNull();
  });
});

describe('a refusal on the path students actually use (V2-064)', () => {
  // The autosave above is not how decisions are saved in the product:
  // `updateDraft` is called by no page, so `isDirty` never becomes true and
  // `saveDraft` never runs. Every real save is a page's own patchDecision,
  // and those pages discard the error. These tests cover the route that
  // carries them -- the axios interceptor -- because a fix that only worked
  // through saveDraft would be a fix no student could reach.
  const refusedConfig = {
    method: 'patch',
    url: '/games/1/teams/2/decisions/round/3/finance/',
  };

  test("a page's refused save raises the notice even though the page ignored it", async () => {
    await mount();
    expect(screen.queryByText('decision_save.not_saved_title')).not.toBeInTheDocument();

    await act(async () => {
      publishSaveFailure({
        config: refusedConfig,
        response: {
          status: 409,
          data: { code: 'lifecycle_in_progress', detail: 'busy' },
        },
      });
    });

    expect(screen.getByText('decision_save.not_saved_title')).toBeInTheDocument();
    expect(screen.getByText('decision_save.lifecycle_conflict')).toBeInTheDocument();
  });

  test('the refused request itself is re-sent, not a rebuilt one', async () => {
    await mount();
    await act(async () => {
      publishSaveFailure({
        config: refusedConfig,
        response: { status: 409, data: { code: 'lifecycle_in_progress' } },
      });
    });

    await act(async () => { jest.advanceTimersByTime(2000); });

    expect(client.request).toHaveBeenCalledTimes(1);
    expect(client.request).toHaveBeenCalledWith(refusedConfig);
  });

  test('a later successful save clears the notice', async () => {
    await mount();
    await act(async () => {
      publishSaveFailure({
        config: refusedConfig,
        response: { status: 400, data: { detail: 'No.' } },
      });
    });
    expect(screen.getByText('decision_save.not_saved_title')).toBeInTheDocument();

    await act(async () => { publishSaveSuccess(); });

    expect(screen.queryByText('decision_save.not_saved_title')).not.toBeInTheDocument();
    expect(ctx.lastSaved).not.toBeNull();
  });
});

describe('the indicator stops claiming a save that did not happen (V2-064)', () => {
  test('no successful save is ever claimed after a refusal', async () => {
    saveDecisions.mockRejectedValue(LIFECYCLE_REFUSAL);
    await mount();
    await save();

    expect(ctx.lastSaved).toBeNull();
    expect(screen.getByText('game_status.not_saved')).toBeInTheDocument();
    expect(screen.queryByText(/^game_status\.saved/)).not.toBeInTheDocument();
  });

  test('a refusal after a good save replaces the stale "Saved" timestamp', async () => {
    // The defect verbatim: `lastSaved` is only ever set on success and is
    // never cleared, so the bar read "Saved 14:32" over an unsaved edit.
    saveDecisions
      .mockResolvedValueOnce({ data: {} })
      .mockRejectedValue(LIFECYCLE_REFUSAL);
    await mount();
    await save();
    expect(screen.getByText('game_status.saved')).toBeInTheDocument();

    await save();
    expect(screen.getByText('game_status.not_saved')).toBeInTheDocument();
    expect(screen.queryByText('game_status.saved')).not.toBeInTheDocument();
  });
});

describe('one section being saved does not hide another that was refused', () => {
  const allocation = {
    method: 'patch', url: '/games/1/teams/2/decisions/round/3/talent/',
  };
  const esg = { method: 'patch', url: '/games/1/teams/2/decisions/round/3/esg/' };

  test('the notice stays up, and Retry re-sends the refused one', async () => {
    await mount();
    await act(async () => {
      publishSaveFailure({
        config: allocation,
        response: { status: 400, data: { talent_allocations: ['Allocated staff (45) must equal the selected team headcount (50).'] } },
      });
    });
    await act(async () => { publishSaveSuccess(esg); });

    expect(screen.getByText('decision_save.not_saved_title')).toBeInTheDocument();
    expect(screen.getByText(
      'Allocated staff (45) must equal the selected team headcount (50).')).toBeInTheDocument();

    await act(async () => { fireEvent.click(screen.getByText('decision_save.retry_now')); });
    expect(client.request).toHaveBeenCalledWith(allocation);
  });
});

describe('what a page reads back is what the server holds (2026-09-21)', () => {
  // The provider sits above every student route, so it mounted once and read
  // the draft once. Pages rebuild "the whole list" from that draft on every
  // save, so a second product created in one sitting was sent as [second] and
  // replaced the first; and a page revisited without a reload showed the
  // round as it stood when the student logged in.
  test('loadDraft re-reads the draft', async () => {
    getDecisions.mockResolvedValueOnce({ data: {} });
    await mount();
    expect(ctx.draft).toEqual({});

    getDecisions.mockResolvedValueOnce({ data: { product_creates: [{ product_name: 'A' }] } });
    await act(async () => { await ctx.loadDraft(); });
    expect(ctx.draft.product_creates).toEqual([{ product_name: 'A' }]);
  });

  test('a refresh that finds nothing new keeps the same draft object', async () => {
    // Pages re-initialise their state when `draft` changes identity, so a
    // no-change refresh must not reset a page the student is typing on.
    getDecisions.mockResolvedValueOnce({ data: { esg: { social_investment: 5 } } });
    await mount();
    const before = ctx.draft;
    getDecisions.mockResolvedValueOnce({ data: { esg: { social_investment: 5 } } });
    await act(async () => { await ctx.loadDraft(); });
    expect(ctx.draft).toBe(before);
  });

  test('a refresh that fails keeps the draft it had', async () => {
    // Blanking it would be worse than staleness: the next replace-style save
    // built from an empty draft deletes what the server holds.
    getDecisions.mockResolvedValueOnce({ data: { status: 'locked', acquisitions: [{ acquisition_target: 4 }] } });
    await mount();
    expect(ctx.locked).toBe(true);

    getDecisions.mockRejectedValueOnce(new Error('offline'));
    await act(async () => { await ctx.loadDraft(); });

    expect(ctx.draft.acquisitions).toEqual([{ acquisition_target: 4 }]);
    expect(ctx.locked).toBe(true);
  });
});

/**
 * V2-064: which requests count as "a team saving a decision".
 *
 * The refusal notice is driven from the axios interceptor rather than from the
 * pages, because the pages discard their own save errors. That only works if
 * this predicate is right, so it is asserted directly rather than through a
 * rendered screen.
 */
import {
  isDecisionWrite, publishSaveFailure, publishSaveSuccess,
  subscribeToSaves, getLastFailedRequest, resetSaveFailures,
  reportUnpublishedFailure,
} from './saveFailures';

afterEach(() => resetSaveFailures());

describe('which requests are decision writes', () => {
  const url = '/games/1/teams/2/decisions/round/3/marketing/';

  test('a write to a decisions route counts', () => {
    expect(isDecisionWrite({ method: 'patch', url })).toBe(true);
    expect(isDecisionWrite({ method: 'POST', url })).toBe(true);
    expect(isDecisionWrite({ method: 'put', url })).toBe(true);
  });

  test('reads do not count -- a failed read is fixed by reloading', () => {
    expect(isDecisionWrite({ method: 'get', url })).toBe(false);
    expect(isDecisionWrite({ method: 'head', url })).toBe(false);
    // axios defaults to GET when the config omits the method.
    expect(isDecisionWrite({ url })).toBe(false);
  });

  test('writes to other routes do not count', () => {
    expect(isDecisionWrite({ method: 'post', url: '/auth/login/' })).toBe(false);
    expect(isDecisionWrite({
      method: 'post', url: '/games/1/instructor/advance-round/',
    })).toBe(false);
  });

  test('a malformed config never throws', () => {
    expect(isDecisionWrite(undefined)).toBe(false);
    expect(isDecisionWrite({})).toBe(false);
  });
});

describe('publishing', () => {
  test('a failure is announced and its request kept for the retry', () => {
    const seen = [];
    subscribeToSaves(e => seen.push(e));
    const config = { method: 'patch', url: '/decisions/' };
    publishSaveFailure({ config, response: { status: 409 } });

    expect(seen).toHaveLength(1);
    expect(seen[0].type).toBe('failed');
    // The retry must re-send the refused edit, not rebuild one.
    expect(getLastFailedRequest()).toBe(config);
  });

  test('a success clears the kept request', () => {
    publishSaveFailure({ config: { url: '/decisions/' } });
    publishSaveSuccess();
    expect(getLastFailedRequest()).toBeNull();
  });

  test('unsubscribing stops delivery', () => {
    const seen = [];
    const stop = subscribeToSaves(e => seen.push(e));
    stop();
    publishSaveSuccess();
    expect(seen).toHaveLength(0);
  });
});

/**
 * 2026-09-21. Two pages save several sections each, and the notice was cleared
 * by ANY successful decision write: a refused staff allocation followed by an
 * accepted ESG save took the notice down with the allocation still unsaved.
 * That is the silent loss R17 forbids, arrived at through the repair for it.
 */
describe('one section succeeding does not excuse another that was refused', () => {
  const allocation = { method: 'patch', url: '/games/1/teams/2/decisions/round/3/talent-allocations/' };
  const esg = { method: 'patch', url: '/games/1/teams/2/decisions/round/3/esg/' };
  const refusal = (config) => ({ config, response: { status: 400, data: {} } });

  test('the refused request is still the one to retry', () => {
    const seen = [];
    subscribeToSaves(e => seen.push(e));
    publishSaveFailure(refusal(allocation));
    publishSaveSuccess(esg);

    expect(getLastFailedRequest()).toBe(allocation);
    // The listener is told the failure still stands, not that all is saved.
    expect(seen.map(e => e.type)).toEqual(['failed', 'failed']);
    expect(seen[1].error.config).toBe(allocation);
  });

  test('the same section succeeding does clear it', () => {
    const seen = [];
    subscribeToSaves(e => seen.push(e));
    publishSaveFailure(refusal(allocation));
    publishSaveSuccess({ ...allocation });

    expect(getLastFailedRequest()).toBeNull();
    expect(seen.map(e => e.type)).toEqual(['failed', 'saved']);
  });

  test('two refused sections are worked through one at a time', () => {
    publishSaveFailure(refusal(allocation));
    publishSaveFailure(refusal(esg));
    expect(getLastFailedRequest()).toBe(esg);
    publishSaveSuccess(esg);
    expect(getLastFailedRequest()).toBe(allocation);
    publishSaveSuccess(allocation);
    expect(getLastFailedRequest()).toBeNull();
  });

  test('a newer refusal of the same section replaces the older request', () => {
    const newer = { ...allocation, data: '{"newer":true}' };
    publishSaveFailure(refusal(allocation));
    publishSaveFailure(refusal(newer));
    expect(getLastFailedRequest()).toBe(newer);
    publishSaveSuccess(newer);
    expect(getLastFailedRequest()).toBeNull();
  });
});

describe('the other student writes whose failures were swallowed', () => {
  test('choosing a tax structure is a decision write', () => {
    expect(isDecisionWrite({
      method: 'post', url: '/games/1/teams/2/context/tax-structure/',
    })).toBe(true);
    // ...and reading the same route is not.
    expect(isDecisionWrite({
      method: 'get', url: '/games/1/teams/2/context/tax-structure/',
    })).toBe(false);
  });

  test('autosaving a stakeholder communication draft is a decision write', () => {
    expect(isDecisionWrite({
      method: 'post', url: '/games/1/teams/2/communications/7/draft/',
    })).toBe(true);
  });
});

describe('a failure the interceptor never saw', () => {
  test('is announced, so it cannot be silent', () => {
    const seen = [];
    subscribeToSaves(e => seen.push(e));
    reportUnpublishedFailure(new TypeError('payload could not be built'));
    expect(seen.map(e => e.type)).toEqual(['failed']);
  });

  test('is not announced twice when the interceptor already did', () => {
    const seen = [];
    subscribeToSaves(e => seen.push(e));
    const error = {
      config: { method: 'patch', url: '/games/1/teams/2/decisions/round/3/esg/' },
      response: { status: 400, data: {} },
    };
    publishSaveFailure(error);
    reportUnpublishedFailure(error);
    expect(seen).toHaveLength(1);
  });
});

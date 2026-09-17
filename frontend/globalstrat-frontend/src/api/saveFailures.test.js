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

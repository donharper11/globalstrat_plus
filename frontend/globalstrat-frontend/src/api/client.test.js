import fs from 'fs';
import path from 'path';

import { isSessionExpiry } from './client';

/**
 * A wrong password is answered 401 -- and every 401 used to send the browser
 * to `/login`, reloading the page. So the one refusal every student can meet,
 * "Invalid username or password" (now said in their language), was wiped off
 * the screen by the reload before it could be read, and an instructor who
 * mistyped a password on `/instructor/login` landed on the student form.
 */
describe('a 401 means the session ended, except from the login form', () => {
  const refused = (url, status = 401) => ({ response: { status }, config: { url } });

  test('an expired session redirects', () => {
    expect(isSessionExpiry(refused('/games/3/teams/4/decisions/round/1/'))).toBe(true);
    expect(isSessionExpiry(refused('/auth/me/'))).toBe(true);
  });

  test('a refused login stays on the page to say why', () => {
    expect(isSessionExpiry(refused('/auth/login/'))).toBe(false);
    expect(isSessionExpiry(refused('/auth/login'))).toBe(false);
  });

  test('nothing else is a session expiry', () => {
    expect(isSessionExpiry(refused('/auth/login/', 403))).toBe(false);
    expect(isSessionExpiry(refused('/games/3/', 403))).toBe(false);
    expect(isSessionExpiry({})).toBe(false);
    expect(isSessionExpiry(undefined)).toBe(false);
  });

  test('the interceptor asks this question rather than its own', () => {
    const source = fs.readFileSync(path.join(__dirname, 'client.js'), 'utf8');
    expect(source).toMatch(/if \(isSessionExpiry\(error\)\) \{/);
    expect(source).not.toMatch(/error\.response\.status === 401\) \{/);
  });
});

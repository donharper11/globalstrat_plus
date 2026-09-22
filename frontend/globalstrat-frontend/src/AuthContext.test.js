import { syncLanguagePreference } from './AuthContext';
import { setLanguagePreference } from './api/auth';

/**
 * W-CE-15. The language chosen on the login page (`localStorage.gs_language`,
 * written by the switch before there is a token) becomes the signed-in
 * person's stated preference, through the existing preference route. The
 * team's language is read from that preference (R43), so without this a team
 * playing in Chinese was refused in English by the analyst route.
 */
jest.mock('./api/auth', () => ({
  getCurrentUser: jest.fn(),
  setLanguagePreference: jest.fn(() => Promise.resolve({ data: {} })),
}));

beforeEach(() => {
  localStorage.clear();
  jest.clearAllMocks();
  // CRA resets mock implementations between tests; restore the promise.
  setLanguagePreference.mockImplementation(() => Promise.resolve({ data: {} }));
});

test('a choice that differs from the stored preference is sent at sign-in', () => {
  localStorage.setItem('gs_language', 'zh-CN');
  expect(syncLanguagePreference({ language: 'en' })).toBe('zh-CN');
  expect(setLanguagePreference).toHaveBeenCalledWith('zh-CN');
});

test('a choice the server already holds is not sent again', () => {
  localStorage.setItem('gs_language', 'zh-CN');
  expect(syncLanguagePreference({ language: 'zh-CN' })).toBeNull();
  expect(setLanguagePreference).not.toHaveBeenCalled();
});

test('no choice, nothing sent: the enrolment keeps what it has', () => {
  expect(syncLanguagePreference({ language: 'en' })).toBeNull();
  expect(setLanguagePreference).not.toHaveBeenCalled();
});

test('a value the platform does not support is never sent', () => {
  localStorage.setItem('gs_language', 'fr');
  expect(syncLanguagePreference({ language: 'en' })).toBeNull();
  expect(setLanguagePreference).not.toHaveBeenCalled();
});

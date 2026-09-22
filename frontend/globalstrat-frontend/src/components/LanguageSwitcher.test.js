import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import LanguageSwitcher from './LanguageSwitcher';
import DSTopBar from './design-system/TopBar';
import { setLanguagePreference } from '../api/auth';

/**
 * W-CE-11: a switch inside the game, and W-CE-15: the choice is recorded as
 * the signed-in person's preference through the existing route.
 */

const mockChangeLanguage = jest.fn();
let mockLanguage = 'en';
jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
    i18n: { get language() { return mockLanguage; }, changeLanguage: mockChangeLanguage },
  }),
}));
jest.mock('../api/auth', () => ({
  setLanguagePreference: jest.fn(() => Promise.resolve({ data: {} })),
  getCurrentUser: jest.fn(),
}));
jest.mock('react-router-dom', () => ({ useNavigate: () => jest.fn() }));
jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { display_name: 'Ada Lovelace' }, logout: jest.fn() }),
}));
jest.mock('../contexts/GameContext', () => ({
  useGame: () => ({ currentRound: 1, totalRounds: 10, roundStatus: 'open', budgets: null, team: { name: 'Aurora' } }),
}));
jest.mock('../contexts/DecisionContext', () => ({
  useDecisions: () => ({ locked: false }),
}));

beforeEach(() => {
  mockLanguage = 'en';
  localStorage.clear();
  jest.clearAllMocks();
  setLanguagePreference.mockImplementation(() => Promise.resolve({ data: {} }));
});

describe('the switch', () => {
  test('offers the other language and changes it for the session', () => {
    render(<LanguageSwitcher />);
    fireEvent.click(screen.getByText('中文'));
    expect(mockChangeLanguage).toHaveBeenCalledWith('zh-CN');
    expect(localStorage.getItem('gs_language')).toBe('zh-CN');
  });

  test('records the choice through the preference route when signed in', () => {
    localStorage.setItem('access_token', 'token');
    render(<LanguageSwitcher />);
    fireEvent.click(screen.getByText('中文'));
    expect(setLanguagePreference).toHaveBeenCalledWith('zh-CN');
  });

  test('records nothing before sign-in: there is no one to record it for', () => {
    render(<LanguageSwitcher />);
    fireEvent.click(screen.getByText('中文'));
    expect(setLanguagePreference).not.toHaveBeenCalled();
  });

  test('from Chinese it offers English', () => {
    mockLanguage = 'zh-CN';
    render(<LanguageSwitcher />);
    fireEvent.click(screen.getByText('EN'));
    expect(mockChangeLanguage).toHaveBeenCalledWith('en');
  });
});

describe('W-CE-11: the switch is in the game top bar', () => {
  test('the student top bar renders the switch', () => {
    render(<DSTopBar onToggle={() => {}} isMobile={false} />);
    expect(screen.getByText('中文')).toBeInTheDocument();
  });
});

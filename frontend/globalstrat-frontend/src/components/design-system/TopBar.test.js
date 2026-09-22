import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import DSTopBar from './TopBar';

/**
 * W-CE-10 (walkthrough of 2026-09-22). The student top bar carried a bell:
 * a button with no handler, no label and nothing behind it -- no
 * notifications API serves a student, and the instructor alerts are
 * instructor-only. It is gone rather than wired to a subsystem that does
 * not exist. Every control left in the top bar does something and says
 * what.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

jest.mock('../../AuthContext', () => ({
  useAuth: () => ({
    user: { user_id: 2, display_name: 'Ava Chen', role: 'student' },
    logout: jest.fn(),
  }),
}));

jest.mock('../../contexts/GameContext', () => ({
  useGame: () => ({
    currentRound: 1, totalRounds: 10, roundStatus: 'open', budgets: null,
    team: { name: 'Aurora Devices' },
  }),
}));

jest.mock('../../contexts/DecisionContext', () => ({
  useDecisions: () => ({ locked: false }),
}));

describe('the student top bar', () => {
  test('has no decorative control: every button is named', () => {
    render(<MemoryRouter><DSTopBar onToggle={() => {}} isMobile={false} /></MemoryRouter>);

    const buttons = Array.from(document.querySelectorAll('.ds-topbar button'));
    expect(buttons.length).toBeGreaterThan(0);
    const unnamed = buttons.filter((button) => !(
      button.getAttribute('title') || button.getAttribute('aria-label')
      || button.textContent.trim()));
    expect(unnamed.map((button) => button.outerHTML)).toEqual([]);
    expect(document.querySelector('[data-icon="bell"]')).toBeNull();
    expect(screen.getByTitle('topbar.log_out')).toBeInTheDocument();
  });
});

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from './Sidebar';

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key, i18n: { language: 'en' } }),
}));
jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { team_name: 'Team A', role: 'instructor', is_instructor: true } }),
}));
jest.mock('../contexts/GameContext', () => ({
  useGame: () => ({ gameId: 1, teamId: 2, currentRound: 1, sidebarLabels: null }),
}));
jest.mock('../api/decisions', () => ({
  getDecisionSummary: () => new Promise(() => {}),
}));

const openGroups = (container) => container.querySelectorAll('.ant-menu-submenu-open');
const groupTitle = (label) => screen.getByText(label).closest('.ant-menu-submenu-title');

describe('sidebar menu groups', () => {
  test('open one at a time, starting with the current page\'s group', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/games/1/teams/2/news']}>
        <Sidebar collapsed={false} />
      </MemoryRouter>,
    );
    expect(openGroups(container)).toHaveLength(1);
    expect(openGroups(container)[0]).toHaveTextContent('nav.information');

    fireEvent.click(groupTitle('nav.decisions'));
    expect(openGroups(container)).toHaveLength(1);
    expect(openGroups(container)[0]).toHaveTextContent('nav.decisions');

    fireEvent.click(groupTitle('nav.results'));
    expect(openGroups(container)).toHaveLength(1);
    expect(openGroups(container)[0]).toHaveTextContent('nav.results');

    fireEvent.click(groupTitle('nav.results'));
    expect(openGroups(container)).toHaveLength(0);
  });
});

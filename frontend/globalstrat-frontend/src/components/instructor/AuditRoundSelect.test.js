import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import AuditRoundSelect from './AuditRoundSelect';

const openMenu = () => fireEvent.mouseDown(
  document.querySelector('.ant-select-selector'));

describe('historical round selection', () => {
  test('offers every round played so far and no more', () => {
    render(<AuditRoundSelect value={3} currentRound={3} onChange={() => {}} />);
    openMenu();
    const options = Array.from(
      document.querySelectorAll('.ant-select-item-option-content'))
      .map(node => node.textContent);
    expect(options).toEqual(['Round 1', 'Round 2', 'Round 3']);
  });

  test('choosing an earlier round reports that round', () => {
    const onChange = jest.fn();
    render(<AuditRoundSelect value={3} currentRound={3} onChange={onChange} />);
    openMenu();
    fireEvent.click(screen.getByTitle('Round 1'));
    expect(onChange).toHaveBeenCalledWith(1, expect.anything());
  });

  test('shows the round currently being viewed', () => {
    render(<AuditRoundSelect value={2} currentRound={4} onChange={() => {}} />);
    expect(screen.getByTitle('Round 2')).toBeInTheDocument();
  });

  test('a game that has not started offers nothing to select', () => {
    render(<AuditRoundSelect value={undefined} currentRound={0} onChange={() => {}} />);
    openMenu();
    expect(document.querySelectorAll('.ant-select-item-option-content'))
      .toHaveLength(0);
  });

  test('a missing round count is treated as no rounds, not as a crash', () => {
    render(<AuditRoundSelect value={undefined} currentRound={undefined} onChange={() => {}} />);
    openMenu();
    expect(document.querySelectorAll('.ant-select-item-option-content'))
      .toHaveLength(0);
  });
});

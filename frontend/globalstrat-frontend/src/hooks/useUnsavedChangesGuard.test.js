import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import useUnsavedChangesGuard from './useUnsavedChangesGuard';

const Guarded = ({ dirty = true }) => {
  useUnsavedChangesGuard(dirty, 'Discard unsaved changes?');
  return <a href="/next">Next</a>;
};

describe('useUnsavedChangesGuard', () => {
  let confirm;

  beforeEach(() => {
    window.history.replaceState({}, '', '/current');
    confirm = jest.spyOn(window, 'confirm').mockReturnValue(false);
  });

  afterEach(() => confirm.mockRestore());

  test('blocks a same-origin link when the user cancels', () => {
    render(<Guarded />);
    fireEvent.click(screen.getByRole('link', { name: 'Next' }));
    expect(confirm).toHaveBeenCalledWith('Discard unsaved changes?');
    expect(window.location.pathname).toBe('/current');
  });

  test('does not prompt when the page is clean', () => {
    render(<Guarded dirty={false} />);
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(confirm).not.toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(false);
  });

  test('marks beforeunload as prevented while dirty', () => {
    render(<Guarded />);
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });
});

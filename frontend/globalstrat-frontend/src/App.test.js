import { render, screen } from '@testing-library/react';
import App from './App';

/**
 * The only test that mounts the whole application.
 *
 * It replaces Create React App's stock "renders learn react link" assertion,
 * which never applied to this app and had been failing silently behind a module
 * resolution error: `react-router-dom@7` declares a `main` that does not exist,
 * jest 27 has no `exports` support, and the suite could not import App at all.
 * With the import fixed the placeholder was simply revealed as a placeholder.
 *
 * What is worth asserting here is what the resolution failure hid: that the
 * router mounts, the default route resolves, and the login screen renders.
 * The shared authentication bootstrap now initialises i18n as part of mounting
 * the app, so the assertion checks the default English label as well as the
 * route and form structure.
 */
test('mounts, resolves the default route and renders the login screen', () => {
  render(<App />);

  expect(screen.getByRole('textbox', { name: 'Username' })).toBeInTheDocument();
  expect(screen.getByLabelText('Password')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Log In' })).toBeInTheDocument();
});

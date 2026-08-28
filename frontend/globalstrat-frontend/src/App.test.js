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
 * Deliberately structural — i18n is not initialised under test, so every label
 * is a translation key and asserting on visible text would test the fixture.
 */
test('mounts, resolves the default route and renders the login screen', () => {
  const { container } = render(<App />);

  expect(container.querySelector('input#username')).toBeInTheDocument();
  expect(container.querySelector('input[type="password"]')).toBeInTheDocument();
  // `/login/i` would match the demo button too — both labels are raw i18n
  // keys under test (`login.log_in`, `login.try_demo`).
  expect(screen.getByRole('button', { name: 'login.log_in' })).toBeInTheDocument();
});

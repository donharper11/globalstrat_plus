import axios from 'axios';
import {
  isDecisionWrite, publishSaveFailure, publishSaveSuccess,
} from './saveFailures';

const API_BASE = process.env.REACT_APP_API_URL || '/api';

const client = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

const isLoginRequest = (config) => /\/auth\/login\/?$/.test(config?.url || '');

// Attach auth token to every request -- except the login itself. A token left
// over from yesterday is refused as expired before the password is even read,
// and since a refused login no longer reloads the page (below), nothing would
// ever clear it: the student could not log in at all.
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token && !isLoginRequest(config)) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Send user's language preference so backend can localize responses
  const lang = localStorage.getItem('gs_language');
  if (lang) {
    config.headers['Accept-Language'] = lang;
  }
  // Also send legacy headers for backward compat
  const sessionId = localStorage.getItem('gs_session_id');
  if (sessionId) {
    config.headers['X-Session-Id'] = sessionId;
  }
  try {
    const stored = localStorage.getItem('gs_user');
    if (stored) {
      const user = JSON.parse(stored);
      if (user?.user_id) config.headers['X-User-Id'] = user.user_id;
      if (user?.instance_id) config.headers['X-Instance-ID'] = user.instance_id;
    }
  } catch { /* ignore */ }
  return config;
});

/**
 * A 401 means the session has ended -- except from the login form itself,
 * where it means a wrong password. Redirecting that one reloaded the page and
 * wiped the refusal ("Invalid username or password") before it could be read,
 * and sent an instructor who mistyped on /instructor/login to the student form.
 */
export const isSessionExpiry = (error) => (
  error?.response?.status === 401 && !isLoginRequest(error?.config)
);

// Handle 401 — redirect to login
client.interceptors.response.use(
  (response) => {
    if (isDecisionWrite(response.config)) publishSaveSuccess(response.config);
    return response;
  },
  (error) => {
    if (isSessionExpiry(error)) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('gs_user');
      localStorage.removeItem('gs_session_id');
      window.location.href = '/login';
    } else if (isDecisionWrite(error.config)) {
      // R17. Announced here rather than at each call site because the pages
      // that save decisions swallow their own errors, and this is the one
      // point every one of them passes through. The rejection is still
      // re-thrown, so a page that DOES handle its own failure -- MarketingPage
      // does, from V2-107 -- keeps doing so.
      publishSaveFailure(error);
    }
    return Promise.reject(error);
  }
);

export default client;

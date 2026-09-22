import React, { createContext, useContext, useState, useEffect } from 'react';
import { getCurrentUser, setLanguagePreference } from './api/auth';

const SUPPORTED_LANGUAGES = ['en', 'zh-CN'];

/**
 * The language chosen on the login page becomes the signed-in person's stated
 * preference (W-CE-15, 2026-09-22).
 *
 * The switch on the login page can only write `localStorage.gs_language`:
 * there is no token yet, so nothing reached the server, and the enrolment
 * kept its default 'en'. The team's language -- what the analyst route and
 * Phase 2 speak to a student in (R43) -- is read from the enrolment, so a
 * team playing in Chinese was refused in English. Sent once, at sign-in, only
 * when the stored choice differs from what the server holds; best effort.
 */
export const syncLanguagePreference = (userData) => {
  let chosen = null;
  try {
    chosen = localStorage.getItem('gs_language');
  } catch {
    return null;
  }
  if (!SUPPORTED_LANGUAGES.includes(chosen)) return null;
  if ((userData?.language || 'en') === chosen) return null;
  setLanguagePreference(chosen).catch(() => {});
  return chosen;
};

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('gs_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      localStorage.removeItem('gs_user');
      return null;
    }
  });
  const [loading, setLoading] = useState(() => !localStorage.getItem('gs_user'));

  useEffect(() => {
    const stored = localStorage.getItem('gs_user');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        // Render the last server-verified session immediately. API authorization
        // remains server-side while this background request refreshes the user.
        setLoading(false);
        getCurrentUser(parsed.user_id, parsed.section_id)
          .then((res) => {
            const userData = res.data;
            // Preserve demo flag across refreshes
            if (parsed.is_demo) userData.is_demo = true;
            localStorage.setItem('gs_user', JSON.stringify(userData));
            setUser(userData);
          })
          .catch(() => {
            localStorage.removeItem('gs_user');
            localStorage.removeItem('access_token');
            setUser(null);
          })
          .finally(() => setLoading(false));
      } catch {
        localStorage.removeItem('gs_user');
        setUser(null);
        setLoading(false);
      }
    } else {
      setLoading(false);
    }
  }, []);

  const login = (userData) => {
    const chosen = syncLanguagePreference(userData);
    const stored = chosen ? { ...userData, language: chosen } : userData;
    localStorage.setItem('gs_user', JSON.stringify(stored));
    setUser(stored);
  };

  const logout = () => {
    localStorage.removeItem('gs_user');
    localStorage.removeItem('access_token');
    setUser(null);
  };

  const selectSection = (sectionData) => {
    const updated = { ...user, ...sectionData, requires_section_selection: false };
    delete updated.enrollments;
    localStorage.setItem('gs_user', JSON.stringify(updated));
    setUser(updated);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, selectSection }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

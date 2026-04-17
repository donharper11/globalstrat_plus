import React, { createContext, useContext, useState, useEffect } from 'react';
import { getCurrentUser } from './api/auth';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('gs_user');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
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
        setLoading(false);
      }
    } else {
      setLoading(false);
    }
  }, []);

  const login = (userData) => {
    localStorage.setItem('gs_user', JSON.stringify(userData));
    setUser(userData);
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

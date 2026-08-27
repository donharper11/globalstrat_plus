import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import LoadingSpinner from './LoadingSpinner';

const ProtectedRoute = ({ children, redirectTo = '/login', requiredRole }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return <LoadingSpinner fullPage />;
  }

  if (!user) {
    return <Navigate to={redirectTo} replace />;
  }

  if (requiredRole) {
    const role = (user.role || '').toLowerCase();
    const allowed = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
    if (!allowed.includes(role)) {
      return <Navigate to="/" replace />;
    }
  }

  return children;
};

export default ProtectedRoute;

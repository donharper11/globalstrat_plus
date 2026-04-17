import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../AuthContext';

const InstructorRoute = () => {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  const role = (user.role || '').toLowerCase();
  if (role !== 'instructor' && role !== 'admin') {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
};

export default InstructorRoute;

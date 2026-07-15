import client from './client';

// ---- Round lifecycle control ----
export const getRoundControl = (gameId) =>
  client.get(`/games/${gameId}/round-control/`);

export const closeRound = (gameId) =>
  client.post(`/games/${gameId}/round-control/close/`);

export const reopenRound = (gameId, deadline) =>
  client.post(`/games/${gameId}/round-control/reopen/`, { deadline });

export const processRound = (gameId, force = false) =>
  client.post(`/games/${gameId}/round-control/process/`, { force });

export const advanceToNextRound = (gameId, force = false) =>
  client.post(`/games/${gameId}/round-control/advance/`, { force });

export const setRoundDeadline = (gameId, payload) =>
  client.post(`/games/${gameId}/round-control/deadline/`, payload);

// ---- Student accounts / passwords ----
export const getStudentAccounts = (params) =>
  client.get('/instructor/student-accounts/', { params });

export const setStudentPassword = (userId, payload) =>
  client.post(`/instructor/student-accounts/${userId}/password/`, payload);

export const bulkResetPasswords = (payload) =>
  client.post('/instructor/student-accounts/bulk-reset/', payload);

// ---- Sessions ----
export const getActiveSessions = (params) =>
  client.get('/instructor/active-sessions/', { params });

export const logout = (sessionId) =>
  client.post('/auth/logout/', { session_id: sessionId });

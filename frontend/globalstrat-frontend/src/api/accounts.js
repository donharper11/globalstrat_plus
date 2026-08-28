import client from './client';

// ---- Round lifecycle control ----
// Every mutating call carries what the console was showing. The API compares
// it under its lock and answers 409 `state_moved` if the round changed since,
// so an operator who clicks on a stale screen is told what happened instead of
// getting a message about a state they never saw.
const seen = (round) => (round
  ? { expected_round_number: round.round_number, expected_status: round.status }
  : {});

export const getRoundControl = (gameId) =>
  client.get(`/games/${gameId}/round-control/`);

export const closeRound = (gameId, round) =>
  client.post(`/games/${gameId}/round-control/close/`, seen(round));

export const reopenRound = (gameId, deadline, round) =>
  client.post(`/games/${gameId}/round-control/reopen/`,
    { deadline, ...seen(round) });

export const processRound = (gameId, force = false, round, reason) =>
  client.post(`/games/${gameId}/round-control/process/`,
    { force, ...(reason ? { reason } : {}), ...seen(round) });

export const advanceToNextRound = (gameId, force = false, round, reason) =>
  client.post(`/games/${gameId}/round-control/advance/`,
    { force, ...(reason ? { reason } : {}), ...seen(round) });

export const setRoundDeadline = (gameId, payload, round) =>
  client.post(`/games/${gameId}/round-control/deadline/`,
    { ...payload, ...seen(round) });

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

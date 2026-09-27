import client from './client';

// ---- Student endpoints ----

export const getStudentReasoning = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/rounds/${roundNumber}/reasoning/`);

export const getStudentReasoningHistory = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/reasoning/history/`);

// ---- Instructor / Judge endpoints ----

export const getInstructorReasoningAllTeams = (gameId, params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return client.get(`/instructor/games/${gameId}/reasoning/${qs ? '?' + qs : ''}`);
};

export const getInstructorReasoningTeam = (gameId, teamId) =>
  client.get(`/instructor/games/${gameId}/teams/${teamId}/reasoning/`);

export const getInstructorReasoningComparison = (gameId, params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return client.get(`/instructor/games/${gameId}/reasoning/comparison/${qs ? '?' + qs : ''}`);
};

export const getInstructorReasoningAggregate = (gameId) =>
  client.get(`/instructor/games/${gameId}/reasoning/aggregate/`);

export const exportReasoningCsv = (gameId) =>
  client.get(`/instructor/games/${gameId}/reasoning/export/`, {
    responseType: 'blob',
  });

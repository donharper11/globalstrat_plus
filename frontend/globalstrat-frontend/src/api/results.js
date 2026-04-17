import client from './client';

export const getRoundResults = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/results/round/${roundNumber}/`);

export const getCompetitorIntel = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/competitors/round/${roundNumber}/`);

export const getLeaderboard = (gameId, roundNumber) =>
  client.get(`/games/${gameId}/leaderboard/round/${roundNumber}/`);

export const getLeaderboardHistory = (gameId) =>
  client.get(`/games/${gameId}/leaderboard/history/`);

export const getBalancedScorecard = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/dashboard/scorecard/`);

export const getInvestorRelations = (gameId, teamId, params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return client.get(`/games/${gameId}/teams/${teamId}/investor-relations/${qs ? '?' + qs : ''}`);
};

export const getLatestBriefing = (gameId, teamId, userId) =>
  client.get(`/games/${gameId}/teams/${teamId}/briefing/latest/${userId ? '?user_id=' + userId : ''}`);

export const getRoundBriefing = (gameId, teamId, roundNumber, userId) =>
  client.get(`/games/${gameId}/teams/${teamId}/briefing/round/${roundNumber}/${userId ? '?user_id=' + userId : ''}`);

export const markBriefingRead = (gameId, teamId, briefingId, userId) =>
  client.post(`/games/${gameId}/teams/${teamId}/briefing/${briefingId}/read/`, { user_id: userId });

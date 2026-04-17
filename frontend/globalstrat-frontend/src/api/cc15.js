import client from './client';

// Industry News
export const getIndustryNews = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/news/round/${roundNumber}/`);

// Research Queries
export const getResearchQueries = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/research/queries/`, {
    params: roundNumber ? { round_number: roundNumber } : {},
  });

export const submitResearchQuery = (gameId, teamId, query) =>
  client.post(`/games/${gameId}/teams/${teamId}/research/query/`, { query });

// Strategy Tools
export const getFrameworkAnalyses = (gameId, teamId, params = {}) =>
  client.get(`/games/${gameId}/teams/${teamId}/tools/analysis/`, { params });

export const saveFrameworkAnalysis = (gameId, teamId, data) =>
  client.post(`/games/${gameId}/teams/${teamId}/tools/analysis/`, data);

export const getFrameworkHistory = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/tools/analysis/history/`);

export const getEntryMatrixData = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/tools/entry-matrix-data/`);

// Financial Reports
export const getFinancialHistory = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/financial-reports/history/`);

// Forecast
export const getForecast = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/forecast/`);

export const getForecastScenarios = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/forecast/scenarios/`, {
    params: roundNumber ? { round_number: roundNumber } : {},
  });

export const saveForecastScenario = (gameId, teamId, data) =>
  client.post(`/games/${gameId}/teams/${teamId}/forecast/scenarios/`, data);

// News Ticker
export const getTickerItems = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/ticker/`);

// Round Processing Status (CC-32H)
export const getRoundStatus = (gameId) =>
  client.get(`/games/${gameId}/round-status/`);

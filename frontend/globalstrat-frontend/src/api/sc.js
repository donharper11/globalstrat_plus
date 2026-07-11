import client from './client';

// CC-8/CC-9/CC-10: Supply-chain scenario content + decisions.

// Scenario-content (read-only): supplier roster for the active scenario.
export const getSuppliers = (scenarioId, specialization) =>
  client.get(`/scenarios/${scenarioId}/suppliers/`, {
    params: specialization ? { specialization } : {},
  });

// Sourcing decision GET/POST for the active team/round.
export const getSourcing = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/sourcing/`);

export const saveSourcing = (gameId, teamId, roundNumber, data) =>
  client.post(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/sourcing/`, data);

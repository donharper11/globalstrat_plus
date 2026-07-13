import client from './client';

// CC-8/CC-9/CC-10/CC-12/CC-13/CC-14: Supply-chain scenario content + decisions.

// ---- Scenario content (read-only) ----
export const getSuppliers = (scenarioId, specialization) =>
  client.get(`/scenarios/${scenarioId}/suppliers/`, {
    params: specialization ? { specialization } : {},
  });

export const getLanes = (scenarioId) =>
  client.get(`/scenarios/${scenarioId}/lanes/`);

export const getInstruments = (scenarioId) =>
  client.get(`/scenarios/${scenarioId}/trade-finance-instruments/`);

export const getMarkets = (scenarioId) =>
  client.get(`/scenarios/${scenarioId}/markets/`);

export const getSegments = (scenarioId, segmentType) =>
  client.get(`/scenarios/${scenarioId}/segments/`, {
    params: segmentType ? { segment_type: segmentType } : {},
  });

export const getComplianceRegimes = (scenarioId) =>
  client.get(`/scenarios/${scenarioId}/compliance-regimes/`);

// ---- SC engine state (read-only, CC-15 dashboard) ----
export const getResilienceScore = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/resilience-score/`);
export const getSCEvents = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/sc-events/`);
export const getHedgePositions = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/sc/hedge-positions/`);

// ---- Sourcing (CC-10) ----
export const getSourcing = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/sourcing/`);
export const saveSourcing = (gameId, teamId, roundNumber, data) =>
  client.post(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/sourcing/`, data);

// ---- Logistics (CC-12) ----
export const getLogistics = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/logistics/`);
export const saveLogistics = (gameId, teamId, roundNumber, data) =>
  client.post(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/logistics/`, data);

// ---- Trade finance & FX (CC-13) ----
export const getTradeFinance = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/trade-finance/`);
export const saveTradeFinance = (gameId, teamId, roundNumber, data) =>
  client.post(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/trade-finance/`, data);

// ---- Inventory & resilience (CC-14) ----
export const getInventory = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/inventory/`);
export const saveInventory = (gameId, teamId, roundNumber, data) =>
  client.post(`/games/${gameId}/teams/${teamId}/sc/round/${roundNumber}/inventory/`, data);

// ---- Instructor SC panel (CC-16) ----
export const getInstructorSCPanel = (gameId, round) =>
  client.get(`/games/${gameId}/instructor/sc-panel/`, { params: round ? { round } : {} });
export const getInstructorSCEventCatalog = (gameId) =>
  client.get(`/games/${gameId}/instructor/sc-event-catalog/`);
export const injectSCEvent = (gameId, eventTemplateId) =>
  client.post(`/games/${gameId}/instructor/inject-sc-event/`, { event_template_id: eventTemplateId });
export const getResilienceWeightOverrides = (gameId) =>
  client.get(`/games/${gameId}/resilience-weight-overrides/`);
export const saveResilienceWeightOverride = (gameId, data) =>
  client.post(`/games/${gameId}/resilience-weight-overrides/`, data);

import client from './client';

// Decision CRUD
export const getDecisions = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/decisions/round/${roundNumber}/`);

export const saveDecisions = (gameId, teamId, roundNumber, data) =>
  client.post(`/games/${gameId}/teams/${teamId}/decisions/round/${roundNumber}/`, data);

export const patchDecision = (gameId, teamId, roundNumber, decisionType, data) =>
  client.patch(`/games/${gameId}/teams/${teamId}/decisions/round/${roundNumber}/${decisionType}/`, data);

export const lockDecisions = (gameId, teamId, roundNumber) =>
  client.post(`/games/${gameId}/teams/${teamId}/decisions/round/${roundNumber}/lock/`);

export const getDecisionSummary = (gameId, teamId, roundNumber) =>
  client.get(`/games/${gameId}/teams/${teamId}/decisions/round/${roundNumber}/summary/`);

// Context endpoints
export const getRDContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/rd/`);

export const getProductContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/products/`);

export const getMarketingContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/marketing/`);

export const getStrategyContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/strategy/`);

export const getFinanceContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/finance/`);

export const getTalentContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/talent/`);

// CC-31: Talent allocation & localization context
export const getTalentAllocationContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/talent-allocation/`);

export const getComplianceContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/compliance/`);

export const getMarketLocalization = (gameId, teamId, marketCode) =>
  client.get(`/games/${gameId}/teams/${teamId}/markets/${marketCode}/localization/`);

// CC-31J: Governance commitments
export const getGovernanceContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/governance/`);

export const getTaxStructureContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/tax-structure/`);

export const setTaxStructure = (gameId, teamId, structureCode) =>
  client.post(`/games/${gameId}/teams/${teamId}/context/tax-structure/`, { structure_code: structureCode });

// CC-32D: AI Alliance Partners
export const getAllianceState = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/alliances/`);

// CC-32F: AI Government Relations
export const getGovernmentRelations = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/government-relations/`);

// CC-32A: Stakeholder Communications
export const getCommunicationAssignments = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/communications/assignments/`);

export const saveCommunicationDraft = (gameId, teamId, assignmentId, content) =>
  client.post(`/games/${gameId}/teams/${teamId}/communications/${assignmentId}/draft/`, { content });

export const submitCommunication = (gameId, teamId, assignmentId, content) =>
  client.post(`/games/${gameId}/teams/${teamId}/communications/${assignmentId}/submit/`, { content });

export const getCommunicationHistory = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/communications/history/`);

// CC-19: Research reports
// Team change notifications
export const getTeamChanges = (gameId, teamId, params = {}) =>
  client.get(`/games/${gameId}/teams/${teamId}/changes/`, { params });

export const getResearchReport = (gameId, teamId, reportType, params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return client.get(`/games/${gameId}/teams/${teamId}/research/reports/${reportType}/${qs ? '?' + qs : ''}`);
};

// CC-32B: Organizational structure
export const getOrgStructureContext = (gameId, teamId) =>
  client.get(`/games/${gameId}/teams/${teamId}/context/org-structure/`);

export const switchOrgStructure = (gameId, teamId, structureId) =>
  client.post(`/games/${gameId}/teams/${teamId}/context/org-structure/`, { structure_id: structureId });

import client from './client';

export const login = (username, password) =>
  client.post('/auth/login/', { username, password });

export const getCurrentUser = (userId, sectionId) =>
  client.get('/auth/me/', { params: { user_id: userId, section_id: sectionId } });

export const getTeams = () => client.get('/teams/');
export const getTeam = (id) => client.get(`/teams/${id}/`);
export const getRounds = (gameId) => client.get('/rounds/', { params: { game_id: gameId } });

// Onboarding
export const getOnboardingData = (gameId, teamId) =>
  client.get('/onboarding/', { params: { game_id: gameId, team_id: teamId } });
export const completeOnboarding = (userId, sectionId) =>
  client.post('/onboarding/complete/', { user_id: userId, section_id: sectionId });

import client from './client';

export const getInstructorDashboard = (gameId) =>
  client.get(`/games/${gameId}/instructor/dashboard/`);

export const advanceRound = (gameId, force = false) =>
  client.post(`/games/${gameId}/instructor/advance-round/`, { force });

export const injectEvent = (gameId, eventTemplateId, targetMarketId) =>
  client.post(`/games/${gameId}/instructor/inject-event/`, {
    event_template_id: eventTemplateId,
    target_market_id: targetMarketId,
  });

export const extendDeadline = (gameId, data) =>
  client.post(`/games/${gameId}/instructor/extend-deadline/`, data);

export const getResearchQueries = (gameId) =>
  client.get(`/games/${gameId}/instructor/research-queries/`);

export const getInstructorAlerts = (gameId, params = {}) =>
  client.get(`/games/${gameId}/instructor/alerts/`, { params });

export const acknowledgeAlert = (gameId, alertId) =>
  client.post(`/games/${gameId}/instructor/alerts/${alertId}/acknowledge/`);

export const getAlertSummary = (gameId, params = {}) =>
  client.get(`/games/${gameId}/instructor/alerts/summary/`, { params });

// Event templates and markets for injection dropdown
export const getEventTemplates = (gameId) =>
  client.get(`/games/${gameId}/instructor/event-templates/`);

// Team briefings
export const getTeamBriefings = (gameId) =>
  client.get(`/games/${gameId}/instructor/briefings/`);

// Team decisions drill-down
export const getTeamDecisions = (gameId, teamId, round) =>
  client.get(`/games/${gameId}/instructor/teams/${teamId}/decisions/`, { params: round != null ? { round } : {} });

// Course management
export const getCourses = (instructorId) =>
  client.get('/courses/', { params: instructorId ? { instructor_id: instructorId } : {} });
export const createCourse = (data) => client.post('/courses/', data);
export const updateCourse = (id, data) => client.put(`/courses/${id}/`, data);
export const deleteCourse = (id) => client.delete(`/courses/${id}/`);

// Section management
export const getSections = (courseId) =>
  client.get('/sections/', { params: courseId ? { course_id: courseId } : {} });
export const createSection = (data) => client.post('/sections/', data);
export const updateSection = (id, data) => client.put(`/sections/${id}/`, data);
export const deleteSection = (id) => client.delete(`/sections/${id}/`);

// Roster management
export const getRoster = (sectionId) =>
  client.get('/roster/', { params: { section_id: sectionId } });
export const uploadRoster = (sectionId, csvText) =>
  client.post('/roster/', { action: 'upload', section_id: sectionId, csv: csvText });
export const addStudent = (sectionId, data) =>
  client.post('/roster/', { action: 'add', section_id: sectionId, ...data });
export const removeEnrollment = (enrollmentId) =>
  client.delete('/roster/', { params: { enrollment_id: enrollmentId } });

// Team management
export const getTeamManagement = (sectionId) =>
  client.get('/team-management/', { params: { section_id: sectionId } });
export const generateTeams = (sectionId, method = 'random') =>
  client.post('/team-management/', { section_id: sectionId, method });
export const assignStudents = (assignments) =>
  client.put('/team-management/', { action: 'assign', assignments });
export const renameTeam = (teamId, name) =>
  client.put('/team-management/', { action: 'rename', team_id: teamId, team_name: name });

// CC-31: Team configuration — home market assignment
export const getTeamConfig = (gameId) =>
  client.get(`/games/${gameId}/instructor/team-config/`);
export const updateTeamConfig = (gameId, data) =>
  client.put(`/games/${gameId}/instructor/team-config/`, data);
export const randomizeHomeMarkets = (gameId) =>
  client.post(`/games/${gameId}/instructor/randomize-home-markets/`);

// Simulation control
export const controlSimulation = (instanceId, action, extra = {}) =>
  client.post('/simulation-control/', { instance_id: instanceId, action, ...extra });

// Grading
export const seedRubric = (courseId) =>
  client.post('/grades/seed-rubric/', { course_id: courseId });
export const calculateGrades = (instanceId, courseId) =>
  client.post('/grades/calculate/', { instance_id: instanceId, course_id: courseId });
export const getGradingCategories = (rubricId) =>
  client.get('/grading-categories/', { params: rubricId ? { rubric_id: rubricId } : {} });
export const updateGradingCategory = (id, data) =>
  client.patch(`/grading-categories/${id}/`, data);
export const createGradingCategory = (data) =>
  client.post('/grading-categories/', data);
export const deleteGradingCategory = (id) =>
  client.delete(`/grading-categories/${id}/`);
export const getGradingRubrics = (courseId) =>
  client.get('/grading-rubrics/', { params: courseId ? { course_id: courseId } : {} });
export const getComponentLabels = () =>
  client.get('/grades/component-labels/');
export const getTeamGrades = (teamId) =>
  client.get('/team-grades/', { params: teamId ? { team_id: teamId } : {} });
export const overrideGrade = (instanceId, teamId, categoryId, score, comments) =>
  client.post('/grades/override/', { instance_id: instanceId, team_id: teamId, category_id: categoryId, override_score: score, comments });
export const exportTeamGradesCsv = (instanceId) =>
  client.get('/grades/export/teams/', { params: { instance_id: instanceId }, responseType: 'blob' });
export const exportStudentGradesCsv = (instanceId) =>
  client.get('/grades/export/students/', { params: { instance_id: instanceId }, responseType: 'blob' });

// Scenario listing & game creation
export const getScenarios = () => client.get('/scenarios/');
export const getGames = (params = {}) => client.get('/games/', { params });
export const getGameTeams = (gameId) => client.get(`/games/${gameId}/teams/`);
export const createGame = (data) => client.post('/games/create/', data);

export const getScenarioDetail = (scenarioId) =>
  client.get(`/scenarios/${scenarioId}/`);

// Round schedule (game-based)
export const getRoundSchedule = (gameId) =>
  client.get(`/games/${gameId}/round-schedule/`);
export const updateRoundSchedule = (gameId, rounds) =>
  client.post(`/games/${gameId}/round-schedule/`, { rounds });

// Game lifecycle
export const activateGame = (gameId) =>
  client.post(`/games/${gameId}/activate/`);
export const pauseGame = (gameId) =>
  client.post(`/games/${gameId}/pause/`);
export const resumeGame = (gameId) =>
  client.post(`/games/${gameId}/resume/`);
export const resetGame = (gameId) =>
  client.post(`/games/${gameId}/reset/`);
export const archiveGame = (gameId) =>
  client.post(`/games/${gameId}/archive/`);
export const deleteGame = (gameId) =>
  client.delete(`/games/${gameId}/delete/`);

// Edit enrollment (update student details)
export const updateEnrollment = (enrollmentId, data) =>
  client.put('/roster/', { action: 'update', enrollment_id: enrollmentId, ...data });

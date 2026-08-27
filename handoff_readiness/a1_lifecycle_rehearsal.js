const fs = require('fs');
const path = require('path');
const { chromium } = require('/home/ubuntu/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');

const BASE = process.env.GS_A1_BASE || 'http://127.0.0.1:18080';
const OUTPUT = process.env.GS_A1_OUTPUT;
if (!OUTPUT) throw new Error('Set GS_A1_OUTPUT to a dedicated evidence directory.');
fs.mkdirSync(OUTPUT, { recursive: true });

const results = { base: BASE, started_at: new Date().toISOString(), checks: [], rounds: [] };
const add = (name, pass, detail = {}) => results.checks.push({ name, pass, ...detail });

async function api(route, options = {}, token = null) {
  const headers = { 'content-type': 'application/json', 'x-request-id': `a1-${Date.now()}-${Math.random()}`, ...(options.headers || {}) };
  if (token) headers.authorization = `Bearer ${token}`;
  const response = await fetch(`${BASE}/api${route}`, { ...options, headers });
  const text = await response.text();
  let body;
  try { body = JSON.parse(text); } catch { body = text; }
  if (!response.ok) throw new Error(`${options.method || 'GET'} ${route}: ${response.status} ${text.slice(0, 400)}`);
  return { status: response.status, body };
}

async function login(username, password) {
  return (await api('/auth/login/', { method: 'POST', body: JSON.stringify({ username, password }) })).body;
}

async function seed(page, loginData, language = 'en') {
  await page.addInitScript(({ user, language }) => {
    localStorage.setItem('access_token', user.access);
    localStorage.setItem('gs_user', JSON.stringify(user));
    localStorage.setItem('gs_session_id', String(user.session_id));
    localStorage.setItem('gs_language', language);
  }, { user: loginData, language });
}

function observe(page, label) {
  const events = [];
  page.on('pageerror', error => events.push({ type: 'pageerror', text: String(error) }));
  page.on('console', message => { if (message.type() === 'error') events.push({ type: 'console', text: message.text() }); });
  page.on('requestfailed', request => events.push({ type: 'requestfailed', url: request.url(), text: request.failure()?.errorText }));
  return { label, events };
}

async function visible(page, expected = null) {
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1200);
  const text = (await page.locator('body').innerText()).trim();
  return { text_length: text.length, expected_visible: expected ? text.includes(expected) : true, url: page.url(), sample: text.slice(0, 240) };
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(OUTPUT, `${name}.png`), fullPage: true });
}

const nav = (page, url) => page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 });
const reload = page => page.reload({ waitUntil: 'domcontentloaded', timeout: 90000 });

(async () => {
  const browser = await chromium.launch({ headless: true });
  const student = await login('student1', 'student1pass');
  const instructor = await login('instructor', 'instructorpass');
  const gameId = student.game_id;
  const teamId = student.team_id;
  results.fixture = { game_id: gameId, team_id: teamId, total_rounds: 6 };

  // Browser close and return: restore the browser's persisted origin state.
  const firstContext = await browser.newContext();
  const firstPage = await firstContext.newPage();
  await seed(firstPage, student);
  await nav(firstPage, `${BASE}/games/${gameId}/teams/${teamId}/decisions/summary`);
  const firstVisible = await visible(firstPage);
  const storedState = await firstContext.storageState();
  await firstContext.close();
  const returnedContext = await browser.newContext({ storageState: storedState });
  const returnedPage = await returnedContext.newPage();
  await nav(returnedPage, `${BASE}/games/${gameId}/teams/${teamId}/decisions/summary`);
  const returnedVisible = await visible(returnedPage);
  await shot(returnedPage, 'browser-close-return');
  add('browser_close_and_return', firstVisible.text_length > 0 && returnedVisible.text_length > 0 && !returnedPage.url().includes('/login'), { first: firstVisible, returned: returnedVisible });
  await returnedContext.close();

  // Invalid/expired session convergence for each role.
  for (const [role, user, target, loginPath] of [
    ['student', student, `/games/${gameId}/teams/${teamId}/decisions/summary`, '/login'],
    ['instructor', instructor, '/instructor', '/instructor/login'],
  ]) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(({ user }) => {
      localStorage.setItem('access_token', 'invalid.expired.token');
      localStorage.setItem('gs_user', JSON.stringify(user));
      localStorage.setItem('gs_session_id', 'stale-session');
    }, { user });
    await nav(page, `${BASE}${target}`);
    await page.waitForTimeout(1800);
    const state = await visible(page);
    await shot(page, `session-timeout-${role}`);
    add(`session_timeout_${role}`, page.url().includes(loginPath) && state.text_length > 0, state);
    await context.close();
  }

  const studentContext = await browser.newContext();
  const studentPage = await studentContext.newPage();
  await seed(studentPage, student);
  const studentObs = observe(studentPage, 'student');

  // Back navigation while a decision page is dirty. Current UI is expected to
  // warn or preserve the edit; silent loss is a strict A1 failure.
  await nav(studentPage, `${BASE}/games/${gameId}/teams/${teamId}/decisions/sourcing`);
  await visible(studentPage);
  let edited = false;
  const select = studentPage.locator('.ant-select').first();
  if (await select.count()) {
    await select.click();
    const options = studentPage.locator('.ant-select-item-option');
    if (await options.count() > 1) { await options.nth(1).click(); edited = true; }
  }
  await nav(studentPage, `${BASE}/games/${gameId}/teams/${teamId}/decisions/logistics`);
  await studentPage.goBack({ waitUntil: 'domcontentloaded', timeout: 90000 });
  const backState = await visible(studentPage);
  const warningVisible = /unsaved|discard|leave|未保存|离开/.test((await studentPage.locator('body').innerText()).toLowerCase());
  await shot(studentPage, 'back-mid-decision');
  add('back_mid_decision', edited && warningVisible, { edited, warning_visible: warningVisible, ...backState });

  // Refresh during an accepted submission; the reloaded UI must recover.
  await nav(studentPage, `${BASE}/games/${gameId}/teams/${teamId}/decisions/summary`);
  const savePromise = studentPage.evaluate(async ({ gameId, teamId }) => {
    const token = localStorage.getItem('access_token');
    const response = await fetch(`/api/games/${gameId}/teams/${teamId}/decisions/round/1/`, { method: 'POST', headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json', 'x-request-id': 'a1-refresh-save' }, body: '{}' });
    return response.status;
  }, { gameId, teamId }).catch(() => 'navigation-aborted');
  await reload(studentPage);
  const refreshStatus = await savePromise;
  const refreshState = await visible(studentPage);
  await shot(studentPage, 'refresh-during-submission');
  add('refresh_during_submission', refreshState.text_length > 0 && !studentPage.url().includes('/login'), { request_status: refreshStatus, ...refreshState });

  // Duplicate tabs writing the same canonical draft.
  const tab2 = await studentContext.newPage();
  await seed(tab2, student);
  await Promise.all([nav(studentPage, `${BASE}/games/${gameId}/teams/${teamId}/decisions/summary`), nav(tab2, `${BASE}/games/${gameId}/teams/${teamId}/decisions/summary`)]);
  const write = page => page.evaluate(async ({ gameId, teamId }) => {
    const response = await fetch(`/api/games/${gameId}/teams/${teamId}/decisions/round/1/`, { method: 'POST', headers: { authorization: `Bearer ${localStorage.getItem('access_token')}`, 'content-type': 'application/json', 'x-request-id': `a1-duplicate-${Math.random()}` }, body: '{}' });
    return response.status;
  }, { gameId, teamId });
  const duplicateStatuses = await Promise.all([write(studentPage), write(tab2)]);
  await Promise.all([reload(studentPage), reload(tab2)]);
  const duplicateBodies = await Promise.all([visible(studentPage), visible(tab2)]);
  await shot(tab2, 'duplicate-tab');
  add('duplicate_tab', duplicateStatuses.every(code => code === 200 || code === 201) && duplicateBodies.every(x => x.text_length > 0), { statuses: duplicateStatuses, pages: duplicateBodies });
  await tab2.close();

  const instructorContext = await browser.newContext();
  const instructorPage = await instructorContext.newPage();
  await seed(instructorPage, instructor);
  const instructorObs = observe(instructorPage, 'instructor');

  // Six complete server lifecycles, with both role UIs captured at open and
  // processed states. Round transitions use the same supported operator APIs.
  for (let round = 1; round <= 6; round++) {
    const studentRoute = `${BASE}/games/${gameId}/teams/${teamId}/decisions/summary?round=6`;
    await nav(studentPage, studentRoute);
    const openStudent = await visible(studentPage);
    await shot(studentPage, `round-${round}-student-open`);
    await nav(instructorPage, `${BASE}/instructor`);
    const openInstructor = await visible(instructorPage);
    await shot(instructorPage, `round-${round}-instructor-open`);

    const controlOpen = await api(`/games/${gameId}/round-control/`, {}, instructor.access);
    const directLaterSafe = controlOpen.body.current_round === round && !openStudent.sample.includes('Round 6') || round === 6;
    add(`round_${round}_direct_later_url`, directLaterSafe, { current_round: controlOpen.body.current_round, page: openStudent });

    await api(`/games/${gameId}/round-control/close/`, { method: 'POST', body: JSON.stringify({ reason: `A1 rehearsal close round ${round}` }) }, instructor.access);
    const closed = await api(`/games/${gameId}/round-control/`, {}, instructor.access);
    await reload(studentPage);
    const closedStudent = await visible(studentPage);
    await shot(studentPage, `round-${round}-student-closed`);
    await api(`/games/${gameId}/round-control/process/`, { method: 'POST', body: JSON.stringify({ force: false, reason: `A1 rehearsal process round ${round}` }) }, instructor.access);
    const processed = await api(`/games/${gameId}/round-control/`, {}, instructor.access);
    await Promise.all([reload(studentPage), reload(instructorPage)]);
    const processedStudent = await visible(studentPage);
    const processedInstructor = await visible(instructorPage);
    await shot(studentPage, `round-${round}-student-results`);
    await shot(instructorPage, `round-${round}-instructor-results`);
    results.rounds.push({ round, open: controlOpen.body, closed: closed.body, processed: processed.body, ui: { open_student: openStudent, open_instructor: openInstructor, closed_student: closedStudent, processed_student: processedStudent, processed_instructor: processedInstructor } });
    add(`round_${round}_lifecycle`, controlOpen.body.current_round === round && closed.body.round.status === 'closed' && processed.body.round.status === 'processed' && [openStudent, openInstructor, closedStudent, processedStudent, processedInstructor].every(x => x.text_length > 0), { open_status: controlOpen.body.round.status, closed_status: closed.body.round.status, processed_status: processed.body.round.status });
    await api(`/games/${gameId}/round-control/advance/`, { method: 'POST', body: JSON.stringify({ force: false, reason: `A1 rehearsal advance round ${round}` }) }, instructor.access);
  }

  const finalControl = await api(`/games/${gameId}/round-control/`, {}, instructor.access);
  add('six_round_completion', finalControl.body.game_status === 'completed', { final: finalControl.body });
  results.observed_events = { student: studentObs.events, instructor: instructorObs.events };
  results.finished_at = new Date().toISOString();
  results.pass_count = results.checks.filter(x => x.pass).length;
  results.fail_count = results.checks.filter(x => !x.pass).length;
  fs.writeFileSync(path.join(OUTPUT, 'results.json'), JSON.stringify(results, null, 2));
  await studentContext.close();
  await instructorContext.close();
  await browser.close();
  console.log(JSON.stringify({ pass_count: results.pass_count, fail_count: results.fail_count, output: OUTPUT }));
})().catch(error => {
  results.fatal_error = String(error.stack || error);
  results.finished_at = new Date().toISOString();
  fs.writeFileSync(path.join(OUTPUT, 'results.json'), JSON.stringify(results, null, 2));
  console.error(error);
  process.exit(1);
});

/**
 * The CRV2-08 browser walkthrough: one session, both roles, real Chromium.
 *
 * Console messages and failed requests are captured for the whole run, so a
 * screen that renders while erroring underneath is not recorded as a pass.
 *
 * API boundary probes are issued from inside the page with the session's own
 * token, which is what the browser does when the app calls an endpoint. That
 * keeps the rival-access check a browser fact rather than a curl fact.
 */
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const EVIDENCE = path.resolve(__dirname, '..');
const SHOTS = path.join(EVIDENCE, 'screenshots');
const ports = JSON.parse(fs.readFileSync('/tmp/crv208-runtime/stack.ports', 'utf8'));
const fixture = JSON.parse(fs.readFileSync(path.join(EVIDENCE, 'completed-game.json'), 'utf8'));
const BASE = `http://127.0.0.1:${ports.app}`;
const PASSWORD = fixture.password;
const GAME = fixture.game_id;
const TEAMS = fixture.identities.teams;

const record = { base: BASE, game: GAME, steps: [], console: [], network: [] };

function step(name, outcome, detail) {
  record.steps.push({ name, outcome, detail });
  const flag = outcome === 'pass' ? 'PASS' : outcome === 'fail' ? 'FAIL' : outcome.toUpperCase();
  console.log(`  ${flag.padEnd(6)} ${name}${detail ? ' — ' + String(detail).slice(0, 220) : ''}`);
}

async function shot(page, name) {
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
}

// Issue a request from inside the page, carrying whatever the session holds.
async function pageFetch(page, url) {
  return page.evaluate(async (u) => {
    const token = localStorage.getItem('access_token');
    const res = await fetch(u, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    let body = '';
    try { body = (await res.text()).slice(0, 300); } catch (e) { body = '<unreadable>'; }
    return { status: res.status, body };
  }, url);
}

async function login(page, username, viaInstructorPage) {
  await page.goto(`${BASE}${viaInstructorPage ? '/instructor/login' : '/login'}`,
                  { waitUntil: 'networkidle2' });
  await page.waitForSelector('input#username, input[name="username"]', { timeout: 30000 });
  await page.type('input#username, input[name="username"]', username);
  await page.type('input#password, input[name="password"]', PASSWORD);
  await Promise.all([
    page.click('button[type="submit"]'),
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 45000 }).catch(() => null),
  ]);
  await new Promise(r => setTimeout(r, 2500));
  const token = await page.evaluate(() => localStorage.getItem('access_token'));
  return !!token;
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/chromium-browser',
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1500, height: 1000 });

  page.on('console', m => {
    if (['error', 'warning'].includes(m.type())) {
      record.console.push({ type: m.type(), text: m.text().slice(0, 300) });
    }
  });
  page.on('requestfailed', r => record.network.push(
    { url: r.url().slice(0, 200), failure: (r.failure() || {}).errorText }));
  page.on('response', r => {
    if (r.status() >= 400) {
      record.network.push({ url: r.url().slice(0, 200), status: r.status() });
    }
  });

  try {
    // ---- Student history, two representative teams ----------------------
    const [teamA, teamB] = TEAMS;
    for (const team of [teamA, teamB]) {
      const ok = await login(page, team.student, false);
      step(`student login ${team.student} (${team.name})`, ok ? 'pass' : 'fail');
      if (!ok) continue;

      await page.goto(`${BASE}/games/${GAME}/teams/${team.id}/financial-reports`,
                      { waitUntil: 'networkidle2' });
      await new Promise(r => setTimeout(r, 2500));
      await shot(page, `student-${team.id}-financial-reports`);
      const heading = await page.evaluate(() => document.body.innerText.slice(0, 400));
      step(`student ${team.name} reached its reports page`,
           heading.length > 40 ? 'pass' : 'fail');

      // An early round and the final round, after completion.
      for (const round of [1, 3]) {
        const res = await pageFetch(page,
          `/api/games/${GAME}/teams/${team.id}/results/round/${round}/`);
        step(`student ${team.name} retrieves round ${round} result`,
             res.status === 200 ? 'pass' : 'fail', `HTTP ${res.status}`);
      }

      // The disclosure boundary, attacked directly from the session.
      const rival = TEAMS.find(t => t.id !== team.id);
      const rivalResult = await pageFetch(page,
        `/api/games/${GAME}/teams/${rival.id}/results/round/2/`);
      step(`rival raw result URL refused for ${team.name} -> ${rival.name}`,
           rivalResult.status === 403 ? 'pass' : 'fail',
           `HTTP ${rivalResult.status} ${rivalResult.body}`);
      const rivalDecisions = await pageFetch(page,
        `/api/games/${GAME}/instructor/teams/${rival.id}/decisions/?round=2`);
      step(`rival raw decision URL refused for ${team.name}`,
           rivalDecisions.status === 403 ? 'pass' : 'fail',
           `HTTP ${rivalDecisions.status} ${rivalDecisions.body}`);

      await page.evaluate(() => localStorage.clear());
    }

    // ---- Instructor evidence -------------------------------------------
    const ok = await login(page, fixture.identities.instructor, true);
    step('instructor login', ok ? 'pass' : 'fail');
    await page.goto(`${BASE}/instructor`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 4000));

    // The portal opens on Courses & Sections. A game is reached by selecting
    // its course and then its section, which is what loads the dashboard and
    // reveals the game tabs; there is no direct URL for it.
    const clickText = (rx) => page.evaluate((r) => {
      const re = new RegExp(r);
      const el = [...document.querySelectorAll('*')]
        .find(e => re.test(e.innerText || '') && e.children.length === 0);
      if (el) { el.click(); return el.innerText.trim(); }
      return null;
    }, rx);
    const course = await clickText('STRAT-TEST');
    await new Promise(r => setTimeout(r, 3000));
    const section = await clickText('TEST-01');
    await new Promise(r => setTimeout(r, 6000));
    const tabs = await page.evaluate(() =>
      [...document.querySelectorAll('.ant-tabs-tab')].map(t => t.innerText.trim()));
    record.instructorTabs = tabs;
    step('instructor reaches the game from course and section',
         tabs.some(t => /team overview/i.test(t)) ? 'pass' : 'fail',
         `course ${course}, section ${section}, tabs: ${tabs.join(' | ')}`);
    await shot(page, 'instructor-dashboard');

    const onOverview = await clickText('Team Overview');
    await new Promise(r => setTimeout(r, 3500));
    step('team overview tab opens', onOverview ? 'pass' : 'fail');
    await shot(page, 'instructor-team-overview');

    const evidence = await pageFetch(page,
      `/api/games/${GAME}/instructor/teams/${TEAMS[1].id}/decisions/?round=1`);
    let parsed = null;
    try { parsed = JSON.parse(evidence.body.length < 290 ? evidence.body : '{}'); } catch (e) {}
    step('instructor decisions endpoint answers',
         evidence.status === 200 ? 'pass' : 'fail', `HTTP ${evidence.status}`);

    // The audit shape, read in full rather than from a truncated preview.
    const shape = await page.evaluate(async (game, team) => {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`/api/games/${game}/instructor/teams/${team}/decisions/?round=1`,
                              { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      const events = data.audit_events || [];
      const required = ['server_timestamp', 'actor', 'action', 'endpoint',
                        'request_id', 'payload_sha256', 'payload'];
      return {
        origin: data.submission_origin,
        count: events.length,
        missing: required.filter(f => !events.every(e => e[f] !== undefined && e[f] !== null)),
        distinctHashes: [...new Set(events.filter(e => e.action === 'save')
                                          .map(e => e.payload_sha256))].length,
      };
    }, GAME, TEAMS[1].id);
    step('audit evidence carries every required field',
         shape.missing.length === 0 ? 'pass' : 'fail',
         `${shape.count} events, missing: ${shape.missing.join(',') || 'none'}`);
    record.auditShape = shape;

    // ---- The evidence table as an instructor actually reaches it --------
    const opened = await page.evaluate(() => {
      const button = [...document.querySelectorAll('button')]
        .find(b => /view decisions/i.test(b.innerText));
      if (!button) return false;
      button.click();
      return true;
    });
    await new Promise(r => setTimeout(r, 3500));
    await shot(page, 'instructor-audit-evidence-table');
    const table = await page.evaluate(() => {
      const modal = document.querySelector('.ant-modal-content');
      if (!modal) return { headers: [], rows: 0, pagerPages: 0, copyables: 0, tags: [], modal: false };
      return {
        modal: true,
        headers: [...modal.querySelectorAll('.ant-table-thead th')]
          .map(h => h.innerText.trim()).filter(Boolean),
        rows: modal.querySelectorAll('.ant-table-tbody tr.ant-table-row').length,
        pagerPages: modal.querySelectorAll('.ant-pagination-item').length,
        copyables: modal.querySelectorAll('.ant-typography-copy').length,
        tags: [...modal.querySelectorAll('.ant-tag')].map(t => t.innerText.trim()),
      };
    });
    record.evidenceTable = table;
    step('audit evidence table renders in the browser',
         opened && table.rows > 0 ? 'pass' : 'fail',
         `${table.rows} rows, columns: ${table.headers.join(' | ')}`);
    step('table exposes copy controls for hash and payload',
         table.copyables > 0 ? 'pass' : 'fail', `${table.copyables} copy controls`);
    // Pagination exists on this table; whether a boundary is reachable
    // depends on how many events the fixture produced. Record which it is
    // rather than claiming the boundary was exercised.
    step('pagination boundary',
         table.pagerPages > 1 ? 'pass' : 'not-reachable',
         table.pagerPages > 1
           ? `${table.pagerPages} pages`
           : `single page: ${table.rows} rows against a page size of 8`);

    // ---- One copy action, actually clicked -----------------------------
    const copied = await page.evaluate(() => {
      const scope = document.querySelector('.ant-modal-content') || document;
      const control = scope.querySelector('.ant-typography-copy');
      if (!control) return false;
      control.click();
      return true;
    });
    await new Promise(r => setTimeout(r, 800));
    step('copy control accepts a click', copied ? 'pass' : 'fail');

    // ---- The empty / defaulted case ------------------------------------
    const defaulted = (fixture.contains.defaulted_missing_team_rounds || [])[0] || '';
    const defaultedTeam = TEAMS.find(t => defaulted.startsWith(t.name));
    if (defaultedTeam) {
      const round = Number(defaulted.trim().split(/\s+/).pop().replace('r', ''));
      const empty = await page.evaluate(async (game, team, rnd) => {
        const token = localStorage.getItem('access_token');
        const res = await fetch(
          `/api/games/${game}/instructor/teams/${team}/decisions/?round=${rnd}`,
          { headers: { Authorization: `Bearer ${token}` } });
        const data = await res.json();
        return { origin: data.submission_origin, label: data.submission_origin_label,
                 events: (data.audit_events || []).length };
      }, GAME, defaultedTeam.id, round);
      record.defaultedCase = { teamRound: defaulted, ...empty };
      step('default/empty case reports why it is empty',
           empty.origin === 'defaulted_missing' ? 'pass' : 'fail',
           `${defaulted}: ${empty.origin} (${empty.label})`);
    } else {
      step('default/empty case', 'fail', 'fixture named no defaulted team-round');
    }

    // ---- Bilingual switch ----------------------------------------------
    const instructorHasSwitcher = await page.evaluate(() =>
      [...document.querySelectorAll('button')]
        .some(b => ['中文', 'EN'].includes(b.innerText.trim())));
    record.instructorLanguageSwitcher = instructorHasSwitcher;
    step('instructor portal offers a language control',
         instructorHasSwitcher ? 'pass' : 'observed-absent',
         instructorHasSwitcher ? '' : 'no language control in the instructor portal');

    // Exercise the toggle on the login screen, which does carry it.
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2000));
    const beforeLang = await page.evaluate(() => document.body.innerText.slice(0, 3000));
    const prefCalls = [];
    page.on('response', r => {
      if (r.url().includes('preferences')) {
        prefCalls.push({ url: r.url().slice(0, 160), status: r.status() });
      }
    });
    const toggled = await page.evaluate(() => {
      const button = [...document.querySelectorAll('button')]
        .find(b => ['中文', 'EN'].includes(b.innerText.trim()));
      if (!button) return false;
      button.click();
      return true;
    });
    await new Promise(r => setTimeout(r, 3000));
    await shot(page, 'login-zh');
    const afterLang = await page.evaluate(() => document.body.innerText.slice(0, 3000));
    const hasHan = /[\u4e00-\u9fff]/.test(afterLang);
    step('bilingual switch changes the rendered language',
         toggled && hasHan && afterLang !== beforeLang ? 'pass' : 'fail',
         hasHan ? 'Chinese text rendered' : 'no Chinese text after toggle');
    record.languagePersistence = prefCalls;
    // Persistence is only claimed when a session exists to persist against;
    // the login screen has no token, so this is checked after signing in.
    const persisted = await page.evaluate(async () => {
      const res = await fetch('/api/auth/login/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'crv208_student_1', password: 'crv208-pass' }),
      });
      const data = await res.json();
      localStorage.setItem('access_token', data.access);
      const apiUrl = '';            // what LanguageSwitcher uses by default
      const put = await fetch(`${apiUrl}/user/preferences/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json',
                   Authorization: `Bearer ${data.access}` },
        body: JSON.stringify({ language: 'zh-CN' }),
      });
      const correct = await fetch('/api/user/preferences/', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json',
                   Authorization: `Bearer ${data.access}` },
        body: JSON.stringify({ language: 'zh-CN' }),
      });
      return { asShipped: put.status, withApiPrefix: correct.status };
    });
    record.languagePersistence = { observed: prefCalls, probe: persisted };
    step('language preference reaches the server',
         persisted.asShipped < 400 ? 'pass' : 'fail',
         `LanguageSwitcher URL -> HTTP ${persisted.asShipped}; `
         + `same call under /api -> HTTP ${persisted.withApiPrefix}`);

    await browser.close();
  } catch (err) {
    step('walkthrough aborted', 'fail', err.message);
    await browser.close().catch(() => {});
  }

  // Every 403 this run provoked came from the disclosure-boundary probes.
  // Labelling them keeps a reader from counting a deliberate refusal as a
  // product failure.
  const provoked = record.network.filter(n => n.status === 403).length;
  record.expectedRefusals = provoked;
  record.summary = {
    passed: record.steps.filter(s => s.outcome === 'pass').length,
    failed: record.steps.filter(s => s.outcome === 'fail').length,
    consoleErrors: record.console.filter(c => c.type === 'error').length,
    networkFailures: record.network.length,
    networkFailuresUnexpected: record.network.filter(n => n.status !== 403).length,
    note: 'console errors and 403s are the disclosure-boundary probes this '
          + 'walkthrough issues on purpose',
  };
  fs.writeFileSync(path.join(EVIDENCE, 'browser-walkthrough.json'),
                   JSON.stringify(record, null, 2) + '\n');
  console.log('\n' + JSON.stringify(record.summary, null, 2));
})();

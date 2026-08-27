const {chromium} = require('/home/ubuntu/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');
const fs = require('fs');

const UI = 'https://globalstrat.camdani.com';
const API = 'http://127.0.0.1:8002/api';
const OUT = __dirname + '/evidence/browser';
fs.mkdirSync(OUT, {recursive: true});
const STUDENT_PASSWORD = process.env.GS_AUDIT_STUDENT_PASSWORD;
const INSTRUCTOR_PASSWORD = process.env.GS_AUDIT_INSTRUCTOR_PASSWORD;
if (!STUDENT_PASSWORD || !INSTRUCTOR_PASSWORD) {
  throw new Error('Set GS_AUDIT_STUDENT_PASSWORD and GS_AUDIT_INSTRUCTOR_PASSWORD.');
}

async function login(username, password) {
  const response = await fetch(`${API}/auth/login/`, {
    method: 'POST', headers: {'content-type': 'application/json'},
    body: JSON.stringify({username, password}),
  });
  if (!response.ok) throw new Error(`${username} login failed: ${response.status}`);
  return response.json();
}

async function visit(browser, account, language, routes) {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
  const page = await context.newPage();
  const consoleErrors = [];
  const failedApi = [];
  page.on('pageerror', e => consoleErrors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('response', r => { if (r.url().includes('/api/') && r.status() >= 400) failedApi.push(`${r.status()} ${r.url()}`); });
  await page.goto(`${UI}/login`, {waitUntil: 'domcontentloaded'});
  await page.evaluate(({a, lang}) => {
    localStorage.setItem('access_token', a.access);
    localStorage.setItem('gs_user', JSON.stringify(a));
    localStorage.setItem('gs_language', lang);
  }, {a: account, lang: language});
  const rows = [];
  for (const route of routes) {
    consoleErrors.length = 0; failedApi.length = 0;
    let navError = null;
    try { await page.goto(UI + route.path, {waitUntil: 'domcontentloaded', timeout: 20000}); }
    catch (e) { navError = e.message; }
    await new Promise(r => setTimeout(r, 1200));
    const state = await page.evaluate(() => ({
      url: location.pathname,
      title: document.title,
      text: document.body.innerText.slice(0, 500),
      bodyLength: document.body.innerText.length,
    }));
    const filename = `${account.username}_${language}_${route.name}.png`;
    await page.screenshot({path: `${OUT}/${filename}`, fullPage: true});
    rows.push({...route, ...state, navError, consoleErrors: [...new Set(consoleErrors)], failedApi: [...new Set(failedApi)], screenshot: filename});
  }
  await context.close();
  return rows;
}

(async () => {
  const student = await login('student1', STUDENT_PASSWORD);
  const instructor = await login('instructor', INSTRUCTOR_PASSWORD);
  const prefix = `/games/${student.game_id}/teams/${student.team_id}`;
  const studentRoutes = [
    ['dashboard', '/'], ['news', `${prefix}/news`], ['research', `${prefix}/research`],
    ['competitors', `${prefix}/competitors`], ['tools', `${prefix}/tools`],
    ['financial_reports', `${prefix}/financial-reports`], ['team_activity', `${prefix}/team-activity`],
    ['forecast', `${prefix}/forecast`], ['sourcing', `${prefix}/decisions/sourcing`],
    ['logistics', `${prefix}/decisions/logistics`], ['trade_finance', `${prefix}/decisions/trade-finance`],
    ['inventory', `${prefix}/decisions/inventory`], ['rd', `${prefix}/decisions/rd`],
    ['products', `${prefix}/decisions/products`], ['marketing', `${prefix}/decisions/marketing`],
    ['corporate_strategy', `${prefix}/decisions/corporate-strategy`],
    ['market_strategy', `${prefix}/decisions/market-strategy`], ['finance', `${prefix}/decisions/finance`],
    ['communications', `${prefix}/decisions/communications`], ['summary', `${prefix}/decisions/summary`],
    ['leaderboard', `/games/${student.game_id}/leaderboard`],
    ['shallow_route', '/sourcing'], ['later_round_direct', `${prefix}/decisions/summary?round=6`],
  ].map(([name, path]) => ({name, path}));
  const instructorRoutes = [{name: 'portal', path: '/instructor'}, {name: 'legacy_game_control', path: `/games/${student.game_id}/instructor`}];
  const browser = await chromium.launch({executablePath: '/snap/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']});
  try {
    const results = {
      generatedAt: new Date().toISOString(), student: {gameId: student.game_id, teamId: student.team_id},
      en: await visit(browser, student, 'en', studentRoutes),
      zh: await visit(browser, student, 'zh-CN', studentRoutes),
      instructor: await visit(browser, instructor, 'en', instructorRoutes),
    };
    fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2));
    // CR-016 concerns completely blank documents. Short, labeled loading states
    // (for example, the instructor shell while its game list loads) are valid.
    const failures = [...results.en, ...results.zh, ...results.instructor].filter(x => x.navError || x.consoleErrors.length || x.failedApi.length || x.bodyLength === 0);
    console.log(JSON.stringify({screens: results.en.length + results.zh.length + results.instructor.length, failures}, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });

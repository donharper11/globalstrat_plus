// CR-017 render + clean-inert check, incremental (writes after each page).
const fs = require('fs');
const path = require('path');
const { chromium } = require('/home/ubuntu/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');
const BASE = 'http://127.0.0.1:18080';
const OUTPUT = '/home/ubuntu/projects/globalstrat+/handoff_readiness/evidence/a1-lifecycle-20260827';
const OUT = path.join(OUTPUT, 'cr017-regression-sweep.json');
const PAGES = ['marketing', 'sourcing', 'logistics', 'trade-finance', 'inventory'];

async function login(u, p) {
  const r = await fetch(`${BASE}/api/auth/login/`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username: u, password: p }) });
  if (!r.ok) throw new Error(`login ${u}: ${r.status}`);
  return r.json();
}

(async () => {
  const student = await login('student1', 'student1pass');
  const gameId = student.game_id, teamId = student.team_id;
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await context.route('**/*', (route) => {
    const u = route.request().url();
    return (u.startsWith('http://127.0.0.1') || u.startsWith('data:') || u.startsWith('blob:')) ? route.continue() : route.abort();
  });
  await context.addInitScript(({ user }) => {
    localStorage.setItem('access_token', user.access);
    localStorage.setItem('gs_user', JSON.stringify(user));
    localStorage.setItem('gs_session_id', String(user.session_id));
    localStorage.setItem('gs_language', 'en');
  }, { user: student });

  const results = [];
  const write = () => fs.writeFileSync(OUT, JSON.stringify({ timestamp: new Date().toISOString(), base: BASE, game_id: gameId, team_id: teamId, external_requests: 'aborted', results, all_pass: results.length === PAGES.length && results.every(r => r.pass) }, null, 2));

  for (const slug of PAGES) {
    const page = await context.newPage();
    const pageErrors = [];
    page.on('pageerror', e => pageErrors.push(String(e)));
    const dialogs = [];
    page.on('dialog', async (d) => { dialogs.push(d.message()); await d.accept().catch(() => {}); });
    let renders = false, textLen = 0, cleanInert = true;
    try {
      // prime history
      await page.goto(`${BASE}/games/${gameId}/teams/${teamId}/decisions/summary`, { waitUntil: 'commit', timeout: 25000 });
      await page.waitForTimeout(700);
      await page.goto(`${BASE}/games/${gameId}/teams/${teamId}/decisions/${slug}`, { waitUntil: 'commit', timeout: 25000 });
      await page.waitForTimeout(2500);
      const text = (await page.locator('body').innerText()).trim();
      textLen = text.length; renders = textLen > 0;
      const before = dialogs.length;
      await page.goBack({ waitUntil: 'commit', timeout: 25000 }).catch(() => {});
      await page.waitForTimeout(1000);
      cleanInert = dialogs.length === before;
    } catch (e) { pageErrors.push('probe-error: ' + String(e).split('\n')[0]); }
    results.push({ page: slug, renders, text_length: textLen, page_errors: pageErrors, clean_guard_inert: cleanInert, pass: renders && pageErrors.length === 0 && cleanInert });
    write();
    console.log(`${slug}: renders=${renders} len=${textLen} inert=${cleanInert} errs=${pageErrors.length}`);
    await page.close();
  }
  await browser.close();
  console.log('DONE all_pass=' + results.every(r => r.pass));
})().catch(e => { console.error(e); process.exit(1); });

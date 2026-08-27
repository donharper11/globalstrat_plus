const {chromium} = require('/home/ubuntu/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');
const fs = require('fs');
const UI = 'https://globalstrat.camdani.com';
const API = 'http://127.0.0.1:8002/api';
const USERNAME = process.env.GS_AUDIT_USERNAME || 'student1';
const PASSWORD = process.env.GS_AUDIT_PASSWORD;
if (!PASSWORD) throw new Error('Set GS_AUDIT_PASSWORD before running this audit.');

async function login() {
  const r = await fetch(`${API}/auth/login/`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({username: USERNAME, password: PASSWORD})});
  return r.json();
}

(async () => {
  const account = await login();
  const browser = await chromium.launch({executablePath: '/snap/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage']});
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
  const page = await context.newPage();
  const events = [];
  const started = Date.now();
  const stamp = () => Date.now() - started;
  page.on('request', r => { if (r.url().includes('/api/')) events.push({t: stamp(), type: 'request', method: r.method(), url: r.url()}); });
  page.on('response', r => { if (r.url().includes('/api/')) events.push({t: stamp(), type: 'response', status: r.status(), url: r.url()}); });
  page.on('requestfailed', r => events.push({t: stamp(), type: 'failed', url: r.url(), error: r.failure()}));
  page.on('console', m => events.push({t: stamp(), type: `console:${m.type()}`, text: m.text()}));
  page.on('pageerror', e => events.push({t: stamp(), type: 'pageerror', text: String(e)}));
  await page.goto(`${UI}/login`, {waitUntil: 'domcontentloaded'});
  await page.evaluate(a => { localStorage.setItem('access_token', a.access); localStorage.setItem('gs_user', JSON.stringify(a)); localStorage.setItem('gs_language', 'en'); }, account);
  const path = `/games/${account.game_id}/teams/${account.team_id}/decisions/rd`;
  await page.goto(UI + path, {waitUntil: 'domcontentloaded'});
  for (const delay of [0, 250, 500, 1000, 2000, 4000, 8000, 15000]) {
    const target = started + delay;
    if (Date.now() < target) await new Promise(r => setTimeout(r, target - Date.now()));
    const state = await page.evaluate(() => ({
      readyState: document.readyState,
      bodyText: document.body.innerText.slice(0, 300),
      bodyLength: document.body.innerText.length,
      rootHTMLLength: document.querySelector('#root')?.innerHTML.length || 0,
      spinners: document.querySelectorAll('.ant-spin, .ant-spin-spinning').length,
      scripts: [...document.scripts].map(s => s.src).filter(Boolean),
      navigation: performance.getEntriesByType('navigation').map(n => ({dom: n.domContentLoadedEventEnd, load: n.loadEventEnd, transfer: n.transferSize})),
    }));
    events.push({t: stamp(), type: 'sample', delay, state});
  }
  fs.mkdirSync(__dirname + '/evidence/cr016', {recursive: true});
  await page.screenshot({path: __dirname + '/evidence/cr016/final.png', fullPage: true});
  fs.writeFileSync(__dirname + '/evidence/cr016/probe.json', JSON.stringify({account: {game: account.game_id, team: account.team_id}, path, events}, null, 2));
  console.log(JSON.stringify(events.filter(e => e.type === 'sample' || e.type === 'response' || e.type === 'failed' || e.type === 'pageerror'), null, 2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });

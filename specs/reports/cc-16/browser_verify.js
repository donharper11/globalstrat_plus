// CC-16 browser verification: serve the real CRA build, proxy /api to a real
// runserver (:8019, real globalstrat_plus DB, disposable game CC16-BROWSER-VERIFY),
// mock only /api/auth/me (session bootstrap). Puppeteer drives the instructor
// dashboard: opens the Supply Chain tab, reads the per-team resilience audit,
// injects the Taiwan Earthquake, then (after the harness fires the injected
// event server-side) reloads and confirms the disruption shows in the UI.
const http = require('http'); const fs = require('fs'); const path = require('path');
const BUILD = '/home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend/build';
const PORT = 4196; const BACKEND = { host: '127.0.0.1', port: 8019 };
const OUT = '/tmp/cc16verify';
const GAME_ID = 13, INST_USER_ID = 14, SCENARIO_ID = 7;
const SESSION = { user_id: INST_USER_ID, username: 'cc16_browser_inst', role: 'instructor',
  game_id: GAME_ID, scenario_id: SCENARIO_ID, game_name: 'CC16-BROWSER-VERIFY', language: 'en' };
const MIME = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.map': 'application/json', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf' };

const server = http.createServer((req, res) => {
  const urlPath = req.url.split('?')[0];
  if (req.url.startsWith('/api/')) {
    if (urlPath.startsWith('/api/auth/me')) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify(SESSION));
    }
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      const body = Buffer.concat(chunks);
      const headers = { ...req.headers, host: `${BACKEND.host}:${BACKEND.port}` };
      const preq = http.request({ host: BACKEND.host, port: BACKEND.port, method: req.method, path: req.url, headers }, (pres) => {
        res.writeHead(pres.statusCode, pres.headers); pres.pipe(res);
      });
      preq.on('error', (e) => { res.writeHead(502); res.end('proxy error: ' + e.message); });
      if (body.length) preq.write(body);
      preq.end();
    });
    return;
  }
  let fp = path.join(BUILD, decodeURIComponent(urlPath));
  if (urlPath === '/' || !fs.existsSync(fp) || fs.statSync(fp).isDirectory()) {
    if (path.extname(urlPath)) { res.writeHead(404); return res.end('nf'); }
    fp = path.join(BUILD, 'index.html');
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(fp)] || 'application/octet-stream' });
  fs.createReadStream(fp).pipe(res);
});

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const puppeteer = require('puppeteer-core');
  await new Promise(r => server.listen(PORT, r));
  const base = `http://localhost:${PORT}`;
  const browser = await puppeteer.launch({ executablePath: '/usr/bin/chromium-browser', headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1300 });
  const results = {}; const log = (k, v) => { results[k] = v; console.log('[cc16]', k, '=>', JSON.stringify(v)); };
  const consoleErrors = []; page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); }); page.on('pageerror', e => consoleErrors.push('PAGEERROR: ' + e.message));
  await page.evaluateOnNewDocument((uid) => { localStorage.setItem('gs_user', JSON.stringify({ user_id: uid })); }, INST_USER_ID);

  // 1) Instructor dashboard → Supply Chain tab
  await page.goto(base + '/instructor', { waitUntil: 'networkidle0', timeout: 45000 });
  await sleep(1500);
  const clickedTab = await page.evaluate(() => {
    const el = [...document.querySelectorAll('.ant-tabs-tab, [role=tab]')].find(x => /supply chain/i.test(x.innerText));
    if (el) { el.click(); return true; } return false;
  });
  log('supply_chain_tab_found', clickedTab);
  await sleep(2000);
  await page.screenshot({ path: OUT + '/01_panel.png', fullPage: true });
  const bodyText1 = await page.evaluate(() => document.body.innerText);
  log('shows_both_teams', bodyText1.includes('Fragile Single-Source') && bodyText1.includes('Resilient Diversified'));
  log('shows_resilience_scores', bodyText1.includes('12.6') && bodyText1.includes('74.2'));
  log('shows_single_source_flag', bodyText1.includes('semiconductor'));

  // 2) Inject the Taiwan Earthquake via the UI
  await page.evaluate(() => {
    const sel = document.querySelector('.ant-select-selector');
    if (sel) sel.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
  });
  await sleep(800);
  const picked = await page.evaluate(() => {
    const opt = [...document.querySelectorAll('.ant-select-item-option')].find(o => /taiwan earthquake/i.test(o.innerText));
    if (opt) { opt.click(); return opt.innerText; } return null;
  });
  log('event_option_picked', picked);
  await sleep(600);
  const injected = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Inject' && !x.disabled);
    if (b) { b.click(); return true; } return false;
  });
  log('inject_clicked', injected);
  await sleep(2500);
  await page.screenshot({ path: OUT + '/02_injected.png', fullPage: true });
  const bodyText2 = await page.evaluate(() => document.body.innerText);
  log('inject_confirmation', /queued|fires when round/i.test(bodyText2));

  await browser.close();
  await new Promise(r => server.close(r));
  fs.writeFileSync(OUT + '/results_phase1.json', JSON.stringify({ results, consoleErrors }, null, 2));
  console.log('[cc16] consoleErrors:', consoleErrors.length);
  console.log('[cc16] PHASE1 DONE');
})().catch(e => { console.error('HARNESS ERROR', e); process.exit(1); });

// CC-16 browser verification, phase 2: after the injected event has fired
// server-side (round advanced), reload the instructor Supply Chain tab and
// confirm the disruption is reflected in the UI — active-disruption alert +
// the fragile team's tsmc allocation flagged as disrupted.
const http = require('http'); const fs = require('fs'); const path = require('path');
const BUILD = '/home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend/build';
const PORT = 4197; const BACKEND = { host: '127.0.0.1', port: 8019 };
const OUT = '/tmp/cc16verify';
const GAME_ID = 13, INST_USER_ID = 14, SCENARIO_ID = 7;
const SESSION = { user_id: INST_USER_ID, username: 'cc16_browser_inst', role: 'instructor', game_id: GAME_ID, scenario_id: SCENARIO_ID, game_name: 'CC16-BROWSER-VERIFY', language: 'en' };
const MIME = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.map': 'application/json', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf' };

const server = http.createServer((req, res) => {
  const urlPath = req.url.split('?')[0];
  if (req.url.startsWith('/api/')) {
    if (urlPath.startsWith('/api/auth/me')) { res.writeHead(200, { 'Content-Type': 'application/json' }); return res.end(JSON.stringify(SESSION)); }
    const chunks = []; req.on('data', c => chunks.push(c));
    req.on('end', () => {
      const body = Buffer.concat(chunks);
      const headers = { ...req.headers, host: `${BACKEND.host}:${BACKEND.port}` };
      const preq = http.request({ host: BACKEND.host, port: BACKEND.port, method: req.method, path: req.url, headers }, (pres) => { res.writeHead(pres.statusCode, pres.headers); pres.pipe(res); });
      preq.on('error', e => { res.writeHead(502); res.end('proxy error: ' + e.message); });
      if (body.length) preq.write(body); preq.end();
    });
    return;
  }
  let fp = path.join(BUILD, decodeURIComponent(urlPath));
  if (urlPath === '/' || !fs.existsSync(fp) || fs.statSync(fp).isDirectory()) { if (path.extname(urlPath)) { res.writeHead(404); return res.end('nf'); } fp = path.join(BUILD, 'index.html'); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(fp)] || 'application/octet-stream' });
  fs.createReadStream(fp).pipe(res);
});
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  const puppeteer = require('puppeteer-core');
  await new Promise(r => server.listen(PORT, r));
  const base = `http://localhost:${PORT}`;
  const browser = await puppeteer.launch({ executablePath: '/usr/bin/chromium-browser', headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1300 });
  const results = {}; const log = (k, v) => { results[k] = v; console.log('[cc16p2]', k, '=>', JSON.stringify(v)); };
  const consoleErrors = []; page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); }); page.on('pageerror', e => consoleErrors.push('PAGEERROR: ' + e.message));
  await page.evaluateOnNewDocument((uid) => { localStorage.setItem('gs_user', JSON.stringify({ user_id: uid })); }, INST_USER_ID);

  await page.goto(base + '/instructor', { waitUntil: 'networkidle0', timeout: 45000 });
  await sleep(1500);
  await page.evaluate(() => { const el = [...document.querySelectorAll('.ant-tabs-tab, [role=tab]')].find(x => /supply chain/i.test(x.innerText)); if (el) el.click(); });
  await sleep(2500);
  await page.screenshot({ path: OUT + '/03_disruption.png', fullPage: true });
  const body = await page.evaluate(() => document.body.innerText);
  log('active_disruption_shown', /disruption\(s\) active this round|capacity 60%/i.test(body));
  log('supplier_capacity_shown', /capacity 60%/i.test(body));
  // expand the fragile team row to see the disrupted allocation
  await page.evaluate(() => { const b = document.querySelector('.ant-table-row-expand-icon'); if (b) b.click(); });
  await sleep(1200);
  await page.screenshot({ path: OUT + '/04_disrupted_allocation.png', fullPage: true });
  const body2 = await page.evaluate(() => document.body.innerText);
  log('disrupted_allocation_flagged', /disrupted/i.test(body2));

  await browser.close();
  await new Promise(r => server.close(r));
  fs.writeFileSync(OUT + '/results_phase2.json', JSON.stringify({ results, consoleErrors }, null, 2));
  console.log('[cc16p2] consoleErrors:', consoleErrors.length);
  console.log('[cc16p2] PHASE2 DONE');
})().catch(e => { console.error('HARNESS ERROR', e); process.exit(1); });

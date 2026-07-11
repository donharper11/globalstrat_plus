// CC-22 real-stack browser E2E: serve the real build, proxy /api to the REAL
// backend (runserver on :8013, real globalstrat_plus DB) so decisions actually
// persist. Only /api/auth/me is mocked (session bootstrap). Puppeteer drives the
// dashboard + the Sourcing page and submits a real sourcing decision.
const http = require('http'); const fs = require('fs'); const path = require('path');
const BUILD = '/home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend/build';
const PORT = 4194; const BACKEND = { host: '127.0.0.1', port: 8013 };
const SESSION = { user_id: 7, username: 'cc22_browser_inst', role: 'instructor', game_id: 8, team_id: 5, scenario_id: 5, game_name: 'CC22-BROWSER-E2E', team_name: 'BrowserTeam', language: 'en' };
const MIME = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.map': 'application/json', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf' };

const server = http.createServer((req, res) => {
  const urlPath = req.url.split('?')[0];
  if (req.url.startsWith('/api/')) {
    if (urlPath === '/api/auth/me/' || urlPath.startsWith('/api/auth/me')) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify(SESSION));
    }
    // proxy everything else to the real backend, forwarding headers + body
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      const body = Buffer.concat(chunks);
      const headers = { ...req.headers, host: `${BACKEND.host}:${BACKEND.port}` };
      const preq = http.request({ host: BACKEND.host, port: BACKEND.port, method: req.method, path: req.url, headers }, (pres) => {
        res.writeHead(pres.statusCode, pres.headers);
        pres.pipe(res);
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

(async () => {
  const puppeteer = (await import('puppeteer-core')).default;
  await new Promise(r => server.listen(PORT, r));
  const base = `http://localhost:${PORT}`;
  const browser = await puppeteer.launch({ executablePath: '/usr/bin/chromium-browser', headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1300, height: 1200 });
  const results = {}; const log = (k, v) => { results[k] = v; console.log('[cc22b]', k, '=>', JSON.stringify(v)); };
  const consoleErrors = []; page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); }); page.on('pageerror', e => consoleErrors.push('PAGEERROR: ' + e.message));
  // No access_token: rely on the legacy X-User-Id header (a fake Bearer token
  // would trip JWT auth → 403). gs_user.user_id drives the X-User-Id interceptor.
  await page.evaluateOnNewDocument(() => { localStorage.setItem('gs_user', JSON.stringify({ user_id: 7 })); });

  // 1) Dashboard reads the REAL backend
  await page.goto(base + '/games/8/teams/5/sc-dashboard', { waitUntil: 'networkidle0', timeout: 40000 });
  await page.waitForFunction(() => document.body.innerText.includes('Supply Chain Dashboard'), { timeout: 20000 });
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: '/tmp/cc10verify/cc22b_dash.png', fullPage: true });
  log('dashboard_rendered_real', (await page.evaluate(() => document.body.innerText)).includes('Uyghur'));

  // 2) Sourcing page loads suppliers from the REAL backend
  await page.goto(base + '/games/8/teams/5/decisions/sourcing', { waitUntil: 'networkidle0', timeout: 40000 });
  await page.waitForFunction(() => document.body.innerText.includes('Sourcing & Suppliers'), { timeout: 20000 });
  await new Promise(r => setTimeout(r, 1500));
  log('suppliers_loaded_real', (await page.evaluate(() => document.body.innerText)).includes('Taiwan Semiconductor'));

  // 3) Submit a real sourcing decision via the UI
  await page.evaluate(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Add supplier' && !x.disabled); if (b) b.click(); });
  await new Promise(r => setTimeout(r, 600));
  // open the supplier select in the new row and pick first option
  await page.evaluate(() => { const sel = document.querySelector('.ant-table .ant-select-selector'); if (sel) sel.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); });
  await new Promise(r => setTimeout(r, 500));
  const picked = await page.evaluate(() => { const opt = document.querySelector('.ant-select-dropdown .ant-select-item-option'); if (opt) { opt.dispatchEvent(new MouseEvent('click', { bubbles: true })); return opt.innerText; } return null; });
  log('supplier_selected', picked);
  await new Promise(r => setTimeout(r, 400));
  // set allocation pct to 100
  await page.evaluate(() => { const inp = document.querySelector('.ant-table .ant-input-number-input'); const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; inp.focus(); setter.call(inp, '100'); inp.dispatchEvent(new Event('input', { bubbles: true })); inp.blur(); inp.dispatchEvent(new Event('change', { bubbles: true })); });
  await new Promise(r => setTimeout(r, 400));
  await page.evaluate(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Save' && !x.disabled); if (b) b.click(); });
  await new Promise(r => setTimeout(r, 2000));
  const afterSave = await page.evaluate(() => document.body.innerText);
  log('save_success', afterSave.includes('Sourcing decision saved'));
  await page.screenshot({ path: '/tmp/cc10verify/cc22b_saved.png', fullPage: true });

  // 4) Reload and confirm the allocation persisted in the REAL DB
  await page.goto(base + '/games/8/teams/5/decisions/sourcing', { waitUntil: 'networkidle0', timeout: 40000 });
  await page.waitForFunction(() => document.body.innerText.includes('Sourcing & Suppliers'), { timeout: 20000 });
  await new Promise(r => setTimeout(r, 1500));
  log('persisted_after_reload', await page.evaluate(() => document.querySelectorAll('.ant-table .ant-select-selection-item').length > 0));

  log('console_errors', consoleErrors.slice(0, 8));
  await browser.close(); server.close();
  fs.writeFileSync('/tmp/cc10verify/cc22b_results.json', JSON.stringify(results, null, 1));
  console.log('[cc22b] DONE');
})().catch(e => { console.error('FATAL', e); process.exit(1); });

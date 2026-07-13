// CC-23 i18n verification: load the SC Sourcing page with gs_language='zh-CN'
// and confirm the SC surface renders in Chinese (title, section headers, state
// badge) — then switch to English and confirm it flips back.
const http = require('http'); const fs = require('fs'); const path = require('path');
const BUILD = '/home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend/build';
const PORT = 4198; const BACKEND = { host: '127.0.0.1', port: 8019 };
const OUT = '/tmp/cc23verify';
const GAME_ID = 14, USER_ID = 15, TEAM_ID = 24, SCENARIO_ID = 7;
const SESSION = { user_id: USER_ID, username: 'i18n_stu', role: 'instructor', game_id: GAME_ID,
  team_id: TEAM_ID, scenario_id: SCENARIO_ID, game_name: 'I18N-VERIFY', team_name: 'ZHTeam', language: 'zh-CN' };
const MIME = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.map': 'application/json', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf' };

const server = http.createServer((req, res) => {
  const u = req.url.split('?')[0];
  if (req.url.startsWith('/api/')) {
    if (u.startsWith('/api/auth/me')) { res.writeHead(200, { 'Content-Type': 'application/json' }); return res.end(JSON.stringify(SESSION)); }
    const chunks = []; req.on('data', c => chunks.push(c));
    req.on('end', () => {
      const body = Buffer.concat(chunks); const headers = { ...req.headers, host: `${BACKEND.host}:${BACKEND.port}` };
      const preq = http.request({ host: BACKEND.host, port: BACKEND.port, method: req.method, path: req.url, headers }, (pres) => { res.writeHead(pres.statusCode, pres.headers); pres.pipe(res); });
      preq.on('error', e => { res.writeHead(502); res.end('proxy error: ' + e.message); }); if (body.length) preq.write(body); preq.end();
    });
    return;
  }
  let fp = path.join(BUILD, decodeURIComponent(u));
  if (u === '/' || !fs.existsSync(fp) || fs.statSync(fp).isDirectory()) { if (path.extname(u)) { res.writeHead(404); return res.end('nf'); } fp = path.join(BUILD, 'index.html'); }
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
  await page.setViewport({ width: 1200, height: 1000 });
  const results = {}; const log = (k, v) => { results[k] = v; console.log('[cc23]', k, '=>', JSON.stringify(v)); };
  const consoleErrors = []; page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  const sourcingUrl = `${base}/games/${GAME_ID}/teams/${TEAM_ID}/decisions/sourcing`;

  // --- Chinese ---
  await page.evaluateOnNewDocument((uid) => {
    localStorage.setItem('gs_user', JSON.stringify({ user_id: uid }));
    localStorage.setItem('gs_language', 'zh-CN');
  }, USER_ID);
  await page.goto(sourcingUrl, { waitUntil: 'networkidle0', timeout: 45000 });
  await sleep(2000);
  await page.screenshot({ path: OUT + '/01_sourcing_zh.png', fullPage: true });
  const zh = await page.evaluate(() => document.body.innerText);
  log('zh_title', zh.includes('采购'));
  log('zh_approach_header', zh.includes('您的采购策略'));
  log('zh_critical_inputs', zh.includes('关键投入'));
  log('zh_state_badge', zh.includes('已保存') || zh.includes('未保存的更改'));

  // --- English (flip language) ---
  await page.evaluate(() => { localStorage.setItem('gs_language', 'en'); });
  await page.goto(sourcingUrl, { waitUntil: 'networkidle0', timeout: 45000 });
  await sleep(2000);
  await page.screenshot({ path: OUT + '/02_sourcing_en.png', fullPage: true });
  const en = await page.evaluate(() => document.body.innerText);
  log('en_title', en.includes('Sourcing'));
  log('en_approach_header', en.includes('Your Sourcing Approach'));

  await browser.close();
  await new Promise(r => server.close(r));
  fs.writeFileSync(OUT + '/results.json', JSON.stringify({ results, consoleErrors }, null, 2));
  console.log('[cc23] consoleErrors:', consoleErrors.length);
  console.log('[cc23] DONE');
})().catch(e => { console.error('HARNESS ERROR', e); process.exit(1); });

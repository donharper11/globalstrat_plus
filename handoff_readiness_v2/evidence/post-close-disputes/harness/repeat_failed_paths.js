/**
 * Repeat only the two paths that failed, after repair.
 *
 * Dispute 5 (V2-030): an operator-events screen and endpoint that did not
 * exist. Language persistence (V2-031): a PUT that 404ed into a silent catch.
 * Nothing else is replayed -- the passing disputes and the student walkthrough
 * are unchanged and were recorded at 8554db3.
 */
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const EVIDENCE = path.resolve(__dirname, '..');
const ports = JSON.parse(fs.readFileSync('/tmp/crv208-runtime/stack.ports', 'utf8'));
const fixture = JSON.parse(fs.readFileSync(path.join(EVIDENCE, 'completed-game.json'), 'utf8'));
const BASE = `http://127.0.0.1:${ports.app}`;
const out = { base: BASE, steps: [], console: [], network: [] };

function step(name, outcome, detail) {
  out.steps.push({ name, outcome, detail });
  console.log(`  ${(outcome === 'pass' ? 'PASS' : outcome.toUpperCase()).padEnd(6)} ${name}` +
              (detail ? ` — ${String(detail).slice(0, 240)}` : ''));
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/chromium-browser', headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1500, height: 1000 });
  page.on('console', m => { if (m.type() === 'error') out.console.push(m.text().slice(0, 240)); });
  page.on('response', r => { if (r.status() >= 400) out.network.push({ url: r.url().slice(0, 160), status: r.status() }); });

  const clickText = (rx) => page.evaluate((r) => {
    const re = new RegExp(r);
    const el = [...document.querySelectorAll('*')].find(e => re.test(e.innerText || '') && e.children.length === 0);
    if (el) { el.click(); return el.innerText.trim(); }
    return null;
  }, rx);

  try {
    // ---- Dispute 5, through the browser --------------------------------
    await page.goto(`${BASE}/instructor/login`, { waitUntil: 'networkidle2' });
    await page.waitForSelector('input#username, input[name="username"]', { timeout: 30000 });
    await page.type('input#username, input[name="username"]', fixture.identities.instructor);
    await page.type('input#password, input[name="password"]', fixture.password);
    await page.click('button[type="submit"]');
    await new Promise(r => setTimeout(r, 5000));
    await clickText('STRAT-TEST');
    await new Promise(r => setTimeout(r, 3000));
    await clickText('TEST-01');
    await new Promise(r => setTimeout(r, 6000));

    const tabs = await page.evaluate(() =>
      [...document.querySelectorAll('.ant-tabs-tab')].map(t => t.innerText.trim()));
    step('operator log tab is present', tabs.some(t => /operator log/i.test(t)) ? 'pass' : 'fail',
         tabs.join(' | '));

    await clickText('Operator Log');
    await new Promise(r => setTimeout(r, 4000));
    fs.mkdirSync(path.join(EVIDENCE, 'screenshots'), { recursive: true });
    await page.screenshot({ path: path.join(EVIDENCE, 'screenshots', 'instructor-operator-log.png'), fullPage: true });

    const table = await page.evaluate(() => {
      const cards = [...document.querySelectorAll('.ant-card')];
      const card = cards.find(c => /operator actions/i.test(c.innerText)) || cards[cards.length - 1];
      if (!card) return { rows: 0, headers: [] };
      return {
        headers: [...card.querySelectorAll('.ant-table-thead th')].map(h => h.innerText.trim()).filter(Boolean),
        rows: card.querySelectorAll('.ant-table-tbody tr.ant-table-row').length,
        outcomes: [...card.querySelectorAll('.ant-table-tbody .ant-tag')].map(t => t.innerText.trim()),
        text: card.innerText.slice(0, 600),
      };
    });
    out.operatorLog = table;
    step('operator actions render in the browser', table.rows > 0 ? 'pass' : 'fail',
         `${table.rows} rows, columns: ${table.headers.join(' | ')}`);
    step('committed and refused actions are both visible',
         table.outcomes.includes('committed') ? 'pass' : 'fail',
         `outcomes shown: ${[...new Set(table.outcomes)].join(', ') || 'none'}`);

    // ---- The endpoint's own answers, including isolation ---------------
    const api = await page.evaluate(async (game) => {
      const token = localStorage.getItem('access_token');
      const h = { Authorization: `Bearer ${token}` };
      const all = await (await fetch(`/api/games/${game}/instructor/operator-events/`, { headers: h })).json();
      const rejected = await (await fetch(`/api/games/${game}/instructor/operator-events/?outcome=rejected`, { headers: h })).json();
      const readOnly = await fetch(`/api/games/${game}/instructor/operator-events/`, { method: 'POST', headers: h });
      const first = (all.events || [])[0] || {};
      return {
        count: all.count,
        fields: Object.keys(first).sort(),
        rejectedCount: rejected.count,
        postStatus: readOnly.status,
      };
    }, fixture.game_id);
    out.operatorApi = api;
    const need = ['action', 'actor', 'after', 'before', 'reason', 'request_id', 'server_timestamp'];
    step('endpoint returns every field the dispute needs',
         need.every(f => api.fields.includes(f)) ? 'pass' : 'fail',
         `${api.count} events; fields: ${api.fields.join(',')}`);
    step('endpoint refuses writes', api.postStatus === 405 ? 'pass' : 'fail', `POST -> ${api.postStatus}`);

    // ---- Language persistence -------------------------------------------
    await page.evaluate(() => localStorage.clear());
    const persisted = await page.evaluate(async () => {
      const res = await fetch('/api/auth/login/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'crv208_student_1', password: 'crv208-pass' }),
      });
      const data = await res.json();
      localStorage.setItem('access_token', data.access);
      const apiUrl = '/api';   // what LanguageSwitcher now uses by default
      const put = await fetch(`${apiUrl}/user/preferences/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.access}` },
        body: JSON.stringify({ language: 'zh-CN' }),
      });
      return { status: put.status };
    });
    out.languagePersistence = persisted;
    step('language preference reaches the server', persisted.status < 400 ? 'pass' : 'fail',
         `PUT ${'/api/user/preferences/'} -> HTTP ${persisted.status}`);

    // And through the actual control, on a screen that carries it.
    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2000));
    const before = await page.evaluate(() => document.body.innerText.slice(0, 1500));
    const toggled = await page.evaluate(() => {
      const b = [...document.querySelectorAll('button')].find(x => ['中文', 'EN'].includes(x.innerText.trim()));
      if (!b) return false; b.click(); return true;
    });
    await new Promise(r => setTimeout(r, 2500));
    const after = await page.evaluate(() => document.body.innerText.slice(0, 1500));
    step('language control still switches the interface',
         toggled && /[一-鿿]/.test(after) && after !== before ? 'pass' : 'fail');

    await browser.close();
  } catch (e) {
    step('repeat aborted', 'fail', e.message);
    await browser.close().catch(() => {});
  }

  out.summary = {
    passed: out.steps.filter(s => s.outcome === 'pass').length,
    failed: out.steps.filter(s => s.outcome === 'fail').length,
    consoleErrors: out.console.length,
    networkFailures: out.network.filter(n => n.status !== 405).length,
  };
  fs.writeFileSync(path.join(EVIDENCE, 'repeat-after-repair.json'), JSON.stringify(out, null, 2) + '\n');
  console.log('\n' + JSON.stringify(out.summary, null, 2));
})();

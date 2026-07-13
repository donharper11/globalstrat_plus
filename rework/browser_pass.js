// Post-restart browser pass — drives the LIVE served stack (:8014 -> :8012).
// Injects a real JWT + gs_user into localStorage to bootstrap each persona,
// then screenshots the real SC surfaces. Read-only except one sourcing edit
// (draft badge check) that is NOT saved.
const puppeteer = require('/tmp/pptr/node_modules/puppeteer-core');
const fs = require('fs');

const BASE = 'http://127.0.0.1:8014';
const OUT = '/home/ubuntu/projects/globalstrat+/rework/browser-pass';
fs.mkdirSync(OUT, { recursive: true });

const INSTR = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo4LCJ1c2VybmFtZSI6Imluc3RydWN0b3IiLCJyb2xlIjoiaW5zdHJ1Y3RvciIsImlhdCI6MTc4MzkxODIxOCwiZXhwIjoxNzgzOTQ3MDE4fQ.xuNGXpziDMrnSbz4Y4fxVNAEXlTqFu1Qg04ifBDk92k';
const STUD = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo5LCJ1c2VybmFtZSI6InN0dWRlbnQxIiwicm9sZSI6InN0dWRlbnQiLCJpYXQiOjE3ODM5MTgyMTgsImV4cCI6MTc4Mzk0NzAxOH0.bQ0LMXw2Hj6noLJKqN9WsKcSOIOpa2rRQWoPssMNo2M';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];

async function persona(browser, label, token, gsUser, steps) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport({ width: 1400, height: 1000 });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
  page.on('pageerror', (e) => errors.push('PAGEERROR ' + String(e).slice(0, 200)));
  const bad = [];
  page.on('response', (r) => { const u = r.url(); if (u.includes('/api/') && r.status() >= 400) bad.push(r.status() + ' ' + u.replace(BASE, '')); });
  // seed auth before any app code runs
  await page.goto(BASE + '/favicon.ico', { waitUntil: 'domcontentloaded' }).catch(() => {});
  await page.evaluate((t, u) => { localStorage.setItem('access_token', t); localStorage.setItem('gs_user', JSON.stringify(u)); localStorage.setItem('gs_language', 'en'); }, token, gsUser);
  for (const s of steps) {
    await page.goto(BASE + s.path, { waitUntil: 'networkidle2', timeout: 45000 }).catch((e) => errors.push('NAV ' + s.path + ' ' + e.message));
    await sleep(s.wait || 2500);
    if (s.act) { try { await s.act(page); await sleep(1500); } catch (e) { errors.push('ACT ' + s.name + ' ' + e.message); } }
    const file = `${OUT}/${label}_${s.name}.png`;
    await page.screenshot({ path: file, fullPage: true }).catch(() => {});
    const bodyLen = await page.evaluate(() => document.body.innerText.length).catch(() => 0);
    const heading = await page.evaluate(() => (document.querySelector('h1,h2,h3,.ant-typography')||{}).innerText || '').catch(() => '');
    results.push({ persona: label, step: s.name, path: s.path, screenshot: file, bodyTextLen: bodyLen, heading: heading.slice(0, 80) });
  }
  const uniqBad = [...new Set(bad)];
  results.push({ persona: label, consoleErrors: errors.slice(0, 8), api4xx5xx: uniqBad.slice(0, 12) });
  await ctx.close();
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/snap/bin/chromium',
    headless: 'new',
    userDataDir: '/home/ubuntu/.cache/pptr-run',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  try {
    await persona(browser, 'student', STUD, { user_id: 9, section_id: 1 }, [
      { name: '01_dashboard', path: '/', wait: 4000 },
      { name: '02_sourcing', path: '/games/12/teams/18/decisions/sourcing', wait: 4000,
        act: async (page) => {
          // find the first allocation number input, bump it -> should flip badge to "Draft"
          const changed = await page.evaluate(() => {
            const inp = document.querySelector('input.ant-input-number-input');
            if (!inp) return false;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(inp, String((parseFloat(inp.value)||50) === 100 ? 90 : (parseFloat(inp.value)||50)));
            inp.dispatchEvent(new Event('input', { bubbles: true }));
            return true;
          });
          return changed;
        } },
      { name: '03_trade_finance', path: '/games/12/teams/18/decisions/trade-finance', wait: 3500 },
    ]);
    await persona(browser, 'instructor', INSTR, { user_id: 8 }, [
      { name: '01_dashboard', path: '/instructor', wait: 5000 },
      { name: '02_sc_panel', path: '/instructor', wait: 3000,
        act: async (page) => {
          // click a tab whose label mentions supply chain / SC if present
          await page.evaluate(() => {
            const tabs = [...document.querySelectorAll('.ant-tabs-tab, [role="tab"]')];
            const t = tabs.find((x) => /supply|sc\b|resilien/i.test(x.innerText));
            if (t) t.click();
          });
        } },
    ]);
  } finally {
    await browser.close();
    fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  }
})().catch((e) => { console.error('FATAL', e); process.exit(1); });

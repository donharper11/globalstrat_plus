const {chromium} = require('/home/ubuntu/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');
const UI = 'https://globalstrat.camdani.com';
const API = 'http://127.0.0.1:8002/api';
const USERNAME = process.env.GS_AUDIT_USERNAME || 'student1';
const PASSWORD = process.env.GS_AUDIT_PASSWORD;
if (!PASSWORD) throw new Error('Set GS_AUDIT_PASSWORD before running this audit.');

(async () => {
  const response = await fetch(`${API}/auth/login/`, {
    method: 'POST', headers: {'content-type': 'application/json'},
    body: JSON.stringify({username: USERNAME, password: PASSWORD}),
  });
  if (!response.ok) throw new Error(`login failed: ${response.status}`);
  const account = await response.json();
  const prefix = `/games/${account.game_id}/teams/${account.team_id}/decisions`;
  const routes = ['sourcing', 'logistics', 'trade-finance', 'inventory'];
  const browser = await chromium.launch({executablePath: '/snap/bin/chromium', headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']});
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(`${UI}/login`, {waitUntil: 'domcontentloaded'});
    await page.evaluate((a) => {
      localStorage.setItem('access_token', a.access);
      localStorage.setItem('gs_user', JSON.stringify(a));
      localStorage.setItem('gs_language', 'zh-CN');
    }, account);
    const results = [];
    for (const route of routes) {
      const errors = [];
      page.on('pageerror', (e) => errors.push(String(e)));
      await page.goto(`${UI}${prefix}/${route}`, {waitUntil: 'domcontentloaded'});
      await page.waitForTimeout(8000);
      const text = await page.locator('main, .ant-layout-content').last().innerText().catch(
        () => page.locator('body').innerText());
      const untranslated = [
        'Browse suppliers', 'Shipping Routes', 'Buyer Payment Instruments',
        'Inventory Buffers', 'Mode-Switch Rules', 'DRAFT OPEN', 'ROUND CLOSED',
        'Save failed', 'Please fix these',
      ].filter((phrase) => text.includes(phrase));
      results.push({route, textLength: text.length, untranslated, errors});
    }
    console.log(JSON.stringify(results, null, 2));
    if (results.some((r) => r.untranslated.length || r.errors.length)) process.exitCode = 1;
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exit(1); });

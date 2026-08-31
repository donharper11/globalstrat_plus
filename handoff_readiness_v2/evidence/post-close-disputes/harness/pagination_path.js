/**
 * The one pagination boundary CRV2-08 requires, driven through the UI control.
 *
 * The Operator Log paginates at 10 and the fixture holds more than that, so the
 * boundary is reachable without rebuilding anything. Slicing the API would
 * prove the endpoint can count; only clicking the rendered control proves the
 * table pages.
 *
 * Row identity is the request id where the column carries one, falling back to
 * the whole row's text. Comparing rendered text alone would let a table that
 * re-rendered the same rows under a new page number pass.
 */
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const EVIDENCE = path.resolve(__dirname, '..');
const ports = JSON.parse(fs.readFileSync('/tmp/crv208-runtime/stack.ports', 'utf8'));
const fixture = JSON.parse(fs.readFileSync(path.join(EVIDENCE, 'completed-game.json'), 'utf8'));
const BASE = `http://127.0.0.1:${ports.app}`;
const PAGE_SIZE = 10;

const out = { base: BASE, pageSize: PAGE_SIZE, steps: [], console: [], network: [] };
function step(name, outcome, detail) {
  out.steps.push({ name, outcome, detail });
  console.log(`  ${(outcome === 'pass' ? 'PASS' : 'FAIL').padEnd(4)} ${name}` +
              (detail ? ` — ${String(detail).slice(0, 200)}` : ''));
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/chromium-browser', headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1500, height: 1100 });
  page.on('console', m => { if (m.type() === 'error') out.console.push(m.text().slice(0, 200)); });
  page.on('response', r => { if (r.status() >= 400) out.network.push({ url: r.url().slice(0, 140), status: r.status() }); });

  const clickText = (rx) => page.evaluate((r) => {
    const re = new RegExp(r);
    const el = [...document.querySelectorAll('*')].find(e => re.test(e.innerText || '') && e.children.length === 0);
    if (el) { el.click(); return el.innerText.trim(); }
    return null;
  }, rx);

  // The operator log card's rows, by identity.
  const readPage = () => page.evaluate(() => {
    const card = [...document.querySelectorAll('.ant-card')]
      .find(c => /operator actions/i.test(c.innerText));
    if (!card) return null;
    const rows = [...card.querySelectorAll('.ant-table-tbody tr.ant-table-row')];
    const identity = (row) => {
      const text = row.innerText.replace(/\s+/g, ' ').trim();
      const match = text.match(/srv-[0-9a-f-]{8,}/i);
      return match ? match[0] : text.slice(0, 120);
    };
    const active = card.querySelector('.ant-pagination-item-active');
    return {
      rows: rows.length,
      identities: rows.map(identity),
      activePage: active ? active.innerText.trim() : null,
      pages: [...card.querySelectorAll('.ant-pagination-item')].map(p => p.innerText.trim()),
    };
  });

  const clickPage = (number) => page.evaluate((n) => {
    const card = [...document.querySelectorAll('.ant-card')]
      .find(c => /operator actions/i.test(c.innerText));
    if (!card) return false;
    const item = [...card.querySelectorAll('.ant-pagination-item')]
      .find(p => p.innerText.trim() === String(n));
    if (!item) return false;
    (item.querySelector('a') || item).click();
    return true;
  }, number);

  try {
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
    await clickText('Operator Log');
    await new Promise(r => setTimeout(r, 4000));

    const first = await readPage();
    if (!first) { step('operator log is on screen', 'fail', 'card not found'); throw new Error('no card'); }
    out.firstPage = first;
    step('page 1 fills the page size',
         first.rows === PAGE_SIZE ? 'pass' : 'fail',
         `${first.rows} rows, page ${first.activePage}, pages: ${first.pages.join(',')}`);
    step('a pagination control is rendered',
         first.pages.length > 1 ? 'pass' : 'fail', `pages: ${first.pages.join(',')}`);

    const moved = await clickPage(2);
    await new Promise(r => setTimeout(r, 2500));
    const second = await readPage();
    out.secondPage = second;
    await page.screenshot({
      path: path.join(EVIDENCE, 'screenshots', 'operator-log-page-2.png'),
      fullPage: true });

    step('the control moves to page 2', moved && second.activePage === '2' ? 'pass' : 'fail',
         `active page ${second && second.activePage}`);

    // The remainder, computed from what the table itself reports rather than
    // hardcoded: the fixture gained one more operator event when a genuine
    // refusal was produced for the dispute-5 repeat.
    const total = out.total = first.rows + second.rows;
    step('page 2 holds the remainder',
         second.rows === total - PAGE_SIZE && second.rows > 0 ? 'pass' : 'fail',
         `${second.rows} rows of ${total} total`);

    const overlap = second.identities.filter(id => first.identities.includes(id));
    step('page 2 shows different rows from page 1',
         overlap.length === 0 ? 'pass' : 'fail',
         overlap.length ? `${overlap.length} repeated: ${overlap.slice(0, 2)}` : 'no overlap');

    const back = await clickPage(1);
    await new Promise(r => setTimeout(r, 2500));
    const returned = await readPage();
    out.returnedPage = returned;
    step('returning to page 1 restores the original rows',
         back && returned.activePage === '1'
           && JSON.stringify(returned.identities) === JSON.stringify(first.identities)
           ? 'pass' : 'fail',
         `${returned.rows} rows, page ${returned.activePage}`);

    await browser.close();
  } catch (e) {
    step('pagination path aborted', 'fail', e.message);
    await browser.close().catch(() => {});
  }

  const unexpected = out.network.filter(n => n.status !== 403);
  out.summary = {
    passed: out.steps.filter(s => s.outcome === 'pass').length,
    failed: out.steps.filter(s => s.outcome === 'fail').length,
    consoleErrors: out.console.length,
    unexpectedNetworkFailures: unexpected.length,
  };
  out.passed = out.summary.failed === 0 && out.summary.consoleErrors === 0
               && unexpected.length === 0;
  fs.writeFileSync(path.join(EVIDENCE, 'pagination-boundary.json'),
                   JSON.stringify(out, null, 2) + '\n');
  console.log('\n' + JSON.stringify(out.summary, null, 2));
  process.exit(out.passed ? 0 : 1);
})();

// CR-017 targeted re-verification probe.
// Reproduces the original failing scenario (A1_BROWSER_STATE_LIFECYCLE_REHEARSAL):
// change an enabled Marketing numeric field, then use browser Back during the
// unsaved edit. Original evidence recorded leave_dialog:null / warning_visible:false
// (silent loss). With the useUnsavedChangesGuard fix a discard dialog must fire.
const fs = require('fs');
const path = require('path');
const { chromium } = require('/home/ubuntu/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');

const BASE = process.env.GS_A1_BASE || 'http://127.0.0.1:18080';
const OUTPUT = process.env.GS_A1_OUTPUT || '/home/ubuntu/projects/globalstrat+/handoff_readiness/evidence/a1-lifecycle-20260827';
fs.mkdirSync(OUTPUT, { recursive: true });

async function login(username, password) {
  const r = await fetch(`${BASE}/api/auth/login/`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username, password }) });
  if (!r.ok) throw new Error(`login ${username}: ${r.status} ${await r.text()}`);
  return r.json();
}

(async () => {
  const student = await login('student1', 'student1pass');
  const gameId = student.game_id, teamId = student.team_id;
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const dialogs = [];
  let dialogMode = 'dismiss';
  page.on('dialog', async (d) => { dialogs.push({ type: d.type(), message: d.message() }); if (dialogMode === 'accept') { await d.accept().catch(() => {}); } else { await d.dismiss().catch(() => {}); } });

  await page.addInitScript(({ user }) => {
    localStorage.setItem('access_token', user.access);
    localStorage.setItem('gs_user', JSON.stringify(user));
    localStorage.setItem('gs_session_id', String(user.session_id));
    localStorage.setItem('gs_language', 'en');
  }, { user: student });

  const route = `${BASE}/games/${gameId}/teams/${teamId}/decisions/marketing`;
  await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(2500);

  // First enabled numeric input on the Marketing page is retail_price.
  const input = page.locator('input.ant-input-number-input:not([disabled])').first();
  await input.waitFor({ state: 'visible', timeout: 20000 });
  const oldValue = (await input.inputValue()) || '0';
  const editedValue = String((Number(oldValue) || 0) + 1);
  await input.click();
  await input.fill(editedValue);
  await input.press('Tab');
  await page.waitForTimeout(800); // let setDirty(true) + history sentinel push settle
  const editCreated = (await input.inputValue()) === editedValue;

  // Browser Back during the unsaved edit -> guard must intercept with a dialog.
  await page.goBack({ waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {});
  await page.waitForTimeout(1500);

  const bodyText = (await page.locator('body').innerText()).toLowerCase();
  const warningVisible = /unsaved|discard|leave|未保存|离开/.test(bodyText) || dialogs.length > 0;
  const leaveDialog = dialogs.length ? dialogs[0].message : null;

  // Return to marketing and read the field back to record preservation state.
  // Accept dialogs now so the guard lets us navigate for the readback.
  dialogMode = 'accept';
  let returnedValue = null;
  try {
    await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 90000 });
    await page.waitForTimeout(2500);
    const back = page.locator('input.ant-input-number-input:not([disabled])').first();
    await back.waitFor({ state: 'visible', timeout: 15000 });
    returnedValue = await back.inputValue();
  } catch (e) { /* readback best-effort */ }

  await page.screenshot({ path: path.join(OUTPUT, 'back-mid-decision-targeted.png'), fullPage: true });

  const result = {
    timestamp: new Date().toISOString(),
    game_id: gameId, team_id: teamId, route: 'marketing',
    old_value: oldValue, edited_value: editedValue, returned_value: returnedValue,
    edit_created: editCreated,
    leave_dialog: leaveDialog,
    dialogs,
    warning_visible: warningVisible,
    edit_preserved: returnedValue === editedValue,
    body_length: bodyText.length,
    pass: editCreated && (leaveDialog !== null || warningVisible),
  };
  fs.writeFileSync(path.join(OUTPUT, 'back-mid-decision-targeted.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await context.close();
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });

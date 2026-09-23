// System Admin E2E: login, walk all 8 stages, inspect a user + RBAC,
// open dataset validation, verify verdict, ask AI, check persistence.
const { chromium } = require('playwright');

const BASE = 'http://127.0.0.1:3001';
const results = [];
const check = (name, ok, extra = '') => {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${extra ? ' — ' + extra : ''}`);
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  page.on('pageerror', e => console.log('PAGEERROR:', String(e).slice(0, 200)));

  await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
  await page.fill('#ds-officer-id', 'OFF-00667');
  await page.fill('#ds-password', 'Test-Admin-42');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/admin', { timeout: 15000 });
  check('login lands on /admin', page.url().includes('/admin'), page.url());

  await page.getByText('System Administration').first().waitFor({ timeout: 15000 });
  await page.waitForFunction(() => document.body.textContent.includes('Step 1 of 8'), null, { timeout: 15000 });
  await page.waitForFunction(() => /Platform counts|System status/.test(document.body.textContent || ''), null, { timeout: 15000 });
  check('admin header + overview', true);
  check('no sidebar', (await page.locator('aside, [data-sidebar]').count()) === 0);

  const waitStep = async (n) => {
    try {
      await page.waitForFunction((x) => document.body.textContent.includes(`Step ${x} of 8`), n, { timeout: 8000 });
      return true;
    } catch { return false; }
  };
  const waitContent = async (re) => {
    try {
      await page.waitForFunction((src) => new RegExp(src, 'i').test(document.body.textContent || ''), re.source, { timeout: 12000 });
      return true;
    } catch { return false; }
  };

  const stageBtn = (s) => page.getByRole('button', { name: new RegExp('^.*' + s.replace(/[&]/g, '.') + '.*$', 'i') }).first();
  const probes = [
    ['Users & RBAC', /Officers \(|Total users|Active users/i, 2, 'users workspace'],
    ['Dataset & Imports', /Import history|Live vs imported|validation/i, 3, 'datasets workspace'],
    ['System Health', /Health —|Last check|latency/i, 4, 'health workspace'],
    ['Integrations', /PostgreSQL|System of record|OTP/i, 5, 'integrations workspace'],
    ['Security & Audit', /Audit-chain integrity|Failed authentication|Role & access/i, 6, 'security workspace'],
    ['Configuration', /Effective configuration|READ-ONLY|deployment-managed/i, 7, 'config workspace'],
    ['Final System Status', /System verdict|Readiness categories|SYSTEM /i, 8, 'final verdict'],
    ['System Overview', /System status|Platform counts/i, 1, 'overview again'],
  ];
  for (const [s, re, n, label] of probes) {
    await stageBtn(s).click();
    check(`${label} on ${s}`, await waitContent(re));
    check(`step indicator ${s}`, await waitStep(n), `want Step ${n}`);
  }

  // user detail + RBAC permissions + audited action validation (reason gate)
  await stageBtn('Users & RBAC').click();
  await waitContent(/Officers \(/);
  await page.locator('main input[placeholder*="Search"]').fill('OFF-06001');
  await page.waitForTimeout(1500);
  await page.getByRole('button', { name: /OFF-06001/ }).first().click();
  check('user detail opens', await waitContent(/Permissions \(|Recent audit activity/));
  check('RBAC permissions listed', await waitContent(/PROCESS_EPOS|AUTH_LOGIN/));
  await page.getByRole('button', { name: /^Deactivate$/ }).click();
  await page.getByPlaceholder('Reason (required)').fill('x');
  const confirmDisabled = await page.getByRole('button', { name: 'Confirm Change' }).isDisabled();
  check('short reason blocks confirm', confirmDisabled);

  // dataset validation evidence
  await stageBtn('Dataset & Imports').click();
  await waitContent(/Import history/);
  const insp = page.getByRole('button', { name: /Inspect .* validation checks/ }).first();
  if (await insp.count() > 0) {
    await insp.click();
    check('validation checks inspectable', await waitContent(/checks passed|FAILED|validation/i));
  } else check('validation checks inspectable', true, 'no imports in scope');

  // AI + persistence
  await stageBtn('Final System Status').click();
  await waitContent(/System verdict/);
  await page.getByRole('button', { name: 'Which integrations are unavailable?' }).click();
  check('AI answers from backend', await waitContent(/Insight|Source:/));

  await page.reload({ waitUntil: 'networkidle' });
  await page.getByText('System Administration').first().waitFor({ timeout: 15000 });
  const t = await page.textContent('body');
  const m = (t || '').match(/Step (\d) of 8/);
  check('stage persists after refresh', m && Number(m[1]) === 8, m ? `Step ${m[1]}` : 'none');

  const failed = results.filter(r => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  await browser.close();
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error('E2E ERROR', e); process.exit(2); });

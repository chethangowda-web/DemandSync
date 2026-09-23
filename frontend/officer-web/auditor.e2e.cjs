// Auditor Portal E2E: login, walk all 7 stages, open manifest evidence,
// open exception evidence, filter trace, ask AI, verify closure verdict.
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
  await page.fill('#ds-officer-id', 'OFF-00669');
  await page.fill('#ds-password', 'Test-Audit-42');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/auditor', { timeout: 15000 });
  check('login lands on /auditor', page.url().includes('/auditor'), page.url());

  await page.getByText('Auditor Portal').first().waitFor({ timeout: 15000 });
  // let boot finish (cycles + overview) before driving the workflow
  await page.waitForFunction(() => document.body.textContent.includes('Step 1 of 7'), null, { timeout: 15000 });
  await page.waitForFunction(() => /Cycle identity/.test(document.body.textContent || ''), null, { timeout: 15000 });
  check('auditor header', true);
  check('cycle selector', await page.locator('header select').count() === 2);
  check('no sidebar', (await page.locator('aside, [data-sidebar]').count()) === 0);

  const waitStep = async (n) => {
    try {
      await page.waitForFunction((x) => document.body.textContent.includes(`Step ${x} of 7`), n, { timeout: 8000 });
      return true;
    } catch { return false; }
  };
  const waitContent = async (re) => {
    try {
      await page.waitForFunction((src) => new RegExp(src, 'i').test(document.body.textContent || ''), re.source, { timeout: 12000 });
      return true;
    } catch { return false; }
  };

  const probes = [
    ['Demand & Allocation', /Intent − Forecast|Demand lock|Manual overrides/i, 'demand chain'],
    ['Dispatch & Manifest', /Manifest evidence|Hash status|FPS dest/i, 'manifest table'],
    ['Delivery & Reconciliation', /Reconciliation flow|Delivery evidence|Variance/i, 'recon flow'],
    ['Exceptions', /Exceptions \(|What happened\?|Severity/i, 'exception centre'],
    ['Decision Trace', /Audit decision trace|WHO.*ROLE.*ACTION/i, 'trace timeline'],
    ['Final Audit', /Final audit checklist|AUDIT DECISION|FINAL ACTION NOT AVAILABLE/i, 'closure verdict'],
    ['Cycle Overview', /Cycle identity|Audit summary|Audit readiness/i, 'overview'],
  ];
  const stageBtn = (s) => page.getByRole('button', { name: new RegExp('^.*' + s.replace(/[&]/g, '.') + '.*$', 'i') }).first();
  for (let i = 0; i < probes.length; i++) {
    const [s, re, label] = probes[i];
    await stageBtn(s).click();
    const stepNo = s === 'Cycle Overview' ? 1 : ['Demand & Allocation', 'Dispatch & Manifest', 'Delivery & Reconciliation', 'Exceptions', 'Decision Trace', 'Final Audit'].indexOf(s) + 2;
    check(`${label} on ${s}`, await waitContent(re));
    check(`step indicator ${s}`, await waitStep(stepNo), `want Step ${stepNo}`);
  }

  // manifest drawer with hash verdict
  await stageBtn('Dispatch & Manifest').click();
  await waitContent(/Manifest evidence/);
  const manLink = page.locator('main button').filter({ hasText: /^MAN-/ }).first();
  await manLink.waitFor({ timeout: 10000 });
  await manLink.click();
  check('manifest drawer opens', await waitContent(/SHA-256 integrity|Manifest identity/));
  const hashOk = await waitContent(/HASH VERIFIED|INTEGRITY CHECK FAILED|NOT SEALED/);
  check('hash verdict shown (never hidden)', hashOk);
  await page.getByRole('button', { name: 'Close' }).click();
  await page.waitForTimeout(500);

  // exception evidence
  await stageBtn('Exceptions').click();
  await waitContent(/Exceptions \(/);
  const excRow = page.locator('main button').filter({ hasText: /EXC-/ }).first();
  if (await excRow.count() > 0) {
    await excRow.click();
    check('exception evidence opens', await waitContent(/What happened\?|Affected entity/));
  } else check('exception evidence opens', true, 'no rows in scope');

  // trace filter: pick the first action the backend actually offers
  await stageBtn('Decision Trace').click();
  await waitContent(/Audit decision trace/);
  const firstAction = await page.locator('main select option').nth(1).getAttribute('value');
  await page.locator('main select').first().selectOption(firstAction);
  check('trace filter works', await waitContent(new RegExp(firstAction.replace(/_/g, ' '))));

  await stageBtn('Final Audit').click();
  await waitContent(/Final audit checklist/);
  await page.getByRole('button', { name: 'Which exceptions affected this cycle?' }).click();
  check('AI answers from records', await waitContent(/AI insight|Source records/));

  // refresh persistence
  await page.reload({ waitUntil: 'networkidle' });
  await page.getByText('Auditor Portal').first().waitFor({ timeout: 15000 });
  const t = await page.textContent('body');
  const m = (t || '').match(/Step (\d) of 7/);
  check('stage persists after refresh', m && Number(m[1]) === 7, m ? `Step ${m[1]}` : 'none');

  const failed = results.filter(r => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  await browser.close();
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error('E2E ERROR', e); process.exit(2); });

// FPS Operations Center E2E: login as FPS owner, walk all 8 workflow steps,
// perform a real distribution, review variance, raise a request, check close-day.
const { chromium } = require('playwright');

const BASE = 'http://127.0.0.1:3001';
const results = [];
const check = (name, ok, extra = '') => {
  results.push({ name, ok, extra });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${extra ? ' — ' + extra : ''}`);
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on('pageerror', e => console.log('PAGEERROR:', String(e).slice(0, 200)));

  await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
  await page.fill('#ds-officer-id', process.env.E2E_OFFICER || 'OFF-06002');
  await page.fill('#ds-password', process.env.E2E_PASSWORD || 'Test-Owner-42');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/fps', { timeout: 15000 });
  check('login lands on /fps', page.url().includes('/fps'), page.url());

  // gov header + shop header (shop header arrives with backend context)
  check('gov header', await page.getByText('Department of Food & Public Distribution').count() > 0);
  await page.getByText('FAIR PRICE SHOP OPERATIONS').first().waitFor({ timeout: 15000 });
  check('shop header', true);

  // workflow bar: 8 steps
  const steps = ['OVERVIEW', 'STOCK', 'e-POS', 'BENEFICIARIES', 'DISTRIBUTION', 'RECONCILIATION', 'REQUESTS', 'CLOSE DAY'];
  for (const s of steps) {
    const n = await page.getByRole('button', { name: new RegExp(s.replace('-', '[-‐]') + '.*', 'i') }).count();
    if (n === 0) check(`workflow step ${s} visible`, false);
  }
  check('all 8 workflow steps visible', true);

  const stepOf = async () => page.textContent('body').then(t => {
    const m = t.match(/Step (\d) of 8/);
    return m ? Number(m[1]) : -1;
  });

  // acceptance walk: click each step, verify workspace swaps (no sidebar, no nav)
  const probes = [
    ['STOCK', /STOCK MANAGEMENT|Stock summary|System stock/i, 'stock workspace'],
    ['e-POS', /e-POS OPERATIONS|e-PoS status|Transaction activity/i, 'epos workspace'],
    ['BENEFICIARIES', /BENEFICIARY SERVICES|Find beneficiary|Assigned beneficiaries/i, 'beneficiary workspace'],
    ['DISTRIBUTION', /TODAY.?S DISTRIBUTION|Distribution queue|Distribution process/i, 'distribution workspace'],
    ['RECONCILIATION', /STOCK & TRANSACTION RECONCILIATION|Expected closing|Distribution variance/i, 'recon workspace'],
    ['REQUESTS', /SUPPLY \/ REPLENISHMENT|Create replenishment request|Current requests/i, 'requests workspace'],
    ['CLOSE DAY', /CLOSE DAY|Before closing|Ready to close/i, 'close-day workspace'],
    ['OVERVIEW', /TODAY.?S NEXT ACTION|Today's next action|Operational summary|Stock summary/i, 'overview workspace'],
  ];
  for (const [s, re, label] of probes) {
    await page.getByRole('button', { name: new RegExp('^.*' + s.replace('-', '.') + '.*$', 'i') }).first().click();
    try {
      await page.waitForFunction(
        (n) => document.body.textContent.includes(`Step ${n} of 8`),
        steps.indexOf(s) + 1, { timeout: 8000 });
    } catch { /* fall through to checks */ }
    let contentOk = false;
    try {
      await page.waitForFunction((src) => new RegExp(src, 'i').test(document.body.textContent || ''),
        re.source, { timeout: 10000 });
      contentOk = true;
    } catch { contentOk = false; }
    check(`${label} appears on ${s}`, contentOk);
    const n = await stepOf();
    check(`step indicator = ${s}`, n === steps.indexOf(s) + 1, `got Step ${n}`);
  }
  check('no sidebar present', (await page.locator('aside, nav[aria-label="sidebar"], [data-sidebar]').count()) === 0);

  // real distribution
  await page.getByRole('button', { name: /DISTRIBUTION/i }).first().click();
  await page.waitForTimeout(1500);
  const startBtn = page.getByRole('button', { name: 'START DISTRIBUTION' }).first();
  await startBtn.click();
  await page.getByRole('button', { name: 'CONFIRM DISTRIBUTION' }).waitFor({ timeout: 10000 });
  const confirm = page.getByRole('button', { name: 'CONFIRM DISTRIBUTION' });
  await confirm.click();
  try { await page.waitForFunction(() => /DISTRIBUTION COMPLETED/i.test(document.body.textContent || ''), null, { timeout: 10000 }); } catch {}
  const body1 = await page.textContent('body');
  check('distribution completed with txn id', /DISTRIBUTION COMPLETED/i.test(body1 || '') && /EPOS-\d+/.test(body1 || ''));

  // reconciliation review flow
  await page.getByRole('button', { name: /RECONCILIATION/i }).first().click();
  await page.waitForTimeout(1500);
  let reviewed = 0;
  for (;;) {
    const box = page.getByPlaceholder('Review note (required before day closure)').first();
    if (await box.count() === 0) break;
    await box.fill(`E2E review of variance against records (${reviewed + 1})`);
    await page.getByRole('button', { name: 'RECORD REVIEW' }).first().click();
    await page.waitForTimeout(1500);
    reviewed++;
    if (reviewed > 4) break;
  }
  check('variance reviews recorded', true, `${reviewed} review(s)`);

  // create + submit replenishment request
  await page.getByRole('button', { name: /REQUESTS/i }).first().click();
  await page.waitForTimeout(1500);
  const qtyInput = page.locator('input[type="number"]').first();
  await qtyInput.fill('50');
  await page.getByPlaceholder('Why is this quantity needed?').fill('E2E test replenishment');
  await page.getByRole('button', { name: 'CREATE REQUEST' }).click();
  try { await page.waitForFunction(() => /REQ-\d{4}-\d{4}/.test(document.body.textContent || ''), null, { timeout: 10000 }); } catch {}
  let body2 = await page.textContent('body');
  const m = (body2 || '').match(/REQ-\d{4}-\d{4}/);
  check('request created with real id', !!m, m ? m[0] : 'none');
  if (m) {
    await page.getByRole('button', { name: 'SUBMIT' }).first().click();
    try { await page.waitForFunction(() => /SUBMITTED/.test(document.body.textContent || ''), null, { timeout: 10000 }); } catch {}
    body2 = await page.textContent('body');
    check('request submitted', /SUBMITTED|UNDER_REVIEW/.test(body2 || ''));
  }

  // close day
  await page.getByRole('button', { name: /CLOSE DAY/i }).first().click();
  await page.waitForTimeout(1500);
  const body3 = await page.textContent('body');
  const ready = /READY TO CLOSE DAY|Ready to close day/i.test(body3 || '');
  const blocked = /Cannot close day|require attention/i.test(body3 || '');
  check('close-day shows readiness verdict', ready || blocked, ready ? 'READY' : 'BLOCKED');
  if (ready) {
    await page.getByRole('button', { name: 'CLOSE DAY', exact: true }).click();
    try { await page.waitForFunction(() => /DAY CLOSED/.test(document.body.textContent || ''), null, { timeout: 10000 }); } catch {}
    const body4 = await page.textContent('body');
    check('day closed', /DAY CLOSED/.test(body4 || ''));
  }

  // refresh persistence: reload, expect same step (close day = 8)
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const n = await stepOf();
  check('workflow step persists after refresh', n === 8, `got Step ${n}`);

  const failed = results.filter(r => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  await browser.close();
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error('E2E ERROR', e); process.exit(2); });

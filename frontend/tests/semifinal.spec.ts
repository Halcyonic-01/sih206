import {test, expect, type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import path from 'node:path';

const root = path.resolve('..');
const privateDir = path.resolve(root, process.env.SEMIFINAL_DATA_DIR || 'data/semifinal/data');
function credentials() {
  return Object.fromEntries(['demo', 'authority', 'staff'].flatMap(name =>
    readFileSync(path.join(privateDir, `${name}-credentials.txt`), 'utf8').split(/\r?\n/)
      .filter(line => line.includes(': ')).map(line => line.split(': '))));
}
async function login(page: Page, username: string) {
  const passwords = credentials();
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(passwords[username]);
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await expect(page.getByRole('heading', {name: /^Welcome/})).toBeVisible();
}

test.beforeAll(() => {
  const url = new URL(process.env.PLAYWRIGHT_BASE_URL || process.env.PORTAL_URL || 'http://127.0.0.1:8010');
  if (process.env.SEMIFINAL_DISPOSABLE !== '1' || !['127.0.0.1', 'localhost'].includes(url.hostname)) {
    throw new Error('Use a seeded disposable loopback server and set SEMIFINAL_DISPOSABLE=1. Never use the normal demo database.');
  }
});

test('fresh release wizard, three protected clearance PDFs, authorization and completion with external networking blocked', async ({browser}) => {
  test.setTimeout(180000);
  const scenario = JSON.parse(readFileSync(path.join(privateDir, 'release-scenario.json'), 'utf8'));
  const context = await browser.newContext();
  const external: string[] = [];
  await context.route('**/*', route => {
    const host = new URL(route.request().url()).hostname;
    if (host === '127.0.0.1' || host === 'localhost') return route.continue();
    external.push(host); return route.abort();
  });
  const page = await context.newPage();
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await login(page, 'institution_a');
  await page.goto(`/records/${scenario.id}`);
  await page.getByRole('button', {name: 'Request release', exact: true}).click();
  await page.getByLabel('Reason', {exact: true}).fill('Synthetic term complete; please review supporting evidence.');
  await page.getByRole('button', {name: 'Next', exact: true}).click();
  const declarations = page.locator('select');
  await expect(declarations).toHaveCount(6);
  for (const select of await declarations.all()) await select.selectOption('true');
  await page.getByRole('button', {name: 'Next', exact: true}).click();
  await expect(page.getByText('uploaded and readable', {exact: false}).first()).toBeVisible();
  await page.getByRole('button', {name: 'Next', exact: true}).click();
  await page.getByRole('button', {name: 'Submit release request', exact: true}).click();
  await expect(page).toHaveURL(/\/releases\/\d+$/);
  const caseId = Number(new URL(page.url()).pathname.split('/').pop());
  await context.close();
  let evidencePath = '';
  for (const unit of ['pgrc', 'vigilance', 'grants']) {
    const unitContext = await browser.newContext();
    await unitContext.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort());
    const reviewer = await unitContext.newPage();
    await login(reviewer, `clearance_${unit}`);
    await reviewer.goto('/clearance-tasks');
    const form = reviewer.getByRole('group', {name: `Decision for case ${caseId}`, exact: true});
    await form.getByLabel('Supporting clearance PDF').setInputFiles(path.join(root, 'fixtures/release-evidence.pdf'));
    await form.getByRole('button', {name: 'Upload supporting PDF', exact: true}).click();
    await expect(form.getByLabel('Reviewed supporting PDF').locator('option')).toHaveCount(2);
    await form.getByLabel('Reviewed supporting PDF').selectOption({index: 1});
    await form.getByRole('button', {name: 'View supporting PDF', exact: true}).click();
    await expect.poll(() => form.locator('canvas').evaluate((el: HTMLCanvasElement) => el.width)).toBeGreaterThan(0);
    await expect(form.locator('.ant-spin-spinning')).toHaveCount(0);
    if (unit === 'pgrc') {
      await reviewer.setViewportSize({width: 390, height: 844});
      await expect.poll(() => reviewer.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
      await expect(form.locator('.ant-spin-spinning')).toHaveCount(0);
      await reviewer.screenshot({path: path.join(root, 'planning/browser-results/semifinal-clearance-mobile.png'), fullPage: true});
    }
    if (unit === 'pgrc') evidencePath = (await form.getByRole('link', {name: 'Download original'}).getAttribute('href'))!;
    await form.getByLabel('Reason', {exact: true}).fill(`Reviewed synthetic ${unit} PDF; no objection.`);
    await form.getByLabel('Reviewed evidence reference').fill(`${unit.toUpperCase()}/2026/SEMIFINAL`);
    await form.getByRole('button', {name: 'cleared', exact: true}).click();
    await expect(form).not.toBeVisible();
    await unitContext.close();
  }
  const staff = await browser.newContext();
  await staff.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort());
  const officer = await staff.newPage();
  await login(officer, 'officer');
  await officer.goto(`/releases/${caseId}`);
  await officer.getByLabel('Reason / completion notes').fill('Reviewed synthetic documents, all three clearance PDFs and penalties.');
  await officer.getByRole('button', {name: 'Record officer checklist and penalty review complete', exact: true}).click();
  await expect(officer.getByText('Officer review complete: Yes.', {exact: false})).toBeVisible();
  await staff.close();
  const authorityContext = await browser.newContext();
  await authorityContext.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort());
  const authority = await authorityContext.newPage();
  await login(authority, 'authority');
  await authority.goto(`/releases/${caseId}`);
  await authority.getByLabel('Reason / completion notes').fill('Independently reviewed synthetic evidence and all clearances.');
  await authority.getByRole('button', {name: 'Record authority authorization', exact: true}).click();
  await expect(authority.getByText('Release authorized; completion pending.', {exact: true})).toBeVisible();
  await authority.getByLabel('Reason / completion notes').fill('Issue unsigned synthetic demonstration letter.');
  await authority.getByRole('button', {name: 'Issue letter (unsigned)', exact: true}).click();
  const letter = authority.getByRole('button', {name: 'Download protected letter', exact: true});
  await expect(letter).toBeVisible();
  const download = authority.waitForEvent('download'); await letter.click();
  const saved = await download; expect(await saved.failure()).toBeNull();
  await authority.getByLabel('Reason / completion notes').fill('Reviewed new synthetic handover evidence; complete.');
  await authority.getByLabel('New completion PDF').setInputFiles(path.join(root, 'fixtures/release-evidence.pdf'));
  await authority.getByRole('button', {name: 'Record evidence-backed completion', exact: true}).click();
  await expect(authority.getByText('Completed', {exact: true}).first()).toBeVisible();
  await authority.reload();
  await expect(authority.getByText('Completed', {exact: true}).first()).toBeVisible();
  await authorityContext.close();
  const foreignContext = await browser.newContext();
  const foreign = await foreignContext.newPage();
  await login(foreign, 'institution_b');
  expect((await foreign.request.get(evidencePath)).status()).toBe(404);
  await foreignContext.close();
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
});

test('sign-out from records starts the next account at home', async ({page}) => {
  await login(page, 'officer');
  await page.goto('/records');
  await page.getByRole('button', {name: 'Account menu'}).click();
  await page.getByRole('menuitem', {name: 'Sign out'}).click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page, 'institution_b');
  await expect(page).toHaveURL(/\/$/);
});

import {test, expect, type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import path from 'node:path';

const root = path.resolve('..');
const passwords = Object.fromEntries(readFileSync(path.join(root, 'data/demo-credentials.txt'), 'utf8')
  .split(/\r?\n/).filter(line => line.includes(': ')).map(line => line.split(': ')));

async function login(page: Page, username: string) {
  await page.goto('/accounts/login/?next=/workspace/');
  await page.getByLabel('Username:').fill(username);
  await page.getByLabel('Password:').fill(passwords[username]);
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Deposit records'})).toBeVisible();
}

async function openRecord(page: Page, reference: string) {
  await page.goto('/workspace/');
  await page.getByRole('searchbox', {name: 'Search deposit records'}).fill(reference);
  await page.getByRole('searchbox', {name: 'Search deposit records'}).press('Enter');
  await page.getByRole('button', {name: reference, exact: true}).click();
  await expect(page.getByRole('heading', {name: reference, exact: true})).toBeVisible();
}

test('submission, PDF review, discrepancy, correction, acceptance and renewal', async ({browser}) => {
  const ownerContext = await browser.newContext();
  const officerContext = await browser.newContext();
  const owner = await ownerContext.newPage();
  const officer = await officerContext.newPage();
  const reference = `SYNTHETIC-E2E-${Date.now()}`;
  await login(owner, 'institution_a');
  await owner.getByRole('button', {name: 'New deposit', exact: true}).click();
  await owner.getByLabel('Instrument reference', {exact: true}).fill(reference);
  await owner.getByLabel('Issuing bank', {exact: true}).fill('Synthetic browser test bank');
  await owner.getByLabel('Amount (INR)', {exact: true}).fill('500000.25');
  await owner.getByLabel('Issue / payment date', {exact: true}).fill('2026-01-01');
  await owner.getByLabel('Maturity / recorded end date', {exact: true}).fill('2027-01-01');
  await owner.locator('input[type=file]').setInputFiles(path.join(root, 'fixtures/sample-fdr.pdf'));
  await owner.getByRole('button', {name: 'Save draft', exact: true}).click();
  await expect(owner.getByRole('heading', {name: reference, exact: true})).toBeVisible();
  await owner.getByRole('tab', {name: /^Documents/}).click();
  await expect.poll(() => owner.locator('canvas').evaluate((el: HTMLCanvasElement) => el.width)).toBeGreaterThan(0);
  await owner.getByRole('button', {name: 'Extract with AI', exact: true}).click();
  await expect(owner.getByText('AI is off. Continue manual document review.', {exact: true})).toBeVisible();
  await owner.getByRole('button', {name: 'Read with local OCR', exact: true}).click();
  await expect(owner.getByText('Processed locally. Low-confidence, missing and conflicting fields require manual entry.', {exact: true})).toBeVisible();
  await owner.getByRole('button', {name: 'Submit for review', exact: true}).click();
  await owner.getByRole('button', {name: 'Record action', exact: true}).click();
  await expect(owner.getByText('SUBMITTED', {exact: true})).toBeVisible();

  await login(officer, 'officer');
  await openRecord(officer, reference);
  await officer.getByRole('button', {name: 'Add observation', exact: true}).click();
  await officer.getByLabel('Severity', {exact: true}).click();
  await officer.getByText('Blocking', {exact: true}).click();
  await officer.getByLabel('Observation', {exact: true}).fill('Synthetic amount discrepancy: inspect and correct.');
  await officer.getByRole('button', {name: 'Record action', exact: true}).click();
  await expect(officer.getByRole('dialog')).not.toBeVisible();
  await officer.getByRole('button', {name: 'Request corrections', exact: true}).click();
  await officer.getByLabel('Reason', {exact: true}).fill('Please correct the declared amount.');
  await officer.getByRole('button', {name: 'Record action', exact: true}).click();
  await expect(officer.getByText('CHANGES_REQUESTED', {exact: true})).toBeVisible();

  await owner.reload();
  await openRecord(owner, reference);
  await owner.getByRole('button', {name: 'Edit draft', exact: true}).click();
  await owner.getByLabel('Amount (INR)', {exact: true}).fill('600000.00');
  await owner.getByRole('button', {name: 'Save draft', exact: true}).click();
  await expect(owner.getByRole('dialog')).not.toBeVisible();
  await owner.getByRole('button', {name: 'Submit for review', exact: true}).click();
  await owner.getByRole('button', {name: 'Record action', exact: true}).click();
  await expect(owner.getByText('SUBMITTED', {exact: true})).toBeVisible();

  await openRecord(officer, reference);
  await officer.getByRole('tab', {name: 'Checks & observations', exact: true}).click();
  await officer.getByRole('button', {name: 'Resolve', exact: true}).click();
  await officer.getByLabel('How was it resolved?', {exact: true}).fill('Checked synthetic supporting evidence and corrected value.');
  await officer.getByRole('button', {name: 'Record action', exact: true}).click();
  await expect(officer.getByRole('dialog')).not.toBeVisible();
  await officer.getByRole('button', {name: 'Accept for tracking', exact: true}).click();
  await officer.getByLabel('Reason', {exact: true}).fill('Human review of synthetic example completed.');
  await officer.getByRole('button', {name: 'Record action', exact: true}).click();
  await expect(officer.getByText('ACCEPTED', {exact: true})).toBeVisible();
  await officer.getByRole('tab', {name: 'Verification', exact: true}).click();
  await expect(officer.getByText('OFFICER_REVIEW', {exact: true})).toBeVisible();
  await officer.screenshot({path: path.join(root, '../../outputs/verification-workspace.png'), fullPage: true});

  await openRecord(owner, reference);
  await owner.getByRole('button', {name: 'Create renewal', exact: true}).click();
  await owner.getByLabel('Instrument reference', {exact: true}).fill(reference + '-RENEWAL');
  await owner.getByLabel('Issue / payment date', {exact: true}).fill('2027-01-01');
  await owner.getByLabel('Maturity / recorded end date', {exact: true}).fill('2028-01-01');
  await owner.getByRole('button', {name: 'Save draft', exact: true}).click();
  await expect(owner.getByRole('heading', {name: reference + '-RENEWAL', exact: true})).toBeVisible();
  await ownerContext.close(); await officerContext.close();
});

test('dashboard, responsive list, and synthetic reconciliation preview', async ({page}) => {
  await login(page, 'officer');
  await page.getByRole('tab', {name: 'Dashboard', exact: true}).click();
  await expect(page.getByText('Upcoming maturities by month', {exact: true})).toBeVisible();
  await page.screenshot({path: path.join(root, '../../outputs/dashboard-workspace.png'), fullPage: true});
  await page.getByRole('tab', {name: 'Reconciliation', exact: true}).click();
  await page.locator('input[type=file]').setInputFiles(path.join(root, 'fixtures/synthetic-statement.csv'));
  await page.getByRole('button', {name: 'Preview matches', exact: true}).click();
  const reconciliation = page.getByRole('tabpanel', {name: 'Reconciliation'});
  await expect(reconciliation.getByText('SIMULATED_MATCH', {exact: true})).toBeVisible();
  await expect(reconciliation.getByText('DISCREPANCY', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: 'Record previewed batch', exact: true}).click();
  await expect(page.getByText(/Synthetic batch \d+ recorded|already imported/)).toBeVisible();
  await page.setViewportSize({width: 390, height: 844});
  await page.getByLabel('Workspace section', {exact: true}).selectOption('records');
  await expect(page.getByRole('heading', {name: 'Deposit records'})).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('global search cannot expose another institution’s record', async ({page}) => {
  await login(page, 'institution_b');
  const search = page.getByRole('searchbox', {name: 'Global record search', exact: true});
  await search.fill('YASH-RTGS-MATCH');
  await search.press('Enter');
  await expect(page.getByText('No records match these filters', {exact: true})).toBeVisible();
  await expect(page.getByRole('button', {name: 'YASH-RTGS-MATCH', exact: true})).toHaveCount(0);
});

test('notification inbox and delivery operations are available to the officer', async ({page}) => {
  await login(page, 'officer');
  await page.getByRole('tab', {name: 'Notifications', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Notifications', exact: true})).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Delivery operations', exact: true})).toBeVisible();
  await expect(page.getByText('Deposit submitted for review', {exact: true}).first()).toBeVisible();
});

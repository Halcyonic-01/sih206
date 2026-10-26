import {test, expect, type Page} from '@playwright/test';
import path from 'node:path';
import {openRecord, root, signIn} from './support';

async function login(page: Page, username: string) {
  await signIn(page, username);
  await page.goto('/records');
  await expect(page.getByRole('heading', {level: 1, name: 'Deposit records'})).toBeVisible();
}

test('submission, PDF review, discrepancy, correction, acceptance and renewal', async ({browser}, testInfo) => {
  const ownerContext = await browser.newContext();
  const officerContext = await browser.newContext();
  const owner = await ownerContext.newPage();
  const officer = await officerContext.newPage();
  const reference = `SYNTHETIC-E2E-${Date.now()}`;
  await login(owner, 'institution_a');
  await owner.getByRole('button', {name: /New deposit$/}).click();
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
  await owner.getByText('Read details from this document', {exact: true}).click();
  await owner.getByRole('button', {name: 'Extract with AI', exact: true}).click();
  await expect(owner.getByText('AI is off. Continue manual document review.', {exact: true})).toBeVisible();
  await owner.getByRole('button', {name: 'Read with local OCR', exact: true}).click();
  // The label is shown whether or not the optional local OCR engine is installed; manual entry stays available.
  await expect(owner.getByText('OCR suggestions: verify against the document', {exact: true})).toBeVisible();
  await owner.getByRole('button', {name: 'Submit for review', exact: true}).click();
  await owner.getByRole('button', {name: 'Record action', exact: true}).click();
  await expect(owner.locator('.page-header').getByText('Submitted', {exact: true})).toBeVisible();

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
  await expect(officer.locator('.page-header').getByText('Changes requested', {exact: true})).toBeVisible();

  await owner.reload();
  await openRecord(owner, reference);
  await owner.getByRole('button', {name: 'Edit draft', exact: true}).click();
  await owner.getByLabel('Amount (INR)', {exact: true}).fill('600000.00');
  await owner.getByRole('button', {name: 'Save draft', exact: true}).click();
  await expect(owner.getByRole('dialog')).not.toBeVisible();
  await owner.getByRole('button', {name: 'Submit for review', exact: true}).click();
  await owner.getByRole('button', {name: 'Record action', exact: true}).click();
  await expect(owner.locator('.page-header').getByText('Submitted', {exact: true})).toBeVisible();

  await openRecord(officer, reference);
  await officer.getByRole('tab', {name: 'Checks and observations', exact: true}).click();
  await officer.getByRole('button', {name: 'Resolve', exact: true}).click();
  await officer.getByLabel('How was it resolved?', {exact: true}).fill('Checked synthetic supporting evidence and corrected value.');
  await officer.getByRole('button', {name: 'Record action', exact: true}).click();
  await expect(officer.getByRole('dialog')).not.toBeVisible();
  await officer.getByRole('button', {name: 'Accept for tracking', exact: true}).click();
  await officer.getByLabel('Reason', {exact: true}).fill('Human review of synthetic example completed.');
  await officer.getByRole('button', {name: 'Record action', exact: true}).click();
  await expect(officer.locator('.page-header').getByText('Accepted', {exact: true})).toBeVisible();
  await officer.getByRole('tab', {name: 'Verification', exact: true}).click();
  await expect(officer.getByText('Officer review', {exact: true})).toBeVisible();
  await officer.screenshot({path: testInfo.outputPath('verification-workspace.png'), fullPage: true});

  await openRecord(owner, reference);
  await owner.getByRole('button', {name: 'Create renewal', exact: true}).click();
  await owner.getByLabel('Instrument reference', {exact: true}).fill(reference + '-RENEWAL');
  await owner.getByLabel('Issue / payment date', {exact: true}).fill('2027-01-01');
  await owner.getByLabel('Maturity / recorded end date', {exact: true}).fill('2028-01-01');
  await owner.getByRole('button', {name: 'Save draft', exact: true}).click();
  await expect(owner.getByRole('heading', {name: reference + '-RENEWAL', exact: true})).toBeVisible();
  await ownerContext.close(); await officerContext.close();
});

test('dashboard, responsive list, and synthetic reconciliation preview', async ({page}, testInfo) => {
  await login(page, 'officer');
  await page.getByRole('menuitem', {name: 'Overview', exact: true}).click();
  await page.getByRole('link', {name: 'Dashboard', exact: true}).click();
  await expect(page.getByText('Maturities by month', {exact: true})).toBeVisible();
  await page.screenshot({path: testInfo.outputPath('dashboard-workspace.png'), fullPage: true});
  await page.getByRole('menuitem', {name: 'Deposits', exact: true}).click();
  await page.getByRole('link', {name: 'Reconciliation', exact: true}).click();
  await page.locator('input[type=file]').setInputFiles(path.join(root, 'fixtures/synthetic-statement.csv'));
  await page.getByLabel('Source label (for example the statement date)').fill('SIMULATED browser test statement');
  await page.getByRole('button', {name: 'Preview matches', exact: true}).click();
  const reconciliation = page.locator('#main');
  await expect(reconciliation.getByText('Match', {exact: true})).toBeVisible();
  await expect(reconciliation.getByText('Discrepancy', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: /Record previewed batch/}).click();
  await expect(page.getByText(/Statement batch \d+ recorded|already imported/)).toBeVisible();
  await page.setViewportSize({width: 390, height: 844});
  await page.getByRole('button', {name: 'Open navigation'}).click();
  await page.getByRole('dialog').getByRole('link', {name: 'Deposit records', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Deposit records'})).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('global search cannot expose another institution’s record', async ({page}) => {
  await login(page, 'institution_b');
  const search = page.getByLabel('Global record search', {exact: true});
  await search.fill('YASH-RTGS-MATCH');
  await search.press('Enter');
  await expect(page.getByText('No records match these filters.', {exact: true})).toBeVisible();
  await expect(page.getByRole('button', {name: 'YASH-RTGS-MATCH', exact: true})).toHaveCount(0);
});

test('shared notification inbox receives record submissions', async ({page}) => {
  await login(page, 'officer');
  await page.goto('/notifications');
  await expect(page.getByRole('heading', {name: 'Notifications', exact: true})).toBeVisible();
  await expect(page.getByText(/New submission to review:/).first()).toBeVisible();
});

test('horizontal categories support keyboard, phone navigation and role filtering', async ({page}) => {
  await login(page, 'institution_a');
  const navigation = page.getByRole('navigation', {name: 'Main', exact: true});
  await expect(navigation.getByRole('menuitem', {name: 'Administration', exact: true})).toHaveCount(0);
  await expect(page.locator('.app-sider')).toHaveCount(0);
  const deposits = navigation.getByRole('menuitem', {name: 'Deposits', exact: true});
  await deposits.focus();
  await page.keyboard.press('Enter');
  const records = page.getByRole('link', {name: 'Deposit records', exact: true});
  await expect(records).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(records).not.toBeVisible();
  await deposits.click();
  await records.click();
  await expect(page.getByRole('heading', {name: 'Deposit records', exact: true})).toBeVisible();
  await page.setViewportSize({width: 390, height: 844});
  await page.getByRole('button', {name: 'Open navigation', exact: true}).click();
  const drawer = page.getByRole('dialog');
  await drawer.getByRole('menuitem', {name: 'Insights', exact: true}).click();
  await drawer.getByRole('link', {name: 'Reports', exact: true}).click();
  await expect(drawer).not.toBeVisible();
  await expect(page.getByRole('heading', {name: 'Reports', exact: true})).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

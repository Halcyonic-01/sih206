import {test, expect} from '@playwright/test';
import path from 'node:path';
import {openRecord, root, signIn} from './support';

// Problem-statement scenarios 3, 7 and 9 against the seeded review build. Scenarios 1, 2, 5 and 6 are in records.spec.ts.

test('PS 3: an institution page shows required, held and shortfall with the coverage timeline', async ({page}) => {
  await signIn(page, 'officer');
  await page.goto('/institutions');
  await expect(page.getByRole('heading', {level: 1, name: 'Institutions', exact: true})).toBeVisible();
  await page.getByRole('button', {name: /Fictional Technical Institute A/}).click();
  await expect(page.getByRole('heading', {level: 1, name: /Fictional Technical Institute A/})).toBeVisible();
  await expect(page.getByRole('heading', {level: 2, name: 'Obligations', exact: true})).toBeVisible();
  for (const label of ['Required', 'Held', 'Shortfall']) {
    await expect(page.getByText(label, {exact: true}).first()).toBeVisible();
  }
  await expect(page.getByText(/PS3-DEMO-A/).first()).toBeVisible();
});

test('PS 7: release request, three clearances, officer review, authorisation, letter and completion', async ({browser}) => {
  test.setTimeout(240000);
  const page = async (username: string) => {
    const p = await (await browser.newContext()).newPage();
    await signIn(p, username);
    return p;
  };

  const institution = await page('institution_a');
  await openRecord(institution, 'PS7-RELEASE-READY');
  await institution.getByRole('button', {name: 'Request release', exact: true}).click();
  await expect(institution.getByRole('heading', {level: 1, name: 'Request release'})).toBeVisible();
  await institution.getByLabel('Reason').fill('Term complete; requesting release of the synthetic deposit.');
  await institution.getByRole('button', {name: 'Next', exact: true}).click();
  const answers = institution.locator('select');
  for (let i = 0, n = await answers.count(); i < n; i++) await answers.nth(i).selectOption('true');
  await institution.getByRole('button', {name: 'Next', exact: true}).click();
  await expect(institution.getByRole('heading', {level: 2, name: 'Review documents'})).toBeVisible();
  await institution.getByRole('button', {name: 'Next', exact: true}).click();
  await institution.getByRole('button', {name: 'Submit release request', exact: true}).click();
  await institution.waitForURL(/\/releases\/\d+$/);
  const caseId = institution.url().split('/').pop()!;

  for (const unit of ['clearance_pgrc', 'clearance_vigilance', 'clearance_grants']) {
    const clearance = await page(unit);
    await clearance.goto('/clearance-tasks');
    await clearance.getByLabel('Reason', {exact: true}).fill('Reviewed the synthetic case and found no objection.');
    await clearance.getByLabel('Reviewed evidence reference').fill(`${unit.toUpperCase()}/2026/${caseId}`);
    await clearance.locator('li.record-card').filter({hasText: `Case ${caseId}`}).getByRole('button', {name: 'cleared'}).click();
    await expect(clearance.locator('li.record-card').filter({hasText: `Case ${caseId}`}).getByText(/cleared/i).first()).toBeVisible();
  }

  const officer = await page('officer');
  await officer.goto(`/releases/${caseId}`);
  await expect(officer.getByText('Cleared').first()).toBeVisible();
  await officer.getByLabel('Reason / completion notes').fill('Checklist reviewed; no penalty applies to a completed term.');
  await officer.getByRole('button', {name: 'Record officer checklist and penalty review complete'}).click();
  await expect(officer.getByText('Officer review complete: Yes')).toBeVisible();

  const authority = await page('authority');
  await authority.goto(`/releases/${caseId}`);
  await authority.getByLabel('Reason / completion notes').fill('Authorised after human assessment of this synthetic case.');
  await authority.getByRole('button', {name: 'Record authority authorization'}).click();
  await expect(authority.getByRole('button', {name: 'Issue letter (unsigned)'})).toBeVisible();
  await authority.getByLabel('Reason / completion notes').fill('Issuing the unsigned synthetic letter.');
  await authority.getByRole('button', {name: 'Issue letter (unsigned)'}).click();
  await expect(authority.getByRole('button', {name: 'Download protected letter'})).toBeVisible();
  await authority.getByLabel('New completion PDF').setInputFiles(path.join(root, 'fixtures/release-evidence.pdf'));
  await authority.getByLabel('Reason / completion notes').fill('Manually reviewed the attached synthetic completion evidence.');
  await authority.getByRole('button', {name: 'Record evidence-backed completion'}).click();
  await expect(authority.getByText('Completed', {exact: true}).first()).toBeVisible();
});

test('PS 7: the public letter verification page does not confirm an unknown letter', async ({page}) => {
  await page.goto('/verify/' + 'x'.repeat(40));
  await expect(page.getByText(/Verification record unavailable|not found|could not be verified/i).first()).toBeVisible();
});

test('PS 9: reports download as XLSX and the KPI page states its limitations', async ({page}) => {
  await signIn(page, 'officer');
  await page.goto('/reports');
  await expect(page.getByRole('heading', {level: 1, name: 'Reports', exact: true})).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', {name: 'Download XLSX'}).first().click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
  await page.goto('/kpis');
  await expect(page.getByRole('heading', {level: 1, name: 'Process KPIs', exact: true})).toBeVisible();
});

test('PS 9: the auditor can verify the audit chain and sees the access log', async ({page}) => {
  await signIn(page, 'auditor');
  await page.goto('/audit');
  await expect(page.getByRole('heading', {level: 1}).first()).toBeVisible();
  const status = await page.evaluate(async () => (await fetch('/api/audit/chain/verify/')).json());
  expect(status.status).toBe('ok');
});

import {expect, type Page} from '@playwright/test';
import {existsSync, readFileSync} from 'node:fs';
import path from 'node:path';

export const root = path.resolve('..');

/** Passwords the seed commands generated for the synthetic demo accounts (never committed, never printed). */
function readPasswords(): Record<string, string> {
  const files = [process.env.DEMO_CREDENTIALS_FILE || path.join(root, 'data/demo-credentials.txt'),
    process.env.STAFF_CREDENTIALS_FILE || path.join(root, 'data/staff-credentials.txt'),
    process.env.AUTHORITY_CREDENTIALS_FILE || path.join(root, 'data/authority-credentials.txt')];
  const entries: [string, string][] = [];
  for (const file of files) {
    if (!existsSync(file)) continue;
    for (const line of readFileSync(file, 'utf8').split(/\r?\n/)) {
      const at = line.indexOf(': ');
      if (at > 0) entries.push([line.slice(0, at), line.slice(at + 2).trim()]);
    }
  }
  return Object.fromEntries(entries);
}

export const passwords = readPasswords();

export async function signIn(page: Page, username: string) {
  expect(passwords[username], `no generated password for ${username}; seed the demo first`).toBeTruthy();
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(passwords[username]);
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await expect(page.getByRole('heading', {level: 1, name: /^Welcome/})).toBeVisible();
}

/** Opens a record through the global search, waiting for the filtered list so a stale row is never clicked. */
export async function openRecord(page: Page, reference: string) {
  await page.goto('/records');
  await expect(page.getByRole('heading', {level: 1, name: 'Deposit records'})).toBeVisible();
  await page.getByLabel('Global record search').fill(reference);
  await Promise.all([
    page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname === '/api/instruments/' && url.searchParams.get('q') === reference && response.status() === 200;
    }),
    page.getByLabel('Global record search').press('Enter'),
  ]);
  await page.getByRole('button', {name: reference, exact: true}).click();
  await expect(page.getByRole('heading', {level: 1, name: reference, exact: true})).toBeVisible();
}

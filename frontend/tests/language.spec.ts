import {test, expect, type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import path from 'node:path';

const root=path.resolve('..');
const privateDir=path.resolve(root,process.env.SEMIFINAL_DATA_DIR || 'data/semifinal/data');
const passwords=Object.fromEntries(readFileSync(path.join(privateDir,'demo-credentials.txt'),'utf8').split(/\r?\n/)
  .filter(line=>line.includes(': ')).map(line=>line.split(': ')));
test.beforeAll(()=>{if(process.env.SEMIFINAL_DISPOSABLE!=='1')throw new Error('Use the disposable rehearsal profile.');});
async function login(page:Page){
  await page.goto('/login');await page.getByLabel('Username').fill('officer');
  await page.getByLabel('Password',{exact:true}).fill(passwords.officer);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:/Welcome/})).toBeVisible();
}

test('login toggle persists across reload and keeps entered credentials',async({page})=>{
  await page.goto('/login');
  await page.getByLabel('Username').fill('example-unchanged');
  await page.getByRole('button',{name:/हिन्दी/}).click();
  await expect(page.getByRole('heading',{name:'साइन इन करें',exact:true})).toBeVisible();
  await expect(page.getByLabel('उपयोगकर्ता नाम')).toHaveValue('example-unchanged');
  await expect(page.locator('html')).toHaveAttribute('lang','hi');
  await page.reload();
  await expect(page.getByRole('heading',{name:'साइन इन करें',exact:true})).toBeVisible();
  await page.getByRole('button',{name:/English/}).click();
  await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
});

test('unsaved deposit data and dates survive modal language changes; navigation and help translate',async({page})=>{
  // Institution owns deposit creation; reuse its synthetic credentials only.
  await page.goto('/login');await page.getByLabel('Username').fill('institution_a');
  await page.getByLabel('Password',{exact:true}).fill(passwords.institution_a);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:/Welcome/})).toBeVisible();
  await page.goto('/records');await page.getByRole('button',{name:/New deposit$/}).click();
  const dialog=page.getByRole('dialog');
  await dialog.getByLabel('Instrument reference',{exact:true}).fill('LANG-KEEP-REFERENCE');
  await dialog.getByLabel('Issuing bank',{exact:true}).fill('Dashboard');
  await dialog.getByLabel('Amount (INR)',{exact:true}).fill('500000.25');
  await dialog.getByLabel('Issue / payment date',{exact:true}).fill('2026-10-27');
  await dialog.getByRole('button',{name:/हिन्दी/}).click();
  await expect(dialog.getByLabel('लिखत संदर्भ')).toHaveValue('LANG-KEEP-REFERENCE');
  await expect(dialog.getByLabel('जारीकर्ता बैंक')).toHaveValue('Dashboard');
  await expect(dialog.getByLabel('राशि (INR)')).toHaveValue('500000.25');
  await expect(dialog.getByLabel('जारी / भुगतान तिथि')).toHaveValue('2026-10-27');
  await expect(dialog.getByText('रुपयों में, अधिकतम दो दशमलव अंकों के साथ।')).toBeVisible();
  await dialog.getByRole('button',{name:/English/}).click();
  await expect(dialog.getByLabel('Instrument reference',{exact:true})).toHaveValue('LANG-KEEP-REFERENCE');
  await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole('button',{name:/हिन्दी/}).click();
  await expect(page.getByRole('heading',{name:'जमा अभिलेख',exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await expect(page.getByText('फ़िल्टर',{exact:true})).toBeVisible();
  await page.screenshot({path:path.join(root,'planning/browser-results/hindi-records-mobile.png'),fullPage:true});
});

test('system notification text translates while its stored references and dates remain unchanged',async({page})=>{
  await login(page);
  const before=await (await page.request.get('/api/notifications/')).json();
  const item=before.results.find((r:{translations?:{hi?:{subject:string}}})=>r.translations?.hi);
  expect(item).toBeTruthy();
  await page.goto('/notifications');
  await page.getByRole('button',{name:/हिन्दी/}).click();
  await expect(page.getByRole('heading',{name:'सूचनाएँ',exact:true})).toBeVisible();
  await expect(page.getByText(item.translations.hi.subject,{exact:true}).first()).toBeVisible();
  const after=await (await page.request.get('/api/notifications/')).json();
  const saved=after.results.find((r:{id:number})=>r.id===item.id);
  expect(saved.subject).toBe(item.subject);expect(saved.body).toBe(item.body);expect(saved.created_at).toBe(item.created_at);
  await page.getByRole('button',{name:/English/}).click();
  await expect(page.getByText(item.subject,{exact:true}).first()).toBeVisible();
});

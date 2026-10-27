import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {root,signIn} from './support';
const enabled=process.env.READINESS_DISPOSABLE==='1';
const scenario=enabled ? JSON.parse(readFileSync(path.join(root,'data/readiness-browser/scenario.json'),'utf8')) : {};
test.skip(!enabled,'Optional disposable readiness rehearsal; requires private synthetic setup.');
test.beforeAll(()=>{if(process.env.READINESS_DISPOSABLE!=='1')throw new Error('Requires disposable readiness profile');});
test('institution readiness, exact upload and new deposit links, Hindi and mobile',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await signIn(page,'institution_a');
  await page.goto(`/institutions/${scenario.institution_id}`);
  await expect(page.getByRole('heading',{name:'Deposit readiness',exact:true})).toBeVisible();
  const before=await (await page.request.get(`/api/institutions/${scenario.institution_id}/readiness`)).json();
  const obligation=before.obligations.find((o:any)=>o.obligation_id===scenario.obligation_id);
  expect(obligation).toBeTruthy();expect(obligation.items.find((i:any)=>i.id==='affidavit_3').deadline.days_remaining).toBe(8);
  const target=obligation.items.find((i:any)=>i.id==='affidavit_3').targets.find((t:any)=>t.record_id===scenario.record_id);
  await page.getByRole('link',{name:/Upload Affidavit-3.*SYNTHETIC-READINESS-BROWSER/}).click();
  await expect(page).toHaveURL(new RegExp(`/records/${scenario.record_id}\\?readiness=upload&kind=AFFIDAVIT_3`));
  const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();await expect(dialog.locator('.ant-select')).toContainText('Affidavit 3');
  await page.keyboard.press('Escape');await expect(dialog).not.toBeVisible();
  await page.goto(`/records?readiness=new&obligation=${scenario.obligation_id}`);
  await expect(page.getByRole('dialog').getByLabel('Obligation ID (optional)')).toHaveValue(scenario.obligation_id.toString());
  await page.getByRole('dialog').getByRole('button',{name:'Cancel',exact:true}).click();
  await page.goto(`/institutions/${scenario.institution_id}`);
  await page.getByRole('button',{name:/हिन्दी/}).click();
  await expect(page.getByRole('heading',{name:'जमा तैयारी',exact:true})).toBeVisible();
  await expect(page.getByText('SYNTHETIC-READINESS-BROWSER',{exact:false}).first()).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:path.join(root,'data/readiness-browser/mobile.png'),fullPage:true});
  expect(errors).toEqual([]);
});
test('officer receipt deep link saves real scoped review and refreshes readiness',async({page})=>{
  await signIn(page,'officer');
  await page.goto(`/institutions/${scenario.institution_id}`);
  const response=await page.request.get(`/api/institutions/${scenario.institution_id}/readiness`);expect(response.status()).toBe(200);
  const row=(await response.json()).obligations.find((o:any)=>o.obligation_id===scenario.obligation_id);
  const target=row.items.find((i:any)=>i.id==='proof_receipt').targets[0] || {href:"/institutions/"+scenario.institution_id+"?obligation="+scenario.obligation_id+"&readiness=receipts"};await page.goto(target.href);
  const receipt=page.getByRole('region',{name:'Proof receipts'});
  await expect(receipt.getByLabel('Payment proof received on')).toBeFocused();
  await receipt.getByLabel('Payment proof received on').fill(scenario.today);
  await receipt.getByLabel('Affidavit-3 received on').fill(scenario.today);
  await receipt.getByLabel('Reason').fill('SIMULATED browser receipt review; no authenticity claim.');
  await receipt.getByRole('button',{name:'Record receipt review',exact:true}).click();
  await expect(receipt.getByText('Officer review by',{exact:false})).toBeVisible();
  const after=await (await page.request.get(`/api/institutions/${scenario.institution_id}/readiness`)).json();
  expect(after.obligations.find((o:any)=>o.obligation_id===scenario.obligation_id).items.find((i:any)=>i.id==='proof_receipt').state).toBe('COMPLETE');
  await page.screenshot({path:path.join(root,'data/readiness-browser/officer.png'),fullPage:true});
});
test('institution B cannot read A readiness or scoped receipt form',async({page})=>{
  await signIn(page,'institution_b');
  expect((await page.request.get(`/api/institutions/${scenario.institution_id}/readiness`)).status()).toBe(404);
  await page.goto(`/institutions/${scenario.institution_id}?obligation=${scenario.obligation_id}&readiness=receipts`);
  await expect(page.getByRole('button',{name:'Record receipt review',exact:true})).toHaveCount(0);
});


test('weekly digest scoped preview and preference persists without sending email',async({page})=>{
  await signIn(page,'institution_a');await page.goto('/notifications');
  await page.getByRole('button',{name:'Weekly email digest',exact:true}).click();
  await expect(page.getByText('Weekly email digest',{exact:true}).last()).toBeVisible();
  const checkbox=page.getByRole('checkbox',{name:'Receive weekly email digest'});
  if (!(await checkbox.isChecked())) {await checkbox.click();await expect(checkbox).toBeChecked();}
  await page.getByRole('button',{name:'Preview my digest',exact:true}).click();
  await expect(page.locator('pre')).toContainText('Deposits expiring in the rest of this month');
  await checkbox.click();
  await expect.poll(async()=> (await (await page.request.get('/api/notifications/digest-preference/')).json()).enabled).toBe(false);
  await page.reload();await page.getByRole('button',{name:'Weekly email digest',exact:true}).click();await expect(checkbox).not.toBeChecked();
  await checkbox.click();
  await expect.poll(async()=> (await (await page.request.get('/api/notifications/digest-preference/')).json()).enabled).toBe(true);
  await page.screenshot({path:path.join(root,'data/readiness-browser/digest.png'),fullPage:true});
});

import { test, expect } from '@playwright/test';
// Requires the API and Vite servers, a migrated test database, and DEMO_MODE=true.
// Creates a synthetic profile/session. Do not run against a production database.
test('intake → whiteboard → fleet with a rejected unsupported claim',async({page})=>{
 await page.goto('/intake');
 await page.getByLabel('What are you aiming for?').fill('Software engineer — synthetic E2E tester');
 await page.getByLabel('Save my answers and session transcript for this practice.').check();
 await page.getByRole('button',{name:'Build my plan'}).click();
 await expect(page.getByRole('heading',{name:/Your plan/})).toBeVisible();
 await page.getByRole('button',{name:'Start session'}).click();
 await page.getByRole('button',{name:'Type instead'}).click();
 await page.getByLabel('Your answer').fill('What scale are we designing for, and is per-key limiting enough?');
 await page.getByRole('button',{name:'Send',exact:true}).click();
 await expect(page.getByText('What scale are we designing for, and is per-key limiting enough?',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Next step'}).click();
 await page.getByRole('button',{name:'Load demo board + explanation'}).click();
 await expect(page.getByRole('button',{name:'Done, take a look'})).toBeEnabled();
 await page.getByRole('button',{name:'Done, take a look'}).click();
 await page.getByRole('button',{name:'Defend the trade-offs →'}).click();
 await page.getByLabel('Your answer').fill('I chose Redis for shared counters. Failing open preserves availability but weakens the limit.');
 await page.getByRole('button',{name:'Send',exact:true}).click();
 await expect(page.getByRole('button',{name:'Next step'})).toBeEnabled();
 await page.getByRole('button',{name:'Next step'}).click();
 await page.getByRole('button',{name:'Finish session'}).click();
 await expect(page.getByRole('heading',{name:'Four evaluators, in parallel.'})).toBeVisible();
 await expect(page.getByText('Rejected proposal: “Explained Redis failover in detail.”')).toBeVisible();
 await expect(page.getByText('Explained while drawing.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:/Event #/}).first().click();
 await expect(page.getByRole('dialog')).toContainText('candidate');
});

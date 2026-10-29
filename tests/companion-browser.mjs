// Run through the supported CUA browser session: require this module and pass its Tab.
// Uses only documented Tab/Playwright APIs. The synthetic fixture blocks external requests.
import assert from 'node:assert/strict';
export default async function* runCompanionBrowserChecks({tab,baseUrl='http://127.0.0.1:8766',capture=async()=>{}}){
 if(await tab.url()===baseUrl+'/phone-390.html')await tab.reload();else await tab.goto(baseUrl+'/phone-390.html');await tab.getAXState({emit:false});
 const page=tab.playwright.frameLocator('iframe[title="WolfMaster phone preview"]');
 const state=()=>tab.getAXState({emit:false});
 const button=name=>page.getByRole('button',{name,exact:true});
 const value=label=>(label==='Context to share'?page.getByRole('textbox',{name:label,exact:true}):page.getByLabel(label,{exact:true})).evaluate(el=>el.value);
 await state();assert.equal(await page.locator('.comp-finance').count(),0);
 assert.equal(await page.locator('.comp-nav button').count(),4);
 assert(!(await button('Complete: Confirm launch checklist').isEnabled()));
 await button('Complete: Prepare the project review').click();await state();assert.equal(await button('Mark incomplete: Prepare the project review').getAttribute('aria-pressed'),'true');
 await button('Mark incomplete: Prepare the project review').click();await state();
 await button('Sources').click();await state();assert.equal(await page.getByRole('dialog',{name:'Connections & context'}).count(),1);await button('Close dialog').press('Escape');await state();assert.equal(await page.getByRole('dialog').count(),0);
 await button('Think it through with Wallace A context handoff. You’re in control.').click();await state();assert((await value('Context to share')).includes('manual handoff'));await button('Close dialog').press('Shift+Tab');assert.equal(await page.locator('html').evaluate(el=>el.ownerDocument.activeElement.textContent),'Copy context for Wallace ↗');await capture('wallace-390');await button('Copy context for Wallace').press('Escape');await state();
 yield 'Today, sources and Wallace passed';
 await button('Plan').click();await state();assert.equal(await page.getByRole('heading',{name:'Plan.',exact:true}).count(),1);await capture('plan-390');
 await button('Priorities').click();await state();assert.equal(await page.locator('.wm-top3-card').count(),3);yield 'Ready to check browser Back';await tab.back();yield 'Browser Back completed';await state();assert.equal(await button('Schedule').getAttribute('aria-pressed'),'true');
 await button('Projects').click();await state();await capture('projects-390');
 await button('All open tasks 16 ↗').click();await state();assert.equal(await page.locator('.comp-project .comp-task').count(),16);await page.getByLabel('Filter open tasks').fill('Fixture follow-up 9');await state();assert.equal(await page.locator('.comp-project .comp-task').count(),1);await button('← Projects').click();await state();
 await button('People Relationships & follow-ups ↗').click();await state();assert.equal(await page.getByRole('heading',{name:'People & relationships',exact:true}).count(),1);yield 'Ready to check browser Back';await tab.back();yield 'Browser Back completed';await state();assert.equal(await page.getByRole('heading',{name:'Projects.',exact:true}).count(),1);
 yield 'Plan and Projects navigation passed';
 await button('Finance').click();await state();await capture('finance-overview-390');assert.equal(await page.getByRole('heading',{name:'Finance.',exact:true}).count(),1);
 await button('Add snapshot ＋').click();await state();await page.getByLabel('Coverage · sources or accounts included').fill('Synthetic mobile work');await page.getByLabel('Work income · gross YTD',{exact:true}).fill('125');await state();
 await button('Today').click();await state();assert.equal(await page.locator('.comp-finance').count(),0);assert.equal(await page.getByText('Synthetic mobile work',{exact:true}).count(),0);
 await button('Finance').click();await state();assert.equal(await value('Work income · gross YTD'),'125');await capture('finance-entry-390');yield 'Finance draft retained across tabs';await button('Use snapshot for this session').click();await state();assert.equal(await page.locator('.comp-history').count(),1);assert.equal(await value('Year'),'2026');
 await button('Show amounts').click();await state();assert((await page.locator('.comp-money-grid').innerText()).includes('$125'));
 await button('Edit').click();await state();await page.getByLabel('Work income · gross YTD',{exact:true}).fill('999');await button('Cancel draft').click();await state();await button('Show amounts').click();await state();assert((await page.locator('.comp-money-grid').innerText()).includes('$125'));
 await button('Today').click();await state();assert.equal(await page.locator('.comp-finance').count(),0);
 await tab.reload();await state();await button('Finance').click();await state();assert.equal(await page.locator('.comp-history').count(),0,'Session-only entries clear on reload');
 const errors=await tab.dev.logs({levels:['error'],limit:100});
 assert(!errors.some(x=>x.url?.startsWith(baseUrl)&&/ReferenceError|TypeError|SyntaxError/.test(x.message)),'No application-attributed runtime exceptions');
 const unattributedErrors=errors.filter(x=>!x.url); // Keep unknown runner/page errors visible; do not claim a clean console.
 return {functionalChecksPassed:true,unattributedErrors,flows:['Today has no finance','local completion/import lock','sources','Wallace context and focus trap','Plan priorities/browser Back','Projects full list/filter','People route/browser Back','Finance overview/entry/draft navigation/save/edit/cancel/reload'],limits:'Synthetic primary screens; legacy secondary screens verify routing only. No live Auth, data APIs, clipboard write or physical iOS check.'};
};

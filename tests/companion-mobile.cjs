const {chromium,webkit}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>r.request().url().startsWith('http://127.0.0.1:8765/')?r.continue():r.abort());
 await page.goto('http://127.0.0.1:8765');await page.getByRole('heading',{name:'Today',exact:true}).waitFor();
 for(const width of [320,375,390,430]){await page.setViewportSize({width,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Home overflow ${width}`);const boxes=await page.locator('.fixed-tabs .tab').evaluateAll(ns=>ns.map(n=>({width:n.getBoundingClientRect().width,height:n.getBoundingClientRect().height})));assert(boxes.every(b=>b.width>=44&&b.height>=44),`Nav targets ${width}`);}
 await page.setViewportSize({width:390,height:844});
 assert(await page.locator('.comp-brief').isVisible());assert.equal(await page.locator('.comp-brief').locator('details').count(),0,'Main brief never buried');
 await page.getByRole('button',{name:'FINANCE',exact:true}).click();
 const coverage=page.getByLabel('Coverage · sources or accounts included');const work=page.getByLabel('Work income · gross YTD',{exact:true});
 await coverage.fill('Synthetic draft');await work.fill('125');assert.equal(await work.getAttribute('inputmode'),'decimal');assert.equal(await work.evaluate(el=>getComputedStyle(el).fontSize),'16px');
 for(let i=0;i<3;i++){await page.getByRole('button',{name:'HOME',exact:true}).click();await page.getByRole('button',{name:'FINANCE',exact:true}).click();assert.equal(await coverage.inputValue(),'Synthetic draft');assert.equal(await work.inputValue(),'125');}
 await page.getByRole('button',{name:'Cancel draft',exact:true}).click();assert.equal(await coverage.inputValue(),'');assert.equal(await work.inputValue(),'');assert.equal(await page.locator('.comp-history').count(),0);
 await page.getByRole('button',{name:'Use snapshot for this session'}).click();assert(await page.getByRole('alert').innerText());assert.equal(await page.locator('.comp-history').count(),0);
 await coverage.fill('Synthetic mobile work');await work.fill('-1');await page.getByRole('button',{name:'Use snapshot for this session'}).click();assert(await page.getByRole('alert').innerText());assert.equal(await page.locator('.comp-history').count(),0);
 await work.fill('125');await page.getByRole('button',{name:'Use snapshot for this session'}).click();assert.equal(await page.locator('.comp-history').count(),1);assert.equal(await page.getByRole('alert').count(),0);
 await page.getByRole('button',{name:'Edit',exact:true}).click();assert.equal(await work.inputValue(),'125');await work.fill('150');await page.getByRole('button',{name:'Use snapshot for this session'}).click();assert.equal(await page.locator('.comp-history').count(),1,'Same date replaces');
 await page.getByRole('button',{name:'Edit',exact:true}).click();await work.fill('999');await page.getByRole('button',{name:'Cancel draft',exact:true}).click();await page.getByRole('button',{name:'Show amounts',exact:true}).click();assert((await page.locator('.comp-money-grid').innerText()).includes('$150'));
 // Model a shrinking visual viewport while the layout viewport remains fixed, as iOS keyboards do.
 await coverage.focus();await page.evaluate(()=>{Object.defineProperty(window.visualViewport,'height',{configurable:true,value:400});window.visualViewport.dispatchEvent(new Event('resize'));});assert.equal(await page.locator('.fixed-tabs').isVisible(),false);await page.evaluate(()=>{delete window.visualViewport.height;window.visualViewport.dispatchEvent(new Event('resize'));});assert(await page.locator('.fixed-tabs').isVisible());
 await page.setViewportSize({width:390,height:430});await coverage.fill('Short viewport');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.getByRole('button',{name:'Cancel draft',exact:true}).click();
 await page.setViewportSize({width:320,height:700});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Finance 320 overflow');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'qa/finance-mobile-entry.png',fullPage:true});await page.getByRole('button',{name:'HOME',exact:true}).click();await page.screenshot({path:'qa/home-mobile-primary.png',fullPage:true});
 assert.deepEqual(errors,[]);await browser.close();console.log('Mobile passed: 320/375/390/430px Home, 320px Finance, 44px nav targets, draft survives repeated navigation, cancel/save/edit/replace/errors, decimal keyboards, short viewport and simulated visual-viewport keyboard handling. Physical iOS keyboard not tested.');
})().catch(e=>{console.error(e.stack);process.exit(1)});

// CUA-native responsive check. No standalone browser launcher or live data.
import assert from 'node:assert/strict';
export default async function checkCompanionPhoneSizes({tab,baseUrl='http://127.0.0.1:8766',capture=async()=>{}}){
 const results=[];
 for(const width of [320,375,390,430]){
  await tab.goto(baseUrl+'/phone-'+width+'.html');await tab.getAXState({emit:false});
  const page=tab.playwright.frameLocator('iframe[title="WolfMaster phone preview"]');await tab.getAXState({emit:false});
  const row=await page.locator('html').evaluate(el=>({width:el.ownerDocument.defaultView.innerWidth,scrollWidth:el.scrollWidth,scrollHeight:el.scrollHeight,todayHeight:el.querySelector('.comp-today').getBoundingClientRect().height,financeCards:el.querySelectorAll('.comp-finance').length,nav:[...el.querySelectorAll('.comp-nav button')].map(b=>({width:b.getBoundingClientRect().width,height:b.getBoundingClientRect().height}))}));
  assert.equal(row.width,width);assert(row.scrollWidth<=width);assert(row.scrollHeight<=930,'Compact Today, including shell');assert.equal(row.financeCards,0);assert(row.nav.every(x=>x.width>=44&&x.height>=44));results.push(row);await capture('today-'+width,width);
 }
 return {passed:true,results,limits:'CSS phone-width iframes, not physical Safari or safe-area hardware.'};
};

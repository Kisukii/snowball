const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({headless:true, channel:"chrome"});
  try {
    const page = await browser.newPage({viewport:{width:1100,height:800}});
    await page.setContent(`<h1>Citizen services demo</h1>
      <form><label for="secret">Password</label><input id="secret" value="DO-NOT-READ" type="password"><button id="submit">Submit</button></form>
      <section aria-label="Applications"><h2>Track your application</h2><span id="track-label">Track application</span><button id="track" aria-labelledby="track-label">Go</button></section>
      <section aria-label="Appointments"><h2>Appointments</h2><button id="other" aria-label="Track application">Icon</button></section>
      <button id="disabled" aria-disabled="true">Unavailable</button>
      <button id="plain">Open services</button><div id="shadow"></div>`);
    await page.addScriptTag({path:path.join(__dirname,'controls.js')});
    let result = await page.evaluate(() => {
      const c=SnowBallControls;
      return {name:c.name(document.querySelector('#track')), first:c.context(document.querySelector('#track')),
        second:c.context(document.querySelector('#other')), password:c.name(document.querySelector('#secret')),
        hidden:c.visible(document.querySelector('#disabled')), submit:c.canClick(document.querySelector('#submit')),
        plain:c.canClick(document.querySelector('#plain'))};
    });
    assert.equal(result.name,'Track application');
    assert.notEqual(result.first,result.second);
    assert.equal(result.password,'Password');
    assert.equal(result.hidden,false);
    assert.equal(result.submit,false);
    assert.equal(result.plain,true);
    await page.evaluate(() => {
      document.querySelector('#shadow').attachShadow({mode:'open'}).innerHTML='<button aria-label="Shadow service">Service</button>';
    });
    assert.equal(await page.evaluate(() => SnowBallControls.collect().some(el=>SnowBallControls.name(el)==='Shadow service')),true);
    await page.evaluate(async () => {
      const el=document.querySelector('#plain'); window.clicks=0; el.onclick=()=>window.clicks++;
      await SnowBallControls.click(el,SnowBallControls.proof(el));
    });
    assert.equal(await page.evaluate(()=>window.clicks),1);
    assert.equal(await page.evaluate(async () => {
      const el=document.querySelector('#plain'), proof=SnowBallControls.proof(el);
      el.setAttribute('aria-label','Different action');
      try {await SnowBallControls.click(el,proof); return false;} catch {return true;}
    }),true);
    assert.equal(await page.evaluate(async () => {
      const el=document.querySelector('#plain');
      try {await SnowBallControls.click(el,SnowBallControls.proof(el),()=>true); return false;} catch {return true;}
    }),true);
    assert.equal(await page.evaluate(async () => {
      const el=document.querySelector('#plain'), rect=el.getBoundingClientRect();
      const cover=document.createElement('div');
      cover.style.cssText=`position:fixed;left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;height:${rect.height}px;background:red;z-index:999`;
      document.body.append(cover);
      try {await SnowBallControls.click(el,SnowBallControls.proof(el)); return false;} catch {return true;}
    }),true);
    assert.equal(await page.evaluate(()=>window.clicks),1);
    console.log('PASS: accessible names, duplicate context, secret values, disabled controls, submission handoff, shadow DOM, one-shot click, changed target, cancellation, occlusion');

    // Exercise the actual cat + guidance controller with deterministic provider replies.
    const guidePage=await browser.newPage({viewport:{width:1100,height:800}});
    await guidePage.route('**/*', route => route.fulfill({status:200,contentType:'text/html',body:'<html><body></body></html>'}));
    await guidePage.goto('http://snowball.test');
    await guidePage.setContent('<h1>Citizen services</h1><button id="service" type="button">Track application</button>');
    await guidePage.evaluate(() => {
      const storage={};
      window.chrome={runtime:{id:'test-extension',onMessage:{addListener(){}},
        async sendMessage(message) {
          if(message.type==='TAB_ID')return 1;
          if(message.type==='COMPANION_STATUS')return {online:false};
          if(message.type==='GUIDE'){
            window.lastPayload=message.payload;
            const button=message.payload.page.elements.find(el=>el.label==='Track application');
            return {ok:true,step:{element_id:button.id,instruction:'Click Track application.',
              instruction_local:'Click Track application.',icon:'🐾',warning:null,done:false}};
          }
          return {ok:true};
        }},
        storage:{local:{async get(){return {preferences:{voice:false}}},async set(){}},
          session:{async get(){return storage},async set(value){Object.assign(storage,value)},async remove(){}}}};
      window.actions=0;
      document.querySelector('#service').onclick=()=>window.actions++;
    });
    for (const file of ['sprite.js','pet.js','controls.js','content.js']) await guidePage.addScriptTag({path:path.join(__dirname,file)});
    await guidePage.addStyleTag({path:path.join(__dirname,'pet.css')});
    await guidePage.evaluate(()=>PawlyPet.onAction({type:'START',goal:'Find Track application'}));
    await guidePage.waitForSelector('#service[data-pawly-target]');
    await guidePage.waitForTimeout(1600);
    await guidePage.screenshot({path:path.join(__dirname,'../research/snowball-browser-demo.png')});
    assert.equal(await guidePage.evaluate(()=>window.lastPayload.page.context),'Citizen services');
    await guidePage.evaluate(()=>PawlyPet.onAction({type:'CLICK_TARGET'}));
    await guidePage.waitForFunction(()=>window.actions===1);
    await guidePage.evaluate(()=>PawlyPet.onAction({type:'STOP'}));
    assert.equal(await guidePage.locator('[data-pawly-target]').count(),0);
    console.log('PASS: cat flies to highlighted target, heading context reaches provider, explicit click dispatches, Stop clears guidance');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});


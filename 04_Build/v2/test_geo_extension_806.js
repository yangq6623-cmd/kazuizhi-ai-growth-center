"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ext = path.resolve(__dirname, "../../05_V2.0.0_Source/browser_extension/kazuizhi_geo");
const content = fs.readFileSync(path.join(ext, "content-agent.js"), "utf8");
const worker = fs.readFileSync(path.join(ext, "service-worker.js"), "utf8");
const manifest = JSON.parse(fs.readFileSync(path.join(ext, "manifest.json"), "utf8"));

async function main() {
  assert.equal(manifest.version, "2.2.2.806");
  assert.equal(manifest.manifest_version, 3);

  let registrations = 0;
  const sandbox = { chrome: { runtime: { onMessage: {addListener() { registrations++; }}}}, console };
  vm.createContext(sandbox);
  vm.runInContext(content, sandbox, { filename: "content-agent.js" });
  vm.runInContext(content, sandbox, { filename: "content-agent.js" });
  assert.equal(registrations, 1, "manifest + worker re-injection must have one listener");

  // Detached extension context must not cause the observed onMessage TypeError.
  const missing = {console};
  vm.createContext(missing);
  assert.doesNotThrow(() => vm.runInContext(content, missing, {filename: "content-agent.js"}));
  const noListener = {console, chrome:{runtime:{}}};
  vm.createContext(noListener);
  assert.doesNotThrow(() => vm.runInContext(content, noListener, {filename:"content-agent.js"}));

  let sent=0, injections=0, scriptedReady=false, sendError="missing";
  const workerSandbox = {
    console, setTimeout, clearTimeout, Date, URL, AbortSignal,
    chrome: {
      alarms: {create:async()=>{}, onAlarm:{addListener(){}}},
      runtime: {
        getManifest:()=>({version:manifest.version}),
        onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener(){}}
      },
      tabs: {
        get:async()=>({id:9,status:"loading",url:"https://www.n.cn/"}),
        sendMessage:async()=>{
          sent++;
          if(sendError==="missing"&&sent===1) throw Error("Could not establish connection. Receiving end does not exist.");
          if(sendError==="permission") throw Error("permission_denied");
          return {ok:true,state:"ready"};
        }
      },
      scripting: {executeScript:async arg=>{
        if(arg.files){injections++;return[];}
        if(arg.func){scriptedReady=true;return[{result:true}];}
        throw Error("unexpected injection");
      }},
      storage:{local:{get:async()=>({}),set:async()=>{}}}
    }
  };
  vm.createContext(workerSandbox);
  vm.runInContext(worker, workerSandbox, {filename:"service-worker.js"});
  let result=await vm.runInContext("ask(9,{type:'kz-probe'},2000)", workerSandbox);
  assert.equal(result.ok,true);
  assert.equal(injections,1, "only missing receiver should invoke one fallback injection");
  assert.equal(sent,2);
  const partiallyLoaded=await vm.runInContext("waitLoaded(9,2000)", workerSandbox);
  assert.equal(partiallyLoaded.id,9);
  assert.equal(scriptedReady,true, "interactive DOM is sufficient for probe");

  sent=0;injections=0;sendError="permission";
  await assert.rejects(vm.runInContext("ask(9,{type:'kz-probe'},2000)", workerSandbox), /permission_denied/);
  assert.equal(injections,0, "unrelated errors must never trigger re-injection");

  // The bug in 2.2.2.804: stored() silently excluded lastVerified.
  const keysUsed=[];
  const five=Object.keys({doubao_web:1,douyin_search_web:1,deepseek_web:1,qwen_web:1,so360_ai_search:1})
    .map(platform=>({platform,state:"ready"}));
  const fixture={agentId:"agent",token:"token",sessions:five,
    lastVerified:new Date().toISOString(),lastRetryAt:new Date().toISOString()};
  workerSandbox.chrome.storage.local.get=async keys=>{
    keysUsed.push(...keys);
    return Object.fromEntries(keys.filter(k=>Object.hasOwn(fixture,k)).map(k=>[k,fixture[k]]));
  };
  workerSandbox.chrome.storage.local.set=async patch=>Object.assign(fixture,patch);
  workerSandbox.verifyCalls=0;
  workerSandbox.probeCalls=0;
  vm.runInContext("verifyAll=async()=>{verifyCalls++;return []}; probe=async()=>{probeCalls++;return {platform:'qwen_web',state:'ready'}}; identity=async()=>({agentId:'agent',token:'token'});call=async()=>({})",workerSandbox);
  await vm.runInContext("cycle()",workerSandbox);
  assert.ok(keysUsed.includes("lastVerified"),"stored must retrieve lastVerified");
  assert.ok(keysUsed.includes("lastRetryAt"),"stored must retrieve lastRetryAt");
  assert.equal(workerSandbox.verifyCalls,0,"fresh cached 5-platform verification must not run on each timer");
  assert.equal(workerSandbox.probeCalls,0,"ready platforms must not be reprobed");
  // An authorization failure is retried only when the retry cooldown has elapsed.
  fixture.sessions=[...five.slice(0,4),{platform:"so360_ai_search",state:"authorization_required"}];
  fixture.lastRetryAt=new Date().toISOString();
  await vm.runInContext("cycle()",workerSandbox);
  assert.equal(workerSandbox.probeCalls,0,"recently checked authorization must not retry every 3 minutes");
  fixture.lastRetryAt=new Date(Date.now()-11*60*1000).toISOString();
  await vm.runInContext("cycle()",workerSandbox);
  assert.equal(workerSandbox.probeCalls,1,"failed authorization can be retried after cooldown");
  assert.ok(fixture.lastRetryAt,"successful login verification should persist cooldown");
  console.log("PASS: cached platform verification and bounded auth retry");

  const alarmPeriods={};
  workerSandbox.chrome.alarms.create=async (name, opts)=>{ alarmPeriods[name]=opts.periodInMinutes; };
  await vm.runInContext("ensureAlarm()",workerSandbox);
  assert.equal(alarmPeriods["kazuizhi-geo-cycle"],3,"background full GEO cycle must be 3 minutes");
  assert.equal(alarmPeriods["kazuizhi-geo-heartbeat"],1,"heartbeat must run faster than server's 180-second TTL");
  workerSandbox.heartbeatCalls=0;
  vm.runInContext("call=async(path)=>{if(path==='heartbeat')heartbeatCalls++;return {ok:true}}",workerSandbox);
  const hb=await vm.runInContext("heartbeatOnly()",workerSandbox);
  assert.equal(hb.ok,true);
  assert.equal(workerSandbox.heartbeatCalls,1,"lightweight heartbeat must actually reach server endpoint");
  assert.ok(fixture.lastHeartbeatAt && !fixture.lastHeartbeatError,"heartbeats must report success");
  vm.runInContext("call=async()=>{throw Error('server_unavailable')}",workerSandbox);
  const offline=await vm.runInContext("heartbeatOnly()",workerSandbox);
  assert.equal(offline.ok,false,"heartbeats must report failures without claiming success");
  assert.match(fixture.lastHeartbeatError,/server_unavailable/);
  console.log("PASS: sub-TTL heartbeat without GEO task re-run or fabricated Evidence");

  console.log("PASS: Chrome GEO 2.2.2.806 idempotent registration, runtime guard, fallback, partial load");
}
main().catch(e=>{console.error(e);process.exitCode=1;});

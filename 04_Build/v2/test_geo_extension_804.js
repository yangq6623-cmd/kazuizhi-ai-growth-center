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
  assert.equal(manifest.version, "2.2.2.804");
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
  console.log("PASS: Chrome GEO 2.2.2.804 idempotent registration, runtime guard, fallback, partial load");
}
main().catch(e=>{console.error(e);process.exitCode=1;});

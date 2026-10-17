"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const src = fs.readFileSync(path.join(__dirname,"../../05_V2.0.0_Source/browser_extension/kazuizhi_geo/service-worker.js"),"utf8");
const schedule = new Map();
const attempts = [];
let when = 1_800_000;
const chrome = {
  alarms: {
    async get(name) { return schedule.get(name); },
    async create(name, opts) {
      attempts.push({name,at:when});
      schedule.set(name,{name,periodInMinutes:opts.periodInMinutes,scheduledTime:when+opts.periodInMinutes*60_000});
    },
    onAlarm:{addListener(){}},
  },
  runtime:{onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener(){}}},
  storage:{local:{get:async()=>({}),set:async()=>{}}},
};
async function restartWorker() {
  const env={console,chrome,setTimeout(){},clearTimeout(){},Date};
  vm.createContext(env);
  vm.runInContext(src,env,{filename:"service-worker.js"});
  await vm.runInContext("ensureAlarm()",env);
}
async function main() {
  await restartWorker();
  assert.equal(schedule.get("kazuizhi-geo-cycle").periodInMinutes,3);
  assert.equal(schedule.get("kazuizhi-geo-heartbeat").periodInMinutes,1);
  assert.equal(attempts.length,2,"first cold start creates two alarms");
  const originalCycleTime=schedule.get("kazuizhi-geo-cycle").scheduledTime;
  for(let i=0;i<3;i++) {
    when+=60_000;
    await restartWorker(); // simulation of MV3 service worker woken by each heartbeat
    assert.equal(schedule.get("kazuizhi-geo-cycle").scheduledTime,originalCycleTime,
       "heartbeat must not postpone three-minute cycle on cold restart");
  }
  assert.equal(attempts.length,2,"no alarms reset on worker restart");
  schedule.delete("kazuizhi-geo-cycle");
  await restartWorker();
  assert.equal(attempts.length,3,"repair missing cycle alarm");
  const hb=schedule.get("kazuizhi-geo-heartbeat");
  schedule.set("kazuizhi-geo-heartbeat",{...hb,periodInMinutes:2});
  await restartWorker();
  assert.equal(schedule.get("kazuizhi-geo-heartbeat").periodInMinutes,1,"repair wrong heartbeat period");
  assert.equal(attempts.length,4,"repair only wrong alarm");
  console.log("PASS: GEO 3min cycle survives 1min heartbeat cold starts, absent/wrong alarms repaired");
}
main().catch(e=>{console.error(e);process.exitCode=1;});

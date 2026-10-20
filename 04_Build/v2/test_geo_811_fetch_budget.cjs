"use strict";
const fs=require("node:fs");
const vm=require("node:vm");
const assert=require("node:assert/strict");
const path=require("node:path");
const BASE=path.join(__dirname,"../../05_V2.0.0_Source/web/");
const calls=[],blocked=[];
let releaseEvidence=null;
const nativeFetch=(url)=>{
  url=String(url);calls.push(url);
  if(url==="/api/slow-A"||url==="/api/slow-B")
    return new Promise(resolve=>blocked.push(()=>resolve({ok:true,json:async()=>({})})));
  if(url==="/api/r8-24/geo-growth/evidence-compact")
    return new Promise(resolve=>{
      releaseEvidence=()=>resolve({ok:true,json:async()=>({snapshot_ready:false,questions:[],retry_after_ms:30000})});
    });
  return Promise.resolve({ok:true,json:async()=>({acceptance:{},supervisor:{}})});
};
const window={location:{href:"http://127.0.0.1:8876/",origin:"http://127.0.0.1:8876"},fetch:nativeFetch};
const el={textContent:"",innerHTML:"",style:{},dataset:{},className:"",open:true,
  classList:{add(){},remove(){}},querySelectorAll(){return []},querySelector(){return null},
  getClientRects(){return [1]},addEventListener(){}};
const els=new Map();
const document={readyState:"loading",hidden:false,documentElement:{dataset:{}},addEventListener(){},
  getElementById(key){if(!els.has(key))els.set(key,{...el,style:{},dataset:{}});return els.get(key)},
  createElement(){return {...el}},body:{...el}};
const c={window,document,location:{search:""},URL,DOMException,Request,URLSearchParams,
 AbortController,Promise,Date,Math,Object,String,Number,Array,console,
 setTimeout(){return 1},clearTimeout(){},setInterval(){return 2},clearInterval(){},
 fetch:(url,init)=>window.fetch(url,init),getComputedStyle(){return {visibility:"visible"}}};
vm.createContext(c);
vm.runInContext(fs.readFileSync(BASE+"build_info.js","utf8"),c);
let ui=fs.readFileSync(BASE+"geo-growth-os.js","utf8");
const hook="  window.__KZ_GEO_GROWTH_OS_BOOT__=start;";
assert.equal(ui.split(hook).length,2);
ui=ui.replace(hook,'  window.__GEO811_TEST__={loadAdvanced,loadPhase1Acceptance};\n'+hook);
vm.runInContext(ui,c);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const a=window.fetch("/api/slow-A"),b=window.fetch("/api/slow-B");await tick();
 assert.equal(window.KZFetchBudget.snapshot().active,2);
 const fast=window.fetch("/api/r8-24/geo-growth/fast-ui");await tick();
 assert.equal(calls.filter(x=>x.includes("geo-growth/fast-ui")).length,1,
   "Fast owner snapshot must reach native fetch even when both global slots are busy");
 await fast;
 const first=c.window.__GEO811_TEST__.loadAdvanced(true);await tick();
 assert.equal(calls.filter(x=>x.includes("evidence-compact")).length,1,
   "Evidence GET must reach native fetch even when both global slots are busy");
 assert.equal(calls.filter(x=>x.includes("phase1-acceptance")).length,0);
 releaseEvidence();await first;await tick();
 assert.equal(calls.filter(x=>x.includes("phase1-acceptance")).length,1,
   "phase1 GET follows (does not overlap) Evidence GET");
 for(let i=0;i<99;i++){
   const p=c.window.__GEO811_TEST__.loadAdvanced(true);await tick();
   releaseEvidence();await p;await tick();
 }
 assert.equal(calls.filter(x=>x.includes("evidence-compact")).length,100);
 assert.equal(calls.filter(x=>x.includes("phase1-acceptance")).length,1);
 assert.equal(window.KZFetchBudget.snapshot().active,2);
 blocked.forEach(fn=>fn());await Promise.all([a,b]);await tick();
 assert.equal(window.KZFetchBudget.snapshot().active,0);
 console.log("PASS #811: fast UI and 100 GEO evidence reads bypass saturated global slots, no duplicate phase1 reads");
})().catch(error=>{console.error(error);process.exitCode=1});

"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm"),path=require("node:path");
const js=fs.readFileSync(path.resolve(__dirname,"../../05_V2.0.0_Source/web/build_info.js"),"utf8");
const nativeCalls=[],release=[];
const nativeFetch=(url)=>{nativeCalls.push(String(url));
 if(String(url)==="/api/slow-1"||String(url)==="/api/slow-2")
   return new Promise(done=>release.push(()=>done({ok:true})));
 return Promise.resolve({ok:true,json:async()=>({})});
};
const window={location:{href:"http://127.0.0.1:8876/",origin:"http://127.0.0.1:8876"},fetch:nativeFetch};
vm.runInNewContext(js,{window,URL,DOMException,Request,AbortController,console});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const one=window.fetch("/api/slow-1"),two=window.fetch("/api/slow-2");
 await tick();
 assert.equal(window.KZFetchBudget.snapshot().active,2);
 const getPaths=[
   "/api/r8-24/geo-growth/evidence-compact",
   "/api/r8-25/phase1-acceptance",
   "/api/r8-24/geo-growth/evidence-health",
   "/api/r8-24/geo-growth/fast-health",
   "/api/r8-24/geo-growth/http-health",
   "/api/r8-24/geo-growth/liveness",
   "/api/r8-27/geo-browser-agent/status"
 ];
 for(let i=0;i<100;i++)for(const url of getPaths)await window.fetch(url,{method:"GET"});
 assert.equal(nativeCalls.filter(url=>getPaths.includes(url)).length,700,
   "7 lock-free status GETs bypass a congested application data queue");
 assert.equal(window.KZFetchBudget.snapshot().active,2,
   "Unrelated API budget has not been bypassed");
 let wrote=false;
 const write=window.fetch("/api/r8-27/geo-browser-agent/claim",{method:"POST"}).then(()=>wrote=true);
 await tick();
 assert.equal(wrote,false,"POST and mutations stay inside budget");
 assert.equal(nativeCalls.filter(x=>x.includes("/claim")).length,0);
 release.forEach(fn=>fn());await Promise.all([one,two,write]);
 assert.equal(wrote,true);
 assert.equal(nativeCalls.filter(x=>x.includes("/claim")).length,1);
 assert.equal(window.KZFetchBudget.snapshot().active,0);
 console.log("PASS #814: 700 health/agent status GETs bypass blocked slots; task claims still rate-limited");
})().catch(e=>{console.error(e);process.exitCode=1});

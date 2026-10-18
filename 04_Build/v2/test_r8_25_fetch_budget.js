'use strict';
const assert=require('assert');
const fs=require('fs');
const vm=require('vm');
const path=require('path');

const calls=[];
function nativeFetch(input,init={}){
  const url=String(input?.url||input);
  return new Promise((resolve,reject)=>calls.push({url,method:init.method||'GET',resolve,reject}));
}
const window={fetch:nativeFetch,location:{href:'http://127.0.0.1:8876/',origin:'http://127.0.0.1:8876'}};
const context={window,URL,DOMException,Request,Promise,setTimeout,clearTimeout};
vm.createContext(context);
const source=fs.readFileSync(path.join(__dirname,'../../05_V2.0.0_Source/web/build_info.js'),'utf8');
vm.runInContext(source,context,{filename:'build_info.js'});

const turn=()=>new Promise(resolve=>setTimeout(resolve,0));
(async()=>{
  const p1=window.fetch('/api/one');
  const p2=window.fetch('/api/two');
  const p3=window.fetch('/api/three');
  await turn();
  assert.deepStrictEqual(calls.map(x=>x.url),['/api/one','/api/two']);
  assert.strictEqual(window.KZFetchBudget.snapshot().active,2);
  assert.strictEqual(window.KZFetchBudget.snapshot().pending,1);

  const staticPromise=window.fetch('/decision_center.js');
  await turn();
  assert.strictEqual(calls[2].url,'/decision_center.js','static module must bypass the API queue');
  calls[2].resolve('static-ok');
  assert.strictEqual(await staticPromise,'static-ok');

  const controller=new AbortController();
  const aborted=window.fetch('/api/aborted',{signal:controller.signal}).catch(error=>error.name);
  controller.abort();
  assert.strictEqual(await aborted,'AbortError');
  assert(!calls.some(x=>x.url==='/api/aborted'),'aborted queued request reached native fetch');

  const p4=window.fetch('/api/four');
  const mutation=window.fetch('/api/command',{method:'POST'});
  calls[0].resolve('one');
  assert.strictEqual(await p1,'one');
  await turn();
  assert.strictEqual(calls[3].url,'/api/command','mutation did not jump ahead of background reads');
  calls[3].resolve('command');
  assert.strictEqual(await mutation,'command');
  await turn();
  assert.strictEqual(calls[4].url,'/api/three');

  calls[1].resolve('two');
  calls[4].resolve('three');
  assert.strictEqual(await p2,'two');
  assert.strictEqual(await p3,'three');
  await turn();
  assert.strictEqual(calls[5].url,'/api/four');
  calls[5].resolve('four');
  assert.strictEqual(await p4,'four');
  await turn();

  const snapshot=window.KZFetchBudget.snapshot();
  assert.strictEqual(snapshot.peak_active,2);
  assert.strictEqual(snapshot.active,0);
  assert.strictEqual(snapshot.pending,0);
  assert.strictEqual(snapshot.aborted,1);
  console.log('PASS: API fetch budget caps concurrency, preserves static assets, prioritizes writes, and cancels queued timeouts');
})().catch(error=>{console.error(error);process.exitCode=1});

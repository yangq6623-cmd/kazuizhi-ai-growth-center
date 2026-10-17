(function installKazuizhiFetchBudget(){
  'use strict';
  if(window.__KZ_FETCH_BUDGET_INSTALLED__||typeof window.fetch!=='function')return;

  const nativeFetch=window.fetch.bind(window);
  const maxConcurrent=2;
  const queue=[];
  const stats={active:0,pending:0,peak_active:0,completed:0,aborted:0,bypassed:0};
  let sequence=0;

  function abortError(){
    if(typeof DOMException==='function')return new DOMException('The operation was aborted.','AbortError');
    const error=new Error('The operation was aborted.');error.name='AbortError';return error;
  }
  function requestDetails(input,init){
    const raw=typeof input==='string'||input instanceof URL?String(input):String(input?.url||input);
    let url;
    try{url=new URL(raw,window.location.href)}catch(_error){return null}
    if(url.origin!==window.location.origin||!url.pathname.startsWith('/api/'))return null;
    const method=String(init?.method||input?.method||'GET').toUpperCase();
    // #811: Fast read-only owner snapshots must not sit behind unrelated
    // long-running API calls until their 15/20-second abort timers expire.
    // Only these exact GET routes bypass the two-slot shared request budget;
    // the GEO UI independently serializes and rate-limits both reads.
    if(method==='GET'&&(
      url.pathname==='/api/r8-24/geo-growth/evidence-compact'||
      url.pathname==='/api/r8-25/phase1-acceptance'||
      url.pathname==='/api/r8-24/geo-growth/evidence-health'||
      url.pathname==='/api/r8-24/geo-growth/fast-health'||
      url.pathname==='/api/r8-24/geo-growth/http-health'||
      url.pathname==='/api/r8-24/geo-growth/liveness'||
      url.pathname==='/api/r8-27/geo-browser-agent/status'
    ))return null;
    const signal=init?.signal||input?.signal||null;
    let priority=2;
    if(method!=='GET'&&method!=='HEAD')priority=0;
    else if(
      url.pathname==='/api/status'
      ||url.pathname.endsWith('/liveness')
      ||url.pathname.endsWith('/fast-ui')
      ||url.pathname==='/api/r7/jobs'
      ||url.pathname==='/api/r7/engine'
      ||url.pathname==='/api/r7/agents'
      ||url.pathname==='/api/r7/audit'
      ||url.pathname==='/api/r7/model-routes'
      ||url.pathname==='/api/r7/decision-center'
    )priority=1;
    return {method,signal,priority,path:url.pathname};
  }
  function updatePending(){stats.pending=queue.length}
  function removeQueued(task){
    const index=queue.indexOf(task);
    if(index<0)return false;
    queue.splice(index,1);updatePending();return true;
  }
  function pump(){
    while(stats.active<maxConcurrent&&queue.length){
      const task=queue.shift();updatePending();
      if(task.details.signal?.aborted){stats.aborted+=1;task.reject(abortError());continue}
      task.started=true;
      if(task.onAbort)task.details.signal.removeEventListener('abort',task.onAbort);
      stats.active+=1;stats.peak_active=Math.max(stats.peak_active,stats.active);
      nativeFetch(task.input,task.init).then(task.resolve,task.reject).finally(()=>{
        stats.active-=1;stats.completed+=1;pump();
      });
    }
  }
  function scheduledFetch(input,init){
    const details=requestDetails(input,init);
    if(!details){stats.bypassed+=1;return nativeFetch(input,init)}
    if(details.signal?.aborted){stats.aborted+=1;return Promise.reject(abortError())}
    return new Promise((resolve,reject)=>{
      const task={input,init,details,resolve,reject,sequence:sequence++,started:false,onAbort:null};
      if(details.signal){
        task.onAbort=()=>{
          if(task.started||!removeQueued(task))return;
          stats.aborted+=1;reject(abortError());pump();
        };
        details.signal.addEventListener('abort',task.onAbort,{once:true});
      }
      queue.push(task);
      queue.sort((a,b)=>a.details.priority-b.details.priority||a.sequence-b.sequence);
      updatePending();pump();
    });
  }

  window.fetch=scheduledFetch;
  window.KZFetchBudget=Object.freeze({
    maxConcurrent,
    snapshot:()=>Object.freeze({...stats}),
    nativeFetch
  });
  window.__KZ_FETCH_BUDGET_INSTALLED__=true;
})();

window.KZ_BUILD_INFO = {
  runNumber: "__GITHUB_RUN_NUMBER__",
  commit: "__GITHUB_SHA__",
  branch: "r8-23-final-autonomous-growth-os-20261002",
  phase: "R8-24",
  displayVersion: "V2.2.2 R8-24 GEO Growth OS",
  runtimeBuild: "KZ-ENTERPRISE-V2.2.2-R8-24-GEO-GROWTH-OS"
};

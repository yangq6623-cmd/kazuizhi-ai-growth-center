// Pure rendering tests: no production requests or external sends.
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const source=fs.readFileSync('05_V2.0.0_Source/web/geo-growth-os.js','utf8');
const helpers=source.slice(source.indexOf('  function retestWindowText('),source.indexOf('  function render(data)'));
const ctx=vm.createContext({}); vm.runInContext(helpers,ctx);
assert.equal(ctx.retestWindowText(undefined),'待同步');
assert.equal(ctx.retestWindowText({completed:null,scheduled:null}),'待同步');
assert.equal(ctx.retestWindowText({completed:0,scheduled:12}),'0/12');
assert.equal(ctx.retestWindowText({completed:11,scheduled:12}),'11/12');
assert.equal(ctx.opportunityRetestText(undefined),'复测进度待同步');
const partial=ctx.opportunityRetestText({completed:1,target:3,windows:{'24h':'completed','72h':'scheduled','7d':'queued'}});
assert(partial.includes('三窗口复测未完成 1/3'));
assert(partial.includes('72h 未完成'));
assert(ctx.opportunityRetestText({completed:3,target:3,windows:{'24h':'completed','72h':'completed','7d':'completed'}}).includes('三窗口复测完成 3/3'));
// #818: a timeout must preserve an earlier complete snapshot, or else
// explicitly report unknown. Never synthesize 0/0 for a failed detail request.
const previous={status_ready:true,summary:{completed:11},retest_windows:{
  '24h':{scheduled:12,completed:11},'72h':{scheduled:12,completed:0},
  '7d':{scheduled:12,completed:0}},opportunities:[{id:'historical'}]};
const recovered=ctx.degradedStatus(previous,{status_ready:true,owner_overview:{
  summary:{completed:5},retest_windows:{'24h':{scheduled:13,completed:5}}}},4000);
assert.equal(recovered.retest_windows['24h'].completed,11);
assert.equal(recovered.transport_degraded,true);
assert.equal(recovered.opportunities[0].id,'historical');
const neverFetched=ctx.degradedStatus(null,{status_ready:true,owner_overview:{
  summary:{completed:5}}});
assert.equal(neverFetched.transport_degraded,true);
assert.equal(neverFetched.retest_windows,undefined);
assert.equal(ctx.retestWindowText(neverFetched.retest_windows?.['24h']),'待同步');
assert.equal(ctx.degradedStatus(null,null),null);

console.log('GEO retest rendering assertions passed');

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
console.log('GEO retest rendering assertions passed');

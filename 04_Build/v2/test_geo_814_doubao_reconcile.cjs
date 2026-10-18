"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),vm=require("node:vm");
const source=path.resolve(__dirname,"../../05_V2.0.0_Source");
const js=fs.readFileSync(path.join(source,"browser_extension/kazuizhi_geo/content-agent.js"),"utf8");
const worker=fs.readFileSync(path.join(source,"browser_extension/kazuizhi_geo/service-worker.js"),"utf8");
let composer={value:"",isConnected:true,disabled:false,
  getAttribute:()=>null,closest:()=>null,
  getBoundingClientRect:()=>({left:0,right:600,top:100,bottom:140,width:600,height:40})};
let text="Older generated message";
const store=new Map();let tick=()=>{};
const document={
  body:{get innerText(){return text}},querySelectorAll(selector){
    if(selector==="button")return [];
    if(selector==="*")return [];
    return selector==="textarea"?[composer]:[];
  }
};
const ctx={console,document,location:{href:"https://www.doubao.com/chat/test",hostname:"www.doubao.com",pathname:"/chat/test"},
  sessionStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},
  chrome:{runtime:{onMessage:{addListener(){}}}},
  getComputedStyle:()=>({display:"block",visibility:"visible"}),
  setTimeout:cb=>{tick();cb();}};
vm.createContext(ctx);
const marker="  runtime.onMessage.addListener((message, _sender, sendResponse) => {";
assert.ok(js.includes(marker));
vm.runInContext(js.replace(marker,
  "  globalThis.__TEST814__={questionCount,confirmPosted,postedEchoVisible,submit,recheckPosted};\n"+marker),ctx);
(async()=>{
  const q="卡嘴子 能不能 找维修师傅？";
  const t=ctx.__TEST814__;
  assert.equal(t.questionCount("卡嘴子能不能找维修师傅？",q),1,
    "DOM whitespace normalization must match the same question");
  composer.value=q;
  text="This old message";
  assert.equal(await t.confirmPosted(composer,q,0),false,
    "Composer alone is not a real posted question");
  tick=()=>{text="Older answer\n卡嘴子能不能找维修师傅？";composer.value="";};
  assert.equal(await t.confirmPosted(composer,q,0),true,
    "A new echoed question plus empty composer confirms sending");
  tick=()=>{};
  composer.value=q;
  assert.equal(await t.confirmPosted(composer,q,0),false,
    "No false confirmation if composer is still filled");
  assert.equal(await t.submit(composer,"doubao_web"),false,
    "Never submit by synthetic Enter when there is no real Send button");

  // Reconciliation must never send. The state is persisted by the same tab.
  store.set("kz_geo_execution_v2",JSON.stringify({
    platform:"doubao_web",question:q,beforeCount:0,postConfirmed:false}));
  text="卡嘴子能不能找维修师傅？";composer.value="";
  assert.equal(t.recheckPosted("doubao_web",q).ok,true);
  assert.equal(JSON.parse(store.get("kz_geo_execution_v2")).postConfirmed,true);
  assert.equal(t.recheckPosted("doubao_web","different question").ok,false);

  let time=0,stages=[];
  const fakeDate={now:()=>{time+=10000;return time}};
  const work={
    console,Date:fakeDate,URL,AbortSignal,
    setTimeout:cb=>cb(),clearTimeout(){},
    chrome:{runtime:{getManifest:()=>({version:"2.2.2.808"}),onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener(){}}},
      alarms:{create:async()=>{},onAlarm:{addListener(){}},get:async()=>({})},
      tabs:{update:async()=>{},remove:async()=>{}},
      storage:{local:{get:async()=>({}),set:async()=>{}}}}
  };
  vm.createContext(work);
  vm.runInContext(worker,work);
  work.mockAsk=async(_id,message)=>{
    stages.push(message.type);
    if(message.type==="kz-start")return {ok:false,state:"uncertain",error:"question_not_submitted"};
    if(message.type==="kz-recheck-post")return {ok:true,state:"confirmed"};
    if(message.type==="kz-capture")return {ok:true,state:"ready",url:"https://www.doubao.com/chat/test",
      raw_answer:"独立真实回执需要由外部浏览器页面产生，这里是合成测试回答文本。"};
  };
  vm.runInContext("ask=mockAsk",work);
  const recovered=await vm.runInContext("executeDoubao(1,'doubao_web','卡嘴子测试问题')",work);
  assert.equal(recovered.ok,true);
  assert.deepEqual(stages,["kz-start","kz-recheck-post","kz-capture"],
    "Only one send, one readonly reconciliation, and answer capture");
  stages=[];time=0;
  work.mockAsk=async(_id,message)=>{
    stages.push(message.type);
    return message.type==="kz-start"
      ?{ok:false,state:"uncertain",error:"question_not_submitted"}
      :{ok:false,state:"pending"};
  };
  vm.runInContext("ask=mockAsk",work);
  const uncertain=await vm.runInContext("executeDoubao(1,'doubao_web','卡嘴子测试问题')",work);
  assert.equal(uncertain.state,"uncertain");
  assert.equal(stages.filter(x=>x==="kz-start").length,1);
  assert.equal(stages.filter(x=>x==="kz-capture").length,0);
  console.log("PASS #814: whitespace-safe echo, no synthetic submission, single non-replaying reconciliation, no false Receipt");
})().catch(e=>{console.error(e);process.exitCode=1});

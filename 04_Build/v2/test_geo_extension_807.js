"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ext = path.resolve(__dirname, "../../05_V2.0.0_Source/browser_extension/kazuizhi_geo");
const contentCode = fs.readFileSync(path.join(ext,"content-agent.js"),"utf8");
const workerCode = fs.readFileSync(path.join(ext,"service-worker.js"),"utf8");
const manifest = JSON.parse(fs.readFileSync(path.join(ext,"manifest.json"),"utf8"));

async function main() {
  assert.equal(manifest.version,"2.2.2.807");
  assert.ok(contentCode.includes("question_not_submitted"));
  assert.ok(contentCode.includes("unconfirmed_question"));
  assert.ok(workerCode.includes('type: "kz-start"') && workerCode.includes('type: "kz-capture"'));
  assert.ok(workerCode.includes("doubao_answer_capture_timeout"));
  assert.ok(!workerCode.includes('["deepseek_web", "so360_ai_search", "doubao_web"].includes(platform)'));

  // Simulate real page signals: a filled composer must NOT be mistaken for a
  // posted question, even when a long answer from an older turn is visible.
  let tick = () => {};
  const context = {console, chrome:{runtime:{onMessage:{addListener(){}}}},
    document:{body:{innerText:"Old reply about TV repair."}},
    setTimeout(cb){tick();cb();}};
  vm.createContext(context);
  const injected = contentCode.replace(
    "  runtime.onMessage.addListener((message, _sender, sendResponse) => {",
    "  globalThis.__kzTest = {questionCount, confirmPosted};\n  runtime.onMessage.addListener((message, _sender, sendResponse) => {");
  assert.notEqual(injected,contentCode);
  vm.runInContext(injected,context,{filename:"content-agent.js"});
  const {confirmPosted,questionCount} = context.__kzTest;
  const q="卡嘴子能不能找安装师傅？";
  const composer={value:q,isConnected:true};
  assert.equal(questionCount(context.document.body.innerText,q),0);
  assert.equal(await confirmPosted(composer,q,0),false,"old answer with unsent input must fail");
  context.document.body.innerText="Old question: "+q;
  assert.equal(await confirmPosted(composer,q,1),false,"a cached previous question is not new proof");
  tick=()=>{context.document.body.innerText="Old answer\nNew question: "+q; composer.value="";};
  assert.equal(await confirmPosted(composer,q,0),true,"new question echo plus cleared composer acknowledges posting");
  tick=()=>{};
  composer.value=q;
  assert.equal(await confirmPosted(composer,q,0),false,"question echo with unchanged composer is not confirmed");

  const calls=[];
  const workerSandbox={console,Date,URL,AbortSignal,setTimeout(cb){cb()},clearTimeout(){},
    chrome:{
      runtime:{getManifest:()=>manifest,onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener(){}}},
      alarms:{create:async()=>{},onAlarm:{addListener(){}}},
      tabs:{update:async()=>{},remove:async()=>{}},
      storage:{local:{get:async()=>({}),set:async()=>{}}}
    }};
  vm.createContext(workerSandbox);
  vm.runInContext(workerCode,workerSandbox,{filename:"service-worker.js"});
  // Real split flow: one send and one polling cycle, never a second send.
  let messages=[];
  workerSandbox.mockAsk=async(_id,msg)=>{
    messages.push(msg.type);
    if(msg.type==="kz-start")return {ok:true,state:"submitted"};
    return {ok:true,state:"ready",raw_answer:"独立AI生成的新回答，能够联系专业安装师傅并提供服务信息。",citation_urls:[],url:"https://www.doubao.com/chat/test"};
  };
  vm.runInContext("ask=mockAsk",workerSandbox);
  let result=await vm.runInContext("executeDoubao(9,'doubao_web','卡嘴子能不能找安装师傅？')",workerSandbox);
  assert.equal(result.ok,true);
  assert.deepEqual(messages,["kz-start","kz-capture"]);
  messages=[];
  workerSandbox.mockAsk=async(_id,msg)=>{messages.push(msg.type);return {ok:false,state:"error",error:"question_not_submitted"};};
  vm.runInContext("ask=mockAsk",workerSandbox);
  result=await vm.runInContext("executeDoubao(9,'doubao_web','卡嘴子能不能找安装师傅？')",workerSandbox);
  assert.equal(result.error,"question_not_submitted");
  assert.deepEqual(messages,["kz-start"],"unsent prompts never begin answer collection");

  // Block failures and never write a successful Receipt from an unposted prompt.
  workerSandbox.actions=calls;
  vm.runInContext("platformTab=async()=>({tab:{id:9,url:'https://www.doubao.com/chat/test'},created:false});"+
    "call=async(name,payload)=>{actions.push({name,payload});return {ok:true}};"+
    "executeDoubao=async()=>({ok:false,state:'error',error:'question_not_submitted'})",workerSandbox);
  await assert.rejects(vm.runInContext("executeTask({platform:'doubao_web',question_text:'卡嘴子能不能找安装师傅？',task_id:'TASK-1'},{agent_id:'a',agent_token:'b'})",workerSandbox),/question_not_submitted/);
  assert.equal(calls.filter(x=>x.name==="receipt").length,0);
  assert.equal(calls.filter(x=>x.name==="block").length,1);
  calls.length=0;
  vm.runInContext("executeDoubao=async()=>({ok:true,state:'ready',raw_answer:'真实页面的新回答文字，已通过问题回显与内容稳定性检查。',citation_urls:[],url:'https://www.doubao.com/chat/test'})",workerSandbox);
  result=await vm.runInContext("executeTask({platform:'doubao_web',question_text:'卡嘴子能不能找安装师傅？',task_id:'TASK-1'},{agent_id:'a',agent_token:'b'})",workerSandbox);
  assert.equal(result.completed,true);
  assert.equal(calls.filter(x=>x.name==="receipt").length,1);
  assert.equal(calls.filter(x=>x.name==="block").length,0);
  console.log("PASS: 807 Doubao send confirmation, no stale Evidence, polled answers, receipt fail-closed");
}
main().catch(error=>{console.error(error);process.exitCode=1;});

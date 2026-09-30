(() => {
  'use strict';
  if (window.__KZ_CONTENT_FINAL_V101__) return;
  window.__KZ_CONTENT_FINAL_V101__ = true;

  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api = async (url, options={}) => {
    const r = await fetch(url, options);
    const d = await r.json().catch(()=>({}));
    if (!r.ok) throw new Error(d.error || d.detail || d.message || `HTTP ${r.status}`);
    return d;
  };
  const post = (url, body={}) => api(url, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  let state = null;
  let editor = null;
  let tab = 'acceptance';

  function installStyle(){
    if(byId('kz-v101-style')) return;
    const style=document.createElement('style'); style.id='kz-v101-style';
    style.textContent=`
      .kz-v101-card{margin:0 0 12px;background:#fff;border:1px solid #dce6f1;border-radius:8px;padding:12px 14px;display:flex;align-items:center;justify-content:space-between;gap:14px}.kz-v101-card h3{margin:0 0 4px;font-size:14px;color:#17324f}.kz-v101-card p{margin:0;font-size:11px;color:#71849a}.kz-v101-chips{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.kz-v101-chip{font-size:10px;padding:3px 7px;border-radius:999px;background:#eaf7f1;color:#177455}.kz-v101-chip.warn{background:#fff4df;color:#946314}.kz-v101-open{height:34px;border:0;border-radius:5px;background:#1768e5;color:#fff;padding:0 13px;font-weight:700;cursor:pointer;white-space:nowrap}
      .kz-v101-back{position:fixed;inset:0;background:rgba(13,30,49,.46);z-index:13000;display:flex;align-items:center;justify-content:center;padding:20px}.kz-v101-modal{width:min(1200px,96vw);max-height:92vh;background:#f5f8fc;border-radius:10px;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.3);display:grid;grid-template-rows:auto auto 1fr;color:#17324f}.kz-v101-head{padding:14px 17px;background:#123b68;color:#fff;display:flex;align-items:center;justify-content:space-between}.kz-v101-head h2{margin:0;font-size:18px}.kz-v101-head p{margin:3px 0 0;font-size:11px;opacity:.78}.kz-v101-close{border:0;background:rgba(255,255,255,.12);color:#fff;width:34px;height:34px;border-radius:6px;font-size:18px;cursor:pointer}.kz-v101-tabs{padding:10px 14px;background:#fff;border-bottom:1px solid #dce6f1;display:flex;gap:7px;flex-wrap:wrap}.kz-v101-tabs button{height:32px;border:1px solid #c7d5e5;border-radius:5px;background:#fff;color:#47627f;padding:0 11px;cursor:pointer}.kz-v101-tabs button.active{background:#1768e5;border-color:#1768e5;color:#fff;font-weight:700}.kz-v101-body{padding:14px;overflow:auto}.kz-v101-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.kz-v101-box{background:#fff;border:1px solid #dfe7f1;border-radius:7px;padding:11px}.kz-v101-box b{font-size:12px}.kz-v101-box small{display:block;margin-top:4px;color:#71849a;line-height:1.5}.kz-v101-good{color:#16875c}.kz-v101-bad{color:#b33d3d}.kz-v101-actions{margin-top:12px;display:flex;gap:7px;flex-wrap:wrap}.kz-v101-actions button,.kz-v101-btn{height:34px;border:1px solid #b9cbe0;border-radius:5px;background:#fff;color:#24496f;padding:0 10px;cursor:pointer}.kz-v101-actions button.primary,.kz-v101-btn.primary{background:#1768e5;border-color:#1768e5;color:#fff;font-weight:700}.kz-v101-result{margin-top:12px;background:#fff;border:1px solid #dfe7f1;border-radius:7px;padding:11px;font-size:11px;line-height:1.6}.kz-v101-shot{background:#fff;border:1px solid #dfe7f1;border-radius:7px;padding:10px;margin-bottom:8px}.kz-v101-shot-head{display:flex;justify-content:space-between;gap:8px}.kz-v101-shot p{margin:5px 0;font-size:11px;color:#53677e;line-height:1.5}.kz-v101-shot-actions{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}.kz-v101-shot-actions button{height:27px;border:1px solid #c7d5e5;border-radius:4px;background:#fff;color:#47627f;font-size:10px;cursor:pointer}.kz-v101-shot-actions button.hot{background:#1768e5;border-color:#1768e5;color:#fff}.kz-v101-shot-actions button.danger{color:#b33d3d;border-color:#e4b7b7}.kz-v101-formrow{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end}.kz-v101-formrow label{font-size:11px;color:#53677e}.kz-v101-formrow select,.kz-v101-formrow input{width:100%;height:36px;border:1px solid #c7d5e5;border-radius:5px;background:#fff;padding:0 9px;margin-top:5px}.kz-v101-audio{width:100%;margin-top:10px}.kz-v101-missing{margin-top:10px;padding:9px;background:#fff4df;border:1px solid #edd29c;border-radius:6px;color:#805f1c;font-size:11px;line-height:1.6}@media(max-width:900px){.kz-v101-grid{grid-template-columns:1fr}.kz-v101-card{align-items:flex-start;flex-direction:column}.kz-v101-formrow{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function chips(){
    if(!state) return '';
    const m=state.modules||{};
    const items=[['#96 链接/无素材',m.reference_v96],['#97 资产绑定',m.assets_v97],['#98 声音克隆',m.voice_v98&&state.voice?.available],['#99 镜头编辑',m.editor_v99],['#100 专业后期',state.postproduction?.ready],['#101 最终闭环',state.ready_for_full_acceptance]];
    return items.map(([name,ok])=>`<span class="kz-v101-chip ${ok?'':'warn'}">${ok?'✓':'!'} ${esc(name)}</span>`).join('');
  }

  function installCard(){
    const root=byId('kz-simple-root'); if(!root) return;
    if(byId('kz-v101-card')) return;
    const hero=root.querySelector('.kz-simple-hero'); if(!hero) return;
    const card=document.createElement('section'); card.id='kz-v101-card'; card.className='kz-v101-card';
    card.innerHTML=`<div><h3>六模块内容生产中心 · 最终整合版</h3><p>链接解析、无素材首帧、系列资产、授权声音、镜头编辑、专业后期与最终自检集中在这里。</p><div class="kz-v101-chips" id="kz-v101-chips">正在读取本机能力…</div></div><button type="button" class="kz-v101-open" id="kz-v101-open">最终内容中心</button>`;
    hero.insertAdjacentElement('afterend',card);
    byId('kz-v101-open')?.addEventListener('click',open);
    refreshStatus();
  }

  function shell(){
    let root=byId('kz-v101-modal'); if(root) return root;
    root=document.createElement('div'); root.id='kz-v101-modal'; root.className='kz-v101-back'; root.hidden=true;
    root.innerHTML=`<section class="kz-v101-modal"><header class="kz-v101-head"><div><h2>内容生产中心 · #101 最终整合</h2><p>六个模块一次升级；只认真实本机模型、真实文件和真实执行状态。</p></div><button type="button" class="kz-v101-close">×</button></header><nav class="kz-v101-tabs"></nav><main class="kz-v101-body"></main></section>`;
    document.body.appendChild(root);
    root.querySelector('.kz-v101-close')?.addEventListener('click',close);
    root.addEventListener('click',e=>{if(e.target===root)close();});
    return root;
  }

  function renderTabs(){
    const labels={acceptance:'最终验收',shots:'镜头编辑',voice:'声音试听'};
    shell().querySelector('.kz-v101-tabs').innerHTML=Object.entries(labels).map(([k,v])=>`<button type="button" data-v101-tab="${k}" class="${tab===k?'active':''}">${v}</button>`).join('');
    shell().querySelectorAll('[data-v101-tab]').forEach(btn=>btn.addEventListener('click',async()=>{tab=btn.dataset.v101Tab;await renderBody();}));
  }

  async function refreshStatus(){
    try{state=await api('/api/content-final/status',{cache:'no-store'});}
    catch(error){state={error:error.message,modules:{}};}
    const chip=byId('kz-v101-chips'); if(chip) chip.innerHTML=chips();
    return state;
  }

  function acceptanceHtml(){
    const missing=(state?.missing_runtime_dependencies||[]);
    const modules=[
      ['#96 参考链接 + 无素材首帧',state?.modules?.reference_v96, state?.auto_keyframe?.message||''],
      ['#97 人物 / 场景 / 系列资产绑定',state?.modules?.assets_v97,'所选资产进入真实Wan生成合同'],
      ['#98 授权声音克隆 / 方言TTS',state?.voice?.available,state?.voice?.message||''],
      ['#99 完整镜头编辑器',state?.modules?.editor_v99,'新增、删除、拆分、合并、排序、单镜头重生'],
      ['#100 专业自动后期',state?.postproduction?.ready,'声音母带、可选BGM、封面、9:16/1:1/16:9'],
      ['#101 无人值守最终闭环',state?.ready_for_full_acceptance,state?.truth||''],
    ];
    return `<div class="kz-v101-grid">${modules.map(([n,ok,d])=>`<article class="kz-v101-box"><b class="${ok?'kz-v101-good':'kz-v101-bad'}">${ok?'✓':'!'} ${esc(n)}</b><small>${esc(d)}</small></article>`).join('')}</div>${missing.length?`<div class="kz-v101-missing"><b>完整最终测试前仍缺本机运行依赖：</b><br>${missing.map(x=>`• ${esc(x)}`).join('<br>')}</div>`:''}<div class="kz-v101-actions"><button type="button" class="primary" id="kz-v101-selftest">执行最终自检</button><button type="button" id="kz-v101-refresh">重新读取状态</button></div><div id="kz-v101-result" class="kz-v101-result">${esc(state?.truth||'')}</div>`;
  }

  async function loadEditor(){ editor=await api('/api/content-final/shot-editor',{cache:'no-store'}); return editor; }
  function shotsHtml(){
    const project=editor?.project, shots=editor?.shots||[];
    if(!project) return '<div class="kz-v101-result">当前还没有生产项目。先建立一次内容任务后再编辑镜头。</div>';
    return `<div class="kz-v101-result"><b>${esc(project.name||project.id)}</b> · ${shots.length} 个镜头。修改某个镜头只让该镜头候选失效，其他真实候选保留。</div><div class="kz-v101-actions"><button class="primary" data-shot-action="add" data-project="${esc(project.id)}">＋ 新增镜头</button><button data-shot-refresh>刷新</button></div><section>${shots.map(shot=>`<article class="kz-v101-shot"><div class="kz-v101-shot-head"><b>镜头 ${shot.order} · ${esc(shot.purpose||'')}</b><span>${Number(shot.duration_seconds||0)}秒 · ${Number(shot.candidate_count||1)}候选</span></div><p>${esc(shot.narration||'无旁白')}</p><p>${esc(shot.action||shot.scene||'')}</p><div class="kz-v101-shot-actions"><button data-shot-action="up" data-id="${esc(shot.id)}">上移</button><button data-shot-action="down" data-id="${esc(shot.id)}">下移</button><button class="hot" data-shot-action="edit" data-id="${esc(shot.id)}">修改</button><button data-shot-action="split" data-id="${esc(shot.id)}">拆分</button><button data-shot-action="merge" data-id="${esc(shot.id)}">与下个合并</button><button class="hot" data-shot-action="regen" data-id="${esc(shot.id)}">只重生这个</button><button class="danger" data-shot-action="delete" data-id="${esc(shot.id)}">删除</button></div></article>`).join('')}</section>`;
  }

  async function voicesHtml(){
    const data=await api('/api/series-asset-center',{cache:'no-store'});
    const voices=(data.items||[]).filter(x=>x.type==='voice'&&x.enabled!==false);
    return `<div class="kz-v101-formrow"><label>声音资产<select id="kz-v101-voice">${voices.length?voices.map(x=>`<option value="${esc(x.id)}">${esc(x.name)} · ${esc(x.dialect||x.language||'普通话')} · ${esc(x.clone_status||'')}</option>`).join(''):'<option value="">还没有声音资产</option>'}</select></label><button class="kz-v101-btn primary" id="kz-v101-preview">生成试听</button></div><div class="kz-v101-formrow" style="margin-top:10px"><label>试听文案<input id="kz-v101-preview-text" value="卡嘴子本地服务，真实、专业、离你更近。"></label><span></span></div><div id="kz-v101-voice-result" class="kz-v101-result">只允许本人或明确授权的参考声音进入克隆。公开能听到不等于允许克隆。</div>`;
  }

  async function renderBody(){
    renderTabs(); const body=shell().querySelector('.kz-v101-body');
    if(tab==='acceptance'){await refreshStatus();body.innerHTML=acceptanceHtml();bindAcceptance();return;}
    if(tab==='shots'){try{await loadEditor();body.innerHTML=shotsHtml();bindShots();}catch(e){body.innerHTML=`<div class="kz-v101-result kz-v101-bad">${esc(e.message)}</div>`;}return;}
    try{body.innerHTML=await voicesHtml();bindVoice();}catch(e){body.innerHTML=`<div class="kz-v101-result kz-v101-bad">${esc(e.message)}</div>`;}
  }

  function bindAcceptance(){
    byId('kz-v101-refresh')?.addEventListener('click',renderBody);
    byId('kz-v101-selftest')?.addEventListener('click',async e=>{
      const btn=e.currentTarget;btn.disabled=true;btn.textContent='正在真实检查…';
      try{const d=await post('/api/content-final/self-test',{});const root=byId('kz-v101-result');root.innerHTML=`<b class="${d.passed?'kz-v101-good':'kz-v101-bad'}">${d.passed?'最终自检通过':'最终自检尚未全部通过'}</b><br>${(d.checks||[]).map(x=>`${x.passed?'✓':'✕'} ${esc(x.name)}：${esc(x.detail)}`).join('<br>')}<br><b>下一步：</b>${esc(d.next||'')}`;}
      catch(error){byId('kz-v101-result').textContent=error.message;}
      finally{btn.disabled=false;btn.textContent='执行最终自检';}
    });
  }

  function shotById(id){return (editor?.shots||[]).find(x=>x.id===id);}
  function bindShots(){
    shell().querySelector('[data-shot-refresh]')?.addEventListener('click',renderBody);
    shell().querySelectorAll('[data-shot-action]').forEach(btn=>btn.addEventListener('click',async()=>{
      const action=btn.dataset.shotAction,id=btn.dataset.id||'',project=btn.dataset.project||editor?.project?.id||'';
      let url='',body={shot_id:id};
      if(action==='add'){url='/api/content-final/shot/add';body={project_id:project,after_shot_id:(editor?.shots||[]).at(-1)?.id||'',shot:{purpose:'新增补充镜头',duration_seconds:4,candidate_count:1}};}
      if(action==='up'||action==='down'){url='/api/content-final/shot/move';body={shot_id:id,direction:action};}
      if(action==='split')url='/api/content-final/shot/split';
      if(action==='merge')url='/api/content-final/shot/merge';
      if(action==='regen'){url='/api/content-final/shot/regenerate';const count=Number(prompt('生成几个候选？1-4',String(shotById(id)?.candidate_count||1))||shotById(id)?.candidate_count||1);body={shot_id:id,candidate_count:count};}
      if(action==='delete'){if(!confirm('删除这个镜头？旧候选会保留为历史记录。'))return;url='/api/content-final/shot/delete';}
      if(action==='edit'){
        const s=shotById(id);if(!s)return;
        const narration=prompt('旁白/台词',s.narration||'');if(narration===null)return;
        const actionText=prompt('画面动作',s.action||'');if(actionText===null)return;
        const duration=Number(prompt('镜头秒数 1-12',String(s.duration_seconds||4))||s.duration_seconds||4);
        const count=Number(prompt('候选数量 1-4',String(s.candidate_count||1))||s.candidate_count||1);
        url='/api/content-final/shot/edit';body={shot_id:id,patch:{narration,action:actionText,duration_seconds:duration,candidate_count:count}};
      }
      if(!url)return;
      btn.disabled=true;
      try{await post(url,body);await renderBody();}
      catch(error){alert('镜头操作没有完成：'+error.message);btn.disabled=false;}
    }));
  }

  function bindVoice(){
    byId('kz-v101-preview')?.addEventListener('click',async e=>{
      const btn=e.currentTarget,voiceId=byId('kz-v101-voice')?.value||'',text=byId('kz-v101-preview-text')?.value||'';
      if(!voiceId){byId('kz-v101-voice-result').textContent='请先建立声音资产并上传本人/授权参考录音。';return;}
      btn.disabled=true;btn.textContent='正在本地生成试听…';
      try{const d=await post('/api/content-final/voice/preview',{voice_id:voiceId,text});byId('kz-v101-voice-result').innerHTML=`<b class="kz-v101-good">真实试听已生成</b><br>${esc(d.message||'')}<audio class="kz-v101-audio" controls autoplay src="${esc(d.preview_url||'')}"></audio>`;}
      catch(error){byId('kz-v101-voice-result').innerHTML=`<b class="kz-v101-bad">试听未完成</b><br>${esc(error.message)}`;}
      finally{btn.disabled=false;btn.textContent='生成试听';}
    });
  }

  async function open(){installStyle();shell().hidden=false;await renderBody();}
  function close(){const root=byId('kz-v101-modal');if(root)root.hidden=true;}

  // #96 pure-link bridge. The earlier #88 activation listener may create one
  // synthetic click; this capture handler intentionally handles that second
  // pass, fetches real public text, then replays the button only after success.
  document.addEventListener('click',async event=>{
    const button=event.target.closest?.('#kz-simple-start'); if(!button)return;
    if(button.dataset.kzV101Parsed==='1'){delete button.dataset.kzV101Parsed;return;}
    if(button.dataset.kzV101Parsing==='1')return;
    const source=byId('kz-simple-source');const raw=source?.value.trim()||'';
    const match=raw.match(/https?:\/\/[^\s]+/i);if(!match)return;
    const remaining=raw.replace(/https?:\/\/[^\s]+/ig,' ').replace(/\s+/g,' ').trim();
    if(remaining.length>=8)return;
    event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();
    button.dataset.kzV101Parsing='1';button.disabled=true;const old=button.textContent;button.textContent='正在真实解析参考链接…';
    try{
      const d=await post('/api/content-final/reference/parse',{url:match[0],text:''});
      if(!d.ok||!d.text)throw new Error(d.message||'来源页面没有可验证正文');
      source.value=`${d.text}\n${d.url||match[0]}`;
      button.dataset.kzV101Parsed='1';
      const result=byId('kz-simple-result');if(result){result.hidden=false;result.className='kz-simple-result kz-simple-success';result.innerHTML='<b>参考链接已真实解析。</b> 正在继续AI分析、原创重构与视频生产。';}
      setTimeout(()=>button.click(),20);
    }catch(error){
      const result=byId('kz-simple-result');if(result){result.hidden=false;result.className='kz-simple-result kz-simple-error';result.innerHTML=`<b>纯链接暂时不能自动读取：</b>${esc(error.message)}<br>请补充平台分享文字/字幕；系统不会猜测原内容。`;}
    }finally{delete button.dataset.kzV101Parsing;button.disabled=false;button.textContent=old;}
  },true);

  function install(){installStyle();installCard();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(install,180),{once:true});else setTimeout(install,180);
  const observer=new MutationObserver(()=>installCard());observer.observe(document.documentElement,{childList:true,subtree:true});
})();

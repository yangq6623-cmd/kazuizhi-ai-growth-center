(() => {
  'use strict';
  if (window.__KZ_SERIES_ASSET_CENTER_V92__) return;
  window.__KZ_SERIES_ASSET_CENTER_V92__ = true;

  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api = async (url, options={}) => {
    const response = await fetch(url, options);
    const data = await response.json().catch(()=>({}));
    if(!response.ok) throw new Error(data.error||data.detail||data.message||`HTTP ${response.status}`);
    return data;
  };
  const post = (url, body) => api(url, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  let state = {items:[],counts:{}};
  let activeType = 'character';
  let editingId = '';

  function installStyle(){
    if(byId('kz-series-assets-style')) return;
    const style=document.createElement('style');
    style.id='kz-series-assets-style';
    style.textContent=`
      .kz-sa-backdrop{position:fixed;inset:0;background:rgba(15,31,50,.42);z-index:12000;display:flex;align-items:center;justify-content:center;padding:24px}
      .kz-sa-modal{width:min(1180px,96vw);max-height:92vh;background:#f5f8fc;border-radius:12px;box-shadow:0 24px 70px rgba(0,0,0,.28);display:grid;grid-template-rows:auto auto 1fr;overflow:hidden;color:#17324f}
      .kz-sa-head{background:#123b68;color:#fff;padding:16px 18px;display:flex;align-items:center;justify-content:space-between;gap:12px}.kz-sa-head h2{margin:0;font-size:18px}.kz-sa-head p{margin:4px 0 0;font-size:11px;opacity:.8}.kz-sa-head button{border:0;background:rgba(255,255,255,.12);color:#fff;width:34px;height:34px;border-radius:6px;cursor:pointer;font-size:18px}
      .kz-sa-tabs{display:flex;gap:8px;padding:12px 16px;background:#fff;border-bottom:1px solid #dfe7f1;flex-wrap:wrap}.kz-sa-tabs button{height:34px;border:1px solid #c9d7e7;border-radius:6px;background:#fff;color:#47627f;padding:0 12px;cursor:pointer}.kz-sa-tabs button.active{background:#1768e5;color:#fff;border-color:#1768e5;font-weight:700}.kz-sa-body{display:grid;grid-template-columns:1fr 1.15fr;gap:14px;padding:14px;overflow:auto}
      .kz-sa-panel{background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:14px}.kz-sa-toolbar{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px}.kz-sa-toolbar h3{margin:0;font-size:14px}.kz-sa-primary,.kz-sa-secondary,.kz-sa-danger{height:34px;border-radius:5px;padding:0 11px;cursor:pointer}.kz-sa-primary{background:#1768e5;border:1px solid #1768e5;color:#fff;font-weight:700}.kz-sa-secondary{background:#fff;border:1px solid #b9cbe0;color:#24496f}.kz-sa-danger{background:#fff;border:1px solid #e0aaaa;color:#b33d3d}
      .kz-sa-list{display:grid;gap:8px}.kz-sa-card{border:1px solid #e2e9f2;border-radius:7px;padding:10px;cursor:pointer;background:#fbfdff}.kz-sa-card.active{border-color:#1768e5;box-shadow:0 0 0 1px rgba(23,104,229,.08);background:#f7fbff}.kz-sa-card b{display:block;font-size:12px}.kz-sa-card span{display:block;margin-top:4px;font-size:10px;color:#6d7f96}.kz-sa-empty{color:#8190a3;font-size:11px;padding:24px;text-align:center;border:1px dashed #d2dde9;border-radius:7px}
      .kz-sa-form{display:grid;grid-template-columns:1fr 1fr;gap:10px}.kz-sa-form .wide{grid-column:1/-1}.kz-sa-form label{font-size:11px;color:#53677e}.kz-sa-form input,.kz-sa-form select,.kz-sa-form textarea{width:100%;margin-top:5px;border:1px solid #c9d7e7;border-radius:5px;background:#fff;padding:8px;color:#17324f;font:inherit;box-sizing:border-box}.kz-sa-form input,.kz-sa-form select{height:36px}.kz-sa-form textarea{min-height:74px;resize:vertical}.kz-sa-actions{grid-column:1/-1;display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding-top:3px}.kz-sa-note{grid-column:1/-1;padding:9px 10px;border-radius:6px;background:#fff8ea;border:1px solid #efd59a;color:#805f1c;font-size:11px;line-height:1.55}.kz-sa-good{background:#eefaf4;border-color:#bfe6d2;color:#176d4d}.kz-sa-status{font-size:11px;color:#6d7f96}.kz-sa-audio{width:100%;margin-top:7px}.kz-sa-source-help{font-size:10px;color:#7a8ba0;margin-top:4px;line-height:1.45}
      @media(max-width:900px){.kz-sa-body{grid-template-columns:1fr}.kz-sa-form{grid-template-columns:1fr}.kz-sa-form .wide{grid-column:auto}}
    `;
    document.head.appendChild(style);
  }

  const typeLabel = type => ({character:'人物库',voice:'声音与方言中心',scene:'场景库',series:'系列模板'})[type]||type;
  const sourceLabel = value => ({self_clone:'本人/公司自有声音克隆',authorized_clone:'已授权真人声音克隆',public_licensed:'公共授权声音库',ai_original:'AI原创品牌声音'})[value]||value||'';
  const items = type => (state.items||[]).filter(x=>x.type===type);
  const item = id => (state.items||[]).find(x=>x.id===id)||null;

  function shell(){
    let root=byId('kz-series-assets');
    if(root) return root;
    root=document.createElement('div');
    root.id='kz-series-assets';
    root.className='kz-sa-backdrop';
    root.hidden=true;
    root.innerHTML=`<section class="kz-sa-modal" role="dialog" aria-modal="true"><header class="kz-sa-head"><div><h2>系列资产中心</h2><p>人物固定 · 声音可克隆/方言化 · 场景可替换 · 系列模板长期复用</p></div><button type="button" data-kz-sa-close>×</button></header><nav class="kz-sa-tabs"></nav><div class="kz-sa-body"><section class="kz-sa-panel"><div class="kz-sa-toolbar"><h3 id="kz-sa-list-title"></h3><button class="kz-sa-primary" type="button" id="kz-sa-new">＋ 新增</button></div><div class="kz-sa-list" id="kz-sa-list"></div></section><section class="kz-sa-panel"><div class="kz-sa-toolbar"><h3 id="kz-sa-form-title">新建资产</h3><span class="kz-sa-status" id="kz-sa-status"></span></div><form id="kz-sa-form" class="kz-sa-form"></form></section></div></section>`;
    document.body.appendChild(root);
    root.querySelector('[data-kz-sa-close]')?.addEventListener('click', close);
    root.addEventListener('click', e=>{if(e.target===root) close();});
    byId('kz-sa-new')?.addEventListener('click',()=>{editingId='';render();});
    return root;
  }

  function renderTabs(){
    const root=shell();
    const tabs=root.querySelector('.kz-sa-tabs');
    tabs.innerHTML=['character','voice','scene','series'].map(type=>`<button type="button" data-kz-sa-tab="${type}" class="${activeType===type?'active':''}">${typeLabel(type)} · ${Number(state.counts?.[type]||0)}</button>`).join('');
    tabs.querySelectorAll('[data-kz-sa-tab]').forEach(btn=>btn.addEventListener('click',()=>{activeType=btn.dataset.kzSaTab;editingId='';render();}));
  }

  function renderList(){
    byId('kz-sa-list-title').textContent=typeLabel(activeType);
    const list=items(activeType);
    byId('kz-sa-list').innerHTML=list.length?list.map(x=>{
      const sub=activeType==='voice'?`${sourceLabel(x.source_kind)} · ${esc(x.dialect||x.language||'普通话')} · ${esc(x.clone_status||'')}`:activeType==='series'?`${esc(x.resolution||'1080x1920')} · ${esc(x.fps||30)}fps · ${esc(x.default_duration||'30 秒')}`:`${esc(x.rights||'')} · ${x.enabled===false?'停用':'启用'}`;
      return `<article class="kz-sa-card ${editingId===x.id?'active':''}" data-kz-sa-id="${esc(x.id)}"><b>${esc(x.name)}</b><span>${sub}</span></article>`;
    }).join(''):`<div class="kz-sa-empty">还没有${typeLabel(activeType)}资产。点击“新增”开始建立。</div>`;
    byId('kz-sa-list').querySelectorAll('[data-kz-sa-id]').forEach(card=>card.addEventListener('click',()=>{editingId=card.dataset.kzSaId;render();}));
  }

  function rights(value='待确认'){
    return ['本人或公司自有','已取得授权','公开许可','虚拟资产','待确认'].map(x=>`<option value="${x}" ${value===x?'selected':''}>${x}</option>`).join('');
  }
  function yesNo(value=true){return `<option value="1" ${value!==false?'selected':''}>启用</option><option value="0" ${value===false?'selected':''}>停用</option>`;}
  function genericFields(x={}){
    return `<label>名称<input name="name" value="${esc(x.name||'')}" required placeholder="例如：维修师傅A"></label><label>状态<select name="enabled">${yesNo(x.enabled)}</select></label><label>授权状态<select name="rights">${rights(x.rights)}</select></label><label>标签<input name="tags" value="${esc((x.tags||[]).join('、'))}" placeholder="维修、涟水、真人写实"></label><label class="wide">说明<textarea name="description" placeholder="这个资产长期用于什么内容">${esc(x.description||'')}</textarea></label>`;
  }

  function characterForm(x={}){
    return genericFields(x)+`<label class="wide">外观设定<textarea name="appearance" placeholder="年龄、发型、脸型、身材、气质等">${esc(x.appearance||'')}</textarea></label><label class="wide">默认服装<textarea name="outfit" placeholder="例如：深蓝维修工装、黑色工具腰包">${esc(x.outfit||'')}</textarea></label><label class="wide">人物一致性规则<textarea name="identity_rules" placeholder="同一系列保持脸型、发型、服装、工具一致">${esc(x.identity_rules||'')}</textarea></label>`;
  }
  function sceneForm(x={}){
    return genericFields(x)+`<label class="wide">场景固定规则<textarea name="scene_rules" placeholder="例如：真实居民家庭、自然光、维修现场，不做影棚感">${esc(x.scene_rules||'')}</textarea></label><label class="wide">允许变化项<textarea name="variables" placeholder="房型、设备品牌、时间、天气等">${esc(x.variables||'')}</textarea></label>`;
  }
  function voiceForm(x={}){
    const source=x.source_kind||'self_clone';
    const audio=x.audio_file?`<div class="wide"><audio class="kz-sa-audio" controls src="/api/series-asset-center/audio?id=${encodeURIComponent(x.id)}"></audio></div>`:'';
    return genericFields({...x,rights:x.rights||(source==='ai_original'?'虚拟资产':'待确认')})+`<label>声音来源<select name="source_kind"><option value="self_clone" ${source==='self_clone'?'selected':''}>本人/公司自有声音克隆</option><option value="authorized_clone" ${source==='authorized_clone'?'selected':''}>已授权真人声音克隆</option><option value="public_licensed" ${source==='public_licensed'?'selected':''}>公共授权声音库</option><option value="ai_original" ${source==='ai_original'?'selected':''}>AI原创品牌声音</option></select><div class="kz-sa-source-help">公开能听到不等于允许克隆；公共音色必须登记来源和许可。</div></label><label>语言<input name="language" value="${esc(x.language||'普通话')}" placeholder="普通话"></label><label>方言 / 口音<input name="dialect" value="${esc(x.dialect||'')}" placeholder="例如：涟水方言 / 淮安口音"></label><label>声音风格<input name="style" value="${esc(x.style||'')}" placeholder="稳重、自然、维修师傅口语"></label><label>本地引擎<input name="engine" value="${esc(x.engine||'本地克隆引擎（待接入）')}" placeholder="后续自动绑定本地TTS"></label><label>来源名称<input name="source_name" value="${esc(x.source_name||'')}" placeholder="本人录音 / 某授权配音员 / 声音库名称"></label><label class="wide">许可证 / 授权说明<textarea name="license_note" placeholder="授权范围、许可证、商业使用限制、来源记录">${esc(x.license_note||'')}</textarea></label><label class="wide">参考录音<input type="file" name="audio" accept="audio/*,.wav,.mp3,.m4a,.aac,.ogg,.flac"><div class="kz-sa-source-help">建议正式固定声纹录5–15分钟干净语音；方言包后续可逐步补充。当前先保存录音资产，真正声纹克隆引擎下一阶段接通。</div></label>${audio}<div class="kz-sa-note ${x.audio_file?'kz-sa-good':''}"><b>当前状态：</b>${esc(x.clone_status||'待录音/待克隆')}。系统不会在真正生成声纹模型前把它标记为“克隆可用”。</div>`;
  }
  function seriesForm(x={}){
    const chars=items('character').filter(i=>i.enabled!==false); const voices=items('voice').filter(i=>i.enabled!==false); const scenes=items('scene').filter(i=>i.enabled!==false);
    const opts=(list,val,empty)=>`<option value="">${empty}</option>`+list.map(i=>`<option value="${esc(i.id)}" ${val===i.id?'selected':''}>${esc(i.name)}</option>`).join('');
    return `<label>系列名称<input name="name" value="${esc(x.name||'')}" required placeholder="例如：卡嘴子维修师傅系列"></label><label>状态<select name="enabled">${yesNo(x.enabled)}</select></label><label>固定人物<select name="default_character_id">${opts(chars,x.default_character_id,'自动选择')}</select></label><label>固定声音<select name="default_voice_id">${opts(voices,x.default_voice_id,'自动选择')}</select></label><label>默认场景<select name="default_scene_id">${opts(scenes,x.default_scene_id,'按内容自动换')}</select></label><label>默认时长<input name="default_duration" value="${esc(x.default_duration||'30 秒')}"></label><label>画面比例<input name="ratio" value="${esc(x.ratio||'9:16')}"></label><label>输出规格<input name="resolution" value="${esc(x.resolution||'1080x1920')}"></label><label>帧率<input type="number" min="24" max="60" name="fps" value="${esc(x.fps||30)}"></label><label>字幕风格<input name="subtitle_style" value="${esc(x.subtitle_style||'简洁白字描边')}"></label><label class="wide">默认CTA<textarea name="cta">${esc(x.cta||'')}</textarea></label><label class="wide">系列连续性规则<textarea name="continuity_rules">${esc(x.continuity_rules||'固定人物与声音；场景按内容可替换；同一条视频人物服装和声纹保持一致。')}</textarea></label><label class="wide">系列说明<textarea name="description">${esc(x.description||'')}</textarea></label><div class="kz-sa-note kz-sa-good">系列模板用于以后“一句话 → 自动套用人物/声音/输出规则 → 生成视频”。场景可以固定，也可以留空让AI按内容更换。</div>`;
  }

  function renderForm(){
    const x=item(editingId)||{};
    byId('kz-sa-form-title').textContent=(editingId?'编辑':'新建')+typeLabel(activeType);
    const form=byId('kz-sa-form');
    let html=activeType==='character'?characterForm(x):activeType==='voice'?voiceForm(x):activeType==='scene'?sceneForm(x):seriesForm(x);
    html+=`<div class="kz-sa-actions"><button type="submit" class="kz-sa-primary">保存</button>${editingId?'<button type="button" class="kz-sa-danger" id="kz-sa-delete">删除 / 停用</button>':''}<span class="kz-sa-status" id="kz-sa-inline-status"></span></div>`;
    form.innerHTML=html;
    form.addEventListener('submit',saveCurrent,{once:true});
    byId('kz-sa-delete')?.addEventListener('click',deleteCurrent);
  }

  function formPayload(form){
    const fd=new FormData(form); const obj={type:activeType,id:editingId||'',enabled:fd.get('enabled')!=='0'};
    for(const [key,value] of fd.entries()){
      if(key==='audio'||key==='enabled') continue;
      obj[key]=String(value||'').trim();
    }
    obj.tags=String(obj.tags||'').split(/[、,，\s]+/).map(x=>x.trim()).filter(Boolean);
    if(activeType==='series') obj.fps=Number(obj.fps||30);
    return obj;
  }
  async function fileBase64(file){
    return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(reader.error||new Error('读取录音失败'));reader.readAsDataURL(file);});
  }
  async function saveCurrent(event){
    event.preventDefault(); const form=event.currentTarget; const status=byId('kz-sa-inline-status');
    try{
      status.textContent='正在保存…';
      const payload=formPayload(form);
      const saved=await post('/api/series-asset-center/save',payload);
      editingId=saved.id;
      const audio=form.elements.audio?.files?.[0];
      if(activeType==='voice'&&audio){
        if(audio.size>30*1024*1024) throw new Error('录音文件不能超过30MB');
        status.textContent='正在保存参考录音…';
        await post('/api/series-asset-center/audio-upload',{id:saved.id,name:audio.name,base64:await fileBase64(audio)});
      }
      await refresh();
      await refreshSimpleSelects();
      byId('kz-sa-inline-status').textContent='已保存';
    }catch(error){status.textContent=error.message; status.style.color='#b33d3d'; form.addEventListener('submit',saveCurrent,{once:true});}
  }
  async function deleteCurrent(){
    if(!editingId||!confirm('确认删除这个系列资产？相关人物/声音/场景会从新生产任务中停用。')) return;
    try{await post('/api/series-asset-center/delete',{id:editingId});editingId='';await refresh();await refreshSimpleSelects();}catch(error){byId('kz-sa-inline-status').textContent=error.message;}
  }

  async function refreshSimpleSelects(){
    try{
      const center=await api('/api/ai-content-center');
      const fill=(id,type,auto)=>{const select=byId(id);if(!select)return;const old=select.value;const usable=(center.assets||[]).filter(x=>x.asset_type===type&&x.enabled!==false&&!String(x.rights||'').includes('待确认'));select.innerHTML=`<option value="">${auto}</option>`+usable.map(x=>`<option value="${esc(x.id)}" data-name="${esc(x.name)}">${esc(x.name)} · ${esc(x.rights||'已登记')}</option>`).join('');if([...select.options].some(o=>o.value===old))select.value=old;};
      fill('kz-simple-character','人物','自动选择 / 不固定人物');fill('kz-simple-scene','场景','AI 自动推荐场景');fill('kz-simple-voice','声音','AI 自动选择 / 暂不固定声音');
    }catch(_){ }
  }

  async function refresh(){
    state=await api('/api/series-asset-center',{cache:'no-store'});
    renderTabs();renderList();renderForm();
    const engine=state.voice_engine_status||'';
    const node=byId('kz-sa-status'); if(node) node.textContent=activeType==='voice'?engine:'';
  }
  async function open(){
    installStyle();shell().hidden=false;
    try{await refresh();}catch(error){byId('kz-sa-list').innerHTML=`<div class="kz-sa-empty">${esc(error.message)}</div>`;}
  }
  function close(){const root=byId('kz-series-assets');if(root)root.hidden=true;}
  function render(){renderTabs();renderList();renderForm();}

  function bindEntry(){
    const install=()=>{
      if(!byId('studio-root')) return;
      installStyle();shell();
      const existing=byId('kz-simple-assets');
      if(existing&&!existing.dataset.kzSeriesBound){
        existing.dataset.kzSeriesBound='1';
        existing.textContent='管理人物 / 声音 / 场景 / 系列';
        existing.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();open();},true);
      }
      const actions=document.querySelector('.kz-simple-actions');
      if(actions&&!byId('kz-series-assets-direct')){
        const btn=document.createElement('button');btn.type='button';btn.id='kz-series-assets-direct';btn.className='kz-simple-secondary';btn.textContent='系列资产中心';btn.addEventListener('click',open);actions.appendChild(btn);
      }
    };
    install();
    const observer=new MutationObserver(()=>install());observer.observe(document.documentElement,{childList:true,subtree:true});
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',bindEntry,{once:true}); else bindEntry();
})();

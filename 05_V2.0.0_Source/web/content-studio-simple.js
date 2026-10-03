(() => {
  'use strict';
  if (window.__KZ_CONTENT_STUDIO_SIMPLE__) return;
  window.__KZ_CONTENT_STUDIO_SIMPLE__ = true;

  const REF_KEY = 'kazuizhi.reference-center.v1';
  const PIPELINE_KEY = 'kazuizhi.content-pipeline.v1';
  const MODE_KEY = 'kazuizhi.content-studio.mode';
  const ROUTER_URL = 'http://127.0.0.1:17777/v1/chat/completions';
  const ROUTER_MODEL = 'kazuizhi-auto';
  const byId = id => document.getElementById(id);
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function readJson(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback; }
    catch { return fallback; }
  }
  function writeJson(key, value) { localStorage.setItem(key, JSON.stringify(value)); }
  function now() { return new Date().toISOString(); }
  function apiJson(url, options={}) {
    return fetch(url, options).then(async response => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || data.error || data.message || `HTTP ${response.status}`);
      return data;
    });
  }

  function cleanShareText(raw='') {
    let value = String(raw || '').trim();
    const url = value.match(/https?:\/\/[^\s]+/i)?.[0] || '';
    value = value.replace(/https?:\/\/[^\s]+/ig, ' ')
      .replace(/复制(?:此)?链接[^。！？\n]*/g, ' ')
      .replace(/打开(?:抖音|小红书|B站|哔哩哔哩|微信|视频号|快手)[^。！？\n]*/g, ' ')
      .replace(/\b\d{4}[\/-]\d{1,2}[\/-]\d{1,2}\b/g, ' ')
      .replace(/\b\d{1,2}:\d{2}(?::\d{2})?\b/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    return {url, text:value};
  }

  function inferTitle(text, url) {
    const base = String(text || '').replace(/[#@][^\s]+/g, '').trim();
    if (base) return base.slice(0, 42);
    const u = String(url || '').toLowerCase();
    if (u.includes('douyin')) return '抖音参考视频';
    if (u.includes('xiaohongshu') || u.includes('xhslink')) return '小红书参考内容';
    if (u.includes('bilibili') || u.includes('b23.tv')) return 'B站参考视频';
    if (u.includes('weixin')) return '视频号参考内容';
    if (u.includes('kuaishou')) return '快手参考视频';
    return '外部参考内容';
  }

  function installStyle() {
    if (byId('kz-simple-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-simple-style';
    style.textContent = `
      body.kz-simple-mode .studio-tabs,body.kz-simple-mode #studio-pages,body.kz-simple-mode #kz-pipeline-progress{display:none!important}
      body.kz-simple-mode .studio-brand{min-width:unset}
      .kz-simple-toggle{height:32px;border-radius:4px;border:1px solid rgba(255,255,255,.24);background:rgba(255,255,255,.08);color:#fff;padding:0 11px;font-size:12px;cursor:pointer}
      .kz-simple-toggle.active{background:#1768e5;border-color:#1768e5;font-weight:700}
      .kz-simple{display:none;padding:0 14px 18px}.kz-simple.active{display:block}
      .kz-simple-hero{background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:16px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;gap:16px}
      .kz-simple-hero small{display:block;color:#1768e5;font-weight:700;font-size:11px}.kz-simple-hero h2{font-size:22px;margin:4px 0}.kz-simple-hero p{margin:0;color:#6d7f96;font-size:13px}.kz-simple-badge{font-size:12px;color:#16875c;background:#e8f7f0;border-radius:4px;padding:7px 10px;white-space:nowrap}
      .kz-simple-flow{display:flex;gap:8px;align-items:center;margin:0 0 12px;background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:10px 12px;overflow-x:auto}.kz-simple-flow span{height:28px;display:inline-flex;align-items:center;padding:0 9px;border-radius:4px;background:#edf3fb;color:#55708e;font-size:11px;white-space:nowrap}.kz-simple-flow i{font-style:normal;color:#9aaabd}
      .kz-simple-main{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(330px,.65fr);gap:12px}.kz-simple-card{background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:16px}.kz-simple-card h3{font-size:15px;margin:0 0 4px}.kz-simple-card>p{font-size:12px;color:#6d7f96;margin:0 0 12px}.kz-simple-card label{display:block;font-size:12px;color:#53677e}.kz-simple-card textarea,.kz-simple-card input,.kz-simple-card select{width:100%;margin-top:5px;border:1px solid #c9d7e7;border-radius:4px;background:#fff;color:#17324f;font:inherit}.kz-simple-card textarea{min-height:116px;padding:10px;resize:vertical}.kz-simple-card input,.kz-simple-card select{height:36px;padding:0 10px}
      .kz-simple-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:10px}.kz-simple-wide{grid-column:1/-1}.kz-simple-choice{position:relative}.kz-simple-choice small{display:block;margin-top:4px;color:#8a99aa;font-size:10px}
      .kz-simple-analysis{display:none;margin-top:12px;border:1px solid #dce7f4;background:#f7faff;border-radius:7px;padding:12px}.kz-simple-analysis.show{display:block}.kz-simple-analysis h4{margin:0 0 7px;font-size:13px}.kz-simple-analysis p{margin:4px 0;font-size:12px;line-height:1.6;color:#415c78}.kz-simple-analysis b{color:#17324f}
      .kz-simple-actions{display:flex;gap:8px;align-items:center;margin-top:14px;flex-wrap:wrap}.kz-simple-primary,.kz-simple-secondary{height:40px;border-radius:4px;padding:0 16px;font-size:13px;cursor:pointer}.kz-simple-primary{border:1px solid #1768e5;background:#1768e5;color:#fff;font-weight:800;min-width:180px}.kz-simple-primary:disabled{opacity:.55;cursor:wait}.kz-simple-secondary{border:1px solid #b9cbe0;background:#fff;color:#24496f}
      .kz-simple-progress{display:grid;gap:8px}.kz-simple-progress div{display:flex;align-items:center;gap:10px;padding:10px;border:1px solid #edf1f6;border-radius:6px}.kz-simple-progress i{width:10px;height:10px;border-radius:50%;background:#cbd6e4}.kz-simple-progress div.active i{background:#1768e5}.kz-simple-progress div.done i{background:#1b9a64}.kz-simple-progress div.warn i{background:#d39b35}.kz-simple-progress b{font-size:13px}.kz-simple-progress span{margin-left:auto;font-size:11px;color:#6d7f96;text-align:right}
      .kz-simple-note{margin-top:12px;padding:10px;border-radius:6px;background:#fff8ea;border:1px solid #f1d7a7;color:#8b641d;font-size:12px;line-height:1.6}.kz-simple-result{margin-top:12px;padding:12px;border-radius:6px;background:#f7faff;border:1px solid #dce7f4;font-size:12px;line-height:1.7;color:#415c78}.kz-simple-result b{color:#17324f}.kz-simple-error{background:#fff0f0;border-color:#efc0c0;color:#b33d3d}.kz-simple-success{background:#eefaf4;border-color:#bfe6d2}
      .kz-simple-explain{margin-top:12px;border-top:1px solid #edf1f6;padding-top:12px}.kz-simple-explain summary{font-size:12px;color:#55708e;cursor:pointer}.kz-simple-explain p{font-size:11px;color:#76889d;line-height:1.6}
      @media(max-width:1000px){.kz-simple-main{grid-template-columns:1fr}.kz-simple-grid{grid-template-columns:1fr}.kz-simple-wide{grid-column:auto}.kz-simple-hero{align-items:flex-start;flex-direction:column}}
    `;
    document.head.appendChild(style);
  }

  function announceSimple() {
    try { parent.postMessage({type:'kz-content-studio-route-changed',route:'overview',title:'一键内容生成',subtitle:'选人、选场景、选声音、改内容，其余交给后台'}, location.origin); } catch (_) {}
  }

  function setMode(simple) {
    document.body.classList.toggle('kz-simple-mode', simple);
    byId('kz-simple-root')?.classList.toggle('active', simple);
    byId('kz-simple-toggle')?.classList.toggle('active', simple);
    byId('kz-pro-toggle')?.classList.toggle('active', !simple);
    localStorage.setItem(MODE_KEY, simple ? 'simple' : 'pro');
    if (simple) {
      announceSimple();
      window.scrollTo({top:0,behavior:'auto'});
      loadAssets();
    } else {
      try { window.changePage?.('overview'); } catch (_) {}
    }
    window.dispatchEvent(new Event('resize'));
  }

  function installToggle() {
    const meta = document.querySelector('.studio-route-meta');
    if (!meta || byId('kz-simple-toggle')) return;
    meta.insertAdjacentHTML('afterbegin','<button id="kz-simple-toggle" class="kz-simple-toggle" type="button">简单模式</button><button id="kz-pro-toggle" class="kz-simple-toggle" type="button">专业模式</button>');
    byId('kz-simple-toggle').addEventListener('click',()=>setMode(true));
    byId('kz-pro-toggle').addEventListener('click',()=>setMode(false));
  }

  function buildSimple() {
    if (byId('kz-simple-root')) return;
    const pages = byId('studio-pages');
    if (!pages) return;
    pages.insertAdjacentHTML('beforebegin', `
      <section id="kz-simple-root" class="kz-simple" aria-label="卡嘴子一键内容生成">
        <div class="kz-simple-hero"><div><small>默认模式 · 前台只负责“我想要什么”</small><h2>选人、选地点、选声音、改内容，然后一键生成</h2><p>AI 分析、原创改写、导演、分镜、模型路由、RTX3060 任务、候选和质检都放到后台自动完成。</p></div><span class="kz-simple-badge">推荐日常使用</span></div>
        <div class="kz-simple-flow"><span>1 粘贴参考</span><i>→</i><span>2 改成我们的内容</span><i>→</i><span>3 选择人 / 场景 / 声音</span><i>→</i><span>4 一键生成多个方向</span><i>→</i><span>5 选择喜欢的结果</span></div>
        <div class="kz-simple-main">
          <section class="kz-simple-card">
            <h3>你想做什么视频</h3><p>普通使用只需要把下面几项选清楚，不需要知道后台调用哪个模型。</p>
            <label>参考视频 / 分享内容<textarea id="kz-simple-source" placeholder="直接粘贴抖音、视频号、小红书、B站、快手链接；最好把平台分享出来的整段文字一起粘贴。"></textarea></label>
            <div id="kz-simple-analysis" class="kz-simple-analysis"></div>
            <div class="kz-simple-grid">
              <label class="kz-simple-wide">我想怎么改<textarea id="kz-simple-request" placeholder="可不填。比如：改成涟水本地真实维修案例；不要照搬原文；突出师傅专业、上门快；结尾引导用户进入卡嘴子咨询。"></textarea></label>
              <label class="kz-simple-choice">人物<select id="kz-simple-character"><option value="">正在读取人物资产…</option></select><small>固定人物会用于镜头一致性</small></label>
              <label class="kz-simple-choice">地点 / 场景<select id="kz-simple-scene"><option value="">正在读取场景资产…</option></select><small>不选则由 AI 按内容推荐</small></label>
              <label class="kz-simple-choice">声音<select id="kz-simple-voice"><option value="">正在读取声音资产…</option></select><small>只使用已登记或授权声音</small></label>
              <label>视频方向<select id="kz-simple-direction"><option value="自动推荐">自动推荐</option><option value="真实维修案例">真实维修案例</option><option value="师傅科普">师傅科普</option><option value="真实素材+AI补镜">真实素材 + AI补镜</option><option value="数字人口播">数字人口播</option><option value="轻剧情">轻剧情</option></select></label>
              <label>视频时长<select id="kz-simple-duration"><option value="15 秒">15 秒</option><option value="30 秒" selected>30 秒</option><option value="45 秒">45 秒</option><option value="60 秒">60 秒</option></select></label>
              <label>画面比例<select id="kz-simple-ratio"><option value="9:16" selected>9:16 短视频</option><option value="16:9">16:9 横屏</option><option value="1:1">1:1 方形</option></select></label>
              <label>生成几个方向<select id="kz-simple-version-count"><option value="1">1 个</option><option value="2">2 个</option><option value="3" selected>3 个</option></select></label>
            </div>
            <div class="kz-simple-actions"><button id="kz-simple-start" class="kz-simple-primary" type="button">一键生成卡嘴子版本</button><button id="kz-simple-assets" class="kz-simple-secondary" type="button">管理人物 / 场景 / 声音</button></div>
            <div class="kz-simple-note">当前纯链接若拿不到可验证字幕，系统会提示补充平台分享文案/字幕，不会凭链接编造原视频内容。后续接入真实平台解析器后可进一步做到“只贴链接”。</div>
            <div id="kz-simple-result" class="kz-simple-result" hidden></div>
          </section>
          <aside class="kz-simple-card">
            <h3>后台自动完成</h3><p>这里仅显示人能看懂的阶段，不显示模型和显卡参数。</p>
            <div class="kz-simple-progress">
              <div data-simple-stage="reference"><i></i><b>分析参考内容</b><span>文案 / 开头 / 过程 / 结尾</span></div>
              <div data-simple-stage="creative"><i></i><b>改成我们的内容</b><span>原创重构多个方向</span></div>
              <div data-simple-stage="director"><i></i><b>自动导演和分镜</b><span>人物 / 场景 / 声音 / 镜头</span></div>
              <div data-simple-stage="production"><i></i><b>后台生产</b><span>匹配素材 / RTX3060 补镜</span></div>
              <div data-simple-stage="candidates"><i></i><b>生成候选</b><span>每个镜头进入候选队列</span></div>
            </div>
            <details class="kz-simple-explain"><summary>专业人员需要时再展开</summary><p>专业模式里仍保留内容情报、参考拆解、创意策划、AI 导演、分镜、资产、质检和成片库。简单模式只是给复杂后台盖了一层极简前台，没有删除任何专业能力。</p></details>
          </aside>
        </div>
      </section>`);
    byId('kz-simple-start').addEventListener('click', runSimpleFlow);
    byId('kz-simple-assets').addEventListener('click',()=>{ setMode(false); window.changePage?.('assets'); });
  }

  function setStage(stage, state='active') {
    const order=['reference','creative','director','production','candidates'];
    const index=order.indexOf(stage);
    document.querySelectorAll('[data-simple-stage]').forEach((node,i)=>{
      node.classList.remove('active','done','warn');
      if (i < index || (i === index && state === 'done')) node.classList.add('done');
      else if (i === index) node.classList.add(state === 'warn' ? 'warn' : 'active');
    });
  }

  async function loadAssets() {
    const character=byId('kz-simple-character'), scene=byId('kz-simple-scene'), voice=byId('kz-simple-voice');
    if(!character || !scene || !voice) return;
    try {
      const data=await apiJson('/api/ai-content-center');
      const usable=(type)=>(data.assets||[]).filter(x=>x.asset_type===type && x.enabled!==false && !String(x.rights||'').includes('待确认'));
      const fill=(select,type,autoText)=>{
        const items=usable(type);
        select.innerHTML=`<option value="">${autoText}</option>`+items.map(x=>`<option value="${esc(x.id)}" data-name="${esc(x.name)}">${esc(x.name)} · ${esc(x.rights||'已登记')}</option>`).join('');
      };
      fill(character,'人物','自动选择 / 不固定人物');
      fill(scene,'场景','AI 自动推荐场景');
      fill(voice,'声音','AI 自动选择 / 暂不固定声音');
    } catch (_) {
      character.innerHTML='<option value="">自动选择 / 暂未读取人物</option>';
      scene.innerHTML='<option value="">AI 自动推荐场景</option>';
      voice.innerHTML='<option value="">AI 自动选择声音</option>';
    }
  }

  function selectedMeta(id) {
    const select=byId(id), option=select?.selectedOptions?.[0];
    return {id:select?.value||'', name:option?.dataset?.name || (select?.value ? option?.textContent?.split(' · ')[0] : '') || ''};
  }

  function showAnalysis(item) {
    const box=byId('kz-simple-analysis'); if(!box || !item?.analysis) return;
    const a=item.analysis;
    const structure=(a.structure||[]).map(x=>`${x.stage||x.title||''}：${x.detail||x.content||''}`).filter(Boolean).slice(0,5).join('；');
    box.classList.add('show');
    box.innerHTML=`<h4>AI 已看懂这条参考内容</h4><p><b>主题：</b>${esc(a.summary||item.title||'')}</p><p><b>开头：</b>${esc(a.hook||'已分析')}</p><p><b>过程：</b>${esc(structure||'已完成结构拆解')}</p><p><b>下一步：</b>系统会重新写成卡嘴子自己的内容，不直接复用未授权原画面、声音和水印。</p>`;
  }

  function showResult(html, bad=false, success=false) {
    const box=byId('kz-simple-result'); if(!box) return;
    box.hidden=false;
    box.className=`kz-simple-result${bad?' kz-simple-error':''}${success?' kz-simple-success':''}`;
    box.innerHTML=html;
  }

  async function waitFor(test, timeout=45000, interval=300) {
    const end=Date.now()+timeout;
    while(Date.now()<end){ const value=test(); if(value) return value; await sleep(interval); }
    throw new Error('等待本地 AI 处理超时，请检查本地服务后重试。');
  }

  function selectedReference() {
    const store=readJson(REF_KEY,{items:[],selectedId:''});
    return (store.items||[]).find(x=>x.id===store.selectedId) || (store.items||[])[0] || null;
  }

  function makeCreative(item, version, index, direction, duration, request) {
    const useDirection=direction && direction!=='自动推荐' ? direction : (version.format || '真实案例');
    return {
      id:`CR-${item.id}-${index+1}-${Date.now()}`,
      name:version.name||`卡嘴子版本 ${index+1}`,
      topic:item.title||version.name||'卡嘴子原创内容',
      idea:[version.idea||'',request||''].filter(Boolean).join('\n'),
      hook:version.hook||'',
      format:useDirection,
      audience:'本地服务用户',
      duration,
      cta:'需要本地服务时进入卡嘴子咨询或下单',
      referenceId:item.id,
      updatedAt:now()
    };
  }

  function directorBrief(creative, choices) {
    return [
      `主题：${creative.topic}`,
      creative.idea && `内容修改要求：${creative.idea}`,
      creative.hook && `开头方向：${creative.hook}`,
      `视频方向：${creative.format}`,
      `目标时长：${creative.duration}`,
      choices.character.name && `固定人物：${choices.character.name}`,
      choices.scene.name && `固定场景：${choices.scene.name}`,
      choices.voice.name && `固定声音：${choices.voice.name}`,
      '要求：先理解参考内容，再重写为卡嘴子原创表达；真实素材优先；缺口才调用本地 RTX3060 图片/视频能力；不要复用未授权原画面、原声音、平台水印。'
    ].filter(Boolean).join('\n');
  }

  async function generatePlanFor(creative, reference, choices, previousPlanId='') {
    writeJson(PIPELINE_KEY,{reference,creatives:[creative],selectedCreative:creative,directorPlan:null,productionProjectId:'',updatedAt:now()});
    window.changePage?.('director');
    await sleep(120);
    if(byId('director-character')) byId('director-character').value=choices.character.name;
    if(byId('director-scene')) byId('director-scene').value=choices.scene.name;
    if(byId('director-style')) {
      const select=byId('director-style');
      const map={'真实维修案例':'真实纪实','师傅科普':'专业科普','数字人口播':'生活化口播','真实素材+AI补镜':'真实纪实','轻剧情':'轻剧情'};
      if(map[creative.format] && [...select.options].some(o=>o.value===map[creative.format])) select.value=map[creative.format];
    }
    if(byId('director-brief')) byId('director-brief').value=directorBrief(creative,choices);
    byId('director-to-production')?.click();
    return waitFor(()=>{
      const plan=readJson(PIPELINE_KEY,{}).directorPlan;
      return plan?.shots?.length && plan.id!==previousPlanId ? plan : null;
    },45000,400);
  }

  async function importPlan(plan, creative, reference, choices, ratio, versionIndex) {
    const payload={
      name:`${creative.topic||creative.name||reference.title||'内容项目'} · 版本${versionIndex+1}`,
      script:plan.shots.map(s=>s.narration).filter(Boolean).join('\n'),
      ratio,
      reference_id:reference.id||'',
      creative_id:creative.id||'',
      director_plan_id:plan.id,
      director_goal:plan.goal||'',
      director_style:plan.style||'',
      director_summary:plan.summary||'',
      shots:plan.shots
    };
    const data=await apiJson('/api/ai-content-center/director/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const projectId=data?.project?.id||data?.project_id||'';
    if(!projectId) throw new Error('生产项目已提交，但未返回项目 ID。');
    return projectId;
  }

  async function queueCandidates(projectId, assetIds) {
    const center=await apiJson('/api/ai-content-center');
    const shots=(center.storyboards||[]).filter(x=>x.project_id===projectId).sort((a,b)=>(a.order||0)-(b.order||0));
    let queued=0;
    for(const shot of shots){
      try {
        await apiJson('/api/ai-content-center/candidates/queue',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({shot_id:shot.id,asset_ids:assetIds.filter(Boolean)})});
        queued+=1;
      } catch (_) {}
    }
    return {queued,total:shots.length};
  }

  async function runSimpleFlow() {
    const button=byId('kz-simple-start');
    const raw=byId('kz-simple-source')?.value.trim()||'';
    const parsed=cleanShareText(raw);
    if(!parsed.url && !parsed.text){showResult('<b>先粘贴一个视频链接或分享内容。</b>',true);return;}
    if(!parsed.text){
      showResult('<b>已经识别到链接，但还没有可验证的字幕/文案。</b><br>请把平台“分享”出来的整段文字、字幕或口播内容一起粘贴，再点生成。纯链接解析器接通后这里会进一步自动化。',true);
      return;
    }

    const choices={
      character:selectedMeta('kz-simple-character'),
      scene:selectedMeta('kz-simple-scene'),
      voice:selectedMeta('kz-simple-voice'),
      direction:byId('kz-simple-direction')?.value||'自动推荐',
      duration:byId('kz-simple-duration')?.value||'30 秒',
      ratio:byId('kz-simple-ratio')?.value||'9:16',
      versionCount:Math.max(1,Math.min(3,Number(byId('kz-simple-version-count')?.value||3))),
      request:byId('kz-simple-request')?.value.trim()||''
    };

    button.disabled=true;button.textContent='后台正在自动处理…';
    showResult('<b>已开始：</b>前台不用再操作，后台正在分析参考、原创改写、导演分镜并建立候选任务。');

    try {
      setStage('reference');
      window.changePage?.('reference');
      await sleep(150);
      const url=byId('reference-url'),text=byId('reference-text'),title=byId('reference-title');
      if(!text||!title) throw new Error('参考内容模块还没有准备好，请刷新后重试。');
      if(url) url.value=parsed.url;
      text.value=parsed.text;
      title.value=inferTitle(parsed.text,parsed.url);
      if(byId('reference-rights')) byId('reference-rights').value='reference_only';
      byId('reference-create')?.click();
      const ref=await waitFor(()=>selectedReference(),5000);
      await sleep(150);
      document.querySelector(`[data-ref-analyze="${CSS.escape(ref.id)}"]`)?.click();
      const analyzed=await waitFor(()=>{
        const item=selectedReference();
        if(item?.status==='异常') throw new Error(item.error||'参考分析失败');
        return item?.analysis?item:null;
      },45000,400);
      showAnalysis(analyzed);
      setStage('reference','done');

      setStage('creative');
      document.querySelector(`[data-ref-creative="${CSS.escape(analyzed.id)}"]`)?.click();
      const creativeItem=await waitFor(()=>{
        const item=selectedReference();
        return item?.creative?.versions?.length?item:null;
      },7000);
      const versions=(creativeItem.creative.versions||[]).slice(0,choices.versionCount);
      if(!versions.length) throw new Error('没有生成可用的原创方向。');
      setStage('creative','done');

      const reference={id:creativeItem.id,title:creativeItem.title||'',platform:creativeItem.platform||'',source:creativeItem.url||'',rights:creativeItem.rights||'',analysis:creativeItem.analysis||null};
      const assets=[choices.character.id,choices.scene.id,choices.voice.id].filter(Boolean);
      const results=[];
      let previousPlanId='';
      setStage('director');

      for(let i=0;i<versions.length;i++){
        const creative=makeCreative(creativeItem,versions[i],i,choices.direction,choices.duration,choices.request);
        const plan=await generatePlanFor(creative,reference,choices,previousPlanId);
        previousPlanId=plan.id;
        const projectId=await importPlan(plan,creative,reference,choices,choices.ratio,i);
        results.push({creative,plan,projectId,queue:null});
      }
      setStage('director','done');
      setStage('production');
      setStage('production','done');

      setStage('candidates');
      for(const result of results){
        result.queue=await queueCandidates(result.projectId,assets);
      }
      setStage('candidates','done');

      const totalShots=results.reduce((sum,r)=>sum+(r.plan?.shots?.length||0),0);
      const totalQueued=results.reduce((sum,r)=>sum+(r.queue?.queued||0),0);
      const names=results.map((r,i)=>`版本${i+1}：${r.creative.name}`).join('<br>');
      showResult(`<b>后台生产任务已经建立。</b><br>${names}<br>共 ${results.length} 个方向、${totalShots} 个分镜，已排入 ${totalQueued} 个镜头候选任务。<br><span>本地执行器会继续调用素材和 RTX3060；在真实候选文件生成前不会显示“成片完成”。</span><br><button type="button" class="kz-simple-secondary" id="kz-simple-view-production" style="margin-top:8px">查看后台生产</button>`,false,true);
      byId('kz-simple-view-production')?.addEventListener('click',()=>{setMode(false);window.changePage?.('content');});
      announceSimple();
    } catch(error) {
      showResult(`<b>这一步没有完成：</b>${esc(error.message)}<br>已经完成的数据会保留，可以直接重试。`,true);
      announceSimple();
    } finally {
      button.disabled=false;button.textContent='一键生成卡嘴子版本';
    }
  }

  function install() {
    if(!byId('studio-root')) return;
    installStyle();
    installToggle();
    buildSimple();
    const preferred=localStorage.getItem(MODE_KEY);
    setMode(preferred!=='pro');
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>setTimeout(install,80),{once:true});
  else setTimeout(install,80);
})();
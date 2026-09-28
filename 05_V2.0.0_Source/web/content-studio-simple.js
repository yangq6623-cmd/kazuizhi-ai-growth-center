(() => {
  'use strict';
  if (window.__KZ_CONTENT_STUDIO_SIMPLE__) return;
  window.__KZ_CONTENT_STUDIO_SIMPLE__ = true;

  const REF_KEY = 'kazuizhi.reference-center.v1';
  const PIPELINE_KEY = 'kazuizhi.content-pipeline.v1';
  const MODE_KEY = 'kazuizhi.content-studio.mode';
  const byId = id => document.getElementById(id);
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function readJson(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback; }
    catch { return fallback; }
  }
  function writeJson(key, value) { localStorage.setItem(key, JSON.stringify(value)); }
  function now() { return new Date().toISOString(); }

  function cleanShareText(raw='') {
    let value = String(raw || '').trim();
    const url = value.match(/https?:\/\/[^\s]+/i)?.[0] || '';
    value = value.replace(/https?:\/\/[^\s]+/ig, ' ')
      .replace(/复制(?:此)?链接[^。！？\n]*/g, ' ')
      .replace(/打开(?:抖音|小红书|B站|哔哩哔哩|微信|视频号)[^。！？\n]*/g, ' ')
      .replace(/\b\d{4}[\/-]\d{1,2}[\/-]\d{1,2}\b/g, ' ')
      .replace(/\b\d{1,2}:\d{2}(?::\d{2})?\b/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    return {url, text:value};
  }

  function inferTitle(text, url) {
    const base = String(text || '').replace(/[#@][^\s]+/g, '').trim();
    if (base) return base.slice(0, 42);
    if (url.includes('douyin')) return '抖音参考视频';
    if (url.includes('xiaohongshu') || url.includes('xhslink')) return '小红书参考内容';
    if (url.includes('bilibili') || url.includes('b23.tv')) return 'B站参考视频';
    if (url.includes('weixin')) return '视频号参考内容';
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
      .kz-simple{display:none;padding:0 14px 16px}.kz-simple.active{display:block}
      .kz-simple-hero{background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:16px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;gap:16px}
      .kz-simple-hero small{display:block;color:#1768e5;font-weight:700;font-size:11px}.kz-simple-hero h2{font-size:22px;margin:4px 0}.kz-simple-hero p{margin:0;color:#6d7f96;font-size:13px}.kz-simple-badge{font-size:12px;color:#16875c;background:#e8f7f0;border-radius:4px;padding:7px 10px;white-space:nowrap}
      .kz-simple-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:12px}.kz-simple-step{background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:14px}.kz-simple-step b{display:block;font-size:14px;margin:4px 0}.kz-simple-step span{font-size:12px;color:#6d7f96}.kz-simple-num{width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:#e8f1ff;color:#1768e5;font-weight:800;font-size:12px}
      .kz-simple-main{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(320px,.75fr);gap:12px}.kz-simple-card{background:#fff;border:1px solid #dfe7f1;border-radius:8px;padding:16px}.kz-simple-card h3{font-size:15px;margin:0 0 12px}.kz-simple-card label{display:block;font-size:12px;color:#53677e;margin-top:10px}.kz-simple-card textarea,.kz-simple-card input,.kz-simple-card select{width:100%;margin-top:5px;border:1px solid #c9d7e7;border-radius:4px;background:#fff;color:#17324f;font:inherit}.kz-simple-card textarea{min-height:150px;padding:10px;resize:vertical}.kz-simple-card input,.kz-simple-card select{height:36px;padding:0 10px}
      .kz-simple-actions{display:flex;gap:8px;align-items:center;margin-top:14px}.kz-simple-primary,.kz-simple-secondary{height:40px;border-radius:4px;padding:0 16px;font-size:13px;cursor:pointer}.kz-simple-primary{border:1px solid #1768e5;background:#1768e5;color:#fff;font-weight:800}.kz-simple-primary:disabled{opacity:.55;cursor:wait}.kz-simple-secondary{border:1px solid #b9cbe0;background:#fff;color:#24496f}
      .kz-simple-progress{display:grid;gap:8px}.kz-simple-progress div{display:flex;align-items:center;gap:10px;padding:10px;border:1px solid #edf1f6;border-radius:6px}.kz-simple-progress i{width:10px;height:10px;border-radius:50%;background:#cbd6e4}.kz-simple-progress div.active i{background:#1768e5}.kz-simple-progress div.done i{background:#1b9a64}.kz-simple-progress b{font-size:13px}.kz-simple-progress span{margin-left:auto;font-size:11px;color:#6d7f96}
      .kz-simple-note{margin-top:12px;padding:10px;border-radius:6px;background:#fff8ea;border:1px solid #f1d7a7;color:#8b641d;font-size:12px;line-height:1.6}.kz-simple-result{margin-top:12px;padding:12px;border-radius:6px;background:#f7faff;border:1px solid #dce7f4;font-size:12px;line-height:1.7;color:#415c78}.kz-simple-result b{color:#17324f}.kz-simple-error{background:#fff0f0;border-color:#efc0c0;color:#b33d3d}
      @media(max-width:1000px){.kz-simple-main{grid-template-columns:1fr}.kz-simple-steps{grid-template-columns:1fr}.kz-simple-hero{align-items:flex-start;flex-direction:column}}
    `;
    document.head.appendChild(style);
  }

  function announceSimple() {
    try { parent.postMessage({type:'kz-content-studio-route-changed',route:'overview',title:'一键内容生成',subtitle:'粘贴参考内容、选人物，一键生成卡嘴子版本'}, location.origin); } catch (_) {}
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
      loadCharacters();
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
        <div class="kz-simple-hero"><div><small>默认模式 · 只做三件事</small><h2>粘贴链接 → 选人物 → 一键生成</h2><p>复杂的创意策划、AI 导演、分镜和模型参数由系统自动处理，需要时再进入专业模式修改。</p></div><span class="kz-simple-badge">推荐日常使用</span></div>
        <div class="kz-simple-steps">
          <article class="kz-simple-step"><span class="kz-simple-num">1</span><b>粘贴参考内容</b><span>粘贴视频链接或整段分享文案，AI 拆开头、过程、结尾和表达方法。</span></article>
          <article class="kz-simple-step"><span class="kz-simple-num">2</span><b>选择我们的人物</b><span>从卡嘴子人物资产里选一个固定人物，保持后续镜头一致。</span></article>
          <article class="kz-simple-step"><span class="kz-simple-num">3</span><b>一键生成卡嘴子版本</b><span>系统自动重写创意、AI 导演、分镜并送入生产工作台。</span></article>
        </div>
        <div class="kz-simple-main">
          <section class="kz-simple-card"><h3>开始制作</h3>
            <label>参考视频 / 分享内容<textarea id="kz-simple-source" placeholder="直接粘贴抖音、视频号、小红书、B站链接；也可以把“分享文案 + 链接”整段粘贴进来。"></textarea></label>
            <label>使用人物<select id="kz-simple-character"><option value="">正在读取人物资产…</option></select></label>
            <label>我想要的效果（可不填）<input id="kz-simple-request" placeholder="例如：30 秒，王师傅真人讲解，真实维修风格"></label>
            <div class="kz-simple-actions"><button id="kz-simple-start" class="kz-simple-primary" type="button">一键生成卡嘴子版本</button><button id="kz-simple-assets" class="kz-simple-secondary" type="button">管理人物</button></div>
            <div class="kz-simple-note">如果平台链接暂时无法自动取得可验证字幕，系统会明确提示你补充分享文案/字幕，不会凭链接猜测原视频内容。</div>
            <div id="kz-simple-result" class="kz-simple-result" hidden></div>
          </section>
          <aside class="kz-simple-card"><h3>系统自动完成</h3><div class="kz-simple-progress">
            <div data-simple-stage="reference"><i></i><b>分析参考内容</b><span>开头 / 过程 / 结尾</span></div>
            <div data-simple-stage="creative"><i></i><b>重写卡嘴子创意</b><span>原创表达</span></div>
            <div data-simple-stage="director"><i></i><b>AI 导演与分镜</b><span>人物 / 场景 / 镜头</span></div>
            <div data-simple-stage="production"><i></i><b>进入生产工作台</b><span>候选生成</span></div>
          </div></aside>
        </div>
      </section>`);
    byId('kz-simple-start').addEventListener('click', runSimpleFlow);
    byId('kz-simple-assets').addEventListener('click',()=>{ setMode(false); window.changePage?.('assets'); });
  }

  function setStage(stage, state='active') {
    const order=['reference','creative','director','production'];
    const index=order.indexOf(stage);
    document.querySelectorAll('[data-simple-stage]').forEach((node,i)=>{
      node.classList.remove('active','done');
      if (i < index || (i === index && state === 'done')) node.classList.add('done');
      else if (i === index) node.classList.add('active');
    });
  }

  async function loadCharacters() {
    const select=byId('kz-simple-character'); if(!select) return;
    try {
      const response=await fetch('/api/ai-content-center');
      const data=await response.json();
      const people=(data.assets||[]).filter(x=>x.asset_type==='人物' && x.enabled!==false && !String(x.rights||'').includes('待确认'));
      select.innerHTML='<option value="">自动选择 / 无固定人物</option>'+people.map(x=>`<option value="${esc(x.id)}" data-name="${esc(x.name)}">${esc(x.name)} · ${esc(x.rights||'已登记')}</option>`).join('');
    } catch (_) { select.innerHTML='<option value="">自动选择 / 暂未读取人物资产</option>'; }
  }

  function showResult(html, bad=false) {
    const box=byId('kz-simple-result'); if(!box) return;
    box.hidden=false; box.className=`kz-simple-result${bad?' kz-simple-error':''}`; box.innerHTML=html;
  }

  async function waitFor(test, timeout=45000, interval=250) {
    const end=Date.now()+timeout;
    while(Date.now()<end){ const value=test(); if(value) return value; await sleep(interval); }
    throw new Error('等待本地 AI 处理超时，请检查本地服务后重试。');
  }

  function selectedReference() {
    const store=readJson(REF_KEY,{items:[],selectedId:''});
    return (store.items||[]).find(x=>x.id===store.selectedId) || (store.items||[])[0] || null;
  }

  async function runSimpleFlow() {
    const button=byId('kz-simple-start');
    const raw=byId('kz-simple-source')?.value.trim()||'';
    const parsed=cleanShareText(raw);
    if (!parsed.url && !parsed.text) { showResult('<b>先粘贴一个视频链接或分享文案。</b>',true); return; }
    if (!parsed.text) {
      showResult('<b>链接已识别，但当前还没有可验证的字幕/文案。</b><br>请把平台“分享文案”、字幕或口播文字也一起粘贴到上面的输入框，再点一次生成。',true);
      return;
    }
    button.disabled=true; button.textContent='正在自动生成…';
    showResult('<b>开始处理：</b>系统会自动完成参考拆解、原创创意、AI 导演和分镜。');
    try {
      setStage('reference');
      window.changePage?.('reference');
      await sleep(120);
      const url=byId('reference-url'), text=byId('reference-text'), title=byId('reference-title');
      if (!text || !title) throw new Error('参考内容模块尚未准备好，请刷新页面后重试。');
      if (url) url.value=parsed.url;
      text.value=parsed.text;
      title.value=inferTitle(parsed.text, parsed.url);
      byId('reference-rights') && (byId('reference-rights').value='reference_only');
      byId('reference-create')?.click();
      const ref=await waitFor(()=>selectedReference(),5000);
      await sleep(120);
      document.querySelector(`[data-ref-analyze="${CSS.escape(ref.id)}"]`)?.click();
      const analyzed=await waitFor(()=>{
        const item=selectedReference();
        if (item?.status==='异常') throw new Error(item.error||'参考分析失败');
        return item?.analysis ? item : null;
      },45000,400);
      setStage('reference','done');
      setStage('creative');
      document.querySelector(`[data-ref-creative="${CSS.escape(analyzed.id)}"]`)?.click();
      const creativeItem=await waitFor(()=>{
        const item=selectedReference();
        return item?.creative?.versions?.length ? item : null;
      },6000);
      const version=creativeItem.creative.versions[0];
      const creative={id:`CR-${creativeItem.id}-1`,name:version.name||'卡嘴子原创版',topic:creativeItem.title||version.name||'卡嘴子原创内容',idea:version.idea||'',hook:version.hook||'',format:version.format||'真实案例',audience:'涟水本地用户',duration:'30 秒',cta:'需要本地服务时进入卡嘴子咨询或下单',referenceId:creativeItem.id,updatedAt:now()};
      const reference={id:creativeItem.id,title:creativeItem.title||'',platform:creativeItem.platform||'',source:creativeItem.url||'',rights:creativeItem.rights||'',analysis:creativeItem.analysis||null};
      writeJson(PIPELINE_KEY,{reference,creatives:creativeItem.creative.versions,selectedCreative:creative,directorPlan:null,productionProjectId:'',updatedAt:now()});
      setStage('creative','done');
      setStage('director');
      window.changePage?.('director');
      await sleep(150);
      const characterSelect=byId('kz-simple-character');
      const characterName=characterSelect?.selectedOptions?.[0]?.dataset?.name || '';
      if(byId('director-character')) byId('director-character').value=characterName;
      const request=byId('kz-simple-request')?.value.trim()||'';
      if(byId('director-brief')) byId('director-brief').value=[`主题：${creative.topic}`,`核心观点：${creative.idea}`,creative.hook&&`开头：${creative.hook}`,characterName&&`固定人物：${characterName}`,request&&`老板要求：${request}`,'要求：真实素材优先，缺口再用本地 AI 补镜；不要复用未授权原视频画面、声音和水印。'].filter(Boolean).join('\n');
      byId('director-to-production')?.click();
      const plan=await waitFor(()=>readJson(PIPELINE_KEY,{}).directorPlan?.shots?.length ? readJson(PIPELINE_KEY,{}).directorPlan : null,45000,400);
      setStage('director','done');
      setStage('production');
      await waitFor(()=>byId('kz-confirm-storyboard'),5000,200);
      byId('kz-confirm-storyboard')?.click();
      const finalState=await waitFor(()=>{
        const state=readJson(PIPELINE_KEY,{});
        return state.productionProjectId ? state : null;
      },15000,300);
      setStage('production','done');
      showResult(`<b>已完成一键创导。</b><br>参考：${esc(creativeItem.title)}<br>原创方向：${esc(creative.name)}<br>导演分镜：${plan.shots.length} 个镜头<br>生产项目：${esc(finalState.productionProjectId)}<br><button type="button" class="kz-simple-secondary" id="kz-simple-view-production" style="margin-top:8px">查看生产结果</button>`);
      byId('kz-simple-view-production')?.addEventListener('click',()=>{setMode(false);window.changePage?.('content');});
      announceSimple();
    } catch (error) {
      showResult(`<b>这一步没有完成：</b>${esc(error.message)}<br>已完成的数据会保留，可以重试。`,true);
      announceSimple();
    } finally {
      button.disabled=false; button.textContent='一键生成卡嘴子版本';
    }
  }

  function install() {
    if (!byId('studio-root')) return;
    installStyle();
    installToggle();
    buildSimple();
    const preferred=localStorage.getItem(MODE_KEY);
    setMode(preferred !== 'pro');
  }

  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>setTimeout(install,80),{once:true});
  else setTimeout(install,80);
})();

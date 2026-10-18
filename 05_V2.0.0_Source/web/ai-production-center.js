/* Standalone stage-one workbench. It replaces the legacy content form only. */
(() => {
  const page = document.getElementById('content');
  if (!page) return;
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const api = async (url, options={}) => {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || payload.message || '本地内容中心暂时不可用');
    return payload;
  };
  const tell = (text, bad=false) => {
    const box = document.getElementById('apc-feedback');
    if(!box) return;
    box.textContent = text; box.className = bad ? 'apc-feedback bad' : 'apc-feedback';
  };
  let data = null;
  const goReferenceCenter = () => {
    if (typeof window.changePage === 'function') { window.changePage('reference'); return; }
    document.querySelector('.nav[data-page="reference"]')?.click();
  };
  const renderLoading = () => {
    page.innerHTML = `
      <section class="apc-shell apc-loading" aria-live="polite" aria-label="内容生产正在读取">
        <p>内容生产工作台</p>
        <h2>正在读取本地项目与任务</h2>
        <span>正在核对项目、分镜和本地任务；不会调用模型或发布内容。</span>
      </section>`;
  };
  const assetOptions = (type) => (data.assets || []).filter(x => x.asset_type === type && x.enabled)
    .map(x => `<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');
  const projectOptions = () => (data.projects || []).map(x => `<option value="${esc(x.id)}">${esc(x.name)} · ${esc(x.status)}</option>`).join('');
  const shotsFor = id => (data.storyboards || []).filter(x => x.project_id === id).sort((a,b) => a.order-b.order);
  const currentProject = () => (data.projects || [])[0] || null;
  const render = () => {
    const project = currentProject(); const shots = project ? shotsFor(project.id) : [];
    page.innerHTML = `
      <section class="apc-shell" aria-label="AI 内容生产中心">
        <header class="apc-topbar"><div><p>独立生产工作台 · 阶段 1</p><h2>AI 内容生产中心</h2><span>固定资产 → 文案 → 可编辑分镜 → 候选任务 → 成片复核</span></div><div class="apc-top-actions"><button class="apc-secondary" id="apc-reference-center">参考内容中心</button><button class="apc-secondary" id="apc-refresh">刷新状态</button><button class="apc-primary" id="apc-new-project">新建项目</button></div></header>
        <div id="apc-feedback" class="apc-feedback">${esc(data.truth)}</div>
        <div class="apc-status"><span><b>${data.projects.length}</b> 个项目</span><span><b>${data.assets.length}</b> 项资产</span><span><b>${data.tasks.filter(x=>x.status==='待本地执行器').length}</b> 个待本地执行</span><span>所有对外发布仍需人工确认</span></div>
        <div class="apc-grid">
          <aside class="apc-assets">
            <div class="apc-section-head"><div><small>01 · 可复用资产</small><h3>人物、场景与声音</h3></div><button id="apc-add-asset">登记资产</button></div>
            <div class="apc-asset-tabs">${['人物','物品','场景','声音','真实素材','品牌物料'].map(type=>`<div><b>${type}</b><span>${data.assets.filter(x=>x.asset_type===type).length}</span></div>`).join('')}</div>
            <div class="apc-rights"><b>授权规则</b><span>只有“本人或公司自有 / 已取得授权 / 虚拟资产”可进入生成队列。</span></div>
            <div class="apc-list">${data.assets.length ? data.assets.slice(0,7).map(x=>`<article><b>${esc(x.name)}</b><span>${esc(x.asset_type)} · ${esc(x.rights)}</span></article>`).join('') : '<p class="apc-empty">还没有资产。先登记一个人物、场景或声音。</p>'}</div>
          </aside>
          <main class="apc-canvas">
            <div class="apc-section-head"><div><small>02 · 项目与分镜</small><h3>${project ? esc(project.name) : '从一条真实内容开始'}</h3><span>${project ? `项目状态：${esc(project.status)}` : '新建项目后，粘贴文案生成分镜草稿。'}</span></div>${project ? `<select id="apc-project-select">${projectOptions()}</select>` : ''}</div>
            ${project ? `<div class="apc-script"><label>本条内容文案 <span>ChatGPT 总控负责最终方案；此处先保存本地草稿。</span></label><textarea id="apc-script" maxlength="6000" placeholder="先说明用户问题，再给出真实可验证的解决路径。">${esc(project.script)}</textarea><div><button class="apc-primary" id="apc-storyboard">生成 / 更新分镜草稿</button><span>将生成 3–8 秒镜头卡，等待 ChatGPT 总控确认后才进入本地生产。</span></div></div>` : `<div class="apc-welcome"><b>先建一个内容项目</b><span>最小闭环：1 个固定人物 + 1 个固定场景 + 1 段文案 + 3 个镜头。</span><button class="apc-primary" id="apc-new-project-inline">开始建立</button></div>`}
            <div class="apc-storyboard-list">${shots.length ? shots.map(shot=>`<article class="apc-shot"><header><span>镜头 ${shot.order.toString().padStart(2,'0')}</span><b>${esc(shot.status)}</b></header><h4>${esc(shot.purpose)}</h4><p>${esc(shot.narration)}</p><footer><span>${esc(shot.shot_type)} · ${esc(shot.motion)} · ${shot.duration_seconds} 秒</span><button data-queue="${esc(shot.id)}">提交候选生成</button></footer></article>`).join('') : (project ? '<div class="apc-empty">还没有分镜。先确认文案，再生成第一版草稿。</div>' : '')}</div>
          </main>
          <aside class="apc-control">
            <div class="apc-section-head"><div><small>03 · 生产合同</small><h3>本次全片默认设置</h3></div></div>
            <label>默认人物<select id="apc-character"><option value="">稍后选择</option>${assetOptions('人物')}</select></label>
            <label>默认场景<select id="apc-scene"><option value="">稍后选择</option>${assetOptions('场景')}</select></label>
            <label>默认声音<select id="apc-voice"><option value="">稍后选择</option>${assetOptions('声音')}</select></label>
            <label>画幅<select disabled><option>${project ? esc(project.ratio) : '9:16'}</option></select></label>
            <div class="apc-route"><b>模型分工</b>${data.model_routes.map(x=>`<span>${esc(x.work)}<em>${esc(x.model)}</em></span>`).join('')}</div>
            <div class="apc-warning"><b>未进入发布</b><span>生成、候选、成片和发布是分开的状态；平台账号与最终发布均在“发布准备”处理。</span></div>
          </aside>
        </div>
        <section class="apc-bottom"><div class="apc-section-head"><div><small>04 · 任务与审计</small><h3>只显示真实发生的本地工作</h3></div></div><div class="apc-task-grid"><div>${data.tasks.length ? data.tasks.slice(0,5).map(x=>`<article><b>${esc(x.kind)}</b><span>${esc(x.status)}</span><small>${esc(x.detail)}</small></article>`).join('') : '<p class="apc-empty">还没有任务。生成分镜后会在这里留下可追溯记录。</p>'}</div><div class="apc-audit">${data.events.length ? data.events.slice(0,4).map(x=>`<p><b>${esc(x.detail)}</b><span>${esc(x.created_at)}</span></p>`).join('') : '<p>审计记录会在创建项目、登记资产、生成分镜和提交任务后出现。</p>'}</div></div></section>
      </section>`;
    bind();
  };
  const promptProject = async () => {
    const name = window.prompt('项目名称（例如：涟水水电安装维修 30 秒短片）'); if (!name) return;
    const script = window.prompt('粘贴这条视频的文案，可稍后修改：') || '';
    try { await api('/api/ai-content-center/projects', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,script,ratio:'9:16'})}); await refresh(); tell('项目已建立在本地；尚未调用模型或发布。'); } catch(e) { tell(e.message,true); }
  };
  const promptAsset = async () => {
    const name = window.prompt('资产名称（例如：师傅 A、涟水社区楼道、师傅 A 标准音）'); if (!name) return;
    const type = window.prompt('资产类型：人物 / 物品 / 场景 / 声音 / 真实素材 / 品牌物料', '人物'); if (!type) return;
    const rights = window.prompt('授权状态：本人或公司自有 / 已取得授权 / 虚拟资产 / 待确认', '待确认'); if (!rights) return;
    try { await api('/api/ai-content-center/assets', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,asset_type:type,rights})}); await refresh(); tell('资产已登记；“待确认”资产不会进入生成队列。'); } catch(e) { tell(e.message,true); }
  };
  const refresh = async () => { data = await api('/api/ai-content-center'); render(); };
  const bind = () => {
    document.getElementById('apc-reference-center')?.addEventListener('click', goReferenceCenter);
    document.getElementById('apc-refresh')?.addEventListener('click', () => refresh().catch(e=>tell(e.message,true)));
    document.getElementById('apc-new-project')?.addEventListener('click', promptProject);
    document.getElementById('apc-new-project-inline')?.addEventListener('click', promptProject);
    document.getElementById('apc-add-asset')?.addEventListener('click', promptAsset);
    document.getElementById('apc-project-select')?.addEventListener('change', event => { const index=data.projects.findIndex(x=>x.id===event.target.value); if(index>0){const [item]=data.projects.splice(index,1);data.projects.unshift(item);render();} });
    document.getElementById('apc-storyboard')?.addEventListener('click', async () => { const p=currentProject(); try { await api('/api/ai-content-center/storyboards/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:p.id,script:document.getElementById('apc-script').value})}); await refresh(); tell('已生成本地结构草稿，等待 ChatGPT 总控确认；尚未进入视频生成。'); } catch(e) { tell(e.message,true); }});
    document.querySelectorAll('[data-queue]').forEach(button => button.addEventListener('click', async () => { try { await api('/api/ai-content-center/candidates/queue',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({shot_id:button.dataset.queue,asset_ids:[document.getElementById('apc-character').value,document.getElementById('apc-scene').value,document.getElementById('apc-voice').value].filter(Boolean)})}); await refresh(); tell('候选生成任务已排入本地队列；出现真实候选文件前不会显示“成片”。'); } catch(e) { tell(e.message,true); }}));
  };
  // Preload the independent workbench while it is hidden. Once it has data,
  // clicking "内容生产" paints its own page immediately instead of leaving the
  // execution overview visible while the local API returns.
  window.aiProductionCenterActivate = async () => {
    if (data) {
      render();
      refresh().catch(e => tell(e.message, true));
      return;
    }
    renderLoading();
    try {
      await refresh();
    } catch (e) {
      page.innerHTML = `<section class="apc-shell apc-loading"><p>内容生产工作台</p><h2>暂时无法读取本地项目</h2><span>${esc(e.message)}</span></section>`;
    }
  };
  window.addEventListener('operational:content', () => window.aiProductionCenterActivate());
  window.aiProductionCenterActivate();
})();

/* Load the independent Content Intelligence / Reference Center without changing
   the legacy operational.html contract. The feature remains a separate page,
   not another block inside the production form. */
(() => {
  const load = () => {
    if (!document.querySelector('link[data-reference-center-style]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'content-reference-center.css';
      link.dataset.referenceCenterStyle = '1';
      document.head.appendChild(link);
    }
    if (!document.querySelector('script[data-reference-center-script]')) {
      const script = document.createElement('script');
      script.src = 'content-reference-center.js';
      script.dataset.referenceCenterScript = '1';
      document.body.appendChild(script);
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load, {once:true}); else load();
})();

/* V1.1 closed-loop is loaded natively by the content studio itself. This avoids
   parent-frame runtime injection and keeps initialization one-shot and local. */
(() => {
  const load = () => {
    if (!document.getElementById('studio-root')) return;
    if (document.querySelector('script[data-content-pipeline-native]')) return;
    const script = document.createElement('script');
    script.src = 'content-pipeline-native.js';
    script.async = false;
    script.dataset.contentPipelineNative = '1';
    document.body.appendChild(script);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load, {once:true}); else load();
})();
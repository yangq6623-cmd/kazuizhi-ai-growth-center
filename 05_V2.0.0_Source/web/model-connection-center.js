(() => {
  'use strict';
  if (window.__kazuizhiModelConnectionCenterLoaded) return;
  window.__kazuizhiModelConnectionCenterLoaded = true;

  const PRESETS = {
    ollama: {label:'Ollama（本机）', endpoint:'http://127.0.0.1:11434/v1/chat/completions', protocol:'chat_completions'},
    lm_studio: {label:'LM Studio（本机）', endpoint:'http://127.0.0.1:1234/v1/chat/completions', protocol:'chat_completions'},
    vllm: {label:'vLLM（本机）', endpoint:'http://127.0.0.1:8000/v1/chat/completions', protocol:'chat_completions'},
    custom: {label:'自定义本机兼容服务', endpoint:'', protocol:'chat_completions'}
  };
  const STATUS_TEXT = {ready:'已验证', configured:'待测试', not_configured:'未配置'};
  let state = null;
  let activeEditor = 'local';
  let busy = false;

  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const notify = (message, kind='ok') => {
    if (typeof window.toast === 'function') return window.toast(message, kind === 'error' ? 'error' : undefined);
    if (typeof window.notify === 'function') return window.notify(message, kind === 'error' ? 'error' : undefined);
    const box = byId('kz-model-message');
    if (box) { box.textContent = message; box.dataset.kind = kind; }
  };
  async function request(path, options={}) {
    const response = await fetch(path, {cache:'no-store', ...options});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || body.message || `模型接口返回 ${response.status}`);
    return body;
  }
  const post = (path, payload={}) => request(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});

  function route(routeId) {
    return state?.routes?.[routeId] || {id:routeId,status:'not_configured',status_label:'未配置',verified:false,configured:false,model:'',endpoint:'',provider:routeId==='local'?'ollama':'openai_compatible',protocol:routeId==='local'?'chat_completions':'responses'};
  }
  function statusClass(item) {
    if (item?.verified || item?.status === 'ready') return 'is-success';
    if (item?.configured || item?.status === 'configured') return 'is-waiting';
    return 'is-neutral';
  }
  function routeName(id) { return id === 'local' ? '本地模型' : '云端模型'; }

  function dialogMarkup() {
    return `<div id="kz-model-overlay" class="kz-model-overlay" hidden>
      <section id="kz-model-center" class="kz-model-center" role="dialog" aria-modal="true" aria-labelledby="kz-model-title">
        <header class="kz-model-head">
          <div><p>AI MODEL CONNECTION CENTER</p><h2 id="kz-model-title">AI 大模型接口中心</h2><span>统一管理本地 OpenAI-Compatible 模型与云端模型；连接状态必须经过真实测试。</span></div>
          <button id="kz-model-close" type="button" class="kz-icon-button" aria-label="关闭">×</button>
        </header>

        <div class="kz-model-truth"><b>边界：</b>本地模型可以参与内容分析、生成、分类和辅助计算，但<b>不计入 GEO 正式 A/B 级外部证据</b>。GEO 真实验证仍必须由真实外部 AI + Evidence / Receipt 完成。</div>

        <div class="kz-model-summary">
          <article><span>当前主路由</span><strong id="kz-active-route">--</strong><small id="kz-active-model">--</small></article>
          <article><span>本地模型</span><strong id="kz-local-state">--</strong><small id="kz-local-model">--</small></article>
          <article><span>云端模型</span><strong id="kz-cloud-state">--</strong><small id="kz-cloud-model">--</small></article>
          <article><span>自动降级</span><strong id="kz-fallback-state">--</strong><small>主路由不可用时使用已验证备用路由</small></article>
        </div>

        <nav class="kz-model-tabs" aria-label="模型路线">
          <button type="button" data-model-route="local" class="active">本地模型<span>Ollama / LM Studio / vLLM</span></button>
          <button type="button" data-model-route="cloud">云端模型<span>OpenAI-Compatible HTTPS</span></button>
        </nav>

        <div class="kz-model-form">
          <div class="kz-model-field" id="kz-provider-field"><label for="kz-model-provider">运行服务</label><select id="kz-model-provider"><option value="ollama">Ollama（本机）</option><option value="lm_studio">LM Studio（本机）</option><option value="vllm">vLLM（本机）</option><option value="custom">自定义本机兼容服务</option></select></div>
          <div class="kz-model-field"><label for="kz-model-endpoint">接口地址</label><input id="kz-model-endpoint" autocomplete="off" spellcheck="false"></div>
          <div class="kz-model-field"><label for="kz-model-name">模型名称</label><input id="kz-model-name" autocomplete="off" placeholder="例如 qwen3:8b"></div>
          <div class="kz-model-field" id="kz-api-key-field"><label for="kz-model-api-key">API Key</label><input id="kz-model-api-key" type="password" autocomplete="new-password" placeholder="本地模型无需填写；云端已保存可留空"></div>
          <div class="kz-model-field kz-model-check"><label><input id="kz-model-fallback" type="checkbox" checked> 主路由不可用时允许使用已验证备用路由</label></div>
          <div class="kz-model-actions">
            <button id="kz-model-save" class="kz-primary" type="button">保存并设为当前</button>
            <button id="kz-model-test" class="kz-secondary" type="button">测试当前路线</button>
            <button id="kz-model-detect" class="kz-secondary" type="button">检测本机模型</button>
            <button id="kz-model-clear" class="kz-ghost" type="button">清除此路线</button>
          </div>
        </div>

        <div id="kz-model-message" class="kz-model-message">正在读取模型连接状态…</div>
        <footer class="kz-model-foot"><span>本地接口只允许 127.0.0.1 / localhost；云端必须 HTTPS。</span><button id="kz-open-geo" type="button">查看 GEO 真实验证 →</button></footer>
      </section>
    </div>`;
  }

  function summaryCardMarkup() {
    return `<article id="kz-model-summary-card" class="kz-model-summary-card">
      <div><small>统一模型接口</small><h3>本地模型 + 云端模型</h3><p id="kz-model-card-copy">正在检查模型路由…</p></div>
      <div class="kz-model-card-status"><span id="kz-model-card-local" class="is-neutral">本地 未配置</span><span id="kz-model-card-cloud" class="is-neutral">云端 未配置</span></div>
      <button id="kz-model-card-open" type="button">配置模型接口</button>
    </article>`;
  }

  function ensureUi() {
    if (!byId('kz-model-overlay')) document.body.insertAdjacentHTML('beforeend', dialogMarkup());
    const legacy = byId('connections');
    if (legacy && !byId('kz-model-summary-card')) {
      const oldField = byId('ai-base-url');
      const oldCard = oldField?.closest('article');
      if (oldCard) oldCard.hidden = true;
      const title = legacy.querySelector('.page-title');
      if (title) title.insertAdjacentHTML('afterend', summaryCardMarkup());
      else legacy.insertAdjacentHTML('afterbegin', summaryCardMarkup());
    }
    const health = byId('health') || document.querySelector('[data-page-panel="health"],.page[data-page="health"]');
    if (health && !health.querySelector('#kz-model-summary-card') && !byId('kz-model-summary-card')) {
      health.insertAdjacentHTML('afterbegin', summaryCardMarkup());
    }
    bindUi();
    return byId('kz-model-overlay');
  }

  function bindUi() {
    const overlay = byId('kz-model-overlay');
    if (overlay && overlay.dataset.bound !== '1') {
      overlay.dataset.bound = '1';
      byId('kz-model-close')?.addEventListener('click', closeCenter);
      overlay.addEventListener('click', event => { if (event.target === overlay) closeCenter(); });
      document.addEventListener('keydown', event => { if (event.key === 'Escape' && !overlay.hidden) closeCenter(); });
      document.querySelectorAll('[data-model-route]').forEach(button => button.addEventListener('click', () => selectEditor(button.dataset.modelRoute)));
      byId('kz-model-provider')?.addEventListener('change', applyPreset);
      byId('kz-model-save')?.addEventListener('click', saveRoute);
      byId('kz-model-test')?.addEventListener('click', testRoute);
      byId('kz-model-detect')?.addEventListener('click', detectLocal);
      byId('kz-model-clear')?.addEventListener('click', clearRoute);
      byId('kz-open-geo')?.addEventListener('click', () => { window.location.href = '/geo.html'; });
    }
    const cardOpen = byId('kz-model-card-open');
    if (cardOpen && cardOpen.dataset.bound !== '1') { cardOpen.dataset.bound='1'; cardOpen.addEventListener('click', openCenter); }
  }

  function selectEditor(routeId) {
    activeEditor = routeId === 'cloud' ? 'cloud' : 'local';
    document.querySelectorAll('[data-model-route]').forEach(button => button.classList.toggle('active', button.dataset.modelRoute === activeEditor));
    const item = route(activeEditor);
    const local = activeEditor === 'local';
    byId('kz-provider-field').hidden = !local;
    byId('kz-api-key-field').hidden = local;
    byId('kz-model-detect').hidden = !local;
    if (local) {
      byId('kz-model-provider').value = PRESETS[item.provider] ? item.provider : 'custom';
      byId('kz-model-endpoint').value = item.endpoint || PRESETS[byId('kz-model-provider').value].endpoint;
      byId('kz-model-name').placeholder = '例如 qwen3:8b';
    } else {
      byId('kz-model-endpoint').value = item.endpoint || 'https://api.openai.com/v1/responses';
      byId('kz-model-name').placeholder = '例如 gpt-5.6';
    }
    byId('kz-model-name').value = item.model || '';
    byId('kz-model-api-key').value = '';
    byId('kz-model-fallback').checked = state?.fallback_enabled !== false;
  }

  function applyPreset() {
    if (activeEditor !== 'local') return;
    const preset = PRESETS[byId('kz-model-provider').value] || PRESETS.custom;
    if (preset.endpoint) byId('kz-model-endpoint').value = preset.endpoint;
  }

  function render() {
    ensureUi();
    const local = route('local');
    const cloud = route('cloud');
    const activeId = state?.active_route === 'local' ? 'local' : 'cloud';
    const active = route(activeId);
    byId('kz-active-route').textContent = routeName(activeId);
    byId('kz-active-model').textContent = active.model || '尚未配置模型';
    byId('kz-local-state').textContent = local.status_label || STATUS_TEXT[local.status] || '未配置';
    byId('kz-local-model').textContent = local.model || local.provider || 'Ollama / LM Studio / vLLM';
    byId('kz-cloud-state').textContent = cloud.status_label || STATUS_TEXT[cloud.status] || '未配置';
    byId('kz-cloud-model').textContent = cloud.model || 'OpenAI-Compatible';
    byId('kz-fallback-state').textContent = state?.fallback_enabled === false ? '关闭' : '开启';
    const cardLocal = byId('kz-model-card-local');
    const cardCloud = byId('kz-model-card-cloud');
    if (cardLocal) { cardLocal.className = statusClass(local); cardLocal.textContent = `本地 ${local.status_label || '未配置'}`; }
    if (cardCloud) { cardCloud.className = statusClass(cloud); cardCloud.textContent = `云端 ${cloud.status_label || '未配置'}`; }
    const cardCopy = byId('kz-model-card-copy');
    if (cardCopy) cardCopy.textContent = `${routeName(activeId)}为当前主路由${active.model ? ` · ${active.model}` : ''}；本地模型不会被计入 GEO 正式外部证据。`;
    selectEditor(activeEditor);
  }

  async function load() {
    try {
      state = await request('/api/ai-gateway/status');
      render();
      const verified = Object.values(state.routes || {}).filter(item => item?.verified).length;
      byId('kz-model-message').textContent = verified ? `已验证 ${verified} 条模型路线。当前主路由：${routeName(state.active_route)}。` : '尚无已验证模型路线。请先保存配置，再执行真实连接测试。';
      return state;
    } catch (error) {
      ensureUi();
      byId('kz-model-message').textContent = `模型连接中心暂不可读：${error.message}`;
      throw error;
    }
  }

  function payloadForEditor() {
    const local = activeEditor === 'local';
    const provider = local ? byId('kz-model-provider').value : 'openai_compatible';
    return {
      route: activeEditor,
      provider,
      endpoint: byId('kz-model-endpoint').value.trim(),
      model: byId('kz-model-name').value.trim(),
      protocol: local ? (PRESETS[provider]?.protocol || 'chat_completions') : 'responses',
      api_key: local ? '' : byId('kz-model-api-key').value.trim(),
      set_active: true,
      fallback_enabled: byId('kz-model-fallback').checked
    };
  }

  async function saveRoute() {
    if (busy) return;
    const payload = payloadForEditor();
    if (!payload.endpoint || !payload.model) return notify('请填写模型服务地址和模型名称','error');
    busy = true;
    const button = byId('kz-model-save'); const old = button.textContent; button.disabled = true; button.textContent = '保存中…';
    try {
      state = await post('/api/ai-gateway/config', payload);
      render();
      notify(`${routeName(activeEditor)}已保存并设为当前路线；还需要点击“测试当前路线”完成真实验证。`);
    } catch (error) { notify(error.message,'error'); }
    finally { busy = false; button.disabled = false; button.textContent = old; }
  }

  async function testRoute() {
    if (busy) return;
    busy = true;
    const button = byId('kz-model-test'); const old = button.textContent; button.disabled = true; button.textContent = '测试中…';
    try {
      state = await post('/api/ai-gateway/test', {route:activeEditor});
      render();
      notify(`${routeName(activeEditor)}真实连接测试通过，状态已更新为“已验证”。`);
    } catch (error) { await load().catch(()=>{}); notify(error.message,'error'); }
    finally { busy = false; button.disabled = false; button.textContent = old; }
  }

  async function detectLocal() {
    if (busy || activeEditor !== 'local') return;
    busy = true;
    const button = byId('kz-model-detect'); const old = button.textContent; button.disabled = true; button.textContent = '检测中…';
    try {
      const health = await request('/api/local-ai/health');
      const models = Array.isArray(health.loaded_models) ? health.loaded_models : [];
      if (models.length && !byId('kz-model-name').value.trim()) byId('kz-model-name').value = models[0];
      notify(health.ok ? `本机 AI 服务已启动${models.length ? `；检测到 ${models.join('、')}` : '。请填写已安装模型名称后保存测试。'}` : (health.message || '本机 AI 服务正在启动'));
    } catch (error) { notify(error.message,'error'); }
    finally { busy = false; button.disabled = false; button.textContent = old; }
  }

  async function clearRoute() {
    if (busy) return;
    if (!window.confirm(`确认清除${routeName(activeEditor)}配置？`)) return;
    busy = true;
    try { state = await post('/api/ai-gateway/clear',{route:activeEditor}); render(); notify(`${routeName(activeEditor)}配置已清除。`); }
    catch (error) { notify(error.message,'error'); }
    finally { busy = false; }
  }

  async function openCenter() {
    ensureUi();
    const overlay = byId('kz-model-overlay'); overlay.hidden = false; document.documentElement.classList.add('kz-model-open');
    try { await load(); } catch (_) {}
    setTimeout(() => byId('kz-model-center')?.focus?.(), 0);
  }
  function closeCenter() {
    const overlay = byId('kz-model-overlay'); if (overlay) overlay.hidden = true;
    document.documentElement.classList.remove('kz-model-open');
  }

  window.kzOpenModelConnectionCenter = openCenter;
  window.kzReloadModelConnectionCenter = load;

  ensureUi();
  load().catch(()=>{});
  const observer = new MutationObserver(() => ensureUi());
  observer.observe(document.documentElement,{childList:true,subtree:true});
  setInterval(() => load().catch(()=>{}), 30000);
})();
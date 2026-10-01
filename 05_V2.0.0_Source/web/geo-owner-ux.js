(() => {
  'use strict';
  if (window.__KZ_GEO_OWNER_UX__) return;
  window.__KZ_GEO_OWNER_UX__ = true;

  const byId = id => document.getElementById(id);
  const request = async (path, options={}) => {
    const response = await fetch(path, {cache:'no-store', ...options});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || body.message || `接口返回 ${response.status}`);
    return body;
  };
  const post = (path, payload={}) => request(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});

  function ensureApiDialog() {
    if (byId('kz-geo-api-overlay')) return byId('kz-geo-api-overlay');
    document.body.insertAdjacentHTML('beforeend', `
      <div id="kz-geo-api-overlay" class="kz-geo-api-overlay" hidden>
        <section class="kz-geo-api-dialog" role="dialog" aria-modal="true" aria-labelledby="kz-geo-api-title">
          <header class="kz-geo-api-head">
            <div><p>GEO · CLOUD API</p><h2 id="kz-geo-api-title">配置云端大模型 API</h2><span>填写名称、接口地址、模型和密钥即可保存。支持 OpenAI-compatible HTTPS 接口；“保存并测试”会使用当前表单内容，不需要先单独保存。API 只是可选加速通道，网页真实验证仍可独立工作。</span></div>
            <button id="kz-geo-api-close" class="kz-geo-api-close" type="button" aria-label="关闭">×</button>
          </header>
          <div class="kz-geo-api-truth"><b>证据规则：</b>配置云端 API 不会自动把结果记为 GEO A/B 级证据。只有具备相应真实外部验证能力并生成可追溯 Evidence / Receipt 的执行器，才计入正式 GEO 成绩。</div>
          <div class="kz-geo-api-form">
            <div class="kz-geo-api-field"><label for="kz-geo-api-provider">API 名称</label><input id="kz-geo-api-provider" autocomplete="off" placeholder="例如 豆包 / DeepSeek / 通义千问 / OpenAI / 自定义"></div>
            <div class="kz-geo-api-field"><label for="kz-geo-api-protocol">接口协议</label><select id="kz-geo-api-protocol"><option value="chat_completions">OpenAI Chat Completions 兼容</option><option value="responses">OpenAI Responses 兼容</option></select></div>
            <div class="kz-geo-api-field full"><label for="kz-geo-api-endpoint">API 接口地址</label><input id="kz-geo-api-endpoint" autocomplete="off" spellcheck="false" placeholder="https://api.example.com/v1/chat/completions"></div>
            <div class="kz-geo-api-field"><label for="kz-geo-api-model">模型名称</label><input id="kz-geo-api-model" autocomplete="off" placeholder="例如 doubao-seed-2-0-mini-260428 / deepseek-chat / qwen-plus"></div>
            <div class="kz-geo-api-field"><label for="kz-geo-api-key">API Key</label><input id="kz-geo-api-key" type="password" autocomplete="new-password" placeholder="已保存过密钥时可留空"></div>
            <div id="kz-geo-api-status" class="kz-geo-api-status">尚未读取当前云端 API 配置。</div>
            <div class="kz-geo-api-actions">
              <button id="kz-geo-api-clear" class="ghost" type="button">清除配置</button>
              <button id="kz-geo-api-test" class="secondary" type="button">保存并测试</button>
              <button id="kz-geo-api-save" class="primary" type="button">仅保存 API 配置</button>
            </div>
          </div>
        </section>
      </div>`);
    const overlay = byId('kz-geo-api-overlay');
    byId('kz-geo-api-close')?.addEventListener('click', closeApiDialog);
    overlay.addEventListener('click', event => { if (event.target === overlay) closeApiDialog(); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && !overlay.hidden) closeApiDialog(); });
    byId('kz-geo-api-save')?.addEventListener('click', saveApi);
    byId('kz-geo-api-test')?.addEventListener('click', testApi);
    byId('kz-geo-api-clear')?.addEventListener('click', clearApi);
    return overlay;
  }

  function apiStatus(message, kind='') {
    const box = byId('kz-geo-api-status');
    if (!box) return;
    box.className = `kz-geo-api-status${kind ? ` ${kind}` : ''}`;
    box.textContent = message;
  }

  async function loadApiForm() {
    const data = await request('/api/ai-gateway/status');
    const cloud = data?.routes?.cloud || {};
    byId('kz-geo-api-provider').value = cloud.label || (cloud.provider && cloud.provider !== 'openai_compatible' ? cloud.provider : '自定义云端 API');
    byId('kz-geo-api-protocol').value = cloud.protocol === 'responses' ? 'responses' : 'chat_completions';
    byId('kz-geo-api-endpoint').value = cloud.endpoint || '';
    byId('kz-geo-api-model').value = cloud.model || '';
    byId('kz-geo-api-key').value = '';
    const state = cloud.verified ? '已验证' : cloud.configured ? '已保存，待测试' : '未配置';
    apiStatus(`当前状态：${state}${cloud.model ? ` · ${cloud.model}` : ''}${cloud.last_error ? ` · ${cloud.last_error}` : ''}`, cloud.verified ? 'ok' : '');
    syncApiModeCard(data);
    return data;
  }

  async function openApiDialog() {
    const overlay = ensureApiDialog();
    overlay.hidden = false;
    apiStatus('正在读取当前云端 API 配置…');
    try { await loadApiForm(); }
    catch (error) { apiStatus(`读取失败：${error.message}`, 'error'); }
  }
  function closeApiDialog() { const overlay = byId('kz-geo-api-overlay'); if (overlay) overlay.hidden = true; }

  function apiPayload() {
    const label = byId('kz-geo-api-provider').value.trim();
    return {
      route: 'cloud',
      provider: (label || 'custom_cloud').slice(0, 40),
      label: label || '自定义云端 API',
      endpoint: byId('kz-geo-api-endpoint').value.trim(),
      model: byId('kz-geo-api-model').value.trim(),
      protocol: byId('kz-geo-api-protocol').value,
      api_key: byId('kz-geo-api-key').value.trim(),
      set_active: true,
      fallback_enabled: true,
    };
  }

  function validateApiPayload(payload) {
    if (!payload.endpoint || !payload.model) {
      apiStatus('请先填写 API 接口地址和模型名称。', 'error');
      return false;
    }
    if (!/^https:\/\//i.test(payload.endpoint)) {
      apiStatus('云端 API 必须使用 HTTPS 地址。', 'error');
      return false;
    }
    return true;
  }

  async function saveApi() {
    const payload = apiPayload();
    if (!validateApiPayload(payload)) return;
    const button = byId('kz-geo-api-save'); const old = button.textContent; button.disabled = true; button.textContent = '保存中…';
    try {
      const data = await post('/api/ai-gateway/config', payload);
      byId('kz-geo-api-key').value = '';
      apiStatus('API 配置已安全保存。需要验证时点击“保存并测试”。', 'ok');
      syncApiModeCard(data);
    } catch (error) { apiStatus(`保存失败：${error.message}`, 'error'); }
    finally { button.disabled = false; button.textContent = old; }
  }

  async function testApi() {
    // Important: test the values currently visible in the form.  Older builds
    // only sent {route:'cloud'} to /test, so a user could fill every field and
    // still receive “请先完整填写...” because the form had not been persisted yet.
    const payload = apiPayload();
    if (!validateApiPayload(payload)) return;
    const button = byId('kz-geo-api-test'); const old = button.textContent; button.disabled = true; button.textContent = '保存并测试中…';
    try {
      const saved = await post('/api/ai-gateway/config', payload);
      byId('kz-geo-api-key').value = '';
      syncApiModeCard(saved);
      apiStatus('当前填写已安全保存，正在验证模型服务…');
      const data = await post('/api/ai-gateway/test', {route:'cloud'});
      apiStatus('连接测试通过，云端 API 已验证。', 'ok');
      syncApiModeCard(data);
    } catch (error) { apiStatus(`保存/连接测试失败：${error.message}`, 'error'); }
    finally { button.disabled = false; button.textContent = old; }
  }

  async function clearApi() {
    if (!confirm('确认清除当前云端 API 配置？')) return;
    try {
      const data = await post('/api/ai-gateway/clear', {route:'cloud'});
      byId('kz-geo-api-provider').value = '自定义云端 API';
      byId('kz-geo-api-endpoint').value = '';
      byId('kz-geo-api-model').value = '';
      byId('kz-geo-api-key').value = '';
      apiStatus('云端 API 配置已清除。');
      syncApiModeCard(data);
    } catch (error) { apiStatus(`清除失败：${error.message}`, 'error'); }
  }

  function syncApiModeCard(data) {
    const cloud = data?.routes?.cloud;
    const state = byId('geo-api-state');
    const note = byId('geo-api-note');
    if (!state || !note || !cloud) return;
    if (cloud.verified) { state.textContent = '已验证'; note.textContent = `${cloud.label || cloud.provider || '云端API'} · ${cloud.model || ''}`; }
    else if (cloud.configured) { state.textContent = '待测试'; note.textContent = `${cloud.label || cloud.provider || '云端API'} · 已保存`; }
    else { state.textContent = '可选未配置'; note.textContent = '点击这里配置名称、地址、模型与密钥'; }
  }

  function scrollToWorkbench() {
    const panel = document.querySelector('#geo-growth-pane .geo-browser-workbench');
    panel?.scrollIntoView({behavior:'smooth', block:'start'});
    setTimeout(() => byId('geo-browser-one')?.focus(), 350);
  }
  function openLocalTools() {
    const details = [...document.querySelectorAll('#geo-growth-pane details')].find(node => /本地辅助预检|本地预检/.test(node.textContent || ''));
    if (details) { details.open = true; details.scrollIntoView({behavior:'smooth', block:'center'}); }
    else byId('geo-local-one')?.scrollIntoView({behavior:'smooth', block:'center'});
  }

  function decorateModes() {
    const cards = document.querySelectorAll('#geo-growth-pane .geo-mode-grid article');
    if (cards.length < 3) return false;
    const specs = [
      {cls:'mode-local', label:'查看预检', action:openLocalTools, title:'打开本地模型辅助预检工具'},
      {cls:'mode-browser', label:'进入验证', action:scrollToWorkbench, title:'进入真实网页验证工作台'},
      {cls:'mode-api', label:'配置 API', action:openApiDialog, title:'配置可选云端大模型 API'},
    ];
    cards.forEach((card, index) => {
      const spec = specs[index]; if (!spec) return;
      card.classList.add(spec.cls); card.tabIndex = 0; card.setAttribute('role','button'); card.title = spec.title;
      if (!card.querySelector('.geo-mode-action')) {
        const button = document.createElement('button'); button.type='button'; button.className='geo-mode-action'; button.textContent=spec.label;
        button.addEventListener('click', event => { event.stopPropagation(); spec.action(); }); card.appendChild(button);
      }
      if (card.dataset.kzModeBound !== '1') {
        card.dataset.kzModeBound = '1';
        card.addEventListener('click', event => { if (!event.target.closest('button')) spec.action(); });
        card.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); spec.action(); } });
      }
    });
    return true;
  }

  async function syncStatusOnce() {
    try { syncApiModeCard(await request('/api/ai-gateway/status')); } catch (_) {}
  }

  let attempts = 0;
  const timer = setInterval(() => {
    attempts += 1;
    if (decorateModes() || attempts > 16) clearInterval(timer);
  }, 300);
  [0, 800, 2200].forEach(delay => setTimeout(() => { decorateModes(); syncStatusOnce(); }, delay));
  window.addEventListener('focus', () => setTimeout(syncStatusOnce, 120));
})();

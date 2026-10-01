(() => {
  'use strict';
  if (window.__KZ_GEO_AUTONOMY_UI__) return;
  window.__KZ_GEO_AUTONOMY_UI__ = true;

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const byId = id => document.getElementById(id);
  let timer = null;

  async function request(path, options={}) {
    const response = await fetch(path, {cache:'no-store', ...options});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.message || `GEO自动运行接口返回 ${response.status}`);
    return data;
  }
  const post = (path, body={}) => request(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});

  function ensureStyle() {
    if (byId('geo-auto-style')) return;
    const style = document.createElement('style');
    style.id = 'geo-auto-style';
    style.textContent = `
      .geo-auto{margin:12px 0 16px;border:1px solid #cbdcff;border-radius:12px;background:#f8fbff;padding:14px 16px;box-shadow:0 5px 18px rgba(37,99,235,.05)}
      .geo-auto-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.geo-auto-head p{margin:0;color:#315d9f;font-size:11px;font-weight:800;letter-spacing:.04em}.geo-auto-head h3{margin:3px 0 4px;font-size:18px}.geo-auto-head small{display:block;color:#64748b;line-height:1.55}.geo-auto-state{flex:0 0 auto;border-radius:4px;padding:5px 9px;font-size:12px;font-weight:800;background:#e2e8f0;color:#475569}.geo-auto-state.running{background:#eaf1ff;color:#245ec7}.geo-auto-state.completed{background:#e7f7ee;color:#16895f}.geo-auto-state.paused,.geo-auto-state.attention{background:#fff0d8;color:#a86500}
      .geo-auto-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:12px}.geo-auto-metric{border:1px solid #e2e8f0;border-radius:8px;background:#fff;padding:9px 10px;min-width:0}.geo-auto-metric span{display:block;color:#718096;font-size:11px}.geo-auto-metric b{display:block;margin-top:3px;font-size:17px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.geo-auto-metric small{display:block;color:#8793a5;font-size:10px;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .geo-auto-progress{height:7px;background:#e5eaf2;border-radius:99px;overflow:hidden;margin:11px 0 7px}.geo-auto-progress i{display:block;height:100%;background:#2563eb;transition:width .25s ease}.geo-auto-current{font-size:12px;color:#4a5b72;min-height:20px}.geo-auto-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.geo-auto-actions button{border:1px solid #cbd7e8;border-radius:8px;background:#fff;color:#315d9f;padding:8px 12px;font-weight:800;cursor:pointer}.geo-auto-actions button.primary{background:#2563eb;border-color:#2563eb;color:#fff}.geo-auto-actions button:disabled{opacity:.5;cursor:not-allowed}.geo-auto-truth{margin-top:10px;padding-top:9px;border-top:1px dashed #ccd8ea;color:#607086;font-size:11px;line-height:1.55}.geo-auto-error{color:#b42318;font-weight:700}
      @media(max-width:1050px){.geo-auto-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:620px){.geo-auto-head{flex-direction:column}.geo-auto-grid{grid-template-columns:repeat(2,1fr)}}
    `;
    document.head.appendChild(style);
  }

  function markup() {
    return `<section id="geo-autonomy" class="geo-auto" aria-label="GEO自动验证">
      <div class="geo-auto-head"><div><p>GEO · AUTONOMOUS CLOUD SCAN</p><h3>GEO 自动验证 · 50问自治运行</h3><small>云端 API 已验证后，系统可自动逐题执行、保存回答和回执，无需人工点击 50 次。</small></div><span id="geo-auto-state" class="geo-auto-state">待启动</span></div>
      <div class="geo-auto-grid">
        <div class="geo-auto-metric"><span>云端自动扫描</span><b id="geo-auto-progress-text">0 / 50</b><small>C级辅助结果</small></div>
        <div class="geo-auto-metric"><span>正式 A/B Evidence</span><b id="geo-auto-formal">0 / 50</b><small>正式 GEO 成绩</small></div>
        <div class="geo-auto-metric"><span>排队</span><b id="geo-auto-queued">0</b><small>待自动执行</small></div>
        <div class="geo-auto-metric"><span>失败 / 待授权</span><b id="geo-auto-failed">0</b><small>异常才需要处理</small></div>
        <div class="geo-auto-metric"><span>云端模型</span><b id="geo-auto-model">--</b><small id="geo-auto-provider">读取中</small></div>
        <div class="geo-auto-metric"><span>运行状态</span><b id="geo-auto-mode">待启动</b><small>单任务顺序执行</small></div>
      </div>
      <div class="geo-auto-progress"><i id="geo-auto-bar" style="width:0%"></i></div>
      <div id="geo-auto-current" class="geo-auto-current">当前没有自动 GEO 任务。</div>
      <div class="geo-auto-actions">
        <button id="geo-auto-start" class="primary" type="button">启动自动50问</button>
        <button id="geo-auto-pause" type="button">暂停</button>
        <button id="geo-auto-resume" type="button">继续</button>
        <button id="geo-auto-retry" type="button">重试失败题</button>
        <button id="geo-auto-refresh" type="button">刷新状态</button>
      </div>
      <div id="geo-auto-truth" class="geo-auto-truth">证据边界：普通豆包/云端 API 回答会真实保存，但没有可核验的联网搜索证据时固定为 C 级辅助；只有真实 A/B Evidence 才进入正式 GEO 成绩。</div>
    </section>`;
  }

  function mount() {
    const pane = byId('geo-growth-pane');
    if (!pane || byId('geo-autonomy')) return Boolean(byId('geo-autonomy'));
    ensureStyle();
    const holder = document.createElement('div');
    holder.innerHTML = markup();
    const node = holder.firstElementChild;
    const anchor = pane.querySelector('.geo-mode-grid');
    if (anchor?.parentNode) anchor.parentNode.insertBefore(node, anchor.nextSibling);
    else pane.prepend(node);
    byId('geo-auto-start')?.addEventListener('click', event => act(event.currentTarget, '/api/r8-19/geo/autonomy/start', {target:50}));
    byId('geo-auto-pause')?.addEventListener('click', event => act(event.currentTarget, '/api/r8-19/geo/autonomy/pause'));
    byId('geo-auto-resume')?.addEventListener('click', event => act(event.currentTarget, '/api/r8-19/geo/autonomy/resume'));
    byId('geo-auto-retry')?.addEventListener('click', event => act(event.currentTarget, '/api/r8-19/geo/autonomy/retry-failed'));
    byId('geo-auto-refresh')?.addEventListener('click', () => refresh(true));
    refresh();
    if (!timer) timer = setInterval(refresh, 2500);
    return true;
  }

  function render(data) {
    if (!data || !byId('geo-autonomy')) return;
    const target = Number(data.target || 50);
    const completed = Number(data.cloud_completed || 0);
    const formal = Number(data.formal_ab_completed || 0);
    const queue = data.queue || {};
    const executor = data.executor || {};
    const stateLabels = {idle:'待启动',running:'运行中',paused:'已暂停',completed:'已完成',attention:'需要处理'};
    const state = data.state || 'idle';
    const stateNode = byId('geo-auto-state');
    stateNode.textContent = stateLabels[state] || state;
    stateNode.className = `geo-auto-state ${state}`;
    byId('geo-auto-progress-text').textContent = `${completed} / ${target}`;
    byId('geo-auto-formal').textContent = `${formal} / 50`;
    byId('geo-auto-queued').textContent = String(Number(queue.queued || 0));
    byId('geo-auto-failed').textContent = String(Number(queue.failed || 0) + Number(queue.authorization_required || 0));
    byId('geo-auto-model').textContent = executor.model || '--';
    byId('geo-auto-provider').textContent = `${executor.label || '云端API'} · ${executor.ready ? '已验证' : '未就绪'}`;
    byId('geo-auto-mode').textContent = stateLabels[state] || state;
    byId('geo-auto-bar').style.width = `${Math.max(0, Math.min(100, target ? completed / target * 100 : 0))}%`;
    const current = queue.current || {};
    const error = data.last_error || (!executor.ready ? executor.reason : '');
    byId('geo-auto-current').innerHTML = error
      ? `<span class="geo-auto-error">${esc(error)}</span>`
      : current.question_id
        ? `当前：<b>${esc(current.question_id)}</b> · ${esc(current.question_text || '')}`
        : completed >= target ? '本轮云端自动扫描已完成。' : '当前没有正在执行的题目。';
    byId('geo-auto-start').disabled = Boolean(data.enabled) || !executor.ready;
    byId('geo-auto-pause').disabled = !data.enabled || Boolean(data.paused);
    byId('geo-auto-resume').disabled = !data.enabled || !data.paused || !executor.ready;
    byId('geo-auto-retry').disabled = (Number(queue.failed || 0) + Number(queue.authorization_required || 0)) === 0;
  }

  async function refresh(announce=false) {
    if (!mount()) return;
    try {
      const data = await request('/api/r8-19/geo/autonomy');
      render(data);
      if (announce) window.notify?.('GEO 自动运行状态已刷新。');
    } catch (error) {
      const node = byId('geo-auto-current');
      if (node) node.innerHTML = `<span class="geo-auto-error">${esc(error.message)}</span>`;
    }
  }

  async function act(button, path, body={}) {
    const old = button.textContent;
    button.disabled = true;
    button.textContent = '处理中…';
    try {
      const data = await post(path, body);
      render(data.status || data);
      window.notify?.(path.endsWith('/start') ? 'GEO 自动50问已启动。' : 'GEO 自动运行状态已更新。');
      setTimeout(refresh, 300);
    } catch (error) {
      window.notify?.(error.message, 'error');
      const node = byId('geo-auto-current');
      if (node) node.innerHTML = `<span class="geo-auto-error">${esc(error.message)}</span>`;
    } finally {
      button.disabled = false;
      button.textContent = old;
      setTimeout(refresh, 600);
    }
  }

  function boot() {
    if (mount()) return;
    let tries = 0;
    const wait = setInterval(() => {
      tries += 1;
      if (mount() || tries > 60) clearInterval(wait);
    }, 250);
  }

  window.KZGeoAutonomy = {refresh};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();

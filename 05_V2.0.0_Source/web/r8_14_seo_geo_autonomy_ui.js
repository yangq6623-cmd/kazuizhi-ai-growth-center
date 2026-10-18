(() => {
  'use strict';
  if (window.__KZ_R814_SEO_GEO_AUTONOMY_UI__) return;
  window.__KZ_R814_SEO_GEO_AUTONOMY_UI__ = true;

  const api = async (path, options) => {
    const response = await fetch(path, {cache:'no-store', ...(options || {})});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || payload.message || `HTTP ${response.status}`);
    return payload.data || payload;
  };
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  function ensureStyle() {
    if (document.getElementById('r814-autonomy-style')) return;
    const style = document.createElement('style');
    style.id = 'r814-autonomy-style';
    style.textContent = `
      .r814-auto-card{margin:16px 0;background:#fff;border:1px solid #e4eaf3;border-radius:16px;box-shadow:0 8px 28px rgba(24,52,93,.04);padding:18px}
      .r814-auto-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.r814-auto-title{font-size:20px;font-weight:800}.r814-auto-sub{font-size:13px;color:#6c7b91;margin-top:4px}.r814-auto-toggle{display:flex;gap:8px;flex-wrap:wrap}.r814-mode{border:1px solid #ccd7ea;background:#fff;color:#2457bd;padding:8px 12px;border-radius:10px;cursor:pointer;font-weight:700}.r814-mode.active{background:#2563eb;color:#fff;border-color:#2563eb}
      .r814-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:15px}.r814-stat{background:#f8faff;border:1px solid #edf1f6;border-radius:12px;padding:12px}.r814-stat b{font-size:20px;display:block;margin-top:4px}.r814-stat span{font-size:12px;color:#728097}
      .r814-human{margin-top:14px;border-top:1px solid #edf1f6;padding-top:12px}.r814-item{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;padding:11px 12px;border-radius:10px;background:#fff5e6;border:1px solid #fde4bd;margin-top:8px}.r814-item b{display:block;color:#9b5b00}.r814-item span{display:block;color:#6d778a;font-size:12px;margin-top:3px;line-height:1.6}.r814-item button{border:1px solid #e6c57f;background:#fff;color:#8a5a00;padding:8px 11px;border-radius:9px;cursor:pointer;font-weight:700;white-space:nowrap}.r814-actions{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}.r814-action{border:0;background:#2563eb;color:#fff;padding:9px 13px;border-radius:10px;font-weight:700;cursor:pointer}.r814-action.secondary{background:#eef4ff;color:#245ec7}.r814-feedback{min-height:20px;margin-top:10px;font-size:12px;color:#355176}.r814-feedback.error{color:#b42318}.r814-truth{font-size:12px;color:#355176;background:#eef5ff;border-radius:10px;padding:10px 12px;margin-top:12px}
      @media(max-width:800px){.r814-auto-head{flex-direction:column}.r814-stats{grid-template-columns:1fr 1fr}.r814-item{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function mount() {
    ensureStyle();
    if (document.getElementById('r814-autonomy-card')) return;
    const tabs = document.querySelector('.tabs');
    const target = tabs || document.querySelector('.hero')?.nextSibling || document.querySelector('.wrap');
    if (!target || !target.parentNode) return;
    const card = document.createElement('section');
    card.id = 'r814-autonomy-card';
    card.className = 'r814-auto-card';
    card.innerHTML = `
      <div class="r814-auto-head"><div><div class="r814-auto-title">SEO/GEO 自治运行</div><div class="r814-auto-sub">本地发现、规划、生成、QC可自动完成；公网、搜索平台和GEO结果仍必须通过真实连接器与证据门槛。</div></div><div class="r814-auto-toggle"><button class="r814-mode" data-mode="observe">观察模式</button><button class="r814-mode" data-mode="assisted">半自动</button><button class="r814-mode" data-mode="autonomous">自治模式</button></div></div>
      <div class="r814-stats"><div class="r814-stat"><span>当前模式</span><b id="r814-mode-label">--</b></div><div class="r814-stat"><span>真实公开页面</span><b id="r814-public">0</b></div><div class="r814-stat"><span>真实提交URL</span><b id="r814-submitted">0</b></div><div class="r814-stat"><span>SEO/GEO 待人工处理</span><b id="r814-human-count">0</b></div></div>
      <div class="r814-actions"><button class="r814-action" id="r814-run">立即执行自治循环</button><button class="r814-action secondary" id="r814-refresh">刷新自治状态</button></div><div class="r814-feedback" id="r814-feedback" role="status" aria-live="polite"></div>
      <div class="r814-human" id="r814-human"></div>
      <div class="r814-truth">自治 ≠ 绕过平台。没有真实公网URL、提交回执、抓取/收录证据、AI可见性证据时，系统不会把对应步骤标记为成功。</div>`;
    target.parentNode.insertBefore(card, target);
    card.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => setMode(button.dataset.mode)));
    document.getElementById('r814-run').addEventListener('click', runNow);
    document.getElementById('r814-refresh').addEventListener('click', refresh);
    refresh();
  }

  function blockerTarget(item) {
    const key = String(item?.key || '');
    if (key.includes('search_connector')) return {id:'connectors-section', label:'查看搜索连接器'};
    if (key.includes('public_deploy')) return {id:'technical', label:'查看公网部署条件'};
    return {id:'pipeline-section', label:'查看处理位置'};
  }

  function bindBlockerButtons(container) {
    container.querySelectorAll('[data-r814-target]').forEach(button => button.addEventListener('click', () => {
      const target = document.getElementById(button.dataset.r814Target);
      if (!target) return feedback('未找到对应区域，请刷新页面后重试。', true);
      target.scrollIntoView({behavior:'smooth', block:'start'});
      target.setAttribute('tabindex', '-1');
      target.focus({preventScroll:true});
      window.parent?.postMessage({type:'kz-r813-focus', target:button.dataset.r814Target}, location.origin);
      feedback('已定位到该事项的连接器与下一步。');
    }));
  }

  function feedback(message, isError) {
    const node = document.getElementById('r814-feedback');
    if (!node) return;
    node.textContent = message || '';
    node.classList.toggle('error', Boolean(isError));
  }

  function render(state) {
    document.querySelectorAll('.r814-mode').forEach(button => button.classList.toggle('active', button.dataset.mode === state.mode));
    const labels = {observe:'观察', assisted:'半自动', autonomous:'自治'};
    document.getElementById('r814-mode-label').textContent = labels[state.mode] || state.mode || '--';
    document.getElementById('r814-public').textContent = state.today?.public_pages ?? 0;
    document.getElementById('r814-submitted').textContent = state.today?.submitted_urls ?? 0;
    document.getElementById('r814-human-count').textContent = state.human_item_count ?? 0;
    const human = document.getElementById('r814-human');
    const rows = state.human_items || [];
    human.innerHTML = rows.length
      ? `<b>只把真正需要老板的事情放这里</b>${rows.map(item => { const target=blockerTarget(item); return `<div class="r814-item"><div><b>${esc(item.title)}</b><span>${esc(item.reason)}</span><span>下一步：${esc(item.action)}</span></div><button data-r814-target="${target.id}">${target.label}</button></div>`; }).join('')}`
      : '<b>当前无需人工处理</b><div class="r814-auto-sub">本地可自动完成的SEO/GEO任务会继续运行。</div>';
    bindBlockerButtons(human);
  }

  async function refresh() {
    try { render(await api('/api/r8-14/seo-geo/autonomy')); feedback('自治状态已刷新。'); }
    catch (error) { console.warn('SEO/GEO autonomy status deferred', error); feedback(`刷新失败：${error.message || String(error)}`, true); }
  }

  async function setMode(mode) {
    try {
      const state = await api('/api/r8-14/seo-geo/autonomy/config', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({mode, enabled:true}),
      });
      render(state); feedback(`已切换为${({observe:'观察', assisted:'半自动', autonomous:'自治'})[mode] || mode}模式。`);
    } catch (error) { feedback(`切换失败：${error.message || String(error)}`, true); }
  }

  async function runNow() {
    const button = document.getElementById('r814-run');
    button.disabled = true;
    button.textContent = '正在执行…';
    feedback('正在执行自治循环；外部步骤仍需真实连接器与回执。');
    try {
      await api('/api/r8-14/seo-geo/autonomy/run', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({force:true})});
      await refresh();
      if (typeof window.load === 'function') window.load();
      feedback('自治循环已完成，已刷新真实状态。');
    } catch (error) {
      feedback(`执行失败：${error.message || String(error)}`, true);
    } finally {
      button.disabled = false;
      button.textContent = '立即执行自治循环';
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once:true});
  else mount();
})();

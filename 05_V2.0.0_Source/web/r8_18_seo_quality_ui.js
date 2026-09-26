(() => {
  'use strict';
  if (window.__KZ_R818_SEO_QUALITY_UI__) return;
  window.__KZ_R818_SEO_QUALITY_UI__ = true;

  let quality = null;
  let applying = false;

  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  async function api(path, options) {
    const response = await fetch(path, {cache:'no-store', ...(options || {})});
    const payload = await response.json().catch(() => ({}));
    const data = payload.data || payload;
    if (!response.ok) throw new Error(data.error || data.message || `HTTP ${response.status}`);
    return data;
  }

  function post(path, body={}) {
    return api(path, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body || {}),
    });
  }

  function status(message, error=false) {
    const node = $('action-status');
    if (!node) return;
    node.textContent = message || '';
    node.classList.toggle('error', !!error);
  }

  function setBusy(button, busy, label) {
    if (!button) return;
    if (busy) {
      if (!button.dataset.kzOldText) button.dataset.kzOldText = button.textContent;
      button.disabled = true;
      button.textContent = label || '正在执行…';
    } else {
      button.disabled = false;
      button.textContent = button.dataset.kzOldText || button.textContent;
      delete button.dataset.kzOldText;
    }
  }

  function ensureStyle() {
    if ($('r818-quality-style')) return;
    const style = document.createElement('style');
    style.id = 'r818-quality-style';
    style.textContent = `
      .r818-actions{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin-top:8px}
      .r818-btn{border:1px solid #cbd8ee;background:#fff;color:#2457bd;border-radius:8px;padding:7px 10px;font-weight:700;font-size:12px;cursor:pointer}
      .r818-btn.primary{background:#2563eb;border-color:#2563eb;color:#fff}
      .r818-btn:disabled{opacity:.55;cursor:wait}
      .r818-note{margin-top:6px;font-size:11px;color:#65748a;line-height:1.55}
      .r818-score{font-weight:800;color:#176a50}
      .r818-warning{color:#a86500}
      .r818-error{color:#b42318}
    `;
    document.head.appendChild(style);
  }

  function findHealthItem(name) {
    return [...document.querySelectorAll('#health .health-item')].find(node => (node.querySelector('b')?.textContent || '').trim() === name) || null;
  }

  async function refreshQuality() {
    quality = await api('/api/r8-18/seo-quality/status');
    apply();
    return quality;
  }

  function applyPerformance() {
    const item = findHealthItem('性能测速');
    if (!item || !quality) return;
    const p = quality.performance || {};
    const left = item.querySelector('div');
    const badge = item.querySelector('.tag');
    const mobile = p.mobile_score;
    const desktop = p.desktop_score;
    if (p.last_run_at) {
      const scores = [];
      if (mobile !== null && mobile !== undefined) scores.push(`移动 ${mobile}`);
      if (desktop !== null && desktop !== undefined) scores.push(`桌面 ${desktop}`);
      if (left) left.querySelector('.sub').innerHTML = `${scores.length ? `PageSpeed：<span class="r818-score">${esc(scores.join(' / '))}</span>` : 'PageSpeed 已运行但没有可用评分'}；最近证据 ${esc(p.last_run_at)}。`;
      if (badge) { badge.textContent = scores.length ? '已有证据' : '需复查'; badge.className = `tag ${scores.length ? 'ok' : 'warn'}`; }
    }
    if (!item.querySelector('[data-r818-performance]')) {
      const actions = document.createElement('div');
      actions.className = 'r818-actions';
      actions.innerHTML = '<button class="r818-btn" data-r818-performance>运行 PageSpeed</button>';
      left?.appendChild(actions);
      actions.querySelector('button').onclick = async event => {
        const button = event.currentTarget;
        setBusy(button, true, '测速中…');
        status('正在调用 PageSpeed/Lighthouse 独立测速，可能需要几十秒。');
        try {
          const result = await post('/api/r8-18/seo-quality/performance', {limit:3});
          await refreshQuality();
          status(result.successful > 0 ? `性能测速完成：${result.successful}/${result.tested} 组取得真实 Lighthouse 证据。` : '性能测速未取得可用结果；如果 Google 限流，可稍后重试或配置 PageSpeed API Key。', result.successful <= 0);
        } catch (error) {
          status(`性能测速失败：${error.message || String(error)}`, true);
        } finally { setBusy(button, false); }
      };
    }
  }

  function applyInternalLinks() {
    const item = findHealthItem('内链结构');
    if (!item || !quality) return;
    const audit = quality.internal_links || {};
    const left = item.querySelector('div');
    const badge = item.querySelector('.tag');
    if (audit.last_run_at) {
      const orphanCount = (audit.orphans || []).length;
      const brokenCount = (audit.broken || []).length;
      if (left) left.querySelector('.sub').innerHTML = `已审计 ${Number(audit.pages || 0)} 个公开页、${Number(audit.links || 0)} 条 /seo/ 内链；孤儿页 <b>${orphanCount}</b>，断链 <b>${brokenCount}</b>。`;
      if (badge) { badge.textContent = orphanCount === 0 && brokenCount === 0 ? '结构正常' : '需优化'; badge.className = `tag ${orphanCount === 0 && brokenCount === 0 ? 'ok' : 'warn'}`; }
    }
    if (!item.querySelector('[data-r818-links]')) {
      const actions = document.createElement('div');
      actions.className = 'r818-actions';
      actions.innerHTML = '<button class="r818-btn" data-r818-links>审计内链</button>';
      left?.appendChild(actions);
      actions.querySelector('button').onclick = async event => {
        const button = event.currentTarget;
        setBusy(button, true, '审计中…');
        status('正在逐页读取真实公开 HTML，检查 /seo/ 内链、孤儿页与断链。');
        try {
          const result = await post('/api/r8-18/seo-quality/internal-links', {limit:50});
          await refreshQuality();
          status(`内链审计完成：${result.pages || 0} 页，孤儿页 ${result.orphan_count || 0}，断链 ${result.broken_count || 0}。`);
        } catch (error) {
          status(`内链审计失败：${error.message || String(error)}`, true);
        } finally { setBusy(button, false); }
      };
    }
  }

  function applyResultVerification() {
    const pipeline = $('pipeline');
    if (!pipeline || !quality) return;
    const steps = [...pipeline.querySelectorAll('.step')];
    const step = steps.find(node => (node.querySelector('b')?.textContent || '').trim().startsWith('07'));
    if (!step) return;
    const verify = quality.result_verification || {};
    const google = quality.google || {};
    if (!step.querySelector('[data-r818-verify]')) {
      const actions = document.createElement('div');
      actions.className = 'r818-actions';
      actions.innerHTML = '<button class="r818-btn primary" data-r818-verify>验证真实结果</button>';
      step.appendChild(actions);
      actions.querySelector('button').onclick = async event => {
        const button = event.currentTarget;
        setBusy(button, true, '验证中…');
        status('正在检查 Google Search Console 的抓取、收录与搜索表现证据；没有真实证据不会升级状态。');
        try {
          const result = await post('/api/r8-18/seo-quality/verify-results', {limit:20});
          await refreshQuality();
          if (typeof window.load === 'function') await window.load();
          if (result.skipped) {
            status('结果验证仍在等待 Google Search Console 完成站点验证和 OAuth；百度/IndexNow 的提交回执不会被误算成收录。', true);
          } else {
            status(`结果验证完成：抓取证据 ${result.crawled_evidence || 0}，收录证据 ${result.indexed_evidence || 0}，排名证据 ${result.ranking_evidence || 0}。`);
          }
        } catch (error) {
          status(`结果验证失败：${error.message || String(error)}`, true);
        } finally { setBusy(button, false); }
      };
    }
    let note = step.querySelector('.r818-note');
    if (!note) { note = document.createElement('div'); note.className = 'r818-note'; step.appendChild(note); }
    note.textContent = google.oauth_ready
      ? `Google Search Console 已授权；最近验证：${verify.last_run_at || '尚未运行'}。`
      : 'Google DNS 所有权验证 / OAuth 尚未完成。当前保持等待，不把“已提交”写成“已收录”。';
  }

  function applyGoogleWaiting() {
    const googleRow = [...document.querySelectorAll('#connectors .connector')].find(node => (node.querySelector('b')?.textContent || '').includes('Google Search Console'));
    if (!googleRow || !quality) return;
    const google = quality.google || {};
    let note = googleRow.querySelector('.r818-note');
    if (!note) { note = document.createElement('div'); note.className = 'r818-note'; googleRow.querySelector('div')?.appendChild(note); }
    note.textContent = google.oauth_ready
      ? 'Google Search Console OAuth 已就绪，可运行“07 结果验证”。'
      : 'DNS TXT 在 Google 官方验证通过前可能需要传播时间；请保持 TXT 不变，官方验证成功后再完成 OAuth。';
  }

  function apply() {
    if (applying) return;
    applying = true;
    try {
      ensureStyle();
      applyPerformance();
      applyInternalLinks();
      applyResultVerification();
      applyGoogleWaiting();
    } finally { applying = false; }
  }

  const observer = new MutationObserver(() => apply());
  observer.observe(document.documentElement, {childList:true, subtree:true});

  async function boot() {
    try { await refreshQuality(); }
    catch (error) { console.warn('R8-18 SEO quality status deferred', error); }
    apply();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();


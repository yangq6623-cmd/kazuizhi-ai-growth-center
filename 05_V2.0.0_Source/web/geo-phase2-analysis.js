(() => {
  'use strict';
  if (window.__KZ_GEO_PHASE2_ANALYSIS__) return;
  window.__KZ_GEO_PHASE2_ANALYSIS__ = true;

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[char]));
  const fmt = value => Number(value || 0).toLocaleString('zh-CN');

  async function json(path, options) {
    const response = await fetch(path, {cache:'no-store', ...(options || {})});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `GEO分析服务返回 ${response.status}`);
    return data;
  }

  async function post(path, body = {}) {
    return json(path, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)
    });
  }

  function panelMarkup() {
    return `
      <section id="geo-phase2-analysis" class="geo2-analysis" aria-label="GEO第二阶段分析与比较">
        <div class="geo2-head">
          <div>
            <p class="geo2-eyebrow">R8-19 · Phase 2 · 50% → 70%</p>
            <h2>GEO 分析与比较</h2>
            <p class="geo2-subtitle">只分析已有 A/B Evidence；不创造证据，不把本地模型结果计入正式指标。</p>
          </div>
          <div class="geo2-actions">
            <span id="geo2-status" class="geo2-status neutral">等待真实证据</span>
            <button id="geo2-refresh" class="geo2-btn primary" type="button">刷新分析</button>
            <button id="geo2-copy" class="geo2-btn secondary" type="button">复制 ChatGPT 分析包</button><button id="geo2-chatgpt" class="geo2-btn secondary" type="button">提交总脑分析</button>
          </div>
        </div>

        <div class="geo2-metrics" id="geo2-metrics"></div>

        <div class="geo2-columns">
          <article class="geo2-card">
            <div class="geo2-card-head"><div><p>按问题类型</p><h3>自然发现 / 商业推荐 / 品牌认知</h3></div></div>
            <div id="geo2-type-grid" class="geo2-type-grid"></div>
          </article>
          <article class="geo2-card">
            <div class="geo2-card-head"><div><p>问题结果</p><h3>逐题可见度与缺口</h3></div><span id="geo2-result-count" class="geo2-count">0</span></div>
            <div class="geo2-table-wrap">
              <table class="geo2-table">
                <thead><tr><th>问题</th><th>状态</th><th>推荐</th><th>官网</th><th>可见度</th><th>缺口</th></tr></thead>
                <tbody id="geo2-result-rows"><tr><td colspan="6" class="empty">尚无 A/B Evidence。</td></tr></tbody>
              </table>
            </div>
          </article>
        </div>

        <div class="geo2-columns lower">
          <article class="geo2-card">
            <div class="geo2-card-head"><div><p>Top 10</p><h3>当前 GEO 缺口</h3></div><span class="geo2-count" id="geo2-gap-count">0</span></div>
            <div id="geo2-gaps" class="geo2-list"><div class="geo2-empty">真实证据产生后，这里自动列出缺口。</div></div>
          </article>
          <article class="geo2-card">
            <div class="geo2-card-head"><div><p>候选平台雷达</p><h3>竞品/平台候选矩阵</h3></div><span class="geo2-count" id="geo2-platform-count">0</span></div>
            <div id="geo2-platforms" class="geo2-list"><div class="geo2-empty">目前没有明确出现的平台候选。</div></div>
            <p class="geo2-note">系统只记录回答中明确出现的名称；默认不会自动认定为正式竞品，后续由 ChatGPT 总脑确认。</p>
          </article>
        </div>

        <div id="geo2-chatgpt-box" class="geo2-chatgpt"><div class="geo2-chatgpt-title"><span>ChatGPT 总脑判断</span><span id="geo2-chatgpt-status" class="geo2-status neutral">尚未分析</span></div><div id="geo2-chatgpt-content" class="geo2-chatgpt-content">配置云端API并取得A/B Evidence后，可提交给ChatGPT总脑进行结构化分析。这里的结果仅作为判断依据，不会直接改变Evidence或执行任务。</div></div>

        <div class="geo2-footer">
          <span><b>分析控制：</b>确定性规则自动整理事实；战略解释、任务优先级、内容动作和复测由 ChatGPT 总脑决定。</span>
          <span id="geo2-generated">--</span>
        </div>
      </section>`;
  }

  function ensurePanel() {
    const pane = document.getElementById('geo-growth-pane');
    if (!pane) return null;
    if (!document.getElementById('geo-phase2-analysis')) {
      const node = document.createElement('div');
      node.innerHTML = panelMarkup();
      const panel = node.firstElementChild;
      const anchor = pane.querySelector('.geo-kpis');
      if (anchor?.parentNode) anchor.parentNode.insertBefore(panel, anchor.nextSibling);
      else pane.prepend(panel);
    }
    return document.getElementById('geo-phase2-analysis');
  }

  function rate(value) {
    return value == null ? '--' : `${value}%`;
  }

  function render(data) {
    ensurePanel();
    const summary = data?.summary || {};
    const metrics = [
      ['已分析', `${fmt(summary.tested)}题`, 'A/B级正式证据'],
      ['品牌提及', rate(summary.mention_rate), `${fmt(summary.mentioned)}题`],
      ['明确推荐', rate(summary.recommendation_rate), `${fmt(summary.recommended)}题`],
      ['官网引用', rate(summary.citation_rate), `${fmt(summary.cited)}题`],
      ['平均可见度', summary.avg_visibility_score == null ? '--' : `${summary.avg_visibility_score}`, '逐题透明计算'],
    ];
    document.getElementById('geo2-metrics').innerHTML = metrics.map(item =>
      `<article><span>${esc(item[0])}</span><strong>${esc(item[1])}</strong><small>${esc(item[2])}</small></article>`
    ).join('');

    const tested = Number(summary.tested || 0);
    const status = document.getElementById('geo2-status');
    status.textContent = tested ? `已分析 ${tested} 题` : '等待真实证据';
    status.className = `geo2-status ${tested ? 'success' : 'neutral'}`;

    const types = summary.by_type || {};
    const order = [['discovery','自然发现'],['commercial','商业推荐'],['brand','品牌认知']];
    document.getElementById('geo2-type-grid').innerHTML = order.map(([key,label]) => {
      const item = types[key] || {};
      return `<div class="geo2-type-card">
        <div><b>${esc(label)}</b><span>${fmt(item.tested)}题</span></div>
        <div class="geo2-type-line"><span>提及</span><strong>${rate(item.mention_rate)}</strong></div>
        <div class="geo2-type-line"><span>推荐</span><strong>${rate(item.recommendation_rate)}</strong></div>
        <div class="geo2-type-line"><span>官网</span><strong>${rate(item.citation_rate)}</strong></div>
        <div class="geo2-type-line"><span>平均可见度</span><strong>${item.avg_visibility_score == null ? '--' : esc(item.avg_visibility_score)}</strong></div>
      </div>`;
    }).join('');

    const results = data?.question_results || [];
    document.getElementById('geo2-result-count').textContent = fmt(results.length);
    document.getElementById('geo2-result-rows').innerHTML = results.length ? results.map(item => {
      const gaps = (item.gaps || []).map(g => g.label).slice(0,2).join('；');
      const state = item.brand_recommended ? '明确推荐' : item.brand_mentioned ? '已提及' : '未出现';
      const cls = item.brand_recommended ? 'success' : item.brand_mentioned ? 'info' : 'danger';
      return `<tr>
        <td><b>${esc(item.question_text || item.question_id)}</b><small>${esc(item.question_id)} · ${esc(item.question_type || '')}</small></td>
        <td><span class="geo2-pill ${cls}">${state}</span></td>
        <td>${item.brand_recommended ? '是' : '否'}</td>
        <td>${item.brand_cited ? '是' : '否'}</td>
        <td><strong>${esc(item.visibility_score)}</strong></td>
        <td>${esc(gaps || '—')}</td>
      </tr>`;
    }).join('') : '<tr><td colspan="6" class="empty">尚无 A/B Evidence；真实测试完成后自动出现。</td></tr>';

    const gaps = summary.gaps || [];
    document.getElementById('geo2-gap-count').textContent = fmt(gaps.length);
    document.getElementById('geo2-gaps').innerHTML = gaps.length ? gaps.map(item =>
      `<div class="geo2-list-row"><span class="geo2-severity ${item.severity === 'high' ? 'high' : 'medium'}">${item.severity === 'high' ? '高' : '中'}</span><div><b>${esc(item.label)}</b><small>${fmt(item.count)}题 · 示例：${esc(item.example_question || '—')}</small></div></div>`
    ).join('') : '<div class="geo2-empty">暂无缺口；必须有真实 A/B Evidence 后才会产生分析。</div>';

    const platforms = summary.platform_candidates || [];
    document.getElementById('geo2-platform-count').textContent = fmt(platforms.length);
    document.getElementById('geo2-platforms').innerHTML = platforms.length ? platforms.map(item =>
      `<div class="geo2-list-row"><span class="geo2-platform-dot"></span><div><b>${esc(item.name)}</b><small>出现 ${fmt(item.question_count)} 题 · ${item.confirmed_competitor ? '已确认竞品' : '待ChatGPT确认'}</small></div></div>`
    ).join('') : '<div class="geo2-empty">暂无明确平台候选。</div>';

    document.getElementById('geo2-generated').textContent = data?.generated_at ? `分析时间：${esc(data.generated_at)}` : '尚未生成分析快照';
  }

  async function loadChatGPT() { try { const data = await json('/api/r8-19/geo/analysis/chatgpt'); renderChatGPT(data); } catch (_) {} }

  function renderChatGPT(data) { const status = data && data.status ? data.status : {}; const snap = data && data.snapshot ? data.snapshot : {}; const box = document.getElementById('geo2-chatgpt-content'); const badge = document.getElementById('geo2-chatgpt-status'); const button = document.getElementById('geo2-chatgpt'); if (button) button.disabled = !status.ready; if (!box || !badge) return; if (snap.analysis) { badge.textContent = '已完成'; badge.className = 'geo2-status success'; const a=snap.analysis; const findings=(a.key_findings||[]).slice(0,4).map(x => '<li><b>'+esc(x.title)+'</b>：'+esc(x.detail)+'</li>').join(''); const actions=(a.candidate_actions||[]).slice(0,4).map(x => '<li>'+esc(x.action)+'<small>'+esc(x.why)+'</small></li>').join(''); box.innerHTML='<p>'+esc(a.executive_summary||'')+'</p>'+(findings?'<div><b>关键发现</b><ul>'+findings+'</ul></div>':'')+(actions?'<div><b>候选行动（待总控确认）</b><ul>'+actions+'</ul></div>':''); return; } badge.textContent = status.ready ? '可提交' : 'API未配置'; badge.className = 'geo2-status '+(status.ready?'success':'neutral'); box.textContent = status.ready ? '当前可以提交总脑分析。' : (status.reason || '请先在GEO API入口完成云端模型连接验证。'); }

  async function runChatGPT(button) { if(button) button.disabled=true; try { const data=await post('/api/r8-19/geo/analysis/chatgpt/run'); renderChatGPT({status:{ready:true},snapshot:data.result||data}); window.notify?.('ChatGPT 总脑分析已完成；候选行动仍需总控确认。'); } catch(error) { window.notify?.(error.message,'error'); loadChatGPT(); } finally { if(button) button.disabled=false; } }

  async function load() {
    ensurePanel();
    try {
      const data = await json('/api/r8-19/geo/analysis');
      render(data);
      loadChatGPT();
      return data;
    } catch (error) {
      const status = document.getElementById('geo2-status');
      if (status) { status.textContent = '分析服务未就绪'; status.className = 'geo2-status danger'; }
      return null;
    }
  }

  async function refresh(button) {
    if (button) button.disabled = true;
    try {
      const data = await post('/api/r8-19/geo/analysis/refresh');
      render(data.result || data);
      window.notify?.('GEO第二阶段分析已刷新：仅使用现有A/B Evidence。');
    } catch (error) {
      window.notify?.(error.message, 'error');
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function copyPack() {
    try {
      const pack = await json('/api/r8-19/geo/analysis/brief');
      const text = JSON.stringify(pack, null, 2);
      await navigator.clipboard.writeText(text);
      window.notify?.('ChatGPT 分析包已复制，可交给总脑进行战略判断。');
    } catch (error) {
      window.notify?.(error.message, 'error');
    }
  }

  function bind() {
    const panel = ensurePanel();
    if (!panel || panel.dataset.bound === '1') return;
    panel.dataset.bound = '1';
    document.getElementById('geo2-refresh')?.addEventListener('click', event => refresh(event.currentTarget));
    document.getElementById('geo2-copy')?.addEventListener('click', copyPack);
    document.getElementById('geo2-chatgpt')?.addEventListener('click', event => runChatGPT(event.currentTarget));
    const receiptList = document.getElementById('geo-receipt-list');
    if (receiptList && window.MutationObserver) {
      let timer = null;
      new MutationObserver(() => {
        clearTimeout(timer);
        timer = setTimeout(load, 180);
      }).observe(receiptList, {childList:true,subtree:true});
    }
    load();
  }

  function start() {
    bind();
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      bind();
      if (document.getElementById('geo-phase2-analysis') || tries > 40) clearInterval(timer);
    }, 250);
  }

  window.KZGeoPhase2Analysis = {load, refresh, copyPack};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
(() => {
  'use strict';
  if (window.__KZ_CONTENT_MISSION_CARD__) return;
  window.__KZ_CONTENT_MISSION_CARD__ = true;

  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api = async (url, options={}) => {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.detail || data.message || `HTTP ${response.status}`);
    return data;
  };
  const post = (url, body) => api(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  let timer = null;
  let lastMission = null;

  function installStyle() {
    if (byId('kz-mission-card-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-mission-card-style';
    style.textContent = `
      .kz-mission-card{margin-top:12px;border:1px solid #dbe5f0;border-radius:8px;background:#fff;padding:13px;display:grid;gap:10px}
      .kz-mission-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.kz-mission-head h4{margin:0 0 4px;font-size:14px;color:#17324f}.kz-mission-head p{margin:0;font-size:11px;color:#71839a;line-height:1.5}.kz-mission-state{font-size:10px;border-radius:999px;padding:5px 8px;background:#edf3fb;color:#4e6782;white-space:nowrap}.kz-mission-state.running{background:#e8f1ff;color:#1768e5}.kz-mission-state.paused,.kz-mission-state.waiting_retry{background:#fff6e6;color:#9a671c}.kz-mission-state.needs_attention{background:#fff0f0;color:#b33d3d}.kz-mission-state.awaiting_review,.kz-mission-state.completed{background:#e8f7f0;color:#16875c}
      .kz-mission-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}.kz-mission-metric{border:1px solid #e6ecf3;border-radius:6px;padding:9px;background:#fbfdff}.kz-mission-metric small{display:block;font-size:9px;color:#8898aa;margin-bottom:3px}.kz-mission-metric b{font-size:12px;color:#17324f}.kz-mission-next{border:1px solid #e1e8f1;border-radius:6px;padding:9px 10px;background:#f8fbff;font-size:11px;color:#53677e}.kz-mission-next b{color:#17324f}.kz-mission-actions{display:flex;gap:6px;flex-wrap:wrap}.kz-mission-actions button{height:30px;border-radius:4px;border:1px solid #b9cbe0;background:#fff;color:#24496f;padding:0 10px;font-size:10px;cursor:pointer}.kz-mission-actions button.primary{background:#1768e5;border-color:#1768e5;color:#fff;font-weight:700}.kz-mission-actions button:disabled{opacity:.5;cursor:wait}
      .kz-mission-details{border-top:1px solid #edf1f6;padding-top:8px}.kz-mission-details summary{font-size:10px;color:#63778f;cursor:pointer}.kz-mission-details dl{margin:8px 0 0;display:grid;grid-template-columns:90px 1fr;gap:5px 8px;font-size:10px}.kz-mission-details dt{color:#8998aa}.kz-mission-details dd{margin:0;color:#425c78;white-space:pre-wrap;word-break:break-word;max-height:120px;overflow:auto}.kz-mission-empty{font-size:11px;color:#73869b;background:#f8fbff;border:1px dashed #d4dfeb;border-radius:6px;padding:10px}
      @media(max-width:1050px){.kz-mission-grid{grid-template-columns:1fr 1fr}.kz-mission-head{flex-direction:column}}
    `;
    document.head.appendChild(style);
  }

  function ensureRoot() {
    const simple = byId('kz-simple-root');
    if (!simple) return false;
    if (byId('kz-content-mission-card')) return true;
    const root = document.createElement('section');
    root.id = 'kz-content-mission-card';
    root.className = 'kz-mission-card';
    const monitor = byId('kz-production-monitor');
    if (monitor) monitor.insertAdjacentElement('afterend', root);
    else {
      const actions = simple.querySelector('.kz-simple-actions');
      if (actions) actions.insertAdjacentElement('afterend', root); else simple.appendChild(root);
    }
    root.innerHTML = '<div class="kz-mission-empty">正在读取内容任务卡与断点记录…</div>';
    return true;
  }

  function statusLabel(status='') {
    return ({
      ready:'等待执行', running:'生产中', paused:'已暂停', waiting_retry:'等待自动重试',
      needs_attention:'需要处理', awaiting_review:'等待审核', awaiting_final_render:'等待成片合成',
      completed:'已完成'
    })[status] || status || '等待任务';
  }

  function modeLabel(mode='') {
    return ({auto:'全自动',assisted:'我提供内容',manual:'手动细调'})[mode] || '我提供内容';
  }

  function qualityLabel(value='') {
    return ({fast:'快速',standard:'标准',high:'高质量',premium:'精品'})[value] || '高质量';
  }

  function render(payload) {
    if (!ensureRoot()) return;
    const root = byId('kz-content-mission-card');
    const mission = payload?.mission || null;
    lastMission = mission;
    if (!mission) {
      root.innerHTML = '<div class="kz-mission-head"><div><h4>内容生产任务卡</h4><p>GPT导演生成生产任务后，这里会自动保存文案、镜头和断点。</p></div></div><div class="kz-mission-empty">当前还没有可恢复的生产任务。</div>';
      return;
    }
    const current = mission.current || {};
    const card = mission.content_card || {};
    const total = Number(mission.total_candidates || 0);
    const done = Number(mission.completed_candidates || 0);
    const percent = total ? Math.round(done / total * 100) : 0;
    const canResume = ['paused','ready','waiting_retry','needs_attention'].includes(mission.status);
    const canPause = mission.status === 'running';
    const hasFailed = Number(mission.terminal_failed || 0) > 0;
    const nextText = current.shot_order
      ? `正在处理镜头 ${current.shot_order}，候选 ${current.candidate_index || '-'}，第 ${current.attempt || 1} 次执行`
      : (mission.status === 'awaiting_review' ? '候选生成检查点已完成，等待镜头筛选。' : '系统会从第一个未完成检查点继续，不会重跑已完成候选。');
    root.innerHTML = `
      <div class="kz-mission-head"><div><h4>内容生产任务卡</h4><p>${esc(mission.name || '内容任务')} · ${esc(modeLabel(mission.production_mode))} · ${esc(qualityLabel(mission.quality_profile))}</p></div><span class="kz-mission-state ${esc(mission.status || '')}">${esc(statusLabel(mission.status))}</span></div>
      <div class="kz-mission-grid">
        <div class="kz-mission-metric"><small>动态镜头</small><b>${Number(mission.total_shots || 0)}</b></div>
        <div class="kz-mission-metric"><small>计划候选</small><b>${total}</b></div>
        <div class="kz-mission-metric"><small>已保存检查点</small><b>${done} / ${total}</b></div>
        <div class="kz-mission-metric"><small>自动重试等待</small><b>${Number(mission.waiting_retry || 0)}</b></div>
        <div class="kz-mission-metric"><small>整体进度</small><b>${percent}%</b></div>
      </div>
      <div class="kz-mission-next"><b>断点续跑：</b>${esc(nextText)}</div>
      <div class="kz-mission-actions">
        ${canResume ? '<button type="button" class="primary" id="kz-mission-resume">恢复未完成任务</button>' : ''}
        ${canPause ? '<button type="button" id="kz-mission-pause">暂停任务</button>' : ''}
        ${hasFailed ? '<button type="button" id="kz-mission-retry">重试失败候选</button>' : ''}
      </div>
      <details class="kz-mission-details"><summary>查看内容任务卡</summary><dl>
        <dt>内容来源</dt><dd>${esc(card.source_title || card.source_kind || '当前创作内容')}</dd>
        <dt>参考链接</dt><dd>${esc(card.source_url || '无')}</dd>
        <dt>GPT分析</dt><dd>${esc(card.ai_analysis || '等待补充')}</dd>
        <dt>最终文案</dt><dd>${esc(card.final_script || '等待确认')}</dd>
        <dt>审核状态</dt><dd>${esc(card.review_status || '待生产')}</dd>
        <dt>发布状态</dt><dd>${esc(card.publish_status || '未发布')}</dd>
      </dl></details>`;
    bindActions();
  }

  function bindActions() {
    const mission = lastMission;
    if (!mission) return;
    byId('kz-mission-resume')?.addEventListener('click', async event => {
      event.currentTarget.disabled = true;
      try { await post('/api/production-missions/resume', {mission_id:mission.id}); await refresh(); }
      catch (error) { event.currentTarget.textContent = error.message; event.currentTarget.disabled = false; }
    }, {once:true});
    byId('kz-mission-pause')?.addEventListener('click', async event => {
      event.currentTarget.disabled = true;
      try { await post('/api/production-missions/pause', {mission_id:mission.id}); await refresh(); }
      catch (error) { event.currentTarget.textContent = error.message; event.currentTarget.disabled = false; }
    }, {once:true});
    byId('kz-mission-retry')?.addEventListener('click', async event => {
      event.currentTarget.disabled = true;
      try { await post('/api/production-missions/retry', {mission_id:mission.id}); await refresh(); }
      catch (error) { event.currentTarget.textContent = error.message; event.currentTarget.disabled = false; }
    }, {once:true});
  }

  async function refresh() {
    if (!ensureRoot()) return;
    try { render(await api('/api/production-missions/current')); }
    catch (error) {
      const root = byId('kz-content-mission-card');
      if (root) root.innerHTML = `<div class="kz-mission-empty">任务卡暂时不可读：${esc(error.message)}</div>`;
    }
  }

  function start() {
    installStyle();
    let attempts = 0;
    const wait = setInterval(() => {
      attempts += 1;
      if (ensureRoot() || attempts > 30) {
        clearInterval(wait);
        refresh();
        timer = setInterval(refresh, 4000);
      }
    }, 300);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true}); else start();
  window.addEventListener('beforeunload', () => { if (timer) clearInterval(timer); }, {once:true});
})();

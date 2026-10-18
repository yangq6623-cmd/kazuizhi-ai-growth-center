(() => {
  'use strict';
  if (window.__KZ_GEO_PHASE3_UI__) return;
  window.__KZ_GEO_PHASE3_UI__ = true;

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const byId = id => document.getElementById(id);
  let cache = null;
  let actionBusy = false;

  async function json(path, options){
    const response = await fetch(path, {cache:'no-store', ...(options || {})});
    const data = await response.json().catch(() => ({}));
    if(!response.ok) throw new Error(data.error || `GEO Phase 3 返回 ${response.status}`);
    return data;
  }
  async function post(path, body={}){
    return json(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  }

  function installStyle(){
    if(byId('geo3-style')) return;
    const style = document.createElement('style');
    style.id = 'geo3-style';
    style.textContent = `
      .geo3{margin:16px 0;border:1px solid #cfd9eb;border-radius:10px;background:#fff;overflow:hidden}
      .geo3-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding:15px 16px;border-bottom:1px solid #e6ebf3;background:#f8fbff}
      .geo3-head p{margin:0 0 3px;font-size:10px;letter-spacing:.08em;color:#55719b;font-weight:800}.geo3-head h2{margin:0;font-size:17px}.geo3-head small{display:block;margin-top:5px;color:#64748b;line-height:1.5}
      .geo3-badge{padding:5px 9px;border-radius:4px;background:#eef4ff;color:#285fc9;font-size:11px;font-weight:800;white-space:nowrap}
      .geo3-body{padding:14px 16px}.geo3-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.geo3-kpis article{border:1px solid #e1e7f0;border-radius:7px;padding:9px;min-width:0}.geo3-kpis span{display:block;color:#77859a;font-size:10px}.geo3-kpis strong{display:block;margin-top:3px;font-size:16px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.geo3-kpis small{display:block;margin-top:2px;color:#8a96a8;font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .geo3-actions{margin-top:12px;border:1px solid #e1e7f0;border-radius:7px;overflow:auto}.geo3-table{width:100%;border-collapse:collapse;font-size:11px}.geo3-table th,.geo3-table td{padding:8px 9px;border-bottom:1px solid #edf1f6;text-align:left;vertical-align:top}.geo3-table th{background:#fafbfd;color:#65748a;font-weight:700}.geo3-table small{display:block;color:#8995a6;margin-top:2px;line-height:1.4}.geo3-pill{display:inline-block;padding:3px 6px;border-radius:4px;background:#eef4ff;color:#285fc9;font-size:10px;font-weight:700}.geo3-pill.ok{background:#edf9f1;color:#247a45}.geo3-pill.wait{background:#fff7e8;color:#9a6400}.geo3-pill.bad{background:#fff0f0;color:#b02b2b}
      .geo3-buttons{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.geo3-buttons button{border:1px solid #c8d5e8;border-radius:7px;background:#fff;color:#294b7a;padding:7px 11px;font-size:11px;font-weight:700;cursor:pointer}.geo3-buttons button.primary{background:#2865dc;border-color:#2865dc;color:#fff}.geo3-buttons button:disabled{opacity:.45;cursor:not-allowed}.geo3-note{margin-top:10px;padding:8px 10px;border-radius:6px;background:#f7f9fc;color:#66758a;font-size:10px;line-height:1.5}.geo3-msg{margin-top:9px;font-size:11px;color:#54657b}.geo3-empty{padding:14px;color:#8793a5;text-align:center}
      @media(max-width:1050px){.geo3-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:650px){.geo3-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.geo3-head{display:block}.geo3-badge{display:inline-block;margin-top:8px}}
    `;
    document.head.appendChild(style);
  }

  function markup(){
    return `<section id="geo-phase3-panel" class="geo3">
      <div class="geo3-head">
        <div><p>R8-19 · PHASE 3 · 70% → 80%</p><h2>GEO 自动优化闭环</h2><small>真实 A/B Evidence → 缺口 → ChatGPT/老板授权 → AI员工执行 → 公网发布 → 真实复测 → Before / After。普通云模型 C级结果不进入正式成绩。</small></div>
        <span id="geo3-state" class="geo3-badge">等待分析</span>
      </div>
      <div class="geo3-body">
        <div id="geo3-kpis" class="geo3-kpis"></div>
        <div class="geo3-actions"><table class="geo3-table"><thead><tr><th>缺口 / 动作</th><th>问题</th><th>AI员工任务</th><th>公开页</th><th>复测</th><th>变化</th></tr></thead><tbody id="geo3-action-rows"><tr><td colspan="6" class="geo3-empty">等待真实A/B证据和Phase 2分析。</td></tr></tbody></table></div>
        <div class="geo3-buttons">
          <button id="geo3-plan" type="button">生成 / 刷新优化计划</button>
          <button id="geo3-run" class="primary" type="button">执行本轮优化</button>
          <button id="geo3-refresh" type="button">刷新状态</button>
        </div>
        <div id="geo3-msg" class="geo3-msg"></div>
        <div class="geo3-note"><b>真值规则：</b>第二阶段软件只剩 1→3→10→50 实机放量验收；第三阶段可以并行运行。任何“有效/无效”判断必须来自优化后的新 A/B Evidence，不会用豆包普通API回答、内容生成或发布动作冒充GEO提升。</div>
      </div>
    </section>`;
  }

  function ensurePanel(){
    installStyle();
    const pane = byId('geo-growth-pane');
    if(!pane) return null;
    if(byId('geo-phase3-panel')) return byId('geo-phase3-panel');
    const wrap = document.createElement('div');
    wrap.innerHTML = markup();
    const panel = wrap.firstElementChild;
    const anchor = byId('geo-phase2-analysis') || byId('geo-autonomy');
    if(anchor && anchor.parentNode) anchor.parentNode.insertBefore(panel, anchor.nextSibling);
    else pane.appendChild(panel);
    bind();
    return panel;
  }

  function stateLabel(state){
    return ({waiting_authorization:'等待授权',authorized:'已授权',executing:'执行中',waiting_publish:'等待公网发布',waiting_retest:'等待真实复测',completed:'闭环完成'}[state] || (state ? state : '待生成'));
  }
  function jobLabel(state){
    return ({not_dispatched:'未派发',queued:'排队',running:'执行中',completed:'已完成',failed:'失败',human_required:'待人工'}[state] || state || '—');
  }

  function render(data){
    cache = data || {};
    ensurePanel();
    const phase2 = data?.phase2 || {};
    const plan = data?.plan || {};
    const actions = plan.actions || [];
    const auth = data?.authorization || plan.authorization || {};
    const published = (plan.publish_state || []).filter(x => ['PUBLISHED','SUBMITTED','CRAWLED','INDEXED','RANKED','MENTIONED','CITED','CONVERTED'].includes(x.stage)).length;
    const retested = actions.filter(x => x.retest_evidence_id).length;
    const completedJobs = actions.filter(x => x.job_state === 'completed').length;
    const state = plan.status || '';
    const kpis = [
      ['Phase 2 软件', phase2.code_state === 'closed_candidate' ? '收口候选' : '检查中', (phase2.software_remaining || []).length ? '仅剩实机放量验收' : '无遗留'],
      ['正式 A/B', `${Number(phase2.formal_evidence || 0)} / 50`, '第三阶段唯一正式输入'],
      ['优化动作', `${actions.length}`, plan.decision_source === 'chatgpt_advisory' ? 'ChatGPT分析包' : '缺口候选待授权'],
      ['AI员工完成', `${completedJobs} / ${actions.length || 0}`, '非资金任务'],
      ['公网发布', `${published} / ${actions.length || 0}`, '必须有真实发布状态'],
      ['真实复测', `${retested} / ${actions.filter(x=>x.question_id).length || 0}`, plan.outcome && plan.outcome !== 'pending' ? `结论：${plan.outcome}` : '等待新A/B Evidence'],
    ];
    byId('geo3-kpis').innerHTML = kpis.map(x => `<article><span>${esc(x[0])}</span><strong>${esc(x[1])}</strong><small>${esc(x[2])}</small></article>`).join('');
    const badge = byId('geo3-state');
    badge.textContent = stateLabel(state);
    const publishByAction = Object.fromEntries((plan.publish_state || []).map(x => [x.action_id, x]));
    byId('geo3-action-rows').innerHTML = actions.length ? actions.map(action => {
      const pub = publishByAction[action.action_id] || {};
      const delta = action.delta == null ? '—' : `${Number(action.delta) >= 0 ? '+' : ''}${Number(action.delta)}`;
      const deltaCls = action.delta == null ? 'wait' : Number(action.delta) > 0 ? 'ok' : Number(action.delta) < 0 ? 'bad' : 'wait';
      return `<tr>
        <td><b>${esc(action.gap_label || action.gap_code)}</b><small>${esc(action.title || '')}</small></td>
        <td>${esc(action.question_id || '—')}<small>${esc(action.service || '')}</small></td>
        <td><span class="geo3-pill ${action.job_state === 'completed' ? 'ok' : action.job_state === 'failed' ? 'bad' : 'wait'}">${esc(jobLabel(action.job_state))}</span><small>${esc(action.job_id || '尚未派发')}</small></td>
        <td><span class="geo3-pill ${pub.stage === 'PUBLISHED' || pub.public_url ? 'ok' : 'wait'}">${esc(pub.stage || '等待')}</span><small>${esc(pub.public_url || '必须有真实公网回执')}</small></td>
        <td><span class="geo3-pill ${action.retest_evidence_id ? 'ok' : 'wait'}">${action.retest_evidence_id ? '已复测' : '等待'}</span><small>${esc(action.retest_evidence_id || action.retest_task_id || '发布后自动排入')}</small></td>
        <td><span class="geo3-pill ${deltaCls}">${esc(delta)}</span><small>${action.after_score == null ? `Before ${Number(action.baseline_score || 0)}` : `Before ${Number(action.baseline_score || 0)} → After ${Number(action.after_score || 0)}`}</small></td>
      </tr>`;
    }).join('') : '<tr><td colspan="6" class="geo3-empty">目前没有可执行缺口。先完成真实GEO验证并刷新Phase 2。</td></tr>';

    const planButton = byId('geo3-plan');
    const runButton = byId('geo3-run');
    const refreshButton = byId('geo3-refresh');
    if(planButton) planButton.disabled = actionBusy;
    if(runButton){
      runButton.textContent = auth.command_id ? '执行已获 ChatGPT 授权的优化' : '老板批准并执行本轮优化';
      runButton.disabled = actionBusy || !actions.length || ['executing','waiting_publish','waiting_retest','completed'].includes(state);
    }
    if(refreshButton) refreshButton.disabled = actionBusy;
    byId('geo3-msg').textContent = plan.plan_id ? `计划 ${plan.plan_id} · ${stateLabel(state)} · 授权：${auth.command_id ? 'ChatGPT Command' : plan.authorization_mode === 'owner_explicit' ? '老板明确批准' : '等待'}` : `Phase 2 正式证据 ${Number(phase2.formal_evidence || 0)} 条；有真实缺口后可生成第三阶段计划。`;
  }

  async function load(){
    try{
      const data = await json('/api/r8-19/geo/phase3');
      render(data);
      return data;
    } catch(error){
      ensurePanel();
      if(byId('geo3-msg')) byId('geo3-msg').textContent = `Phase 3 暂不可用：${error.message}`;
      return null;
    }
  }

  async function withBusy(button, work){
    if(actionBusy){
      if(byId('geo3-msg')) byId('geo3-msg').textContent = '已有 GEO Phase 3 操作正在执行，请等待完成。';
      return;
    }
    actionBusy = true;
    const oldText = button?.textContent || '';
    render(cache || {});
    if(button){
      button.disabled = true;
      button.textContent = '处理中…';
      button.setAttribute('aria-busy','true');
    }
    try{
      await work();
    } catch(error){
      if(byId('geo3-msg')) byId('geo3-msg').textContent = error.message;
    } finally {
      actionBusy = false;
      if(button){
        button.removeAttribute('aria-busy');
        button.textContent = oldText;
      }
      await load();
    }
  }

  function bind(){
    const panel = byId('geo-phase3-panel');
    if(!panel || panel.dataset.bound === '1') return;
    panel.dataset.bound = '1';
    byId('geo3-plan')?.addEventListener('click', event => withBusy(event.currentTarget, async () => {
      const data = await post('/api/r8-19/geo/phase3/plan',{force:true});
      render(data.phase3 || await json('/api/r8-19/geo/phase3'));
    }));
    byId('geo3-run')?.addEventListener('click', event => withBusy(event.currentTarget, async () => {
      const ownerApproved = !(cache?.authorization?.command_id || cache?.plan?.authorization?.command_id);
      const data = await post('/api/r8-19/geo/phase3/run',{owner_approved:ownerApproved});
      render(data.phase3 || await json('/api/r8-19/geo/phase3'));
    }));
    byId('geo3-refresh')?.addEventListener('click', event => withBusy(event.currentTarget, load));
  }

  function start(){ ensurePanel(); load(); setInterval(() => { if(!actionBusy) load(); }, 12000); }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true}); else start();
  window.addEventListener('operational:search-updated', () => { ensurePanel(); if(!actionBusy) load(); });
})();

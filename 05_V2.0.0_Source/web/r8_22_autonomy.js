(() => {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let timer = null;

  function installStyle(){
    if(document.getElementById('kz-r8-22-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-r8-22-style';
    style.textContent = `
      .kz22-panel{margin:14px 0 16px;border:1px solid #cfdcf1;border-radius:14px;background:#fff;box-shadow:0 8px 24px rgba(28,64,122,.06);overflow:hidden;font-family:inherit}
      .kz22-head{display:flex;gap:14px;align-items:flex-start;justify-content:space-between;padding:15px 17px;background:linear-gradient(110deg,#102d62,#205cd8);color:#fff}
      .kz22-head small{display:block;opacity:.78;font-size:11px;letter-spacing:.05em}.kz22-head h3{margin:3px 0 4px;font-size:18px}.kz22-head p{margin:0;opacity:.9;font-size:12px;line-height:1.55}
      .kz22-state{white-space:nowrap;border:1px solid rgba(255,255,255,.35);border-radius:999px;padding:6px 9px;font-size:12px;background:rgba(255,255,255,.12)}
      .kz22-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;padding:12px 14px}.kz22-metric{border:1px solid #e2e9f4;border-radius:9px;padding:9px 10px;background:#fbfcff}.kz22-metric span{display:block;color:#6c7c95;font-size:11px}.kz22-metric b{display:block;margin-top:4px;font-size:17px;color:#172a49}.kz22-metric small{display:block;margin-top:2px;color:#8190a7;font-size:10px}
      .kz22-progress{height:6px;margin:0 14px 12px;background:#edf1f7;border-radius:999px;overflow:hidden}.kz22-progress i{display:block;height:100%;background:#2563eb;border-radius:inherit;transition:width .3s ease}
      .kz22-body{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,.75fr);gap:10px;padding:0 14px 14px}.kz22-card{border:1px solid #e2e9f4;border-radius:10px;padding:11px 12px}.kz22-card h4{font-size:12px;margin:0 0 8px;color:#344765}.kz22-events{display:grid;gap:6px;max-height:220px;overflow:auto}.kz22-event{display:grid;grid-template-columns:76px 1fr;gap:8px;font-size:11px;line-height:1.45}.kz22-event time{color:#8390a5}.kz22-event b{font-weight:600;color:#243754}.kz22-empty{font-size:11px;color:#8795aa;padding:8px 0}.kz22-alert{padding:7px 8px;border-radius:7px;font-size:11px;margin:5px 0}.kz22-alert.human{background:#fff3df;color:#94570c}.kz22-alert.defer{background:#f2f5f9;color:#5b6c83}.kz22-truth{margin:0 14px 12px;padding:7px 9px;border-radius:7px;background:#eff6ff;color:#46658d;font-size:10px;line-height:1.5}.kz22-legacy-note{display:block!important;margin:4px 0 8px;padding:5px 8px;border-radius:6px;background:#f4f6f9;color:#6d7b8f;font-size:10px}
      @media(max-width:1000px){.kz22-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.kz22-body{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function host(){
    let panel = document.getElementById('kz-r8-22-autonomy');
    if(panel) return panel;
    panel = document.createElement('section');
    panel.id = 'kz-r8-22-autonomy';
    panel.className = 'kz22-panel';
    const strip = document.getElementById('mission-command-strip');
    if(strip && strip.parentElement){ strip.insertAdjacentElement('afterend', panel); return panel; }
    const main = document.querySelector('main');
    if(main){ main.prepend(panel); return panel; }
    document.body.prepend(panel);
    return panel;
  }

  function markLegacy(){
    document.querySelectorAll('h1,h2,h3').forEach(node => {
      if(!String(node.textContent || '').includes('MISSION CONTROL LEDGER')) return;
      const container = node.closest('section,article,div');
      if(!container || container.querySelector('.kz22-legacy-note')) return;
      const note = document.createElement('small');
      note.className = 'kz22-legacy-note';
      note.textContent = '历史兼容账本：保留审计记录；当前执行权、Mission 和进度请以 R8-22 自治主线为准。';
      node.insertAdjacentElement('afterend', note);
    });
  }

  function eventRows(items){
    if(!Array.isArray(items) || !items.length) return '<div class="kz22-empty">等待当前 Mission 的真实状态变化。</div>';
    return items.slice(0,10).map(item => {
      const at = String(item.at || '').replace('T',' ').slice(11,19) || '--:--:--';
      return `<div class="kz22-event"><time>${esc(at)}</time><b>${esc(item.message || item.kind || '状态更新')}</b></div>`;
    }).join('');
  }

  function alerts(data){
    const human = Array.isArray(data.human_blockers) ? data.human_blockers : [];
    const deferred = Array.isArray(data.deferred_channels) ? data.deferred_channels : [];
    let html = '';
    if(human.length){
      html += human.slice(0,5).map(item => `<div class="kz22-alert human">需老板处理：${esc(item.title || item.reason || item.action || '授权/高风险事项')}</div>`).join('');
    }else{
      html += '<div class="kz22-alert defer">当前没有必须老板介入的事项。</div>';
    }
    if(deferred.length){
      html += `<div class="kz22-alert defer">${deferred.length} 个可选外部渠道已延后，不阻断官网 SEO/GEO 核心闭环。</div>`;
    }
    return html;
  }

  function render(data){
    const panel = host();
    const command = data.command || {};
    const mission = data.mission || {};
    const plan = data.plan || {};
    const progress = data.progress || {};
    const pct = Math.max(0, Math.min(100, Number(progress.percent || 0)));
    const lanes = Array.isArray(plan.lanes) ? plan.lanes : [];
    panel.innerHTML = `
      <div class="kz22-head">
        <div><small>R8-22 · 7×24 AUTONOMOUS CONVERGENCE</small><h3>${esc(mission.title || '等待老板目标')}</h3><p>Command ${esc(command.command_id || '—')} → Mission ${esc(mission.mission_id || '—')} → Plan ${esc(plan.plan_id || '—')}</p></div>
        <span class="kz22-state">${esc(mission.user_state || (command.command_id ? '自动处理中' : '等待目标'))}</span>
      </div>
      <div class="kz22-grid">
        <div class="kz22-metric"><span>当前 Mission</span><b>${command.command_id ? '已接管' : '等待'}</b><small>${esc(mission.priority || '—')}</small></div>
        <div class="kz22-metric"><span>Controller Plan</span><b>${plan.plan_id ? '已自动生成' : '等待'}</b><small>${lanes.length} 条执行泳道</small></div>
        <div class="kz22-metric"><span>任务进度</span><b>${Number(progress.completed||0)} / ${Number(progress.total||0)}</b><small>${pct}%</small></div>
        <div class="kz22-metric"><span>正在执行</span><b>${Number(progress.running||0)}</b><small>${esc(data.current_action || '')}</small></div>
        <div class="kz22-metric"><span>队列</span><b>${Number(progress.queued||0)}</b><small>当前 Mission 优先</small></div>
        <div class="kz22-metric"><span>失败</span><b>${Number(progress.failed||0)}</b><small>真实记录</small></div>
      </div>
      <div class="kz22-progress"><i style="width:${pct}%"></i></div>
      <div class="kz22-body">
        <div class="kz22-card"><h4>实时工作动态 · 最近真实事件</h4><div class="kz22-events">${eventRows(data.events)}</div></div>
        <div class="kz22-card"><h4>老板介入 / 延后渠道</h4>${alerts(data)}<h4 style="margin-top:11px">下一步</h4><div class="kz22-empty">${esc(data.next_action || '系统根据真实 Receipt 自动推进下一轮。')}</div></div>
      </div>
      <div class="kz22-truth">${esc(data.truth_rule || '只认真实 Receipt / Evidence；本地执行不冒充公网发布、搜索收录、排名或正式 GEO 成绩。')}</div>`;
    markLegacy();
  }

  async function refresh(){
    try{
      const response = await fetch('/api/r8-22/autonomy', {cache:'no-store'});
      if(!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
    }catch(error){
      const panel = host();
      panel.innerHTML = `<div class="kz22-head"><div><small>R8-22 · AUTONOMY</small><h3>自治主线状态暂不可读</h3><p>${esc(error.message || error)}</p></div><span class="kz22-state">等待恢复</span></div>`;
    }
  }

  function boot(){
    installStyle();
    refresh();
    if(timer) clearInterval(timer);
    timer = setInterval(refresh, 5000);
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();

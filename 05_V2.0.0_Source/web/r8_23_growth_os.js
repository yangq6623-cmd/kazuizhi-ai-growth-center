(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let timer = null;

  function style(){
    if(document.getElementById('kz-r8-23-style')) return;
    const node = document.createElement('style');
    node.id = 'kz-r8-23-style';
    node.textContent = `
      .kz23{margin:0 0 16px;border:1px solid #d8e1ef;border-radius:12px;background:#fff;overflow:hidden}.kz23-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding:13px 15px;background:#101c33;color:#fff}.kz23-head small{opacity:.7;font-size:10px;letter-spacing:.06em}.kz23-head h3{margin:3px 0;font-size:16px}.kz23-head p{margin:0;font-size:11px;opacity:.84;line-height:1.5}.kz23-tag{border:1px solid rgba(255,255,255,.3);border-radius:999px;padding:5px 8px;font-size:10px;white-space:nowrap}.kz23-body{padding:12px 14px;display:grid;gap:10px}.kz23-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.kz23-card{border:1px solid #e2e8f2;border-radius:9px;padding:10px}.kz23-card h4{margin:0 0 7px;font-size:12px;color:#2d405d}.kz23-engines,.kz23-employees{display:flex;flex-wrap:wrap;gap:6px}.kz23-chip{padding:6px 8px;border-radius:7px;background:#f3f6fb;color:#435771;font-size:10px}.kz23-chip b{display:block;color:#1e3555;font-size:11px;margin-bottom:2px}.kz23-table{width:100%;border-collapse:collapse;font-size:10px}.kz23-table th,.kz23-table td{border-bottom:1px solid #edf1f6;padding:6px;text-align:left;vertical-align:top}.kz23-table th{color:#718098;font-weight:600}.kz23-ready{color:#147451}.kz23-wait{color:#9a651f}.kz23-note{font-size:10px;line-height:1.55;color:#65758d;background:#f6f8fb;border-radius:7px;padding:7px 9px}@media(max-width:1000px){.kz23-row{grid-template-columns:1fr}}
    `;
    document.head.appendChild(node);
  }

  function host(){
    let panel = document.getElementById('kz-r8-23-growth-os');
    if(panel) return panel;
    panel = document.createElement('section');
    panel.id = 'kz-r8-23-growth-os'; panel.className = 'kz23';
    const r22 = document.getElementById('kz-r8-22-autonomy');
    if(r22){ r22.insertAdjacentElement('afterend', panel); return panel; }
    const main = document.querySelector('main'); if(main){ main.prepend(panel); return panel; }
    document.body.prepend(panel); return panel;
  }

  function capabilities(items){
    if(!Array.isArray(items) || !items.length) return '<div class="kz23-note">等待能力状态。</div>';
    return `<table class="kz23-table"><thead><tr><th>能力</th><th>职责/触发</th><th>状态</th><th>实际利用</th></tr></thead><tbody>${items.map(row => {
      const util = row.utilization || {}; const count = Number(util.invoke_count || 0);
      const ready = row.ready === true; const unknown = row.ready == null;
      return `<tr><td><b>${esc(row.name)}</b></td><td>${esc(row.trigger || '')}<br><span>${esc(row.returns_to || '')}</span></td><td class="${ready?'kz23-ready':'kz23-wait'}">${esc(unknown ? row.state || '策略就绪' : ready ? '可用' : row.state || '等待')}</td><td>${count} 次${util.last_invoked_at ? `<br>${esc(String(util.last_invoked_at).replace('T',' ').slice(5,16))}` : ''}${util.last_receipt_id ? `<br>${esc(util.last_receipt_id)}` : ''}</td></tr>`;
    }).join('')}</tbody></table>`;
  }

  function render(data){
    const panel = host();
    const engines = Array.isArray(data.business_engines) ? data.business_engines : [];
    const employees = Array.isArray(data.employees) ? data.employees : [];
    panel.innerHTML = `<div class="kz23-head"><div><small>R8-23 · FINAL 7×24 AUTONOMOUS GROWTH OS</small><h3>ChatGPT 总脑 · 双增长引擎 · 8个AI员工 · 能力按需调用</h3><p>Command ${esc(data.command_id || '—')} · Mission ${esc(data.mission_id || '—')} · Plan ${esc(data.plan_id || '—')}</p></div><span class="kz23-tag">唯一战略总控：ChatGPT</span></div>
      <div class="kz23-body"><div class="kz23-row"><div class="kz23-card"><h4>双增长引擎</h4><div class="kz23-engines">${engines.map(x => `<div class="kz23-chip"><b>${esc(x.name)}</b>${esc((x.outcomes||[]).join(' → '))}</div>`).join('')}</div></div><div class="kz23-card"><h4>8个AI员工</h4><div class="kz23-employees">${employees.map(x => `<div class="kz23-chip"><b>${esc(x.name)}</b>${esc(x.responsibility)}</div>`).join('')}</div></div></div>
      <div class="kz23-card"><h4>能力利用情况 · 连接不等于使用，使用不等于外部成功</h4>${capabilities(data.capabilities)}</div>
      <div class="kz23-note">${esc(data.operating_rule || '')}<br>${esc(data.truth_rule || '')}<br>${esc(data.external_authorization || '')}</div></div>`;
  }

  async function refresh(){
    try{ const response = await fetch('/api/r8-23/growth-os',{cache:'no-store'}); if(!response.ok) throw new Error(`HTTP ${response.status}`); render(await response.json()); }
    catch(error){ host().innerHTML = `<div class="kz23-head"><div><small>R8-23 · GROWTH OS</small><h3>增长操作系统状态暂不可读</h3><p>${esc(error.message || error)}</p></div><span class="kz23-tag">等待恢复</span></div>`; }
  }
  function boot(){ style(); refresh(); if(timer) clearInterval(timer); timer=setInterval(refresh,10000); }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();

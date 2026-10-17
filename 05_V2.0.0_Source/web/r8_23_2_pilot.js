(() => {
  'use strict';

  const API = '/api/r8-23-2/pilot';
  const q = (sel, root=document) => root.querySelector(sel);
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function dashboardRoot() {
    return document.getElementById('dashboard') || q('.page[data-page="dashboard"]');
  }

  function ensureStyle() {
    if (document.getElementById('kz-r8232-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-r8232-style';
    style.textContent = `
      #kz-r8232-pilot{margin:0 0 12px;padding:10px 12px;border:1px solid #dbe4ee;border-radius:8px;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,.04);font-size:12px;color:#334155}
      #kz-r8232-pilot .kz-pilot-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
      #kz-r8232-pilot .kz-pilot-title{font-weight:700;color:#0f172a;font-size:13px;margin-right:4px}
      #kz-r8232-pilot .kz-pill{display:inline-flex;align-items:center;gap:4px;padding:3px 7px;border-radius:4px;background:#f1f5f9;color:#475569;white-space:nowrap}
      #kz-r8232-pilot .kz-ready{background:#ecfdf5;color:#047857}
      #kz-r8232-pilot .kz-degraded{background:#fffbeb;color:#b45309}
      #kz-r8232-pilot .kz-blocked{background:#fef2f2;color:#b91c1c}
      #kz-r8232-pilot .kz-truth{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;max-width:310px;overflow:hidden;text-overflow:ellipsis}
      #kz-r8232-pilot .kz-model{color:#475569}
      #kz-r8232-pilot details{margin-left:auto}
      #kz-r8232-pilot summary{cursor:pointer;color:#2563eb;list-style:none}
      #kz-r8232-pilot .kz-detail{margin-top:8px;padding-top:8px;border-top:1px solid #eef2f7;line-height:1.65}
      body .kz-r8232-advanced-note{font-size:11px;color:#64748b;margin:4px 0 8px}
    `;
    document.head.appendChild(style);
  }

  function ensurePanel() {
    const root = dashboardRoot();
    if (!root) return null;
    let panel = document.getElementById('kz-r8232-pilot');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'kz-r8232-pilot';
      const mission = document.getElementById('mission-command-strip');
      const growth = document.getElementById('kz-r8-23-growth-os');
      if (growth && growth.parentNode === root) root.insertBefore(panel, growth);
      else if (mission && mission.parentNode === root && mission.nextSibling) root.insertBefore(panel, mission.nextSibling);
      else root.prepend(panel);
    }
    return panel;
  }

  function stateClass(state) {
    return state === 'READY' ? 'kz-ready' : state === 'BLOCKED' ? 'kz-blocked' : 'kz-degraded';
  }

  function render(data) {
    const panel = ensurePanel();
    if (!panel) return;
    const readiness = data.readiness || {};
    const truth = data.truth || {};
    const queue = data.queue || {};
    const pack = data.decision_pack || {};
    const release = data.release || {};
    const model = (data.model_routes || {}).geo_gap_analysis || {};
    const conflicts = Array.isArray(truth.conflicts) ? truth.conflicts : [];
    panel.innerHTML = `
      <div class="kz-pilot-row">
        <span class="kz-pilot-title">R8-23.2 Pilot · 运行真值</span>
        <span class="kz-pill ${stateClass(readiness.state)}">自治准备度 ${esc(readiness.state || 'UNKNOWN')}</span>
        <span class="kz-pill kz-truth">Command ${esc(truth.command_id || '未绑定')}</span>
        <span class="kz-pill kz-truth">Mission ${esc(truth.mission_id || '未绑定')}</span>
        <span class="kz-pill ${conflicts.length ? 'kz-blocked' : 'kz-ready'}">单一真值 ${conflicts.length ? '冲突' : '一致'}</span>
        <span class="kz-pill ${queue.timed_out ? 'kz-degraded' : ''}">等待 ${esc(queue.waiting || 0)} · 超时 ${esc(queue.timed_out || 0)}</span>
        <span class="kz-pill ${pack.valid ? 'kz-ready' : 'kz-degraded'}">Decision Pack ${pack.valid ? '有效' : '待刷新'}</span>
        <span class="kz-pill kz-model">本地优先 · SEO/GEO关键节点豆包必经</span>
        <details>
          <summary>查看运行规则</summary>
          <div class="kz-detail">
            <div>版本：${esc(release.phase || 'R8-23.2 Pilot')}；运行身份保持 ${esc(release.runtime_identity || '')}</div>
            <div>ChatGPT：战略总控；本地大模型/RTX3060：高频主执行；豆包：SEO/GEO关键增强与复核。</div>
            <div>真值：配置 ≠ 调用 ≠ 外部成功；正式GEO仍只认真实外部A/B Evidence。</div>
            <div>资金：永久人工处理。24h / 72h / 7天实机验收仍需现场完成。</div>
          </div>
        </details>
      </div>`;
  }

  async function refresh() {
    try {
      const response = await fetch(API, {cache:'no-store'});
      if (!response.ok) throw new Error(String(response.status));
      const raw = await response.json();
      render(raw.data || raw);
    } catch (e) {
      const panel = ensurePanel();
      if (panel) panel.innerHTML = '<div class="kz-pilot-row"><span class="kz-pilot-title">R8-23.2 Pilot · 运行真值</span><span class="kz-pill kz-degraded">状态暂不可读，核心旧链路继续</span></div>';
    }
  }

  function start() {
    ensureStyle();
    refresh();
    window.setInterval(refresh, 15000);
    const observer = new MutationObserver(() => { ensurePanel(); });
    observer.observe(document.documentElement, {subtree:true, childList:true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();

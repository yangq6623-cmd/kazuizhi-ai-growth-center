(() => {
  'use strict';

  async function readJson(path) {
    try {
      const response = await fetch(path, {cache:'no-store', credentials:'same-origin'});
      if (!response.ok) return null;
      return await response.json();
    } catch (_) {
      return null;
    }
  }

  function ensureTransportSummary() {
    const card = document.querySelector('.r810-connector-card');
    if (!card || document.getElementById('kz-local-transport-summary')) return;
    const box = document.createElement('div');
    box.id = 'kz-local-transport-summary';
    box.className = 'r810-local-transport-summary';
    box.innerHTML = `
      <div><small>实时辅助</small><b id="kz-local-main-label">Site Tools 本机直连</b><span id="kz-local-main-state">检查中</span></div>
      <div><small>远程备用</small><b>安全 Relay</b><span>默认不启用</span></div>
    `;
    card.appendChild(box);
  }

  function apply(status) {
    ensureTransportSummary();
    const label = document.getElementById('kz-local-main-state');
    const siteTools = document.documentElement.dataset.kzSiteTools;
    const verified = Boolean(status?.verified);

    if (label) {
      label.textContent = verified ? '已验证实时连接' : (siteTools === 'available' ? '已就绪，等待首次调用' : '当前离线，不影响本地自治');
      label.className = verified ? 'ok' : 'waiting';
    }
  }

  async function refresh() {
    apply(await readJson('/api/kz-local-control/status'));
  }

  function patchAdvancedCopy() {
    const page = document.getElementById('connections');
    if (!page) return;
    const title = page.querySelector('.page-title p');
    if (title) title.textContent = '日常主控使用普通 ChatGPT + 私有异步控制总线；Site Tools 只用于同机实时辅助，Relay 只用于远程备用。';
  }

  const style = document.createElement('style');
  style.textContent = `
    .r810-local-transport-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px;width:100%}
    .r810-local-transport-summary>div{border:1px solid rgba(148,163,184,.22);border-radius:10px;padding:10px 12px;display:grid;gap:3px;background:rgba(15,23,42,.03)}
    .r810-local-transport-summary small{font-size:11px;color:#64748b}.r810-local-transport-summary b{font-size:14px}.r810-local-transport-summary span{font-size:12px;color:#64748b}
    .r810-local-transport-summary span.ok{color:#15803d}.r810-local-transport-summary span.waiting{color:#64748b}
    @media(max-width:760px){.r810-local-transport-summary{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  window.addEventListener('kz-site-tools-ready', refresh);
  window.addEventListener('kz-local-control-changed', refresh);

  const start = () => {
    patchAdvancedCopy();
    refresh();
    setInterval(refresh, 15000);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(start, 350));
  else setTimeout(start, 350);
})();

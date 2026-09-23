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
      <div><small>主连接方式</small><b id="kz-local-main-label">本机直连</b><span id="kz-local-main-state">检查中</span></div>
      <div><small>远程备用</small><b>安全 Relay</b><span>默认不启用</span></div>
    `;
    card.appendChild(box);
  }

  function apply(status) {
    ensureTransportSummary();
    const copy = document.getElementById('r810-connector-copy');
    const label = document.getElementById('kz-local-main-state');
    const siteTools = document.documentElement.dataset.kzSiteTools;
    const verified = Boolean(status?.verified);

    if (label) {
      label.textContent = verified ? '已验证' : (siteTools === 'available' ? '已就绪，等待首次调用' : '等待桌面 Site Tools');
      label.className = verified ? 'ok' : 'waiting';
    }

    if (copy) {
      if (verified) {
        copy.textContent = '本机直连已验证：ChatGPT 可通过当前电脑上的 Site Tools 直接读取状态、创建 Mission、启动内容执行并读取 Receipt；不经过业务服务器。';
      } else if (siteTools === 'available') {
        copy.textContent = '本机直连已就绪：当前页面已经向 ChatGPT 桌面端暴露 Site Tools，等待第一次真实工具调用完成验证。';
      } else {
        copy.textContent = '本机控制接口已就绪。请在 ChatGPT 桌面应用的内置浏览器打开本页；账号支持 Site Tools 时，ChatGPT 可直接调用本机工具，无需公网服务器。';
      }
    }
  }

  async function refresh() {
    apply(await readJson('/api/kz-local-control/status'));
  }

  function patchAdvancedCopy() {
    const page = document.getElementById('connections');
    if (!page) return;
    const title = page.querySelector('.page-title p');
    if (title) title.textContent = '默认使用 ChatGPT 桌面端本机直连；只有需要远程无人值守时才启用安全 Relay。所有状态都必须有真实回执。';
  }

  const style = document.createElement('style');
  style.textContent = `
    .r810-local-transport-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px;width:100%}
    .r810-local-transport-summary>div{border:1px solid rgba(148,163,184,.22);border-radius:10px;padding:10px 12px;display:grid;gap:3px;background:rgba(15,23,42,.03)}
    .r810-local-transport-summary small{font-size:11px;color:#64748b}.r810-local-transport-summary b{font-size:14px}.r810-local-transport-summary span{font-size:12px;color:#64748b}
    .r810-local-transport-summary span.ok{color:#15803d}.r810-local-transport-summary span.waiting{color:#b45309}
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

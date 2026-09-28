(() => {
  'use strict';

  const PAGE_ID = 'content-studio';
  const FRAME_ID = 'content-studio-frame';
  let retryTimer = null;
  let ensureAttempts = 0;

  function installStyle() {
    if (document.getElementById('content-studio-shell-style')) return;
    const style = document.createElement('style');
    style.id = 'content-studio-shell-style';
    style.textContent = `
      #content-studio{padding:0!important;background:#f4f7fb;min-height:calc(100vh - 92px)}
      .content-studio-shell{width:100%;min-width:0;background:#f4f7fb}
      .content-studio-frame{display:block;width:100%;min-height:940px;border:0;background:#f4f7fb}
      .r810-nav-button[data-target="content-studio"] .r810-icon{font-size:12px;font-weight:800}
      @media(max-width:900px){.content-studio-frame{min-height:1080px}}
    `;
    document.head.appendChild(style);
  }

  function ensureLegacyRoute(nav) {
    let proxy = nav.querySelector(`.nav[data-page="${PAGE_ID}"]`);
    if (proxy) return proxy;
    proxy = document.createElement('button');
    proxy.className = 'nav r810-legacy-route';
    proxy.dataset.page = PAGE_ID;
    proxy.dataset.title = '内容情报与参考中心';
    proxy.dataset.subtitle = '导入优秀内容，AI 拆解结构与方法，重构为卡嘴子原创生产方案';
    proxy.hidden = true;
    proxy.textContent = '内容创导';
    nav.appendChild(proxy);
    return proxy;
  }

  function ensurePage(main) {
    let page = document.getElementById(PAGE_ID);
    if (page) return page;
    page = document.createElement('section');
    page.id = PAGE_ID;
    page.className = 'page content-studio-page';
    page.innerHTML = `
      <div class="content-studio-shell" aria-label="卡嘴子 AI 内容创导平台">
        <iframe id="${FRAME_ID}" class="content-studio-frame" title="内容情报与参考中心" src="/operational.html?embedded=1&entry=reference" loading="eager"></iframe>
      </div>`;
    main.appendChild(page);
    const frame = document.getElementById(FRAME_ID);
    frame?.addEventListener('load', () => activateReferenceFrame(0));
    return page;
  }

  function activateReferenceFrame(attempt = 0) {
    const frame = document.getElementById(FRAME_ID);
    if (!frame || !frame.contentWindow) return;
    try {
      const win = frame.contentWindow;
      const referenceReady = !!win.document?.getElementById('reference');
      if (referenceReady && typeof win.changeOperationalPage === 'function') {
        win.changeOperationalPage('reference');
        return;
      }
    } catch (_) {}
    if (attempt < 40) window.setTimeout(() => activateReferenceFrame(attempt + 1), 120);
  }

  function setVisibleNavActive() {
    document.querySelectorAll('.r810-nav-button').forEach(button => {
      button.classList.toggle('active', button.dataset.target === PAGE_ID && button.dataset.action !== 'advanced');
    });
  }

  function openStudio() {
    if (typeof window.openPage === 'function') {
      window.openPage(PAGE_ID);
    } else {
      document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === PAGE_ID));
    }
    setVisibleNavActive();
    activateReferenceFrame(0);
    window.scrollTo({top:0, behavior:'smooth'});
  }

  function ensureOwnerNavigation(nav) {
    const primary = nav.querySelector('.r810-primary-nav');
    if (!primary) return false;
    let button = primary.querySelector(`.r810-nav-button[data-target="${PAGE_ID}"]`);
    if (!button) {
      button = document.createElement('button');
      button.className = 'r810-nav-button';
      button.dataset.target = PAGE_ID;
      button.innerHTML = '<span class="r810-icon">创</span><span>内容创导</span>';
      const decision = primary.querySelector('.r810-nav-button[data-target="workflow"]');
      if (decision) decision.insertAdjacentElement('afterend', button);
      else primary.appendChild(button);
      button.addEventListener('click', openStudio);
    }
    return true;
  }

  function ensure() {
    installStyle();
    const nav = document.querySelector('aside nav');
    const main = document.querySelector('main');
    if (!nav || !main) return false;
    ensureLegacyRoute(nav);
    ensurePage(main);
    const ready = ensureOwnerNavigation(nav);
    if (ready) {
      document.documentElement.dataset.kzContentStudio = 'ready';
      return true;
    }
    return false;
  }

  function converge() {
    if (retryTimer) window.clearTimeout(retryTimer);
    if (ensure()) return;
    ensureAttempts += 1;
    if (ensureAttempts < 40) retryTimer = window.setTimeout(converge, 150);
  }

  window.openKazuizhiContentStudio = openStudio;
  window.addEventListener('kz:app-ready', () => { ensureAttempts = 0; converge(); });
  document.addEventListener('r810:workbench-ready', () => { ensureAttempts = 0; converge(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', converge, {once:true});
  else converge();
  window.setTimeout(converge, 500);
  window.setTimeout(converge, 1600);
})();

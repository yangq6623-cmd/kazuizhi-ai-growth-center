(() => {
  'use strict';

  if (window.__KZ_CONTENT_STUDIO_SHELL_STABLE__) return;
  window.__KZ_CONTENT_STUDIO_SHELL_STABLE__ = true;

  const PAGE_ID = 'content-studio';
  const FRAME_ID = 'content-studio-frame';
  let retryTimer = null;
  let ensureAttempts = 0;

  const ROUTE_COPY = {
    overview:['卡嘴子 AI 内容创导平台','内容情报、参考学习、AI 导演、生产、质检与成片统一协同'],
    intelligence:['内容情报','发现真实用户问题、搜索机会与值得生产的主题'],
    reference:['参考内容','导入优秀内容，AI 拆解结构与方法，重构为卡嘴子原创生产方案'],
    creative:['创意策划','把选题变成可执行创意卡'],
    director:['AI 导演','统一决定节奏、镜头、人物、场景与素材策略'],
    content:['生产工作台','分镜、资产、候选任务与本地生成'],
    assets:['资产中心','人物、数字人、场景、声音与品牌资产'],
    qc:['AI 质检','连续性、字幕、品牌、授权与质量门禁'],
    library:['成片库','版本、比例、成片与真实发布回执'],
  };

  function installStyle() {
    if (document.getElementById('content-studio-shell-style')) return;
    const style = document.createElement('style');
    style.id = 'content-studio-shell-style';
    style.textContent = `
      #content-studio{padding:0!important;background:#f4f7fb;min-height:0!important}
      .content-studio-shell{width:100%;min-width:0;background:#f4f7fb;overflow:hidden;border-radius:8px}
      .content-studio-frame{display:block;width:100%;height:calc(100vh - 205px);min-height:680px;max-height:980px;border:0;background:#f4f7fb;overflow:auto}
      .r810-nav-button[data-target="content-studio"] .r810-icon{font-size:12px;font-weight:800}
      @media(max-width:900px){.content-studio-frame{height:calc(100vh - 180px);min-height:620px}}
    `;
    document.head.appendChild(style);
  }

  function ensureLegacyRoute(nav) {
    let proxy = nav.querySelector(`.nav[data-page="${PAGE_ID}"]`);
    if (!proxy) {
      proxy = document.createElement('button');
      proxy.className = 'nav r810-legacy-route';
      proxy.dataset.page = PAGE_ID;
      proxy.hidden = true;
      proxy.textContent = '内容创导';
      nav.appendChild(proxy);
    }
    proxy.dataset.title = ROUTE_COPY.overview[0];
    proxy.dataset.subtitle = ROUTE_COPY.overview[1];
    return proxy;
  }

  function ensurePage(main) {
    let page = document.getElementById(PAGE_ID);
    if (!page) {
      page = document.createElement('section');
      page.id = PAGE_ID;
      page.className = 'page content-studio-page';
      main.appendChild(page);
    }
    page.classList.add('content-studio-page');
    // The startup coordinator may create a lightweight immediate-response shell
    // before this lazy module arrives. Upgrade that shell in place instead of
    // treating its existence as proof that the real Content Studio is mounted.
    if (!page.querySelector(`#${FRAME_ID}`)) {
      page.innerHTML = `
        <div class="content-studio-shell" aria-label="卡嘴子 AI 内容创导平台">
          <iframe id="${FRAME_ID}" class="content-studio-frame" title="卡嘴子 AI 内容创导平台" src="/content-studio.html?entry=overview" loading="eager" scrolling="auto"></iframe>
        </div>`;
    }
    return page;
  }

  function routeFrame(route='overview') {
    const frame = document.getElementById(FRAME_ID);
    if (!frame?.contentWindow) return;
    try { frame.contentWindow.postMessage({type:'kz-content-studio-route', route}, location.origin); } catch (_) {}
  }

  function setVisibleNavActive() {
    document.querySelectorAll('.r810-nav-button').forEach(button => {
      button.classList.toggle('active', button.dataset.target === PAGE_ID && button.dataset.action !== 'advanced');
    });
  }

  function dedupeBaselines() {
    const items = [...document.querySelectorAll('aside .baseline')];
    items.slice(1).forEach(node => node.remove());
  }

  function syncOuterTitle(route='overview', title='', subtitle='') {
    const copy = ROUTE_COPY[route] || ROUTE_COPY.overview;
    const heading = document.getElementById('page-heading');
    const sub = document.getElementById('page-subtitle');
    if (heading) heading.textContent = title || copy[0];
    if (sub) sub.textContent = subtitle || copy[1];
    const proxy = document.querySelector(`aside nav .nav[data-page="${PAGE_ID}"]`);
    if (proxy) {
      proxy.dataset.title = title || copy[0];
      proxy.dataset.subtitle = subtitle || copy[1];
    }
  }

  function activateOuterPage() {
    const page = document.getElementById(PAGE_ID);
    if (!page) return false;
    try { if (typeof window.openPage === 'function') window.openPage(PAGE_ID); } catch (_) {}
    document.querySelectorAll('main > .page').forEach(node => node.classList.toggle('active', node === page));
    page.hidden = false;
    document.documentElement.dataset.kzActivePage = PAGE_ID;
    setVisibleNavActive();
    return true;
  }

  function openStudio(route='overview') {
    ensure(true);
    activateOuterPage();
    syncOuterTitle(route);
    routeFrame(route);
    // A lazy module or maintenance pass may complete in the same tick as the
    // route click. Re-assert the owner page after the iframe has had a chance
    // to mount so Content Studio can never exist invisibly behind another page.
    [0, 80, 220, 600].forEach(delay => window.setTimeout(() => {
      if (document.querySelector('.r810-nav-button[data-target="content-studio"]')?.classList.contains('active')) {
        activateOuterPage();
      }
    }, delay));
    window.scrollTo({top:0, behavior:'auto'});
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
      if (decision) decision.insertAdjacentElement('afterend', button); else primary.appendChild(button);
    }
    if (button.dataset.kzContentStudioFallbackBound !== '1') {
      button.dataset.kzContentStudioFallbackBound = '1';
      button.addEventListener('click', event => {
        if (event.defaultPrevented) return;
        event.preventDefault();
        openStudio('overview');
      });
    }
    return true;
  }

  function injectEasyFront(doc) {
    if (!doc?.body || doc.querySelector('script[data-kz-easy-front]')) return;
    const easy = doc.createElement('script');
    easy.src = '/content-studio-easy-front.js';
    easy.dataset.kzEasyFront = '1';
    doc.body.appendChild(easy);
  }

  function injectSimpleMode(frame) {
    try {
      const doc = frame.contentDocument;
      if (!doc?.body) return;
      let script = doc.querySelector('script[data-kz-simple-mode]');
      if (!script) {
        script = doc.createElement('script');
        script.src = '/content-studio-simple.js';
        script.dataset.kzSimpleMode = '1';
        script.addEventListener('load', () => injectEasyFront(doc), {once:true});
        doc.body.appendChild(script);
      } else {
        injectEasyFront(doc);
      }
    } catch (_) {}
  }

  function ensure(mountFrame=false) {
    installStyle();
    const nav = document.querySelector('aside nav');
    const main = document.querySelector('main');
    if (!nav || !main) return false;
    dedupeBaselines();
    ensureLegacyRoute(nav);
    const ready = ensureOwnerNavigation(nav);
    if (!ready) return false;

    document.documentElement.dataset.kzContentStudio = 'ready';
    if (!mountFrame) return true;

    const page = ensurePage(main);
    const frame = page?.querySelector(`#${FRAME_ID}`);
    if (frame && !frame.dataset.kzStableBound) {
      frame.dataset.kzStableBound = '1';
      frame.addEventListener('load', () => {
        injectSimpleMode(frame);
        document.documentElement.dataset.kzContentStudioFrame = 'ready';
      });
    }
    if (frame?.contentDocument?.readyState === 'complete') injectSimpleMode(frame);
    window.dispatchEvent(new CustomEvent('kz:content-studio-mounted'));

    if (
      document.documentElement.dataset.kzActivePage === PAGE_ID ||
      nav.querySelector('.r810-nav-button[data-target="content-studio"]')?.classList.contains('active')
    ) activateOuterPage();
    return true;
  }

  function converge() {
    if (retryTimer) window.clearTimeout(retryTimer);
    if (ensure(false)) return;
    ensureAttempts += 1;
    if (ensureAttempts < 24) retryTimer = window.setTimeout(converge, 180);
  }

  window.addEventListener('message', event => {
    if (event.origin !== location.origin) return;
    // Height messages are intentionally ignored. Earlier builds resized the
    // iframe from child Resize/Mutation observers, which could feed back into
    // the child layout and freeze Chrome. The frame now has a stable viewport
    // and scrolls internally instead.
    if (event.data?.type === 'kz-content-studio-route-changed') {
      syncOuterTitle(event.data.route, event.data.title, event.data.subtitle);
      setVisibleNavActive();
    }
  });

  window.openKazuizhiContentStudio = openStudio;
  window.addEventListener('kz:app-ready', () => { ensureAttempts = 0; converge(); });
  document.addEventListener('r810:workbench-ready', () => { ensureAttempts = 0; converge(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', converge, {once:true});
  else converge();
})();
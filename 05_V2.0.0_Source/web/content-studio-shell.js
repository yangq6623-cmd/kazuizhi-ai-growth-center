(() => {
  'use strict';

  const PAGE_ID = 'content-studio';
  const FRAME_ID = 'content-studio-frame';
  let retryTimer = null;
  let ensureAttempts = 0;
  let lastFrameHeight = 0;
  let resizeTimer = null;
  let pendingFrameHeight = 0;

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
      .content-studio-shell{width:100%;min-width:0;background:#f4f7fb;overflow:visible}
      .content-studio-frame{display:block;width:100%;height:620px;min-height:520px;border:0;background:#f4f7fb;overflow:hidden}
      .r810-nav-button[data-target="content-studio"] .r810-icon{font-size:12px;font-weight:800}
      @media(max-width:900px){.content-studio-frame{min-height:620px}}
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
    if (page) return page;
    page = document.createElement('section');
    page.id = PAGE_ID;
    page.className = 'page content-studio-page';
    page.innerHTML = `
      <div class="content-studio-shell" aria-label="卡嘴子 AI 内容创导平台">
        <iframe id="${FRAME_ID}" class="content-studio-frame" title="卡嘴子 AI 内容创导平台" src="/content-studio.html?entry=overview" loading="eager" scrolling="no"></iframe>
      </div>`;
    main.appendChild(page);
    return page;
  }

  function measureSimpleModeHeight(frame) {
    try {
      const doc = frame?.contentDocument;
      if (!doc?.body?.classList.contains('kz-simple-mode')) return 0;
      const simple = doc.getElementById('kz-simple-root');
      if (!simple?.classList.contains('active')) return 0;
      const shell = doc.querySelector('.studio-shell');
      const bodyHeight = Math.max(doc.body.scrollHeight || 0, doc.documentElement?.scrollHeight || 0);
      const simpleHeight = (shell?.offsetHeight || 0) + (simple.scrollHeight || 0) + 44;
      return Math.max(820, bodyHeight, simpleHeight);
    } catch (_) {
      return 0;
    }
  }

  function applyFrameHeight() {
    resizeTimer = null;
    const frame = document.getElementById(FRAME_ID);
    if (!frame) return;
    let target = pendingFrameHeight;
    if (!target) return;
    const simpleHeight = measureSimpleModeHeight(frame);
    if (simpleHeight) target = Math.max(target, simpleHeight);
    target = Math.max(520, Math.min(Math.round(target), 5000));
    const current = lastFrameHeight || Math.round(frame.getBoundingClientRect().height || 0);
    if (current && Math.abs(target - current) < 12) return;
    frame.style.height = `${target}px`;
    lastFrameHeight = target;
  }

  function resizeFrame(height) {
    const frame = document.getElementById(FRAME_ID);
    let raw = Number(height || 0);
    if (!Number.isFinite(raw) || raw <= 0) raw = 520;
    const simpleHeight = measureSimpleModeHeight(frame);
    if (simpleHeight) raw = Math.max(raw, simpleHeight);
    const target = Math.max(520, Math.min(Math.round(raw), 5000));
    if (lastFrameHeight && Math.abs(target - lastFrameHeight) < 12) return;
    pendingFrameHeight = target;
    if (resizeTimer) return;
    resizeTimer = window.setTimeout(applyFrameHeight, 80);
  }

  function forceMeasureFrame(delay=0) {
    window.setTimeout(() => {
      const frame = document.getElementById(FRAME_ID);
      const simpleHeight = measureSimpleModeHeight(frame);
      if (simpleHeight) resizeFrame(simpleHeight);
    }, delay);
  }

  function routeFrame(route = 'overview') {
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

  function openStudio(route = 'overview') {
    if (typeof window.openPage === 'function') {
      window.openPage(PAGE_ID);
    } else {
      document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === PAGE_ID));
    }
    setVisibleNavActive();
    syncOuterTitle(route);
    routeFrame(route);
    forceMeasureFrame(120);
    forceMeasureFrame(420);
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
      if (decision) decision.insertAdjacentElement('afterend', button);
      else primary.appendChild(button);
      button.addEventListener('click', () => openStudio('overview'));
    }
    return true;
  }

  function injectB2BPolish(doc) {
    if (!doc?.head || doc.querySelector('link[data-kz-b2b-polish]')) return;
    const link = doc.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/content-studio-b2b-polish.css';
    link.dataset.kzB2bPolish = '1';
    link.addEventListener('load', () => {
      forceMeasureFrame(60);
      forceMeasureFrame(220);
    }, {once:true});
    doc.head.appendChild(link);
  }

  function injectEasyFront(doc) {
    if (!doc?.body || doc.querySelector('script[data-kz-easy-front]')) return;
    injectB2BPolish(doc);
    const easy = doc.createElement('script');
    easy.src = '/content-studio-easy-front.js';
    easy.dataset.kzEasyFront = '1';
    easy.addEventListener('load', () => {
      forceMeasureFrame(80);
      forceMeasureFrame(320);
      forceMeasureFrame(700);
    }, {once:true});
    doc.body.appendChild(easy);
  }

  function injectSimpleMode(frame) {
    try {
      const doc = frame.contentDocument;
      if (!doc || !doc.body) return;
      injectB2BPolish(doc);
      let script = doc.querySelector('script[data-kz-simple-mode]');
      if (!script) {
        script = doc.createElement('script');
        script.src = '/content-studio-simple.js';
        script.dataset.kzSimpleMode = '1';
        script.addEventListener('load', () => {
          injectEasyFront(doc);
          forceMeasureFrame(100);
          forceMeasureFrame(400);
        }, {once:true});
        doc.body.appendChild(script);
      }
      injectEasyFront(doc);
      forceMeasureFrame(120);
    } catch (_) {}
  }

  function ensure() {
    installStyle();
    const nav = document.querySelector('aside nav');
    const main = document.querySelector('main');
    if (!nav || !main) return false;
    dedupeBaselines();
    ensureLegacyRoute(nav);
    const page = ensurePage(main);
    const frame = page?.querySelector(`#${FRAME_ID}`);
    if (frame && !frame.dataset.kzStableResize) {
      frame.dataset.kzStableResize = '1';
      frame.addEventListener('load', () => {
        lastFrameHeight = Math.round(frame.getBoundingClientRect().height || 620);
        injectSimpleMode(frame);
        forceMeasureFrame(180);
        forceMeasureFrame(600);
      });
    }
    if (frame?.contentDocument?.readyState === 'complete') {
      injectSimpleMode(frame);
      forceMeasureFrame(160);
    }
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

  window.addEventListener('message', event => {
    if (event.origin !== location.origin) return;
    if (event.data?.type === 'kz-content-studio-height') resizeFrame(event.data.height);
    if (event.data?.type === 'kz-content-studio-route-changed') {
      syncOuterTitle(event.data.route, event.data.title, event.data.subtitle);
      setVisibleNavActive();
      forceMeasureFrame(100);
      forceMeasureFrame(360);
    }
  });

  window.openKazuizhiContentStudio = openStudio;
  window.addEventListener('kz:app-ready', () => { ensureAttempts = 0; converge(); });
  document.addEventListener('r810:workbench-ready', () => { ensureAttempts = 0; converge(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', converge, {once:true});
  else converge();
  window.setTimeout(converge, 500);
  window.setTimeout(converge, 1600);
})();
(() => {
  'use strict';

  // #481 field hotfix: the owner execution tabs were visually present but the
  // parent shell silently no-op'd when #operational-frame was absent or the
  // embedded runtime had not exposed changeOperationalPage yet.  Keep one
  // authoritative embedded operational surface and make every tab routable.
  const PAGES = new Set(['dashboard','content','search','accounts','device','conversion','health']);
  const FRAME_ID = 'operational-frame';
  const FRAME_SRC = '/operational.html?embedded=1';

  function notify(message, kind='error') {
    if (typeof window.toast === 'function') {
      window.toast(message, kind === 'error' ? 'error' : undefined);
      return;
    }
    let node = document.getElementById('r811-execution-route-status');
    const hub = document.getElementById('operational-hub');
    if (!node && hub) {
      node = document.createElement('div');
      node.id = 'r811-execution-route-status';
      node.style.cssText = 'margin:10px 0;padding:10px 12px;border-radius:9px;background:#fff4e4;color:#9b641a;font-size:11px;';
      hub.querySelector('.operational-hub-intro')?.insertAdjacentElement('afterend', node);
    }
    if (node) node.textContent = message;
  }

  function setActiveButton(page, button) {
    document.querySelectorAll('.r810-execution-tabs [data-execution-page]').forEach(item => {
      item.classList.toggle('active', item === button || item.dataset.executionPage === page && !button);
    });
  }

  function showExecutionHub() {
    if (typeof window.openPage === 'function') {
      window.openPage('operational-hub');
      return;
    }
    document.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node.id === 'operational-hub'));
  }

  function ensureFrame() {
    const hub = document.getElementById('operational-hub');
    if (!hub) return null;
    let frame = document.getElementById(FRAME_ID);
    if (!frame) {
      frame = document.createElement('iframe');
      frame.id = FRAME_ID;
      frame.src = FRAME_SRC;
      frame.title = '卡嘴子 AI 执行中心';
      frame.loading = 'eager';
      frame.setAttribute('scrolling', 'no');
      frame.style.cssText = 'display:block;width:100%;min-height:720px;border:0;background:transparent;';
      const intro = hub.querySelector('.operational-hub-intro');
      if (intro) intro.insertAdjacentElement('afterend', frame);
      else hub.appendChild(frame);
    } else if (!String(frame.getAttribute('src') || '').includes('operational.html')) {
      frame.src = FRAME_SRC;
    }
    return frame;
  }

  function makeFrameAuthoritative(frame) {
    const hub = document.getElementById('operational-hub');
    if (!hub || !frame) return;
    [...hub.children].forEach(child => {
      if (child === frame || child.classList?.contains('operational-hub-intro') || child.id === 'r811-execution-route-status') return;
      child.hidden = true;
    });
    frame.hidden = false;
  }

  function routeInsideFrame(frame, page) {
    try {
      const win = frame?.contentWindow;
      const doc = frame?.contentDocument;
      if (!win || !doc) return false;
      if (typeof win.changeOperationalPage === 'function') {
        win.changeOperationalPage(page);
        return true;
      }
      const nav = doc.querySelector(`.nav[data-page="${page}"]`);
      if (nav) {
        nav.click();
        return true;
      }
      const target = doc.getElementById(page);
      if (target) {
        doc.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node === target));
        return true;
      }
    } catch (_) {
      return false;
    }
    return false;
  }

  function route(page, button) {
    if (!PAGES.has(page)) return;
    showExecutionHub();
    setActiveButton(page, button);
    const frame = ensureFrame();
    if (!frame) {
      notify('执行中心容器未初始化，请刷新后重试。');
      return;
    }
    makeFrameAuthoritative(frame);

    let attempts = 0;
    const apply = () => {
      attempts += 1;
      if (routeInsideFrame(frame, page)) {
        makeFrameAuthoritative(frame);
        const status = document.getElementById('r811-execution-route-status');
        if (status) status.remove();
        return;
      }
      if (attempts < 30) {
        window.setTimeout(apply, 100);
        return;
      }
      notify(`执行中心“${button?.textContent?.trim() || page}”未能完成页面切换，请安装最新 Candidate 后重试。`);
    };

    if (frame.contentDocument?.readyState === 'complete') apply();
    else {
      frame.addEventListener('load', apply, {once:true});
      window.setTimeout(apply, 120);
    }
  }

  // Capture phase deliberately runs before the original #481 bubble handler,
  // preventing its silent optional-chaining no-op from swallowing owner clicks.
  document.addEventListener('click', event => {
    const button = event.target.closest?.('.r810-execution-tabs [data-execution-page]');
    if (!button) return;
    const page = String(button.dataset.executionPage || '').trim();
    if (!PAGES.has(page)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    route(page, button);
  }, true);

  // If the unified shell already shows execution center at boot, prepare the
  // embedded runtime without changing the selected page.
  function boot() {
    if (!document.getElementById('operational-hub')) return;
    const active = document.querySelector('.r810-execution-tabs button.active[data-execution-page]');
    if (active) route(String(active.dataset.executionPage || 'dashboard'), active);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 0), {once:true});
  else setTimeout(boot, 0);
})();

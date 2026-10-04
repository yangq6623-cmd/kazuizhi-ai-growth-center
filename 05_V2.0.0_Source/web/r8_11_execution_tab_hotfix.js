(() => {
  'use strict';

  // R8-12.2 owner execution routing.
  // The retired legacy account page is no longer an owner destination. Account
  // identity/authorization/device management is exclusively owned by the
  // R8-12 Unified Account Asset Center.
  const PAGES = new Set(['dashboard','content','accounts','search','device','conversion','health']);
  const FRAME_ID = 'operational-frame';
  const FRAME_SRC = '/operational.html?embedded=1';

  function notify(message) {
    if (typeof window.toast === 'function') return window.toast(message, 'error');
    console.warn(message);
  }

  function setActiveButton(page, button) {
    document.querySelectorAll('.r810-execution-tabs [data-execution-page]').forEach(item => {
      item.classList.toggle('active', item === button || (item.dataset.executionPage === page && !button));
    });
  }

  function showExecutionHub() {
    if (typeof window.openPage === 'function') return window.openPage('operational-hub');
    document.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node.id === 'operational-hub'));
  }

  function ensureFrame() {
    const hub = document.getElementById('operational-hub');
    if (!hub) return null;
    // app.js already owns the execution iframe.  Older R8-11 compatibility
    // code created a second iframe beside it, which rendered two identical
    // execution overviews.  Reuse the canonical frame instead.
    let frame = document.getElementById(FRAME_ID) || hub.querySelector('iframe.operational-hub-frame');
    if (frame) {
      frame.id = FRAME_ID;
      // The execution board is the first screen of this workbench.  It must
      // not remain blank merely because the parent page created it below a
      // lazy-loading threshold.
      frame.loading = 'eager';
    }
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
    }
    return frame;
  }

  function verifyFrameReady(frame) {
    window.setTimeout(() => {
      try {
        const ready = frame?.contentDocument?.querySelector('#execution-overview, .workspace-nav');
        if (!ready && frame && !frame.dataset.r811RecoveryReloaded) {
          frame.dataset.r811RecoveryReloaded = 'true';
          frame.src = FRAME_SRC;
        }
      } catch (_) {}
    }, 1800);
  }

  function retireLegacyAccountSurface(frame) {
    try {
      const doc = frame?.contentDocument;
      const win = frame?.contentWindow;
      if (!doc || !win) return;
      // The accounts route is now the PC QR account center embedded directly
      // inside operational.html.  Keep the route visible; hiding #accounts
      // before the replacement center loads was the source of a blank page.
      if (!win.__KZ_R812_ACCOUNT_RETIRE_GUARD__) {
        const original = typeof win.changeOperationalPage === 'function' ? win.changeOperationalPage.bind(win) : null;
        if (original) {
          win.changeOperationalPage = page => {
            return original(page);
          };
        }
        win.__KZ_R812_ACCOUNT_RETIRE_GUARD__ = true;
      }
    } catch (_) {}
  }

  function makeFrameAuthoritative(frame) {
    const hub = document.getElementById('operational-hub');
    if (!hub || !frame) return;
    // There must be exactly one embedded execution workbench.  Remove a
    // stale compatibility frame rather than merely hiding it, because older
    // CSS may force an iframe back into the layout after a refresh.
    hub.querySelectorAll('iframe').forEach(candidate => {
      if (candidate !== frame) candidate.remove();
    });
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
      retireLegacyAccountSurface(frame);
      if (typeof win.changeOperationalPage === 'function') {
        win.changeOperationalPage(page);
        return true;
      }
      const nav = doc.querySelector(`.nav[data-page="${page}"]`);
      if (nav) { nav.click(); return true; }
      const target = doc.getElementById(page);
      if (target) {
        doc.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node === target));
        return true;
      }
    } catch (_) { return false; }
    return false;
  }

  function route(page, button) {
    if (!PAGES.has(page)) return;
    if (page !== 'accounts') window.KZR812AccountCenter?.close?.();
    showExecutionHub();
    setActiveButton(page, button);
    const frame = ensureFrame();
    if (!frame) return notify('执行中心容器未初始化，请刷新后重试。');
    makeFrameAuthoritative(frame);

    let attempts = 0;
    const apply = () => {
      attempts += 1;
      retireLegacyAccountSurface(frame);
      if (routeInsideFrame(frame, page)) return makeFrameAuthoritative(frame);
      if (attempts < 30) return window.setTimeout(apply, 100);
      notify(`执行中心“${button?.textContent?.trim() || page}”未能完成页面切换。`);
    };
    if (frame.contentDocument?.readyState === 'complete') apply();
    else frame.addEventListener('load', apply, {once:true});
  }

  document.addEventListener('click', event => {
    const button = event.target.closest?.('.r810-execution-tabs [data-execution-page]');
    if (!button) return;
    const page = String(button.dataset.executionPage || '').trim();
    if (page !== 'accounts' && !PAGES.has(page)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    route(page, button);
  }, true);

  function boot() {
    const frame = ensureFrame();
    if (!frame) return;
    const patch = () => {
      retireLegacyAccountSurface(frame);
      verifyFrameReady(frame);
    };
    frame.addEventListener('load', patch);
    window.setTimeout(patch, 250);
    verifyFrameReady(frame);
    const active = document.querySelector('.r810-execution-tabs button.active[data-execution-page]');
    if (active) route(String(active.dataset.executionPage || 'dashboard'), active);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 0), {once:true});
  else setTimeout(boot, 0);
})();

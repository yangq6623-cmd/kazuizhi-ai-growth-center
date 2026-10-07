(() => {
  'use strict';

  // This is intentionally a very small, first-paint route handler.  The
  // SEO/GEO workspace itself remains lazy, but a click must never be held up
  // by an unrelated owner-shell module or silently disappear during startup.
  if (window.__KZ_R813_ROUTE_BOOTSTRAP__) return;
  window.__KZ_R813_ROUTE_BOOTSTRAP__ = true;

  const TARGET = 'r813-seo-geo';
  const SCRIPT = '/r8_13_seo_geo_bridge.js';
  let pending = null;

  function setLoading(button, active) {
    if (!button) return;
    button.toggleAttribute('aria-busy', active);
    // Keep the navigation item clickable.  A disabled button looked like a
    // broken route and could remain visually grey while a cold-start request
    // was recovering.  The shared pending promise already deduplicates clicks.
    button.dataset.kzSeoGeoLoading = active ? '1' : '';
    button.title = active ? '正在打开 SEO/GEO 工作区…' : '';
  }

  function showFailure(message) {
    const feedback = document.getElementById('action-feedback');
    if (feedback) {
      feedback.hidden = false;
      feedback.dataset.kzSeoGeoRouteError = '1';
      feedback.textContent = message;
      feedback.className = 'action-feedback error';
    }
    if (typeof window.toast === 'function') window.toast(message, 'error');
  }

  function clearFailure() {
    const feedback = document.getElementById('action-feedback');
    if (feedback?.dataset.kzSeoGeoRouteError === '1') {
      feedback.hidden = true;
      feedback.textContent = '';
      delete feedback.dataset.kzSeoGeoRouteError;
    }
  }

  async function fallbackLoadBridge() {
    if (window.__KZ_R813_SEO_GEO_BRIDGE__ && !window.KZR813SeoGeoBridge) {
      delete window.__KZ_R813_SEO_GEO_BRIDGE__;
    }
    let lastError = null;
    for (let attempt = 1; attempt <= 2; attempt += 1) {
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), 30000);
      try {
        const response = await fetch(`${SCRIPT}?route_recovery=${Date.now()}-${attempt}`, {cache:'no-store', signal:controller.signal});
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const source = await response.text();
        const tag = document.createElement('script');
        tag.dataset.r813SeoGeoFallback = '1';
        tag.textContent = `${source}\n//# sourceURL=${SCRIPT}`;
        document.body.appendChild(tag);
        if (!window.KZR813SeoGeoBridge?.open) throw new Error('SEO/GEO 工作区未完成初始化');
        window.KZClearStartupModuleFailure?.(SCRIPT, 'route_recovery');
        return window.KZR813SeoGeoBridge;
      } catch (error) {
        lastError = error?.name === 'AbortError' ? new Error('SEO/GEO 工作区加载超时') : error;
        if (attempt < 2) await new Promise(resolve => window.setTimeout(resolve, 500));
      } finally {
        window.clearTimeout(timer);
      }
    }
    throw lastError || new Error('SEO/GEO 工作区加载失败');
  }

  function loadBridge() {
    if (window.KZR813SeoGeoBridge?.open) {
      window.KZClearStartupModuleFailure?.(SCRIPT, 'route_already_ready');
      return Promise.resolve(window.KZR813SeoGeoBridge);
    }
    if (pending) return pending;
    pending = (async () => {
      // The startup coordinator is the single owner of lazy workspace scripts.
      // Reusing it avoids the old route bootstrap racing a second <script src>
      // request against the local server.
      if (typeof window.KZLoadOwnerWorkspace === 'function') {
        const ready = await window.KZLoadOwnerWorkspace('seo_geo');
        if (ready && window.KZR813SeoGeoBridge?.open) return window.KZR813SeoGeoBridge;
      }
      return fallbackLoadBridge();
    })().finally(() => { pending = null; });
    return pending;
  }

  async function open(button) {
    setLoading(button, true);
    try {
      const bridge = await loadBridge();
      bridge.open();
      clearFailure();
    } catch (error) {
      showFailure(`SEO/GEO 增长中心未打开：${error?.message || '未知错误'}。请在“系统状态与连接”查看详情。`);
    } finally {
      setLoading(button, false);
    }
  }

  // Cold-start capture remains, but script ownership is delegated to the
  // startup coordinator whenever it is available.
  document.addEventListener('click', event => {
    const button = event.target?.closest?.(`.r810-nav-button[data-target="${TARGET}"]`);
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    open(button);
  }, true);
})();

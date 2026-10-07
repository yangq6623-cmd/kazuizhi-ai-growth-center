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
    button.disabled = active;
    button.dataset.kzSeoGeoLoading = active ? '1' : '';
    button.title = active ? '正在打开 SEO/GEO 工作区…' : '';
  }

  function showFailure(message) {
    const feedback = document.getElementById('action-feedback');
    if (feedback) {
      feedback.hidden = false;
      feedback.textContent = message;
      feedback.className = 'action-feedback error';
    }
    if (typeof window.toast === 'function') window.toast(message, 'error');
  }

  async function fallbackLoadBridge() {
    if (window.__KZ_R813_SEO_GEO_BRIDGE__ && !window.KZR813SeoGeoBridge) {
      delete window.__KZ_R813_SEO_GEO_BRIDGE__;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(SCRIPT, {cache:'no-store', signal:controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const source = await response.text();
      const tag = document.createElement('script');
      tag.dataset.r813SeoGeoFallback = '1';
      tag.textContent = `${source}\n//# sourceURL=${SCRIPT}`;
      document.body.appendChild(tag);
      if (!window.KZR813SeoGeoBridge?.open) throw new Error('SEO/GEO 工作区未完成初始化');
      return window.KZR813SeoGeoBridge;
    } catch (error) {
      if (error?.name === 'AbortError') throw new Error('SEO/GEO 工作区加载超时');
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function loadBridge() {
    if (window.KZR813SeoGeoBridge?.open) return Promise.resolve(window.KZR813SeoGeoBridge);
    if (pending) return pending;
    pending = (async () => {
      // The startup coordinator is the single owner of lazy workspace scripts.
      // Reusing it avoids the old route bootstrap racing a second <script src>
      // request against the local server.
      if (typeof window.KZLoadOwnerWorkspace === 'function') {
        await window.KZLoadOwnerWorkspace('seo_geo');
        if (window.KZR813SeoGeoBridge?.open) return window.KZR813SeoGeoBridge;
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

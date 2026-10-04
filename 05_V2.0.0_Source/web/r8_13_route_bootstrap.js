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

  function loadBridge() {
    if (window.KZR813SeoGeoBridge?.open) return Promise.resolve(window.KZR813SeoGeoBridge);
    if (pending) return pending;
    pending = new Promise((resolve, reject) => {
      // A previously interrupted legacy load can leave only its guard flag.
      // Clear that incomplete state before loading this known-good bridge.
      if (window.__KZ_R813_SEO_GEO_BRIDGE__ && !window.KZR813SeoGeoBridge) {
        delete window.__KZ_R813_SEO_GEO_BRIDGE__;
      }
      const tag = document.createElement('script');
      const timer = window.setTimeout(() => reject(new Error('SEO/GEO 工作区加载超时')), 5000);
      tag.src = `${SCRIPT}?route=${Date.now()}`;
      tag.async = true;
      tag.onload = () => {
        window.clearTimeout(timer);
        if (window.KZR813SeoGeoBridge?.open) resolve(window.KZR813SeoGeoBridge);
        else reject(new Error('SEO/GEO 工作区未完成初始化'));
      };
      tag.onerror = () => {
        window.clearTimeout(timer);
        reject(new Error('SEO/GEO 工作区脚本未能加载'));
      };
      document.head.appendChild(tag);
    }).finally(() => { pending = null; });
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

  // Capture before the asynchronous startup coordinator registers its lazy
  // listener.  This makes the first click deterministic even on a cold start.
  document.addEventListener('click', event => {
    const button = event.target?.closest?.(`.r810-nav-button[data-target="${TARGET}"]`);
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    open(button);
  }, true);
})();

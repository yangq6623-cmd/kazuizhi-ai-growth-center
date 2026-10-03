(() => {
  'use strict';
  if (window.__KZ_R8235_FULL_RECOVERY__) return;
  window.__KZ_R8235_FULL_RECOVERY__ = true;

  const $ = (sel, root=document) => root.querySelector(sel);
  const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));

  function openSeoGeo(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
      if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation();
    }
    const bridge = window.KZR813SeoGeoBridge;
    if (bridge && typeof bridge.open === 'function') {
      bridge.open();
      return;
    }
    const target = $('#r813-seo-geo, #seo-geo-growth, [data-r813-seo-geo-root]');
    if (target) {
      $$('.page.active').forEach(node => node.classList.remove('active'));
      target.classList.add('active');
      target.hidden = false;
      target.scrollIntoView({block:'start'});
    }
  }

  function bindSeoGeoRoutes() {
    const selectors = [
      'button.nav[data-page="r813-seo-geo"]',
      '.r810-primary-nav [data-target="r813-seo-geo"]',
      '[data-kz-route-role="seo-geo"]'
    ];
    const buttons = selectors.flatMap(sel => $$(sel));
    buttons.forEach(button => {
      button.hidden = false;
      if (button.dataset.kzR8235SeoBound === '1') return;
      button.dataset.kzR8235SeoBound = '1';
      button.addEventListener('click', openSeoGeo, {capture:true});
    });
  }

  function normalizeBaseline() {
    const info = window.KZ_BUILD_INFO || {};
    const baseline = $('.baseline');
    if (!baseline) return;
    const run = String(info.runNumber || '').replace(/^__.*__$/, '');
    const commit = String(info.commit || '').replace(/^__.*__$/, '');
    baseline.innerHTML = `<b>R8-23.5 Full Regression Recovery${run ? ` · #${run}` : ''}</b><br><span>保留后续升级 · SEO/GEO恢复 · 运行链恢复</span>${commit ? `<code>${commit.slice(0,8)}</code>` : ''}`;
  }

  function exposeOwnerCockpit() {
    const dashboard = $('#dashboard');
    const cockpit = $('#kz-r8-23-growth-os');
    if (dashboard && cockpit && cockpit.parentElement !== dashboard) dashboard.prepend(cockpit);
    if (cockpit) cockpit.hidden = false;
  }

  function verifyContracts() {
    bindSeoGeoRoutes();
    normalizeBaseline();
    exposeOwnerCockpit();
    document.documentElement.dataset.kzR8235Recovery = 'ready';
  }

  function boot() {
    verifyContracts();
    [250, 750, 1500, 3000, 6000].forEach(ms => setTimeout(verifyContracts, ms));
    setInterval(verifyContracts, 15000);
    window.addEventListener('kz:app-ready', verifyContracts);
    window.addEventListener('r810:workbench-ready', verifyContracts);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();

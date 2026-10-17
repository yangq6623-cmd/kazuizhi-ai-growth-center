(() => {
  'use strict';
  if (window.__KZ_R819_GEO_LIVE_GATE__) return;
  window.__KZ_R819_GEO_LIVE_GATE__ = true;

  async function json(path, options) {
    const response = await fetch(path, {cache: 'no-store', ...(options || {})});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `GEO 服务返回 ${response.status}`);
    return data;
  }

  async function preflight() {
    const state = await json('/api/r8-19/geo/preflight');
    const browser = state.browser || {};
    const local = state.local_precheck || {};
    const api = state.api || {};
    return {
      ...state,
      browser_ready: browser.ready === true,
      local_ready: local.ready === true,
      api_ready: api.ready === true,
      api_required: false,
      truth_rule: '浏览器真实外部AI可形成A级Evidence；本地模型固定为C级辅助；API是可选加速通道。',
    };
  }

  function decorate() {
    const browserOne = document.getElementById('geo-browser-one');
    const browserTen = document.getElementById('geo-browser-ten');
    const localOne = document.getElementById('geo-local-one');
    const apiRound = document.getElementById('geo-run-round');
    if (browserOne) browserOne.dataset.geoSafeBrowser = '1';
    if (browserTen) browserTen.dataset.geoSafeBrowser = '10';
    if (localOne) localOne.dataset.geoLocalPrecheck = '1';
    if (apiRound) {
      apiRound.dataset.geoOptionalApi = 'true';
      apiRound.title = 'API不是必须项；未配置时继续使用网页真实验证。';
    }
    return Boolean(browserOne || browserTen || apiRound);
  }

  window.KZR819GeoLiveGate = {preflight, decorate};

  function install() {
    if (decorate()) return;
    setTimeout(install, 120);
  }

  install();
  window.addEventListener('kz:app-ready', install);
  window.addEventListener('r810:workbench-ready', install);
})();

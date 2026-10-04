(() => {
  'use strict';

  if (window.__KZ_R812_STARTUP_COORDINATOR__) return;
  window.__KZ_R812_STARTUP_COORDINATOR__ = {
    phase: 'booting',
    started_at: new Date().toISOString(),
    ready_at: null,
    loaded: [],
    failed_modules: [],
    degraded: false,
    heartbeat: 0,
    last_heartbeat_at: null,
    current_module: '',
    lazy_loaded: [],
  };

  const state = window.__KZ_R812_STARTUP_COORDINATOR__;
  // Cold starts share the local Python server with SEO/GEO evidence loading.
  // 4.5 seconds was shorter than a healthy first SEO/GEO request, so two
  // owner-shell scripts could be falsely reported as missing. Keep startup
  // bounded, but give the local server one realistic response window.
  const SCRIPT_TIMEOUT_MS = 12000;
  const SCRIPT_RETRY_DELAY_MS = 350;

  // Keep first paint deliberately small.  The previous startup loaded every
  // iframe-backed workspace before the dashboard became usable.  On Chrome
  // that meant Content Studio + Execution + SEO/GEO could all initialise at
  // once and starve the renderer.  Only lightweight owner-shell modules are
  // allowed in the critical path; heavy workspaces are loaded on first use.
  const SCRIPT_SEQUENCE = [
    ['/r7_manager_patch.js', 'r7ManagerPatch'],
    ['/r8_10_workbench.js', 'r810Workbench'],
    ['/r8_10_truth_convergence.js', 'r810TruthConvergence'],
    ['/r8_11_backbone_ui.js', 'r811Backbone'],
    ['/r8_12_account_center_bridge.js', 'r812AccountCenter'],
    ['/r8_15_ui_truth_patch.js', 'r815UiTruth'],
  ];

  const LAZY_SEQUENCE = {
    execution: [
      ['/r8_11_execution_tab_hotfix.js', 'r811ExecutionTabHotfix'],
    ],
    seo_geo: [
      ['/r8_13_seo_geo_bridge.js', 'r813SeoGeo'],
    ],
    content_studio: [
      ['/content-studio-shell.js', 'contentStudioShell'],
      ['/content-pipeline-host.js', 'contentPipelineHost'],
    ],
    connections: [
      ['/kz_site_tools.js', 'kzSiteTools'],
      ['/kz_local_direct_ui.js', 'kzLocalDirectUi'],
      ['/kz_async_control_ui.js', 'kzAsyncControlUi'],
    ],
  };

  const GENERATED_ID_PREFIXES = ['r8-', 'r810-', 'r811-', 'r812-', 'r813-', 'kz-'];
  const lazyPromises = new Map();

  function emit(name, detail = {}) {
    window.dispatchEvent(new CustomEvent(name, {detail}));
    document.dispatchEvent(new CustomEvent(name, {detail}));
  }

  async function yieldToBrowser(delay = 60) {
    await new Promise(resolve => {
      const finish = () => window.setTimeout(resolve, delay);
      if (typeof window.requestAnimationFrame === 'function') window.requestAnimationFrame(finish);
      else finish();
    });
  }

  function waitForWindowLoad() {
    if (document.readyState === 'complete') return Promise.resolve();
    return new Promise(resolve => window.addEventListener('load', resolve, {once:true}));
  }

  function waitForBaseShell(timeoutMs = 3500) {
    const started = Date.now();
    return new Promise(resolve => {
      const probe = () => {
        const dashboard = document.getElementById('dashboard');
        const nav = document.querySelector('aside nav');
        const serviceText = document.getElementById('service-text')?.textContent || '';
        const baseReady = Boolean(dashboard && nav && !serviceText.includes('正在连接本地服务'));
        if (baseReady || Date.now() - started >= timeoutMs) return resolve();
        window.setTimeout(probe, 80);
      };
      probe();
    });
  }

  function scriptSelector(datasetKey) {
    return `script[data-${datasetKey.replace(/[A-Z]/g, m => '-' + m.toLowerCase())}]`;
  }

  function findExistingScript(src, datasetKey) {
    return document.querySelector(scriptSelector(datasetKey)) || [...document.scripts].find(node => {
      try { return new URL(node.src, location.href).pathname === src; } catch { return false; }
    });
  }

  function loadScript(src, datasetKey, force = false) {
    const existing = findExistingScript(src, datasetKey);
    if (!force && existing && existing.dataset.kzLoadFailed !== '1') {
      state.loaded.push({src, reused:true});
      return Promise.resolve(existing);
    }
    if (existing?.dataset.kzLoadFailed === '1') existing.remove();

    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      let settled = false;
      state.current_module = src;
      document.documentElement.dataset.kzStartupCurrentModule = src;
      console.info('[KZ startup] loading', src);
      const finish = (ok, error) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        if (ok) {
          script.dataset.kzLoadReady = '1';
          state.loaded.push({src, reused:false});
          console.info('[KZ startup] loaded', src);
          resolve(script);
        } else {
          script.dataset.kzLoadFailed = '1';
          reject(error || new Error(`启动模块加载失败：${src}`));
        }
      };
      const timer = window.setTimeout(
        () => finish(false, new Error(`启动模块加载超时：${src}`)),
        SCRIPT_TIMEOUT_MS,
      );
      script.src = src;
      script.async = false;
      script.dataset[datasetKey] = '1';
      script.onload = () => finish(true);
      script.onerror = () => finish(false, new Error(`启动模块加载失败：${src}`));
      document.body.appendChild(script);
    });
  }

  async function loadScriptFailSoft(src, key) {
    try {
      await loadScript(src, key);
      return true;
    } catch (error) {
      // A cold local server can be busy completing its first evidence query.
      // Retry once before declaring a UI module degraded; loadScript removes
      // the failed tag before inserting the replacement script.
      try {
        await yieldToBrowser(SCRIPT_RETRY_DELAY_MS);
        await loadScript(src, key);
        return true;
      } catch (retryError) {
        error = retryError;
      }
      const failure = {src, error: String(error?.message || error), at: new Date().toISOString()};
      state.failed_modules.push(failure);
      state.degraded = true;
      console.error('Owner-shell module degraded, continuing startup', failure);
      emit('kz:startup-module-failed', failure);
      return false;
    }
  }

  async function loadLazyBundle(name) {
    if (lazyPromises.has(name)) return lazyPromises.get(name);
    const sequence = LAZY_SEQUENCE[name] || [];
    const promise = (async () => {
      document.documentElement.dataset.kzLazyWorkspace = name;
      for (const [src, key] of sequence) {
        await loadScriptFailSoft(src, key);
        await yieldToBrowser(70);
      }
      if (!state.lazy_loaded.includes(name)) state.lazy_loaded.push(name);
      emit('kz:lazy-workspace-ready', {name});
      return true;
    })();
    lazyPromises.set(name, promise);
    return promise;
  }

  async function ensureSeoGeoBridge() {
    if (window.KZR813SeoGeoBridge?.open) return true;
    // A script tag can exist in the HTML while a previous cold start was
    // interrupted before it executed.  Do one cache-busting recovery load
    // rather than leaving the SEO/GEO navigation button apparently inert.
    try {
      await loadScript(`/r8_13_seo_geo_bridge.js?recovery=${Date.now()}`, 'r813SeoGeoRecovery', true);
    } catch (error) {
      console.warn('SEO/GEO workspace recovery load failed', error);
    }
    return Boolean(window.KZR813SeoGeoBridge?.open);
  }

  function dedupeGeneratedSingletons() {
    const seen = new Set();
    document.querySelectorAll('[id]').forEach(node => {
      const id = String(node.id || '');
      if (!GENERATED_ID_PREFIXES.some(prefix => id.startsWith(prefix))) return;
      if (seen.has(id)) node.remove();
      else seen.add(id);
    });
  }

  function forceInitialDashboardOnce() {
    if (document.documentElement.dataset.kzInitialRouteLocked === '1') return;
    document.documentElement.dataset.kzInitialRouteLocked = '1';
    try {
      if (typeof window.openPage === 'function') window.openPage('dashboard');
      else {
        document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === 'dashboard'));
        document.querySelectorAll('aside nav .nav').forEach(button => button.classList.toggle('active', button.dataset.page === 'dashboard'));
      }
    } catch (error) {
      console.warn('initial dashboard route failed', error);
    }
  }

  function ensureLazyNavButton(target, label, icon, beforeTarget = '') {
    const primary = document.querySelector('.r810-primary-nav');
    if (!primary) return null;
    let button = primary.querySelector(`.r810-nav-button[data-target="${target}"]`);
    if (button) return button;
    button = document.createElement('button');
    button.className = 'r810-nav-button';
    button.dataset.target = target;
    button.dataset.kzLazyRoute = '1';
    button.innerHTML = `<span class="r810-icon">${icon}</span><span>${label}</span>`;
    const before = beforeTarget ? primary.querySelector(`.r810-nav-button[data-target="${beforeTarget}"]`) : null;
    if (before) primary.insertBefore(button, before); else primary.appendChild(button);
    return button;
  }

  function installLazyWorkspaceRoutes() {
    ensureLazyNavButton('content-studio', '内容创导', '创', 'operational-hub');
    ensureLazyNavButton('r813-seo-geo', 'SEO/GEO增长', '搜', 'r810-evolution');

    if (window.__KZ_R812_LAZY_ROUTE_CAPTURE__) return;
    window.__KZ_R812_LAZY_ROUTE_CAPTURE__ = true;
    window.addEventListener('click', async event => {
      const button = event.target?.closest?.('.r810-nav-button[data-target]');
      if (!button) return;
      const target = String(button.dataset.target || '');
      let bundle = '';
      if (target === 'content-studio') bundle = 'content_studio';
      else if (target === 'r813-seo-geo') bundle = 'seo_geo';
      else if (target === 'operational-hub') bundle = 'execution';
      else if (target === 'connections') bundle = 'connections';
      if (!bundle) return;

      event.preventDefault();
      event.stopImmediatePropagation();
      button.disabled = true;
      button.dataset.kzLoading = '1';
      try {
        await loadLazyBundle(bundle);
        if (target === 'content-studio') window.openKazuizhiContentStudio?.('overview');
        else if (target === 'r813-seo-geo') {
          const ready = await ensureSeoGeoBridge();
          if (ready) window.KZR813SeoGeoBridge.open();
          else {
            button.title = 'SEO/GEO 工作区仍在加载，请稍候后重试';
            console.error('SEO/GEO workspace did not become ready after recovery load');
          }
        }
        else if (target === 'operational-hub') {
          if (typeof window.openPage === 'function') window.openPage('operational-hub');
          else document.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node.id === 'operational-hub'));
        } else if (target === 'connections') {
          if (typeof window.openPage === 'function') window.openPage('connections');
        }
      } finally {
        button.disabled = false;
        delete button.dataset.kzLoading;
      }
    }, true);
  }

  function resolvedBuildValue(value, fallback = '') {
    const text = String(value || '').trim();
    return !text || /^__.+__$/.test(text) ? fallback : text;
  }

  function applyReleaseIdentity() {
    const build = window.KZ_BUILD_INFO || {};
    const phase = resolvedBuildValue(build.phase, 'R8-19');
    const runNumber = resolvedBuildValue(build.runNumber);
    const commit = resolvedBuildValue(build.commit);
    const branch = resolvedBuildValue(build.branch);
    const displayVersion = resolvedBuildValue(build.displayVersion, 'V2.2.2 Autonomous Mission Core');
    const runtimeBuild = resolvedBuildValue(build.runtimeBuild, 'KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922');
    const runLabel = runNumber ? `#${runNumber}` : '本地源码';
    const baseline = document.querySelector('.baseline');
    if (baseline) {
      baseline.replaceChildren();
      const title = document.createElement('b'); title.textContent = `${phase} · ${runLabel}`;
      const br = document.createElement('br');
      const subtitle = document.createElement('span'); subtitle.textContent = '自治运营 · 真实执行 · 真实回执';
      const code = document.createElement('code'); code.textContent = `${displayVersion}${commit ? ` · ${commit}` : ''}`;
      baseline.append(title, br, subtitle, code);
      baseline.title = [runtimeBuild, branch ? `branch: ${branch}` : '', commit ? `commit: ${commit}` : ''].filter(Boolean).join('\n');
    }
    document.title = `卡嘴子 AI 自治运营工作台 · ${phase}${runNumber ? ` · #${runNumber}` : ''}`;
    const meta = document.querySelector('meta[name="kazuizhi-build"]');
    if (meta) meta.setAttribute('content', runtimeBuild);
    document.documentElement.dataset.kzReleasePhase = phase;
    document.documentElement.dataset.kzReleaseRun = runNumber || 'local';
  }

  function refreshTodayLabel() {
    const label = document.getElementById('today-label');
    if (!label) return;
    label.textContent = new Intl.DateTimeFormat('zh-CN', {month:'long', day:'numeric', weekday:'short'}).format(new Date());
  }

  function convergeVisibleReleaseTruth() { applyReleaseIdentity(); refreshTodayLabel(); }

  function installReleaseTruthRefresh() {
    if (window.__KZ_R815_RELEASE_TRUTH_REFRESH__) return;
    window.__KZ_R815_RELEASE_TRUTH_REFRESH__ = true;
    convergeVisibleReleaseTruth();
    window.setInterval(convergeVisibleReleaseTruth, 60000);
    window.addEventListener('focus', convergeVisibleReleaseTruth);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) convergeVisibleReleaseTruth(); });
    document.addEventListener('r810:workbench-ready', convergeVisibleReleaseTruth);
    document.addEventListener('kz:app-ready', convergeVisibleReleaseTruth);
  }

  function installHeartbeat() {
    if (window.__KZ_OWNER_HEARTBEAT_TIMER__) return;
    const beat = () => {
      state.heartbeat += 1;
      state.last_heartbeat_at = Date.now();
      document.documentElement.dataset.kzHeartbeat = String(state.heartbeat);
    };
    beat();
    window.__KZ_OWNER_HEARTBEAT_TIMER__ = window.setInterval(beat, 250);
  }

  function exposeStartupStatus() {
    document.documentElement.dataset.kzStartupPhase = state.phase;
    document.documentElement.dataset.kzStartupDegraded = state.degraded ? '1' : '0';
    document.documentElement.dataset.kzStartupFailures = String(state.failed_modules.length);
    document.documentElement.dataset.kzStartupCurrentModule = state.current_module || '';
  }

  async function boot() {
    state.phase = 'waiting_base';
    exposeStartupStatus();
    installHeartbeat();
    await waitForWindowLoad();
    await waitForBaseShell();
    installReleaseTruthRefresh();
    emit('kz:startup-base-ready');

    state.phase = 'loading_owner_shell';
    exposeStartupStatus();
    try {
      for (const [src, key] of SCRIPT_SEQUENCE) {
        state.current_module = src;
        exposeStartupStatus();
        const loaded = await loadScriptFailSoft(src, key);
        await yieldToBrowser(src === '/r7_manager_patch.js' ? 90 : 55);
        if (src === '/r8_10_workbench.js' && loaded) {
          emit('r810:workbench-ready');
          await yieldToBrowser(100);
        }
      }
      state.current_module = '';
      await yieldToBrowser(120);
      dedupeGeneratedSingletons();
      installLazyWorkspaceRoutes();
      forceInitialDashboardOnce();
      convergeVisibleReleaseTruth();
      state.phase = state.failed_modules.length ? 'degraded' : 'ready';
      state.ready_at = new Date().toISOString();
      exposeStartupStatus();
      emit('kz:app-ready', {
        loaded: state.loaded.slice(),
        failed_modules: state.failed_modules.slice(),
        degraded: state.degraded,
      });
      if (state.failed_modules.length && typeof window.toast === 'function') {
        window.toast(`部分模块未加载（${state.failed_modules.length}），主界面已继续启动；可在系统检查中查看详情。`, 'warning');
      }
    } catch (error) {
      state.phase = 'failed';
      state.error = String(error?.message || error);
      exposeStartupStatus();
      console.error('R8-12 startup coordinator fatal failure', error);
      if (typeof window.toast === 'function') window.toast(`启动协调器异常：${state.error}`, 'error');
    }
  }

  window.KZLoadOwnerWorkspace = loadLazyBundle;
  boot();
})();

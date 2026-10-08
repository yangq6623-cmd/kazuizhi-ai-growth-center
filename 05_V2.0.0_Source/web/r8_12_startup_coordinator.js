(() => {
  'use strict';

  if (window.__KZ_R812_STARTUP_COORDINATOR__) return;
  window.__KZ_R812_STARTUP_COORDINATOR__ = {
    phase: 'booting',
    started_at: new Date().toISOString(),
    ready_at: null,
    loaded: [],
    failed_modules: [],
    recovered_modules: [],
    degraded: false,
    retrying_failures: false,
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
    ['/r8_persistence_patch.js', 'r8PersistencePatch'],
    ['/main-productization.js', 'mainProductization'],
    ['/autonomous-ops.js', 'autonomousOps'],
    ['/r8_10_workbench.js', 'r810Workbench'],
    ['/r8_12_account_center_bridge.js', 'r812AccountCenter'],
  ];

  // Real #674 installs proved that the SEO/GEO bridge, truth convergence and
  // backbone are not first-paint dependencies: when the local service is busy,
  // fetching all three in the critical owner-shell path can create false
  // "module missing" alarms even though the main console is already usable.
  // Keep the critical path small and load these optional surfaces only after
  // the owner shell is visibly ready. An early SEO/GEO click still has its
  // dedicated route-recovery path.
  const POST_READY_SEQUENCE = [
    ['/r8_10_truth_convergence.js', 'r810TruthConvergence'],
    ['/r8_11_backbone_ui.js', 'r811Backbone'],
    ['/r8_15_ui_truth_patch.js', 'r815UiTruth'],
  ];
  const POST_READY_DELAY_MS = 5000;
  const POST_READY_TIMEOUT_MS = 45000;

  const LAZY_SEQUENCE = {
    decision: [
      ['/decision_center.js', 'r7DecisionCenter'],
      ['/decision_layout_patch.js', 'r7DecisionLayout'],
      ['/region_strategy.js', 'r7RegionStrategy'],
    ],
    execution: [
      ['/r8_11_execution_tab_hotfix.js', 'r811ExecutionTabHotfix'],
    ],
    // Keep SEO/GEO lazy, but make the first click execute prefetched source.
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
  const sourceCache = new Map();
  const sourcePromises = new Map();

  function canonicalSourceKey(src) {
    try { return new URL(src, location.href).pathname; } catch { return String(src || ''); }
  }

  async function fetchScriptSource(src, timeoutMs = SCRIPT_TIMEOUT_MS, force = false) {
    const key = canonicalSourceKey(src);
    if (!force && sourceCache.has(key)) return sourceCache.get(key);
    if (!force && sourcePromises.has(key)) return sourcePromises.get(key);
    const promise = (async () => {
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(src, {cache:'no-store', signal:controller.signal});
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const source = await response.text();
        if (!force) sourceCache.set(key, source);
        return source;
      } finally {
        window.clearTimeout(timer);
      }
    })();
    if (!force) sourcePromises.set(key, promise);
    try {
      return await promise;
    } finally {
      if (!force) sourcePromises.delete(key);
    }
  }

  function primeScriptSources(sequence, timeoutMs = SCRIPT_TIMEOUT_MS) {
    sequence.forEach(([src]) => {
      fetchScriptSource(src, timeoutMs, false).catch(error => {
        console.debug('[KZ startup] source prefetch deferred', src, error?.message || error);
      });
    });
  }

  function prefetchWorkspaceDocuments() {
    for (const href of ['/r8_13_seo_geo.html?embed=1', '/geo.html?embed=1']) {
      const absolute = new URL(href, location.href).href;
      if ([...document.querySelectorAll('link[rel="prefetch"]')].some(node => node.href === absolute)) continue;
      const link = document.createElement('link');
      link.rel = 'prefetch';
      link.as = 'document';
      link.href = href;
      document.head.appendChild(link);
    }
  }

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

  async function loadScript(src, datasetKey, force = false, timeoutMs = SCRIPT_TIMEOUT_MS) {
    const existing = findExistingScript(src, datasetKey);
    if (!force && existing && existing.dataset.kzLoadFailed !== '1') {
      state.loaded.push({src, reused:true});
      return existing;
    }
    if (existing) existing.remove();

    state.current_module = src;
    document.documentElement.dataset.kzStartupCurrentModule = src;
    console.info('[KZ startup] loading', src);

    try {
      const source = await fetchScriptSource(src, timeoutMs, force);
      const script = document.createElement('script');
      script.dataset[datasetKey] = '1';
      script.dataset.kzLoadReady = '1';
      script.dataset.kzSource = src;
      script.textContent = `${source}\n//# sourceURL=${src}`;
      document.body.appendChild(script);
      state.loaded.push({src, reused:false});
      console.info('[KZ startup] loaded', src);
      return script;
    } catch (error) {
      const message = error?.name === 'AbortError'
        ? `启动模块加载超时：${src}`
        : `启动模块加载失败：${src} · ${error?.message || error}`;
      throw new Error(message);
    }
  }

  function rememberFailure(src, error) {
    const message = String(error?.message || error || 'unknown startup error');
    let failure = state.failed_modules.find(row => row.src === src);
    if (!failure) {
      failure = {src, error: message, at: new Date().toISOString(), attempts: 1};
      state.failed_modules.push(failure);
    } else {
      failure.error = message;
      failure.at = new Date().toISOString();
      failure.attempts = Number(failure.attempts || 0) + 1;
    }
    state.degraded = true;
    exposeStartupStatus();
    renderStartupDiagnostics();
    console.error('Owner-shell module degraded, continuing startup', failure);
    emit('kz:startup-module-failed', {...failure});
    return failure;
  }

  function clearFailure(src, recoveredBy = 'auto_retry') {
    const index = state.failed_modules.findIndex(row => row.src === src);
    if (index < 0) return false;
    const [failure] = state.failed_modules.splice(index, 1);
    state.recovered_modules.unshift({
      ...failure,
      recovered_at: new Date().toISOString(),
      recovered_by: recoveredBy,
    });
    state.recovered_modules = state.recovered_modules.slice(0, 12);
    state.degraded = state.failed_modules.length > 0;
    exposeStartupStatus();
    renderStartupDiagnostics();
    emit('kz:startup-module-recovered', {src, recovered_by: recoveredBy});
    return true;
  }

  async function loadScriptFailSoft(src, key) {
    try {
      await loadScript(src, key);
      clearFailure(src, 'normal_load');
      return true;
    } catch (error) {
      // A cold local server can be busy completing its first evidence query.
      // Retry once before declaring a UI module degraded; loadScript removes
      // the failed tag before inserting the replacement script.
      try {
        await yieldToBrowser(SCRIPT_RETRY_DELAY_MS);
        await loadScript(src, key);
        clearFailure(src, 'startup_retry');
        return true;
      } catch (retryError) {
        error = retryError;
      }
      rememberFailure(src, error);
      return false;
    }
  }

  async function loadLazyBundle(name) {
    if (lazyPromises.has(name)) return lazyPromises.get(name);
    const sequence = LAZY_SEQUENCE[name] || [];
    const promise = (async () => {
      document.documentElement.dataset.kzLazyWorkspace = name;
      let complete = true;
      for (const [src, key] of sequence) {
        const loaded = await loadScriptFailSoft(src, key);
        complete = Boolean(loaded) && complete;
        await yieldToBrowser(70);
      }
      if (!complete) return false;
      if (!state.lazy_loaded.includes(name)) state.lazy_loaded.push(name);
      emit('kz:lazy-workspace-ready', {name});
      return true;
    })();
    lazyPromises.set(name, promise);
    promise.then(ok => { if (!ok) lazyPromises.delete(name); }, () => lazyPromises.delete(name));
    return promise;
  }

  async function ensureSeoGeoBridge() {
    if (window.KZR813SeoGeoBridge?.open) return true;
    // A script tag can exist in the HTML while a previous cold start was
    // interrupted before it executed.  Do one cache-busting recovery load
    // rather than leaving the SEO/GEO navigation button apparently inert.
    try {
      await loadScript(`/r8_13_seo_geo_bridge.js?recovery=${Date.now()}`, 'r813SeoGeoRecovery', true, 30000);
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

  function installInitialRouteOwnership() {
    if (window.__KZ_SINGLE_HOME_ROUTE_OWNER__) return;
    window.__KZ_SINGLE_HOME_ROUTE_OWNER__ = true;
    document.documentElement.dataset.kzHomeOwner = 'dashboard';
    document.addEventListener('click', event => {
      if (!event.isTrusted) return;
      const route = event.target?.closest?.('.r810-nav-button[data-target],.go-page[data-target],.nav[data-page]');
      if (route) document.documentElement.dataset.kzInitialRouteUserChosen = '1';
    }, true);
  }

  function lockInitialDashboardOnce() {
    if (document.documentElement.dataset.kzInitialRouteLocked === '1') return;
    document.documentElement.dataset.kzInitialRouteLocked = '1';
    if (document.documentElement.dataset.kzInitialRouteUserChosen === '1') return;
    try {
      const dashboard = document.getElementById('dashboard');
      const pages = [...document.querySelectorAll('main > .page')];
      if (dashboard) pages.forEach(page => page.classList.toggle('active', page === dashboard));
      document.querySelectorAll('.r810-nav-button[data-target]').forEach(button => {
        button.classList.toggle('active', button.dataset.target === 'dashboard' && button.dataset.action !== 'advanced');
      });
      document.querySelectorAll('aside nav .nav[data-page]').forEach(button => {
        button.classList.toggle('active', button.dataset.page === 'dashboard');
      });
      document.documentElement.dataset.kzActivePage = 'dashboard';
    } catch (error) {
      console.warn('single homepage lock failed', error);
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

  function ensureImmediateLazyPage(target) {
    const main = document.querySelector('main');
    const nav = document.querySelector('aside nav');
    if (!main || !nav) return null;
    let page = document.getElementById(target);
    const copy = {
      'content-studio': ['卡嘴子 AI 内容创导平台', '内容情报、策划、导演、生产、质检与成片统一协同'],
      'operational-hub': ['执行中心', '增长战役、内容生产、发布准备、搜索增长与经营结果'],
    }[target];
    if (!copy) return page;
    if (!page) {
      page = document.createElement('section');
      page.id = target;
      page.className = 'page';
      if (target === 'content-studio') {
        page.innerHTML = '<div class="r812-lazy-route-loading"><b>正在打开内容创导…</b><span>首次进入会加载内容生产工作区，页面已响应，不需要重复点击。</span></div>';
      } else {
        page.classList.add('operational-hub-page');
        page.innerHTML = '<iframe id="operational-frame" class="operational-hub-frame" title="R8 内容生产与发布闭环" src="/operational.html?embedded=1" loading="eager"></iframe>';
      }
      main.appendChild(page);
    }
    let proxy = nav.querySelector(`.nav[data-page="${target}"]`);
    if (!proxy) {
      proxy = document.createElement('button');
      proxy.className = 'nav r810-legacy-route';
      proxy.dataset.page = target;
      proxy.hidden = true;
      nav.appendChild(proxy);
    }
    proxy.dataset.title = copy[0];
    proxy.dataset.subtitle = copy[1];
    return page;
  }

  function activateOwnerPage(target) {
    const page = document.getElementById(target);
    if (!page) return false;
    try { if (typeof window.openPage === 'function') window.openPage(target); } catch (_) {}
    document.querySelectorAll('main > .page').forEach(node => node.classList.toggle('active', node === page));
    document.documentElement.dataset.kzActivePage = target;
    document.querySelectorAll('.r810-nav-button[data-target]').forEach(button => {
      button.classList.toggle('active', button.dataset.target === target && button.dataset.action !== 'advanced');
    });
    return true;
  }

  function showImmediateLazyTarget(target) {
    if (target === 'content-studio' || target === 'operational-hub') ensureImmediateLazyPage(target);
    if (['workflow','content-studio','operational-hub','connections'].includes(target)) {
      activateOwnerPage(target);
      [90, 260].forEach(delay => window.setTimeout(() => {
        const button = document.querySelector(`.r810-nav-button[data-target="${target}"]`);
        if (button?.getAttribute('aria-busy') === 'true' || button?.classList.contains('active')) activateOwnerPage(target);
      }, delay));
    }
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
      if (target === 'workflow') bundle = 'decision';
      else if (target === 'content-studio') bundle = 'content_studio';
      else if (target === 'r813-seo-geo') bundle = 'seo_geo';
      else if (target === 'operational-hub') bundle = 'execution';
      else if (target === 'connections') bundle = 'connections';
      if (!bundle) return;

      event.preventDefault();
      event.stopImmediatePropagation();
      // #700 owner-route contract: the click must visibly change the page
      // immediately. Heavy lazy modules may load afterwards, but a user should
      // never see an apparently dead Content Studio / Execution button.
      showImmediateLazyTarget(target);
      button.setAttribute('aria-busy','true');
      button.dataset.kzLoading = '1';
      try {
        const bundleReady = await loadLazyBundle(bundle);
        if (!bundleReady && target !== 'r813-seo-geo') {
          button.title = '工作区模块暂未就绪，页面会保留并可再次点击重试';
          const feedback = document.getElementById('action-feedback');
          if (feedback) {
            feedback.hidden = false;
            feedback.className = 'action-feedback error';
            feedback.textContent = '工作区模块暂未加载完成；主界面已响应，请再次点击重试。';
          }
          return;
        }
        if (target === 'workflow') {
          activateOwnerPage('workflow');
        } else if (target === 'content-studio') {
          window.openKazuizhiContentStudio?.('overview');
          activateOwnerPage('content-studio');
        }
        else if (target === 'r813-seo-geo') {
          const ready = await ensureSeoGeoBridge();
          if (ready) window.KZR813SeoGeoBridge.open();
          else {
            button.title = 'SEO/GEO 工作区仍在加载，请稍候后重试';
            console.error('SEO/GEO workspace did not become ready after recovery load');
          }
        }
        else if (target === 'operational-hub') {
          activateOwnerPage('operational-hub');
        } else if (target === 'connections') {
          activateOwnerPage('connections');
        }
      } finally {
        button.removeAttribute('aria-busy');
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

  function renderStartupDiagnostics() {
    const page = document.getElementById('connections');
    if (!page) return;
    let card = document.getElementById('r812-startup-diagnostics');
    if (!card) {
      card = document.createElement('article');
      card.id = 'r812-startup-diagnostics';
      card.className = 'wide';
      const title = page.querySelector('.page-title');
      if (title?.nextSibling) page.insertBefore(card, title.nextSibling);
      else page.prepend(card);
    }
    card.replaceChildren();
    const head = document.createElement('div');
    head.className = 'article-head';
    const titleWrap = document.createElement('div');
    const label = document.createElement('label');
    label.textContent = '启动模块诊断';
    const heading = document.createElement('h3');
    heading.textContent = state.failed_modules.length
      ? `未恢复模块 ${state.failed_modules.length} 个`
      : '启动模块全部正常';
    titleWrap.append(label, heading);
    const retry = document.createElement('button');
    retry.id = 'r812-retry-startup-modules';
    retry.className = 'primary-small';
    retry.textContent = state.retrying_failures ? '正在重试…' : '重试失败模块';
    retry.disabled = state.retrying_failures || !state.failed_modules.length;
    retry.addEventListener('click', () => retryFailedModules('manual'));
    head.append(titleWrap, retry);
    card.appendChild(head);

    const note = document.createElement('p');
    note.className = 'subtle';
    note.textContent = `启动阶段：${state.phase} · 当前未恢复 ${state.failed_modules.length} · 本次已自动恢复 ${state.recovered_modules.length}。这里显示真实文件名和浏览器收到的失败原因，不隐藏错误。`;
    card.appendChild(note);

    const list = document.createElement('div');
    list.className = 'diagnostic-list';
    const rows = [
      ...state.failed_modules.map(row => ({...row, status:'未恢复'})),
      ...state.recovered_modules.map(row => ({...row, status:'已恢复'})),
    ];
    if (!rows.length) {
      const empty = document.createElement('div');
      empty.className = 'friendly-empty';
      empty.textContent = '0 个启动模块异常。';
      list.appendChild(empty);
    } else {
      rows.forEach(row => {
        const item = document.createElement('div');
        item.className = 'diagnostic-item';
        const name = document.createElement('b');
        name.textContent = `${row.status} · ${row.src}`;
        const detail = document.createElement('p');
        detail.textContent = row.status === '已恢复'
          ? `原失败原因：${row.error}；恢复时间：${row.recovered_at || '—'}；恢复方式：${row.recovered_by || '—'}`
          : `失败原因：${row.error}；最近失败：${row.at || '—'}；尝试次数：${row.attempts || 1}`;
        item.append(name, detail);
        list.appendChild(item);
      });
    }
    card.appendChild(list);
  }

  function exposeStartupStatus() {
    document.documentElement.dataset.kzStartupPhase = state.phase;
    document.documentElement.dataset.kzStartupDegraded = state.degraded ? '1' : '0';
    document.documentElement.dataset.kzStartupFailures = String(state.failed_modules.length);
    document.documentElement.dataset.kzStartupCurrentModule = state.current_module || '';
  }

  async function retryFailedModules(reason = 'auto') {
    if (state.retrying_failures || !state.failed_modules.length) {
      renderStartupDiagnostics();
      return state.failed_modules.length === 0;
    }
    state.retrying_failures = true;
    renderStartupDiagnostics();
    const pending = state.failed_modules.map(row => ({...row}));
    for (const failure of pending) {
      const tuple = [...SCRIPT_SEQUENCE, ...POST_READY_SEQUENCE].find(([src]) => src === failure.src);
      if (!tuple) continue;
      const [src, key] = tuple;
      try {
        await loadScript(src, key, false, 30000);
        clearFailure(src, reason);
      } catch (error) {
        const current = state.failed_modules.find(row => row.src === src);
        if (current) {
          current.error = String(error?.message || error);
          current.at = new Date().toISOString();
          current.attempts = Number(current.attempts || 0) + 1;
        }
        await yieldToBrowser(250);
      }
    }
    state.retrying_failures = false;
    state.degraded = state.failed_modules.length > 0;
    if (state.phase === 'degraded' && !state.degraded) state.phase = 'ready';
    exposeStartupStatus();
    renderStartupDiagnostics();
    if (!state.failed_modules.length && typeof window.toast === 'function') {
      window.toast(`启动模块已自动恢复：本次恢复 ${state.recovered_modules.length} 个。`, 'success');
    }
    return state.failed_modules.length === 0;
  }

  async function loadPostReadyModules() {
    for (const [src, key] of POST_READY_SEQUENCE) {
      let loaded = false;
      let lastError = null;
      for (let attempt = 1; attempt <= 3 && !loaded; attempt += 1) {
        try {
          await loadScript(src, key, false, POST_READY_TIMEOUT_MS);
          clearFailure(src, `post_ready_${attempt}`);
          loaded = true;
        } catch (error) {
          lastError = error;
          if (attempt < 3) await yieldToBrowser(attempt * 1200);
        }
      }
      if (!loaded) {
        rememberFailure(src, lastError || new Error(`post-ready module failed: ${src}`));
        if (typeof window.toast === 'function') {
          window.toast(`后台界面增强模块未加载：${src.split('/').pop()}。系统状态页可查看真实原因并重试。`, 'warning');
        }
      }
    }
    state.degraded = state.failed_modules.length > 0;
    if (state.phase === 'degraded' && !state.degraded) state.phase = 'ready';
    exposeStartupStatus();
    renderStartupDiagnostics();
  }

  async function boot() {
    state.phase = 'waiting_base';
    exposeStartupStatus();
    installHeartbeat();
    installInitialRouteOwnership();
    await waitForWindowLoad();
    await waitForBaseShell();
    lockInitialDashboardOnce();
    installReleaseTruthRefresh();
    emit('kz:startup-base-ready');

    state.phase = 'loading_owner_shell';
    exposeStartupStatus();
    primeScriptSources([
      ...SCRIPT_SEQUENCE,
      ...LAZY_SEQUENCE.seo_geo,
      ...POST_READY_SEQUENCE,
    ], SCRIPT_TIMEOUT_MS);
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
      // Do not route again here. A late openPage('dashboard') caused visible
      // homepage jumps after owner modules finished mounting.
      convergeVisibleReleaseTruth();
      state.phase = state.failed_modules.length ? 'degraded' : 'ready';
      state.ready_at = new Date().toISOString();
      exposeStartupStatus();
      emit('kz:app-ready', {
        loaded: state.loaded.slice(),
        failed_modules: state.failed_modules.slice(),
        degraded: state.degraded,
      });
      renderStartupDiagnostics();
      if (state.failed_modules.length && typeof window.toast === 'function') {
        const names = state.failed_modules.map(row => row.src.split('/').pop()).join('、');
        window.toast(`部分模块未加载（${state.failed_modules.length}）：${names}。系统将自动重试；系统状态页可查看真实原因。`, 'warning');
        // Cold-start failures are frequently caused by the local Python server
        // finishing its first evidence query. Retry them after the UI is usable
        // instead of leaving a stale degraded count for the entire session.
        [1500, 7000, 20000].forEach((delay, index) => {
          window.setTimeout(() => retryFailedModules(`auto_retry_${index + 1}`), delay);
        });
      }
      window.setTimeout(() => loadPostReadyModules(), POST_READY_DELAY_MS);
      const warmDocuments = () => prefetchWorkspaceDocuments();
      if (typeof window.requestIdleCallback === 'function') window.requestIdleCallback(warmDocuments, {timeout:1800});
      else window.setTimeout(warmDocuments, 900);
    } catch (error) {
      state.phase = 'failed';
      state.error = String(error?.message || error);
      exposeStartupStatus();
      console.error('R8-12 startup coordinator fatal failure', error);
      if (typeof window.toast === 'function') window.toast(`启动协调器异常：${state.error}`, 'error');
    }
  }

  document.addEventListener('click', event => {
    if (event.target?.closest?.('.r810-nav-button[data-target="connections"],.nav[data-page="connections"],.go-page[data-target="connections"]')) {
      window.setTimeout(renderStartupDiagnostics, 80);
    }
  }, true);
  window.KZLoadOwnerWorkspace = loadLazyBundle;
  window.KZRetryFailedStartupModules = retryFailedModules;
  window.KZClearStartupModuleFailure = (src, reason = 'external_recovery') => clearFailure(src, reason);
  window.KZStartupDiagnostics = () => ({
    phase: state.phase,
    degraded: state.degraded,
    failed_modules: state.failed_modules.map(row => ({...row})),
    recovered_modules: state.recovered_modules.map(row => ({...row})),
  });
  boot();
})();

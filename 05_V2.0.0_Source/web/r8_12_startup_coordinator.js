(() => {
  'use strict';

  if (window.__KZ_R812_STARTUP_COORDINATOR__) return;
  window.__KZ_R812_STARTUP_COORDINATOR__ = {
    phase: 'booting',
    started_at: new Date().toISOString(),
    ready_at: null,
    loaded: [],
  };

  const state = window.__KZ_R812_STARTUP_COORDINATOR__;
  const STARTUP_OBSERVER_DELAYS = [80, 220, 500, 900, 1500, 2200];
  const SCRIPT_SEQUENCE = [
    ['/r8_10_workbench.js', 'r810Workbench'],
    ['/r8_10_truth_convergence.js', 'r810TruthConvergence'],
    ['/r8_11_backbone_ui.js', 'r811Backbone'],
    ['/r8_11_execution_tab_hotfix.js', 'r811ExecutionTabHotfix'],
    ['/r8_12_account_center_bridge.js', 'r812AccountCenter'],
    ['/kz_site_tools.js', 'kzSiteTools'],
    ['/kz_local_direct_ui.js', 'kzLocalDirectUi'],
    ['/kz_async_control_ui.js', 'kzAsyncControlUi'],
  ];
  const GENERATED_ID_PREFIXES = ['r8-', 'r810-', 'r811-', 'r812-', 'kz-'];

  function emit(name, detail = {}) {
    window.dispatchEvent(new CustomEvent(name, {detail}));
    document.dispatchEvent(new CustomEvent(name, {detail}));
  }

  function wait(ms) {
    return new Promise(resolve => window.setTimeout(resolve, ms));
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

  function loadScript(src, datasetKey) {
    const selector = `script[data-${datasetKey.replace(/[A-Z]/g, m => '-' + m.toLowerCase())}]`;
    const existing = document.querySelector(selector) || [...document.scripts].find(node => {
      try { return new URL(node.src, location.href).pathname === src; } catch { return false; }
    });
    if (existing) {
      state.loaded.push({src, reused:true});
      return Promise.resolve(existing);
    }
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = false;
      script.dataset[datasetKey] = '1';
      script.onload = () => { state.loaded.push({src, reused:false}); resolve(script); };
      script.onerror = () => reject(new Error(`启动模块加载失败：${src}`));
      document.body.appendChild(script);
    });
  }

  function installFiniteStartupObserverPolicy() {
    const NativeObserver = window.MutationObserver;
    if (!NativeObserver || window.__KZ_NATIVE_MUTATION_OBSERVER__) return () => {};
    window.__KZ_NATIVE_MUTATION_OBSERVER__ = NativeObserver;

    class FiniteStartupObserver {
      constructor(callback) {
        this.callback = callback;
        this.timers = [];
        this.disconnected = false;
      }
      observe() {
        if (this.disconnected || this.timers.length) return;
        STARTUP_OBSERVER_DELAYS.forEach(delay => {
          this.timers.push(window.setTimeout(() => {
            if (!this.disconnected) {
              try { this.callback([], this); } catch (error) { console.warn('startup observer callback failed', error); }
            }
          }, delay));
        });
      }
      disconnect() {
        this.disconnected = true;
        this.timers.forEach(timer => window.clearTimeout(timer));
        this.timers = [];
      }
      takeRecords() { return []; }
    }

    window.MutationObserver = FiniteStartupObserver;
    return () => {
      if (window.MutationObserver === FiniteStartupObserver) window.MutationObserver = NativeObserver;
      delete window.__KZ_NATIVE_MUTATION_OBSERVER__;
    };
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
      if (typeof window.openPage === 'function') {
        window.openPage('dashboard');
      } else {
        document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === 'dashboard'));
        document.querySelectorAll('aside nav .nav').forEach(button => button.classList.toggle('active', button.dataset.page === 'dashboard'));
      }
    } catch (error) {
      console.warn('initial dashboard route failed', error);
    }
  }

  async function boot() {
    state.phase = 'waiting_base';
    await waitForWindowLoad();
    await waitForBaseShell();
    emit('kz:startup-base-ready');

    const restoreObserverPolicy = installFiniteStartupObserverPolicy();
    state.phase = 'loading_owner_shell';
    try {
      for (const [src, key] of SCRIPT_SEQUENCE) {
        await loadScript(src, key);
        await wait(40);
        dedupeGeneratedSingletons();
        if (src === '/r8_10_workbench.js') {
          await wait(180);
          emit('r810:workbench-ready');
        }
      }
      await wait(180);
      dedupeGeneratedSingletons();
      forceInitialDashboardOnce();
      state.phase = 'ready';
      state.ready_at = new Date().toISOString();
      emit('kz:app-ready', {loaded: state.loaded.slice()});
    } catch (error) {
      state.phase = 'failed';
      state.error = String(error?.message || error);
      console.error('R8-12 startup coordinator failed', error);
      if (typeof window.toast === 'function') window.toast(`启动收敛失败：${state.error}`, 'error');
    } finally {
      window.setTimeout(restoreObserverPolicy, 2600);
    }
  }

  boot();
})();

(() => {
  const DISPLAY_VERSION = 'V2.2.0 R8 Operational';
  const RUNTIME_BUILD = 'KZ-ENTERPRISE-V2.2-R8-OPERATIONAL-20260920';
  const PHASE = 'R8-08 全模块最终交付';
  const PREVIOUS_PHASE = 'R8-01B.5';
  const LEGACY_PHASE = 'R8-01B.4.3';

  function buildLabel() {
    const info = window.KZ_BUILD_INFO || {};
    const run = String(info.runNumber || '').trim();
    const commit = String(info.commit || '').trim();
    const runLabel = run && !run.startsWith('__') ? `Build #${run}` : 'Source build';
    const commitLabel = commit && !commit.startsWith('__') ? commit.slice(0, 8) : 'local';
    return `${runLabel} · ${commitLabel}`;
  }

  function showLoaderStatus(text, kind='warn') {
    const panel = document.getElementById('r8-device-center');
    if (!panel) return;
    let node = document.getElementById('r8-b4-loader-status');
    if (!node) {
      node = document.createElement('div');
      node.id = 'r8-b4-loader-status';
      node.className = 'notice';
      const head = panel.querySelector('.r8-console-head');
      if (head) head.insertAdjacentElement('afterend', node);
      else panel.prepend(node);
    }
    node.textContent = text;
    node.dataset.kind = kind;
    node.style.background = kind === 'ok' ? '#eaf8ef' : kind === 'stop' ? '#f8e5e3' : '#fff7df';
    node.style.color = kind === 'ok' ? '#237244' : kind === 'stop' ? '#9a392f' : '#8b6509';
  }

  function loadBridgeUsabilityPatch() {
    if (document.querySelector('script[data-r7-bridge-usability]')) return;
    const script = document.createElement('script');
    script.src = 'r7_bridge_usability_patch.js';
    script.async = false;
    script.dataset.r7BridgeUsability = '1';
    script.onerror = () => {
      if (typeof toast === 'function') toast('双向运营桥交互恢复模块加载失败，请重新安装最新版本', 'error');
    };
    document.body.appendChild(script);
  }

  function mirrorReady() {
    return !!(window.R8DeviceMirrorSync && typeof window.R8DeviceMirrorSync.syncOnce === 'function');
  }

  function activateMirror() {
    if (!mirrorReady()) return false;
    try {
      if (typeof window.R8DeviceMirrorSync.startContinuous === 'function') {
        window.R8DeviceMirrorSync.startContinuous();
      }
      const panel = document.getElementById('r8-device-center');
      if (panel) panel.dataset.mirrorLoader = 'ready';
      showLoaderStatus('手机屏幕同步模块已加载。连接真机后会自动同步，也可以使用“测试截图”。', 'ok');
      return true;
    } catch (error) {
      showLoaderStatus('屏幕同步模块启动失败：' + error.message, 'stop');
      if (typeof toast === 'function') toast('R8 屏幕同步模块启动失败：' + error.message, 'error');
      return false;
    }
  }

  function loadMirrorDirect() {
    if (mirrorReady()) {
      activateMirror();
      return;
    }

    const old = document.querySelector('script[data-r8-device-b4-hotfix]');
    if (old) old.remove();

    showLoaderStatus('正在加载手机屏幕同步模块…', 'warn');
    const script = document.createElement('script');
    script.src = 'r8_device_b4_mirror_hotfix.js?v=R8-01B.5';
    script.async = false;
    script.dataset.r8DeviceB4Hotfix = '1';
    script.onload = () => {
      if (!activateMirror()) {
        showLoaderStatus('屏幕同步文件已载入，但模块没有完成初始化。请关闭程序后重新打开一次。', 'stop');
      }
      setTimeout(() => {
        if (mirrorReady()) {
          activateMirror();
          if (!document.getElementById('r8-mirror-controls')) {
            showLoaderStatus('同步模块已就绪，但控制条未挂载。请进入社媒中心并重新打开真机操作台。', 'warn');
          }
        }
      }, 500);
    };
    script.onerror = () => {
      showLoaderStatus('屏幕同步脚本加载失败：' + script.src, 'stop');
      if (typeof toast === 'function') toast('R8 真机屏幕同步脚本加载失败，请重新安装最新版本', 'error');
    };
    document.body.appendChild(script);
  }

  function loadDeviceB3Patch() {
    if (document.querySelector('script[data-r8-device-b3]')) return;
    const script = document.createElement('script');
    script.src = 'r8_device_b3_patch.js';
    script.async = false;
    script.dataset.r8DeviceB3 = '1';
    script.onerror = () => {
      if (typeof toast === 'function') toast('R8 熄屏恢复与虚拟手机控制模块加载失败，请重新安装最新版本', 'error');
    };
    document.body.appendChild(script);
  }

  function loadTerminalCockpitPatch() {
    if (document.querySelector('script[data-r8-terminal-cockpit]')) {
      loadDeviceB3Patch();
      return;
    }
    const script = document.createElement('script');
    script.src = 'r8_terminal_cockpit_patch.js';
    script.async = false;
    script.dataset.r8TerminalCockpit = '1';
    script.onload = loadDeviceB3Patch;
    script.onerror = () => {
      if (typeof toast === 'function') toast('R8 社媒终端驾驶舱模块加载失败，请重新安装最新版本', 'error');
      loadDeviceB3Patch();
    };
    document.body.appendChild(script);
  }

  function loadDeviceRuntimeAfterMount() {
    let attempts = 0;
    const start = () => {
      attempts += 1;
      const panel = document.getElementById('r8-device-center');
      if (panel) {
        loadMirrorDirect();
        setTimeout(loadTerminalCockpitPatch, 250);
        return;
      }
      if (attempts < 240) {
        setTimeout(start, 100);
        return;
      }
      if (typeof toast === 'function') toast('R8 真机操作台未完成初始化，请刷新页面或重新安装最新版本', 'error');
    };
    start();
  }
  function loadCommandPyramid() {
    if (document.querySelector('script[data-r8-command-pyramid]')) return;
    const script = document.createElement('script');
    script.src = 'r8_command_pyramid.js';
    script.async = false;
    script.dataset.r8CommandPyramid = '1';
    script.onerror = () => {
      if (typeof toast === 'function') toast('总控金字塔与 0→10 体检模块加载失败，请重新安装最新版', 'error');
    };
    document.body.appendChild(script);
  }


  function loadFinalGrowthCenter() {
    if (!document.querySelector('link[data-r8-final-style]')) {
      const style = document.createElement('link');
      style.rel = 'stylesheet';
      style.href = 'r8_final.css';
      style.dataset.r8FinalStyle = '1';
      document.head.appendChild(style);
    }
    if (document.querySelector('script[data-r8-final-center]')) return;
    const script = document.createElement('script');
    script.src = 'r8_final_center.js';
    script.async = false;
    script.dataset.r8FinalCenter = '1';
    script.onerror = () => {
      if (typeof toast === 'function') toast('R8 最终增长中心加载失败，请重新安装最终版', 'error');
    };
    document.body.appendChild(script);
  }

  async function applyR8Identity() {
    document.title = `卡嘴子 AI 增长运营中心 ${DISPLAY_VERSION}`;
    const meta = document.querySelector('meta[name="kazuizhi-build"]');
    if (meta) meta.setAttribute('content', RUNTIME_BUILD);

    const baseline = document.querySelector('.baseline');
    loadCommandPyramid();
    if (baseline) {
      baseline.innerHTML = `<b>${DISPLAY_VERSION}</b><br><span>${PHASE}</span><code>${buildLabel()}</code>`;
      baseline.dataset.previousPhase = PREVIOUS_PHASE;
      baseline.dataset.legacyPhase = LEGACY_PHASE;
    }

    const badge = document.querySelector('#dashboard .welcome-badge');
    if (badge) badge.textContent = 'R8 Final · R8-00 至 R8-08 全模块';

    const mainButton = document.querySelector('#dashboard .welcome-actions .go-page[data-target="workflow"]');
    if (mainButton) mainButton.innerHTML = '查看 R8 最终工作流 <b>→</b>';

    const workflowLabel = document.querySelector('#workflow .page-title small');
    if (workflowLabel) workflowLabel.textContent = 'R7 稳定底座 + R8-00 至 R8-08 完整增长运营层';

    const heading = document.querySelector('#dashboard .command-welcome h2');
    if (heading) heading.textContent = 'R8 全模块已交付：从平台雷达到内容、视频、发布、线索归因和复盘学习。';

    loadBridgeUsabilityPatch();
    loadDeviceRuntimeAfterMount();
    loadFinalGrowthCenter();

    try {
      const status = await fetch('/api/status', {cache: 'no-store'}).then(r => r.json());
      if (status.runtime_build !== RUNTIME_BUILD || status.r8_phase !== 'R8-08') {
        if (typeof toast === 'function') toast('R8 安装包身份不一致，请重新安装最新 R8 Final', 'error');
      }
    } catch (error) {
      // The normal app health check will surface local-service failures separately.
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyR8Identity, {once: true});
  } else {
    applyR8Identity();
  }
})();

(() => {
  const DISPLAY_VERSION = 'V2.2.2 自治运营核心';
  const RUNTIME_BUILD = 'KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922';
  const PHASE = 'R8-09 自治闭环收口';
  const PREVIOUS_PHASE = 'R8-08';
  const LEGACY_PHASE = 'R8-01B.5';
  let deviceRuntimeArmed = false;
  let deviceRuntimeLoading = false;

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

  function devicePanelVisible() {
    const panel = document.getElementById('r8-device-center');
    const social = document.getElementById('social-center');
    return !!(panel && !panel.hidden && social && social.classList.contains('active'));
  }

  function activateMirror() {
    if (!mirrorReady()) return false;
    try {
      if (devicePanelVisible() && typeof window.R8DeviceMirrorSync.startContinuous === 'function') {
        window.R8DeviceMirrorSync.startContinuous();
      }
      const panel = document.getElementById('r8-device-center');
      if (panel) panel.dataset.mirrorLoader = 'ready';
      showLoaderStatus('手机屏幕同步模块已加载。打开真机操作台后才会启动连续同步，也可以使用“测试截图”。', 'ok');
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
    const existing = document.querySelector('script[data-r8-device-b4-hotfix]');
    if (existing) return;
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
        if (mirrorReady()) activateMirror();
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

  function loadDeviceRuntimeOnDemand() {
    if (deviceRuntimeLoading) return;
    deviceRuntimeLoading = true;
    let attempts = 0;
    const start = () => {
      attempts += 1;
      const panel = document.getElementById('r8-device-center');
      if (panel) {
        loadMirrorDirect();
        setTimeout(loadTerminalCockpitPatch, 120);
        deviceRuntimeLoading = false;
        return;
      }
      if (attempts < 30) {
        setTimeout(start, 100);
        return;
      }
      deviceRuntimeLoading = false;
      if (typeof toast === 'function') toast('R8 真机操作台未完成初始化，请重新打开社媒终端', 'error');
    };
    start();
  }

  function armDeviceRuntimeLoader() {
    if (deviceRuntimeArmed) return;
    deviceRuntimeArmed = true;
    document.addEventListener('click', event => {
      const terminal = event.target.closest && event.target.closest('[data-social-device-control]');
      if (!terminal) return;
      setTimeout(loadDeviceRuntimeOnDemand, 0);
    }, true);
    setTimeout(() => {
      if (devicePanelVisible()) loadDeviceRuntimeOnDemand();
    }, 700);
  }

  function loadCommandPyramid() {
    if (document.querySelector('script[data-r8-command-pyramid]')) return;
    const script = document.createElement('script');
    script.src = 'r8_command_pyramid.js';
    script.async = false;
    script.dataset.r8CommandPyramid = '1';
    script.onerror = () => {
      if (typeof toast === 'function') toast('总控金字塔与体检模块加载失败，请重新安装最新版', 'error');
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
    document.title = `卡嘴子 AI 自治运营中心 ${DISPLAY_VERSION}`;
    const meta = document.querySelector('meta[name="kazuizhi-build"]');
    if (meta) meta.setAttribute('content', RUNTIME_BUILD);

    const baseline = document.querySelector('.baseline');
    loadCommandPyramid();
    if (baseline) {
      baseline.innerHTML = `<b>${DISPLAY_VERSION}</b><br><span>${PHASE}</span><code>${buildLabel()}</code>`;
      baseline.dataset.previousPhase = PREVIOUS_PHASE;
      baseline.dataset.legacyPhase = LEGACY_PHASE;
    }

    document.querySelectorAll('.side-footer b').forEach(node => { node.textContent = DISPLAY_VERSION; });
    const badge = document.querySelector('#dashboard .welcome-badge');
    if (badge) badge.textContent = 'V2.2.2 · 自治运营核心';

    const mainButton = document.querySelector('#dashboard .welcome-actions .go-page[data-target="workflow"]');
    if (mainButton) mainButton.innerHTML = '查看自治运营流水线 <b>→</b>';

    const workflowLabel = document.querySelector('#workflow .page-title small');
    if (workflowLabel) workflowLabel.textContent = 'R7 稳定底座 + Mission + ChatGPT AI Gateway + R8 自动执行';

    const heading = document.querySelector('#dashboard .command-welcome h2');
    if (heading) heading.textContent = '从老板经营目标出发，统一管理AI决策、自动执行、真实发布和结果回流。';

    loadBridgeUsabilityPatch();
    armDeviceRuntimeLoader();
    loadFinalGrowthCenter();

    try {
      const status = await fetch('/api/status', {cache: 'no-store'}).then(r => r.json());
      if (status.runtime_build !== RUNTIME_BUILD || status.r8_phase !== 'R8-09') {
        if (typeof toast === 'function') toast('安装包身份不一致，请重新安装 V2.2.2 自治运营核心', 'error');
      }
    } catch (error) {
      // Normal health checks surface local-service failures separately.
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyR8Identity, {once: true});
  } else {
    applyR8Identity();
  }
})();

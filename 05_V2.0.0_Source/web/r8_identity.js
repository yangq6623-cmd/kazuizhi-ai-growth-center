(() => {
  const DISPLAY_VERSION = 'V2.1.0 Beta R8 Preview';
  const RUNTIME_BUILD = 'KZ-ENTERPRISE-V2.1-BETA-20260918-R8-PREVIEW';
  const PHASE = 'R8-01B.4.1 屏幕同步加载修复';
  const PREVIOUS_PHASE = 'R8-01B.4';
  const LEGACY_PHASE = 'R8-01B.3';

  function buildLabel() {
    const info = window.KZ_BUILD_INFO || {};
    const run = String(info.runNumber || '').trim();
    const commit = String(info.commit || '').trim();
    const runLabel = run && !run.startsWith('__') ? `Build #${run}` : 'Source build';
    const commitLabel = commit && !commit.startsWith('__') ? commit.slice(0, 8) : 'local';
    return `${runLabel} · ${commitLabel}`;
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

  function b4Ready() {
    return !!(window.R8DeviceMirrorSync && typeof window.R8DeviceMirrorSync.syncOnce === 'function');
  }

  function activateB4IfReady() {
    if (!b4Ready()) return false;
    try {
      if (typeof window.R8DeviceMirrorSync.startContinuous === 'function') {
        window.R8DeviceMirrorSync.startContinuous();
      }
      return true;
    } catch (error) {
      if (typeof toast === 'function') toast('R8 屏幕同步模块启动失败：' + error.message, 'error');
      return false;
    }
  }

  function loadDeviceB4Hotfix(force=false) {
    if (b4Ready()) {
      activateB4IfReady();
      return;
    }

    const existing = document.querySelector('script[data-r8-device-b4-hotfix]');
    if (existing && !force) return;
    if (existing && force) existing.remove();

    const script = document.createElement('script');
    script.src = `r8_device_b4_mirror_hotfix.js?v=231-${Date.now()}`;
    script.async = false;
    script.dataset.r8DeviceB4Hotfix = '1';
    script.onload = () => {
      if (!activateB4IfReady() && typeof toast === 'function') {
        toast('R8 屏幕同步文件已加载，但控制模块没有完成初始化，系统将自动重试', 'error');
      }
    };
    script.onerror = () => {
      if (typeof toast === 'function') toast('R8 真机屏幕同步控制模块加载失败，系统将自动重试', 'error');
    };
    document.body.appendChild(script);
  }

  function installB4Watchdog() {
    let checks = 0;
    const verify = () => {
      checks += 1;
      const panel = document.getElementById('r8-device-center');
      if (!panel) {
        if (checks < 20) setTimeout(verify, 500);
        return;
      }

      const controls = document.getElementById('r8-mirror-controls');
      if (b4Ready()) {
        activateB4IfReady();
        if (controls || checks >= 20) return;
      } else {
        loadDeviceB4Hotfix(true);
      }

      if (checks < 20) setTimeout(verify, 700);
      else if (!document.getElementById('r8-mirror-controls') && typeof toast === 'function') {
        toast('R8 屏幕同步控制条仍未显示，请安装最新构建版本', 'error');
      }
    };
    setTimeout(verify, 350);
  }

  function loadDeviceB3Patch() {
    if (document.querySelector('script[data-r8-device-b3]')) {
      loadDeviceB4Hotfix();
      return;
    }
    const script = document.createElement('script');
    script.src = 'r8_device_b3_patch.js';
    script.async = false;
    script.dataset.r8DeviceB3 = '1';
    script.onload = loadDeviceB4Hotfix;
    script.onerror = () => {
      if (typeof toast === 'function') toast('R8 熄屏恢复与虚拟手机控制模块加载失败，请重新安装最新版本', 'error');
      loadDeviceB4Hotfix(true);
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
      loadDeviceB4Hotfix(true);
    };
    document.body.appendChild(script);
  }

  function loadDeviceRuntimeAfterMount() {
    let attempts = 0;
    const start = () => {
      attempts += 1;
      if (document.getElementById('r8-device-center')) {
        loadTerminalCockpitPatch();
        // #230 proved the device console itself can mount while B4 never becomes
        // visible. Load B4 again independently after the real panel exists, so
        // cockpit/B3 loader timing can no longer suppress the screen-sync bar.
        setTimeout(() => loadDeviceB4Hotfix(true), 500);
        setTimeout(() => loadDeviceB4Hotfix(true), 1400);
        installB4Watchdog();
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

  async function applyR8Identity() {
    document.title = `卡嘴子 AI 增长运营中心 ${DISPLAY_VERSION}`;
    const meta = document.querySelector('meta[name="kazuizhi-build"]');
    if (meta) meta.setAttribute('content', RUNTIME_BUILD);

    const baseline = document.querySelector('.baseline');
    if (baseline) {
      baseline.innerHTML = `<b>${DISPLAY_VERSION}</b><br><span>${PHASE}</span><code>${buildLabel()}</code>`;
      baseline.dataset.previousPhase = PREVIOUS_PHASE;
      baseline.dataset.legacyPhase = LEGACY_PHASE;
    }

    const badge = document.querySelector('#dashboard .welcome-badge');
    if (badge) badge.textContent = 'R8 Preview · R8-01B.4.1 屏幕同步加载修复';

    const mainButton = document.querySelector('#dashboard .welcome-actions .go-page[data-target="workflow"]');
    if (mainButton) mainButton.innerHTML = '查看 R8 Preview 工作流 <b>→</b>';

    const workflowLabel = document.querySelector('#workflow .page-title small');
    if (workflowLabel) workflowLabel.textContent = 'R7 Final 稳定底座 + R8-00 安全层 + R8-01 真机设备层';

    const heading = document.querySelector('#dashboard .command-welcome h2');
    if (heading) heading.textContent = 'R7 稳定运行，R8 正在完成 Gate 2 前的真实手机屏幕同步与触控闭环。';

    loadBridgeUsabilityPatch();
    loadDeviceRuntimeAfterMount();

    try {
      const status = await fetch('/api/status', {cache: 'no-store'}).then(r => r.json());
      if (status.runtime_build !== RUNTIME_BUILD || status.r8_phase !== 'R8-01') {
        if (typeof toast === 'function') toast('R8 安装包身份不一致，请重新安装最新 R8 Preview', 'error');
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

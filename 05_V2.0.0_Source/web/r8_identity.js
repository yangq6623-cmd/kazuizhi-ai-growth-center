(() => {
  const DISPLAY_VERSION = 'V2.1.0 Beta R8 Preview';
  const RUNTIME_BUILD = 'KZ-ENTERPRISE-V2.1-BETA-20260918-R8-PREVIEW';
  const PHASE = 'R8-01 单真机设备中心';

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

  async function applyR8Identity() {
    document.title = `卡嘴子 AI 增长运营中心 ${DISPLAY_VERSION}`;
    const meta = document.querySelector('meta[name="kazuizhi-build"]');
    if (meta) meta.setAttribute('content', RUNTIME_BUILD);

    const baseline = document.querySelector('.baseline');
    if (baseline) {
      baseline.innerHTML = `<b>${DISPLAY_VERSION}</b><br><span>${PHASE}</span><code>${buildLabel()}</code>`;
    }

    const badge = document.querySelector('#dashboard .welcome-badge');
    if (badge) badge.textContent = 'R8 Preview · R8-01 单真机设备中心';

    const mainButton = document.querySelector('#dashboard .welcome-actions .go-page[data-target="workflow"]');
    if (mainButton) mainButton.innerHTML = '查看 R8 Preview 工作流 <b>→</b>';

    const workflowLabel = document.querySelector('#workflow .page-title small');
    if (workflowLabel) workflowLabel.textContent = 'R7 Final 稳定底座 + R8-00 安全层 + R8-01 真机设备层';

    const heading = document.querySelector('#dashboard .command-welcome h2');
    if (heading) heading.textContent = 'R7 稳定运行，R8 已进入真实 Android 单真机接入阶段。';

    loadBridgeUsabilityPatch();

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

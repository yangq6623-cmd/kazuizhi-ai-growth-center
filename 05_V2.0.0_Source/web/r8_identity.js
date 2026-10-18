(() => {
  const DISPLAY_VERSION = 'V2.2.2 自治运营核心';
  const RUNTIME_BUILD = 'KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922';
  const PHASE = 'R8-09 自治闭环收口';
  const PREVIOUS_PHASE = 'R8-08';
  const LEGACY_PHASE = 'R8-01B.4.3';

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
    // Real phone / ADB runtime is retired in R8-23 PC browser mode.
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

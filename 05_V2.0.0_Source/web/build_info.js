window.KZ_BUILD_INFO = {
  runNumber: "__GITHUB_RUN_NUMBER__",
  commit: "__GITHUB_SHA__",
  branch: "r8-18-model-connection-center",
  phase: "R8-18",
  displayVersion: "V2.2.2 R8-18 阶段一测试候选",
  runtimeBuild: "KZ-ENTERPRISE-V2.2.2-R8-18-PHASE1-FOUNDATION"
};

(() => {
  const load = () => {
    if (!document.getElementById('studio-root')) return;
    if (document.querySelector('script[data-series-asset-center-v92]')) return;
    const script = document.createElement('script');
    script.src = 'series-asset-center-v92.js';
    script.async = false;
    script.dataset.seriesAssetCenterV92 = '1';
    document.body.appendChild(script);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load, {once:true});
  else load();
  const observer = new MutationObserver(load);
  observer.observe(document.documentElement, {childList:true, subtree:true});
})();

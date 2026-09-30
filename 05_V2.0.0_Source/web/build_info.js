window.KZ_BUILD_INFO = {
  runNumber: "__GITHUB_RUN_NUMBER__",
  commit: "__GITHUB_SHA__",
  branch: "r8-18-model-connection-center",
  phase: "R8-18",
  displayVersion: "V2.2.2 R8-18 内容中心最终整合候选",
  runtimeBuild: "KZ-ENTERPRISE-V2.2.2-R8-18-CONTENT-V101"
};

(() => {
  const addScript = (src, marker) => {
    if (document.querySelector(`script[${marker}]`)) return;
    const script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.setAttribute(marker, '1');
    document.body.appendChild(script);
  };
  const load = () => {
    if (!document.getElementById('studio-root')) return;
    addScript('series-asset-center-v92.js', 'data-series-asset-center-v92');
    addScript('content-final-v101.js', 'data-content-final-v101');
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load, {once:true});
  else load();
  const observer = new MutationObserver(load);
  observer.observe(document.documentElement, {childList:true, subtree:true});
})();

$('save-memory').addEventListener('click', async () => {
  const input = $('memory-statement');
  const statement = input.value.trim();
  if (!statement) {
    toast('请先填写一条已确认事实','error');
    return;
  }
  try {
    await api('/api/memory', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({category: '老板确认', statement, evidence: '老板在本地运营中心手动录入'}),
    });
    input.value = '';
    await loadMemory();
    toast('已保存到 AI Memory');
  } catch (error) {
    toast(error.message,'error');
  }
});

// R8-12.1 startup convergence: the owner shell is loaded through a single
// coordinator after the legacy/base page has settled. Heavy iframe workspaces
// (Content Studio, Execution and SEO/GEO) are intentionally NOT injected here;
// the coordinator now lazy-loads them on first use so the dashboard can become
// responsive before any large child application starts.
(() => {
  if (!document.querySelector('link[data-r810-workbench]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/r8_10_workbench.css';
    link.dataset.r810Workbench = '1';
    document.head.appendChild(link);
  }
  if (document.querySelector('script[data-r812-startup-coordinator]')) return;
  window.__KZ_R812_STARTUP_COORDINATED__ = true;
  const coordinator = document.createElement('script');
  coordinator.src = '/r8_12_startup_coordinator.js';
  coordinator.async = false;
  coordinator.dataset.r812StartupCoordinator = '1';
  coordinator.onerror = () => {
    if (typeof toast === 'function') toast('R8-12 启动协调器加载失败，请重新安装最新版本', 'error');
  };
  document.body.appendChild(coordinator);
})();

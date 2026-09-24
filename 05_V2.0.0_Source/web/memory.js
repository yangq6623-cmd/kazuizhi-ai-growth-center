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

// R8-10 is intentionally loaded as a product shell over the proven #397
// runtime. This keeps the R7/R8 state machines intact while unifying the
// owner-facing workbench. Keeping the loader here avoids a destructive rewrite
// of the legacy index page and makes rollback to #397 straightforward.
(() => {
  if (!document.querySelector('link[data-r810-workbench]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/r8_10_workbench.css';
    link.dataset.r810Workbench = '1';
    document.head.appendChild(link);
  }
  if (!document.querySelector('script[data-r810-workbench]')) {
    const script = document.createElement('script');
    script.src = '/r8_10_workbench.js';
    script.defer = true;
    script.dataset.r810Workbench = '1';
    document.body.appendChild(script);
  }
  // Final owner-facing truth convergence. This deliberately loads as a thin
  // presentation layer over the same backend truth: current Mission only,
  // dynamic closed-loop maturity, daily-routine vs Mission progress, and
  // publish authorization wording that never pretends a real platform receipt.
  if (!document.querySelector('script[data-r810-truth-convergence]')) {
    const truth = document.createElement('script');
    truth.src = '/r8_10_truth_convergence.js';
    truth.defer = true;
    truth.dataset.r810TruthConvergence = '1';
    document.body.appendChild(truth);
  }
  // R8-11 primary backbone visibility: Command/Mission/Video/Publish/Receipt
  // ledger plus the unified acquisition-channel registry. This requires no
  // paid third-party token service and does not change external truth gates.
  if (!document.querySelector('script[data-r811-backbone]')) {
    const backbone = document.createElement('script');
    backbone.src = '/r8_11_backbone_ui.js';
    backbone.defer = true;
    backbone.dataset.r811Backbone = '1';
    document.body.appendChild(backbone);
  }
  // #481 field fix: execution-center tabs must always route into the embedded
  // operational runtime. In particular, “真机执行” must never silently no-op
  // when the iframe has not been created or is still loading.
  if (!document.querySelector('script[data-r811-execution-tab-hotfix]')) {
    const executionTabs = document.createElement('script');
    executionTabs.src = '/r8_11_execution_tab_hotfix.js';
    executionTabs.defer = true;
    executionTabs.dataset.r811ExecutionTabHotfix = '1';
    document.body.appendChild(executionTabs);
  }
  // R8-12 replaces the old Mission/service/device re-binding screen with the
  // durable account asset center.  It loads after the R8-11 tab hotfix and
  // captures only the owner-facing “平台账号” route; legacy APIs remain for
  // migration compatibility but are no longer the normal operating surface.
  if (!document.querySelector('script[data-r812-account-center]')) {
    const accountCenter = document.createElement('script');
    accountCenter.src = '/r8_12_account_center_bridge.js';
    accountCenter.defer = true;
    accountCenter.dataset.r812AccountCenter = '1';
    document.body.appendChild(accountCenter);
  }
  // Optional same-PC real-time helper. Site Tools/WebMCP may call localhost when
  // available, but normal autonomous operation no longer depends on it.
  if (!document.querySelector('script[data-kz-site-tools]')) {
    const siteTools = document.createElement('script');
    siteTools.src = '/kz_site_tools.js';
    siteTools.defer = true;
    siteTools.dataset.kzSiteTools = '1';
    document.body.appendChild(siteTools);
  }
  if (!document.querySelector('script[data-kz-local-direct-ui]')) {
    const localUi = document.createElement('script');
    localUi.src = '/kz_local_direct_ui.js';
    localUi.defer = true;
    localUi.dataset.kzLocalDirectUi = '1';
    document.body.appendChild(localUi);
  }
  // Primary day-to-day owner architecture: normal ChatGPT -> private async
  // control bus -> local Mission -> truthful Receipt. This UI layer makes the
  // distinction between continuous local autonomy and optional realtime AI.
  if (!document.querySelector('script[data-kz-async-control-ui]')) {
    const busUi = document.createElement('script');
    busUi.src = '/kz_async_control_ui.js';
    busUi.defer = true;
    busUi.dataset.kzAsyncControlUi = '1';
    document.body.appendChild(busUi);
  }
})();

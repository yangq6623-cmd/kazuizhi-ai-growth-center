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
      headers: {'Content-Type': 'application/json'},
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
  // Local-first ChatGPT control: when this page is opened in the ChatGPT
  // desktop app built-in browser, WebMCP Site Tools can call the localhost
  // runtime directly. No business server or public port is required.
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
})();

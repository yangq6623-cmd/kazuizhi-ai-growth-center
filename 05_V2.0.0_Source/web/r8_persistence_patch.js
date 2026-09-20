(() => {
  let lastBusinessStatus = null;
  let refreshScheduled = false;
  let refreshRunning = false;

  async function request(path, options) {
    const response = await fetch(path, options || {cache: 'no-store'});
    const type = response.headers.get('content-type') || '';
    const data = type.includes('application/json') ? await response.json() : null;
    if (!response.ok) throw new Error((data && data.error) || `请求失败 ${response.status}`);
    return data;
  }

  function ensureChangeButton() {
    const row = document.querySelector('#save-business-source')?.parentElement;
    if (!row || document.querySelector('#change-business-source-key')) return;
    const button = document.createElement('button');
    button.id = 'change-business-source-key';
    button.className = 'outline-button';
    button.textContent = '更换密钥';
    row.appendChild(button);
  }

  function applyBusinessStatus(data) {
    lastBusinessStatus = data || null;
    const input = document.querySelector('#business-source-key');
    const save = document.querySelector('#save-business-source');
    if (!input || !save || !data) return;
    ensureChangeButton();
    const change = document.querySelector('#change-business-source-key');
    if (data.has_key && input.dataset.changeMode !== '1') {
      input.disabled = true;
      input.value = 'KAZUIZHI_SAVED_KEY';
      input.placeholder = '只读密钥已加密保存在本机；无需重复填写';
      save.textContent = '使用已保存密钥重新验证';
      if (change) change.hidden = false;
    } else {
      input.disabled = false;
      if (input.value === 'KAZUIZHI_SAVED_KEY') input.value = '';
      input.placeholder = '粘贴服务器 SHOW_READONLY_KEY.bat 显示的密钥';
      save.textContent = data.has_key ? '保存新密钥并验证' : '连接并验证';
      if (change) change.hidden = !data.has_key;
    }
  }

  async function refreshBusinessPersistence() {
    if (!document.querySelector('#business-source-key') || refreshRunning) return;
    refreshRunning = true;
    try {
      const data = await request('/api/business-source/status', {cache: 'no-store'});
      applyBusinessStatus(data);
    } catch (_) {
    } finally {
      refreshRunning = false;
    }
  }

  function scheduleBusinessPersistenceRefresh(delay = 80) {
    if (refreshScheduled || !document.querySelector('#business-source-key')) return;
    refreshScheduled = true;
    setTimeout(async () => {
      refreshScheduled = false;
      await refreshBusinessPersistence();
    }, delay);
  }

  document.addEventListener('click', async event => {
    const change = event.target.closest && event.target.closest('#change-business-source-key');
    if (change) {
      event.preventDefault();
      const input = document.querySelector('#business-source-key');
      if (!input) return;
      input.dataset.changeMode = '1';
      input.disabled = false;
      input.value = '';
      input.focus();
      const save = document.querySelector('#save-business-source');
      if (save) save.textContent = '保存新密钥并验证';
      return;
    }

    const button = event.target.closest && event.target.closest('#save-business-source');
    if (!button) return;
    // Stop the legacy listener that incorrectly required re-pasting a key even
    // when Windows already had a DPAPI-encrypted credential.
    event.preventDefault();
    event.stopImmediatePropagation();
    const input = document.querySelector('#business-source-key');
    if (!input) return;
    button.disabled = true;
    button.textContent = '连接验证中…';
    try {
      const status = lastBusinessStatus || await request('/api/business-source/status', {cache: 'no-store'});
      const key = input.disabled ? '' : input.value.trim();
      let data;
      if (key) {
        data = await request('/api/business-source/configure', {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key})
        });
        input.dataset.changeMode = '0';
      } else if (status && status.has_key) {
        data = await request('/api/business-source/test', {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'
        });
      } else {
        throw new Error('本机尚未保存经营数据只读密钥，请先粘贴一次');
      }
      applyBusinessStatus(data);
      if (typeof renderBusinessSource === 'function') renderBusinessSource(data);
      if (typeof loadAnalytics === 'function') await loadAnalytics();
      if (typeof loadSummary === 'function') await loadSummary();
      if (typeof window.loadIntegrations === 'function') await window.loadIntegrations();
      if (typeof toast === 'function') toast('真实经营数据已重新验证；已保存密钥继续复用');
    } catch (error) {
      if (typeof toast === 'function') toast(error.message, 'error');
    } finally {
      button.disabled = false;
      await refreshBusinessPersistence();
    }
  }, true);

  const observer = new MutationObserver(records => {
    const inputWasAdded = records.some(record => [...record.addedNodes].some(node =>
      node.nodeType === Node.ELEMENT_NODE &&
      (node.matches?.('#business-source-key') || node.querySelector?.('#business-source-key'))
    ));
    if (inputWasAdded) scheduleBusinessPersistenceRefresh();
  });
  observer.observe(document.documentElement, {childList: true, subtree: true});
  document.addEventListener('click', event => {
    if (event.target.closest && event.target.closest('[data-page="analytics"], [data-target="analytics"]')) {
      scheduleBusinessPersistenceRefresh(120);
    }
  });
  scheduleBusinessPersistenceRefresh(250);
})();

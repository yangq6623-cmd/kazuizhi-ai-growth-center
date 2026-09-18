(() => {
  const style = document.createElement('style');
  style.id = 'r7-bridge-usability-style';
  style.textContent = `
    #dashboard-bridge-heading{display:flex;justify-content:space-between;align-items:end;gap:14px;margin:14px 0 9px;padding:0 2px}
    #dashboard-bridge-heading h3{margin:2px 0 0;font-size:16px}#dashboard-bridge-heading p{margin:2px 0 0;color:#718096;font-size:11px}
    #dashboard-bridge-strip{grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
    #dashboard-bridge-strip .bridge-dashboard-action{position:relative;min-height:92px;border:1px solid #e2e8f3;border-radius:13px;background:#fff;cursor:pointer;transition:.16s ease;box-shadow:0 2px 8px rgba(32,62,105,.03)}
    #dashboard-bridge-strip .bridge-dashboard-action:hover{transform:translateY(-2px);border-color:#b8cdf7;box-shadow:0 9px 22px rgba(35,82,170,.09)}
    #dashboard-bridge-strip .bridge-dashboard-action:focus{outline:2px solid #7aa3ff;outline-offset:2px}
    #dashboard-bridge-strip .bridge-dashboard-action .bridge-card-action{display:block;margin-top:5px;color:#2d63ce;font-size:10px;font-weight:700}
    #dashboard-bridge-strip .bridge-dashboard-action.is-warning{background:#fffaf2;border-color:#efd6ab}
    #dashboard-bridge-strip .bridge-dashboard-action.is-ready{background:#fbfffd;border-color:#cfe8db}
    #bridge-recovery-detail{margin-top:8px;padding:9px 11px;border-radius:9px;background:#f6f8fc;color:#5d6b80;font-size:11px;line-height:1.55;word-break:break-all}
    #bridge-recovery-detail.warning{background:#fff7e8;color:#8b641f}
    #bridge-recovery-detail.ready{background:#edf9f2;color:#276948}
    #bridge-panel.bridge-focus{animation:bridgeFocus 1.2s ease}
    @keyframes bridgeFocus{0%{box-shadow:0 0 0 0 rgba(49,104,232,.35)}50%{box-shadow:0 0 0 7px rgba(49,104,232,.12)}100%{box-shadow:none}}
    @media(max-width:1120px){#dashboard-bridge-strip{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media(max-width:700px){#dashboard-bridge-strip{grid-template-columns:1fr}#dashboard-bridge-heading{align-items:flex-start;flex-direction:column}}
  `;
  document.head.appendChild(style);

  function bridgeHeading() {
    const strip = document.getElementById('dashboard-bridge-strip');
    if (!strip || document.getElementById('dashboard-bridge-heading')) return;
    const head = document.createElement('div');
    head.id = 'dashboard-bridge-heading';
    head.innerHTML = '<div><small>运行与同步</small><h3>本机、云端与离线运行状态</h3><p>每张卡片都可以点击；同步异常时会给出明确原因和恢复入口。</p></div><span class="status-pill waiting" id="dashboard-bridge-summary">检查中</span>';
    strip.parentNode.insertBefore(head, strip);
  }

  async function waitForBridgePanel(message) {
    if (typeof openPage === 'function') openPage('connections');
    try {
      if (typeof window.loadIntegrations === 'function') await window.loadIntegrations();
    } catch (_) {}
    let panel = document.getElementById('bridge-panel');
    for (let i = 0; !panel && i < 20; i += 1) {
      await new Promise(resolve => setTimeout(resolve, 100));
      panel = document.getElementById('bridge-panel');
    }
    if (panel) {
      panel.scrollIntoView({behavior:'smooth', block:'center'});
      panel.classList.remove('bridge-focus');
      void panel.offsetWidth;
      panel.classList.add('bridge-focus');
    }
    if (typeof toast === 'function' && message) toast(message);
    return panel;
  }

  async function getBridgeStatus() {
    return api('/api/bridge/status');
  }

  async function refreshBridgeViews() {
    const jobs = [];
    if (typeof window.loadIntegrations === 'function') jobs.push(window.loadIntegrations());
    if (typeof window.loadControlCenter === 'function') jobs.push(window.loadControlCenter());
    if (jobs.length) await Promise.all(jobs);
  }

  async function reconnectSavedRoot() {
    const status = await getBridgeStatus();
    if (status.status === 'connected') return status;
    const root = String(status.root || '').trim();
    if (!root) {
      await waitForBridgePanel('请先确认同步目录，再点击“连接双向桥”');
      throw new Error('双向运营桥尚未配置同步目录');
    }
    try {
      return await api('/api/bridge/configure', {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({root})
      });
    } catch (error) {
      await waitForBridgePanel('同步目录仍不可用，已打开连接设置');
      const detail = status.last_error ? `；系统记录：${status.last_error}` : '';
      throw new Error(`无法重新连接同步目录：${root}${detail}`);
    }
  }

  async function syncWithRecovery(button) {
    const label = button ? button.textContent : '';
    if (button) { button.disabled = true; button.textContent = '恢复并同步中…'; }
    try {
      let status = await getBridgeStatus();
      if (status.status !== 'connected') status = await reconnectSavedRoot();
      const data = await api('/api/bridge/sync', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
      await refreshBridgeViews();
      if (!data.synced) throw new Error(data.status?.message || '同步未完成');
      if (typeof toast === 'function') toast(`同步完成，接收 ${data.imported || 0} 条新计划`);
      return data;
    } catch (error) {
      if (typeof toast === 'function') toast(error.message, 'error');
      throw error;
    } finally {
      if (button) { button.disabled = false; button.textContent = label || '立即同步'; }
    }
  }

  async function reportFromDashboard() {
    try {
      const status = await getBridgeStatus();
      if (status.status !== 'connected') {
        await waitForBridgePanel('双向桥未连接，先恢复同步目录后再上报');
        return;
      }
      const data = await api('/api/bridge/report', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
      await refreshBridgeViews();
      if (typeof toast === 'function') toast(data.exported ? '最新本机运营状态已上报' : '上报未完成', data.exported ? 'ok' : 'error');
    } catch (error) {
      if (typeof toast === 'function') toast(error.message, 'error');
    }
  }

  function bindDashboardBridgeActions(node, bridge) {
    node.querySelectorAll('[data-bridge-action]').forEach(card => {
      const action = card.dataset.bridgeAction;
      const activate = async () => {
        if (action === 'report') return reportFromDashboard();
        if (action === 'bridge') return waitForBridgePanel('已打开双向运营桥设置');
        if (action === 'commands') {
          try { await syncWithRecovery(card); } catch (_) {}
          return;
        }
        if (action === 'offline') {
          if (typeof openPage === 'function') openPage('workflow');
          if (typeof window.loadR7 === 'function') window.loadR7();
          if (typeof toast === 'function') toast('已打开本地自动任务；云端桥异常不会停止本地已批准任务');
        }
      };
      card.addEventListener('click', activate);
      card.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); }
      });
    });
  }

  window.renderDashboardBridge = function(bridge) {
    const node = typeof ensureDashboardBridge === 'function' ? ensureDashboardBridge() : document.getElementById('dashboard-bridge-strip');
    if (!node || !bridge) return;
    bridgeHeading();
    const connected = bridge.status === 'connected';
    const degraded = bridge.status === 'degraded';
    const statusText = connected ? '同步正常' : degraded ? '同步需恢复' : '未配置同步';
    const summary = document.getElementById('dashboard-bridge-summary');
    if (summary) { summary.textContent = statusText; summary.className = `status-pill ${connected ? 'ready' : 'waiting'}`; }
    node.innerHTML = `
      <div class="ai-role ai-role-action bridge-dashboard-action ${connected?'is-ready':''}" role="button" tabindex="0" data-bridge-action="report"><span>报</span><div><strong>本机上报</strong><small>${esc(bridge.last_report_at?'最近 '+bridgeTime(bridge.last_report_at):'等待首次同步')}</small><em class="bridge-card-action">${connected?'立即上报 →':'先恢复连接 →'}</em></div><i class="${connected?'ready':'waiting'}">${connected?'可上报':'本地'}</i></div>
      <div class="ai-role ai-role-action bridge-dashboard-action ${connected?'is-ready':degraded?'is-warning':''}" role="button" tabindex="0" data-bridge-action="bridge"><span>云</span><div><strong>双向运营桥</strong><small>${esc(bridge.message)}</small><em class="bridge-card-action">配置 / 检查同步 →</em></div><i class="${connected?'ready':'waiting'}">${esc(bridge.status_label)}</i></div>
      <div class="ai-role ai-role-action bridge-dashboard-action ${bridge.pending_commands?'is-warning':''}" role="button" tabindex="0" data-bridge-action="commands"><span>令</span><div><strong>AI 指令箱</strong><small>${esc(String(bridge.pending_commands||0))} 条等待导入</small><em class="bridge-card-action">立即同步 / 查看 →</em></div><i class="${bridge.pending_commands?'waiting':'ready'}">${bridge.pending_commands?'待处理':'正常'}</i></div>
      <div class="ai-role ai-role-action bridge-dashboard-action is-ready" role="button" tabindex="0" data-bridge-action="offline"><span>离</span><div><strong>离线运行</strong><small>云端不可用时不停止本地已批准任务</small><em class="bridge-card-action">查看本地任务 →</em></div><i class="ready">${esc(bridge.operating_mode_label)}</i></div>`;
    bindDashboardBridgeActions(node, bridge);
  };

  const originalRenderBridgePanel = window.renderBridgePanel;
  function enhanceBridgePanel(bridge) {
    const panel = document.getElementById('bridge-panel');
    if (!panel) return;
    const row = panel.querySelector('.button-row');
    let reconnect = document.getElementById('reconnect-bridge');
    if (row && !reconnect) {
      reconnect = document.createElement('button');
      reconnect.id = 'reconnect-bridge';
      reconnect.className = 'outline-button';
      reconnect.textContent = '重新连接并同步';
      const sync = document.getElementById('sync-bridge');
      row.insertBefore(reconnect, sync || row.firstChild);
      reconnect.addEventListener('click', async () => { try { await syncWithRecovery(reconnect); } catch (_) {} });
    }
    let detail = document.getElementById('bridge-recovery-detail');
    if (!detail) {
      detail = document.createElement('div'); detail.id = 'bridge-recovery-detail';
      const message = document.getElementById('bridge-message');
      (message || panel).insertAdjacentElement('afterend', detail);
    }
    const root = String(bridge?.root || '').trim();
    const connected = bridge?.status === 'connected';
    detail.className = connected ? 'ready' : 'warning';
    if (connected) detail.textContent = `当前同步目录：${root || '已连接'}。可直接点击“立即同步”或“立即上报”。`;
    else if (root) detail.textContent = `已保存同步目录：${root}。${bridge?.last_error ? '最近错误：' + bridge.last_error + '。' : ''} 可点击“重新连接并同步”恢复。`;
    else detail.textContent = '尚未保存同步目录。请填写 Google Drive、OneDrive 或其它 Windows 本地同步目录后连接。';
    const sync = document.getElementById('sync-bridge');
    if (sync && !sync.dataset.recoveryBound) {
      const clone = sync.cloneNode(true);
      clone.dataset.recoveryBound = '1';
      sync.replaceWith(clone);
      clone.addEventListener('click', async () => { try { await syncWithRecovery(clone); } catch (_) {} });
    }
  }

  if (typeof originalRenderBridgePanel === 'function') {
    window.renderBridgePanel = function(bridge) {
      originalRenderBridgePanel(bridge);
      enhanceBridgePanel(bridge);
    };
  }

  const existingPanel = document.getElementById('bridge-panel');
  if (existingPanel) getBridgeStatus().then(enhanceBridgePanel).catch(() => {});
  if (typeof window.loadControlCenter === 'function') window.loadControlCenter().catch(() => {});
})();

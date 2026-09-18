function splitItems(value) {
  return value.split(/[；;\n]+/).map(item => item.trim()).filter(Boolean);
}

async function refreshCompleted() {
  const summary = await api('/api/operation-summary/today');
  const items = summary.completed_items || [];
  $('today-completed').className = items.length ? '' : 'empty';
  $('today-completed').innerHTML = items.length
    ? `<ul>${items.map(item => `<li>${esc(item)}</li>`).join('')}</ul>`
    : '尚未记录完成事项';
}

$('save-today').addEventListener('click', async () => {
  const items = splitItems($('today-input').value);
  if (!items.length) return toast('请先填写今日已完成事项','error');
  try {
    await api('/api/operation-summary', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({completed_items: items})});
    $('today-input').value = '';
    await Promise.all([loadSummary(), loadHistory(), refreshCompleted()]);
    toast('今日运营总结已保存');
  } catch (error) { toast(error.message,'error'); }
});

refreshCompleted().catch(error => toast(error.message));

$('save-plan').addEventListener('click', async () => {
  const items = splitItems($('plan-input').value);
  if (!items.length) return toast('请先填写明日任务','error');
  try {
    await api('/api/tomorrow-plan', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tasks: items})});
    $('plan-input').value = '';
    await Promise.all([loadPlan(), loadHistory()]);
    toast('明日计划已保存为待审核建议');
  } catch (error) { toast(error.message,'error'); }
});

// Compact feedback policy: ordinary success messages use only the small corner toast.
// Keep the wide status bar only for errors that genuinely need attention.
toast = function(message, type='ok') {
  const feedback = $('action-feedback');
  if (feedback) {
    if (type === 'error') {
      feedback.textContent = '需要处理：' + message;
      feedback.className = 'action-feedback error';
      feedback.hidden = false;
    } else {
      feedback.hidden = true;
      feedback.textContent = '';
      feedback.className = 'action-feedback';
    }
  }
  const popup = $('toast');
  if (!popup) return;
  popup.textContent = message;
  popup.className = `show ${type}`;
  const duration = type === 'error' ? 5200 : 2600;
  setTimeout(() => popup.className = '', duration);
};

// Load the manager-focused R7 enhancements after r7.js. The previous loader
// only refreshed R7 when the workflow page happened to be open at the exact
// moment this file finished loading. That left the KPI cards rendered by the
// base UI without their click handlers until a later refresh. Always apply the
// patch immediately and refresh R7 once so the four manager KPI cards work on
// the first visit, not only after waiting for the 15-second scheduler refresh.
(() => {
  if (document.querySelector('script[data-r7-manager-patch]')) return;
  const script = document.createElement('script');
  script.src = 'r7_manager_patch.js';
  script.async = false;
  script.dataset.r7ManagerPatch = '1';
  script.onload = () => {
    try {
      if (typeof applyAutonomyCopy === 'function') applyAutonomyCopy();
      if (typeof loadR7 === 'function') loadR7();
    } catch (error) {
      toast('AI 员工管理增强模块初始化失败：' + error.message, 'error');
    }
  };
  script.onerror = () => toast('AI 员工管理增强模块加载失败，请重新安装最新版本', 'error');
  document.body.appendChild(script);
})();

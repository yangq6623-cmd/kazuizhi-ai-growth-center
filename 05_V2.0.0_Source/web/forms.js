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
  if (!items.length) return toast('请先填写今日已完成事项');
  try {
    await api('/api/operation-summary', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({completed_items: items})});
    $('today-input').value = '';
    await Promise.all([loadSummary(), loadHistory(), refreshCompleted()]);
    toast('今日运营总结已保存');
  } catch (error) { toast(error.message); }
});

refreshCompleted().catch(error => toast(error.message));

$('save-plan').addEventListener('click', async () => {
  const items = splitItems($('plan-input').value);
  if (!items.length) return toast('请先填写明日任务');
  try {
    await api('/api/tomorrow-plan', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tasks: items})});
    $('plan-input').value = '';
    await Promise.all([loadPlan(), loadHistory()]);
    toast('明日计划已保存为待审核建议');
  } catch (error) { toast(error.message); }
});

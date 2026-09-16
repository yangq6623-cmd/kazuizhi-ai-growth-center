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

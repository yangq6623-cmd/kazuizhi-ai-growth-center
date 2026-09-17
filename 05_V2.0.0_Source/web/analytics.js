const metricLabels = {
  mini_program_visits: '小程序访问', repair_requests: '维修需求', new_users: '新增用户', leads: '有效线索',
  new_orders: '新增订单', completed_orders: '完成订单', cancelled_orders: '取消订单',
  new_technicians: '新增师傅', approved_technicians: '审核通过师傅', active_technicians: '活跃师傅', technician_inquiries: '师傅咨询',
  new_leaders: '新增团长', active_leaders: '活跃团长', leader_referrals: '团长引导需求', leader_orders: '团长贡献订单',
  visit_to_request_pct: '访问到需求', request_to_lead_pct: '需求到线索', request_to_order_pct: '需求到订单',
  order_to_complete_pct: '订单完成率', order_cancel_pct: '订单取消率', inquiry_to_approval_pct: '咨询到审核通过', referral_to_order_pct: '引导到订单',
};

function showValue(value, suffix = '') {
  return value === null || value === undefined ? '<b class="missing-value">未接入</b>' : `<b>${esc(value)}${suffix}</b>`;
}

function renderModule(id, module) {
  const values = Object.entries(module.values || {});
  const rates = Object.entries(module.rates || {});
  if (module.status !== 'verified') {
    $(id).className = 'empty';
    $(id).textContent = '该项真实数据尚未接入';
    return;
  }
  $(id).className = 'analysis-body';
  $(id).innerHTML = `<div class="analysis-values">${values.map(([key, value]) => `<div>${showValue(value)}<small>${esc(metricLabels[key] || key)}</small></div>`).join('')}</div>`
    + (rates.length ? `<div class="rate-list">${rates.map(([key, value]) => `<span>${esc(metricLabels[key] || key)} ${value === null ? '数据不足' : `${esc(value)}%`}</span>`).join('')}</div>` : '');
}

function renderChannels(module) {
  const channels = module.breakdown?.channels || [];
  if (!channels.length) {
    $('channel-effect').className = 'empty';
    $('channel-effect').textContent = '渠道访问和订单归因数据尚未接入';
    return;
  }
  $('channel-effect').className = 'channel-table';
  $('channel-effect').innerHTML = '<div class="channel-row channel-header"><span>渠道</span><span>访问</span><span>订单</span><span>转化率</span></div>'
    + channels.map(row => `<div class="channel-row"><strong>${esc(row.channel)}</strong><span>${row.visits ?? '未接入'}</span><span>${row.orders ?? '未接入'}</span><span>${row.conversion_pct === null ? '数据不足' : `${esc(row.conversion_pct)}%`}</span></div>`).join('');
}

async function loadAnalytics() {
  const data = await api('/api/business-analytics');
  const connected = data.status === 'verified';
  const completeness = data.completeness || {present:0,total:0,ratio_pct:0,missing_fields:[]};
  $('analytics-status').textContent = connected ? `已连接已验证经营快照 · 完整度 ${completeness.present}/${completeness.total}` : '真实经营数据尚未接入';
  $('analytics-source').textContent = connected
    ? `来源：${data.source} · 截止：${data.as_of} · 统计窗口：${data.window || '未说明'} · 完整度：${completeness.ratio_pct}%`
    : `${data.message} 需要来源 source、统计时间 as_of 和聚合指标；不接收手机号、地址、身份、密钥或资金明细。`;
  $('analytics-badge').textContent = connected ? (completeness.ratio_pct >= 80 ? '已验证' : '已验证·部分数据') : '待接入';
  $('analytics-badge').className = connected ? 'chip verified' : 'chip';
  $('analytics-truth').textContent = connected && completeness.missing_fields?.length
    ? `${data.truth_rule} 当前仍缺 ${completeness.missing_fields.length} 类聚合指标，缺失项不会用 0 或推测值代替。`
    : data.truth_rule;
  renderModule('user-growth', data.modules.user_growth);
  renderModule('order-conversion', data.modules.order_conversion);
  renderModule('technician-supply', data.modules.technician_supply);
  renderModule('leader-promotion', data.modules.leader_promotion);
  renderChannels(data.modules.channel_effect);
}

$('import-business').addEventListener('click', async () => {
  let payload;
  try {
    payload = JSON.parse($('business-json').value);
  } catch (_error) {
    return toast('请粘贴带来源和统计时间的经营汇总 JSON；当前内容格式不正确','error');
  }
  try {
    const imported = await api('/api/business-metrics/import', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    $('business-json').value = '';
    await Promise.all([loadAnalytics(), loadSummary()]);
    const completeness = imported.completeness || {};
    toast(`已导入并验证经营汇总${completeness.total ? ` · 完整度 ${completeness.present}/${completeness.total}` : ''}`);
  } catch (error) {
    toast(error.message,'error');
  }
});

loadAnalytics().catch(error => toast(error.message));

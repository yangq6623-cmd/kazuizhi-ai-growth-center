const metricLabels = {
  mini_program_visits: '小程序访问', repair_requests: '维修需求', new_users: '新增用户', leads: '有效线索',
  new_orders: '新增订单', completed_orders: '完成订单', cancelled_orders: '取消订单',
  new_technicians: '新增师傅', approved_technicians: '审核通过师傅', active_technicians: '活跃师傅', technician_inquiries: '师傅咨询',
  new_leaders: '新增团长', active_leaders: '活跃团长', leader_referrals: '团长引导需求', leader_orders: '团长贡献订单',
  visit_to_request_pct: '访问到需求', request_to_lead_pct: '需求到线索', request_to_order_pct: '需求到订单',
  order_to_complete_pct: '订单完成率', order_cancel_pct: '订单取消率', inquiry_to_approval_pct: '咨询到审核通过', referral_to_order_pct: '引导到订单',
};

const CORE_BUSINESS_FIELDS = [
  'mini_program_visits', 'repair_requests', 'new_users', 'leads',
  'new_orders', 'completed_orders', 'cancelled_orders',
];

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

function applyCoreAnalyticsLayout() {
  const page = $('analytics');
  if (!page) return;
  const title = page.querySelector('.page-title h2');
  const intro = page.querySelector('.page-title p');
  if (title) title.textContent = '核心经营分析';
  if (intro) intro.textContent = '重点看用户增长和订单转化；师傅、团长、渠道等真实汇总保留在上方辅助数据中，不占核心分析区。';
  ['technician-supply', 'leader-promotion', 'channel-effect'].forEach(id => {
    const article = $(id)?.closest('article');
    if (article) article.style.display = 'none';
  });
}

function coreBusinessSnapshot(source) {
  const s = source?.summary || {};
  const users = s.users || {};
  const orders = s.orders || {};
  return {
    mini_program_visits: null,
    repair_requests: null,
    new_users: users.new_today ?? null,
    leads: null,
    new_orders: orders.today ?? null,
    completed_orders: orders.completed ?? null,
    cancelled_orders: orders.cancelled ?? null,
  };
}

function coreCompleteness(source) {
  const snapshot = coreBusinessSnapshot(source);
  const present = CORE_BUSINESS_FIELDS.filter(key => snapshot[key] !== null && snapshot[key] !== undefined);
  return {
    present: present.length,
    total: CORE_BUSINESS_FIELDS.length,
    ratio_pct: Math.round(present.length * 1000 / CORE_BUSINESS_FIELDS.length) / 10,
    missing_fields: CORE_BUSINESS_FIELDS.filter(key => !present.includes(key)),
  };
}

function renderCoreBusinessMetrics(source) {
  const snapshot = coreBusinessSnapshot(source);
  $('user-growth').className = 'analysis-body';
  $('user-growth').innerHTML = `<div class="analysis-values">
    <div>${showValue(snapshot.mini_program_visits)}<small>小程序访问</small></div>
    <div>${showValue(snapshot.repair_requests)}<small>维修需求</small></div>
    <div>${showValue(snapshot.new_users)}<small>今日新增用户</small></div>
    <div>${showValue(snapshot.leads)}<small>有效线索</small></div>
  </div><div class="rate-list"><span>只显示真实来源；缺失数据不以 0 或估算值补齐</span></div>`;

  $('order-conversion').className = 'analysis-body';
  $('order-conversion').innerHTML = `<div class="analysis-values">
    <div>${showValue(snapshot.repair_requests)}<small>维修需求</small></div>
    <div>${showValue(snapshot.new_orders)}<small>今日新增订单</small></div>
    <div>${showValue(snapshot.completed_orders)}<small>累计已完成订单</small></div>
    <div>${showValue(snapshot.cancelled_orders)}<small>累计取消订单</small></div>
  </div><div class="rate-list"><span>今日新增与累计状态属于不同统计窗口，不跨窗口计算虚假转化率</span></div>`;
}

function ensureLiveBusinessPanel() {
  let panel = $('live-business-panel');
  if (panel) return panel;
  const analytics = $('analytics');
  const anchor = analytics?.querySelector('.analytics-head');
  if (!analytics || !anchor) return null;
  panel = document.createElement('article');
  panel.id = 'live-business-panel';
  panel.className = 'wide ai-command-card';
  panel.innerHTML = `
    <div class="article-head"><div><label>真实经营数据 · 生产只读接口</label><h3>卡嘴子服务器实时经营汇总</h3></div><span id="business-source-badge" class="status-pill waiting">检查中</span></div>
    <div class="content-form">
      <label>服务器接口<input id="business-source-endpoint" value="https://kazuizhi.com/ai-business-summary.ashx" readonly></label>
      <label>只读密钥<input id="business-source-key" type="password" maxlength="500" autocomplete="new-password" placeholder="粘贴服务器 SHOW_READONLY_KEY.bat 显示的密钥"></label>
      <small class="form-help">只需粘贴一次。密钥仅保存在本机并使用 Windows 当前用户加密；不会写入 GitHub、日志或经营快照。</small>
      <div class="button-row"><button id="save-business-source" class="primary-button">连接并验证</button><button id="refresh-business-source" class="outline-button">立即刷新真实数据</button></div>
    </div>
    <div id="business-source-message" class="notice">服务器只读接口已经部署，等待本机 R7 完成密钥验证。</div>
    <div id="business-source-summary" class="analysis-body"></div>`;
  anchor.insertAdjacentElement('afterend', panel);
  $('save-business-source').addEventListener('click', saveBusinessSource);
  $('refresh-business-source').addEventListener('click', refreshBusinessSource);
  return panel;
}

function businessStat(label, value) {
  return `<div><b>${value === null || value === undefined ? '—' : esc(value)}</b><small>${esc(label)}</small></div>`;
}

function renderBusinessSource(data) {
  ensureLiveBusinessPanel();
  if (!data) return;
  const connected = data.status === 'connected';
  $('business-source-badge').textContent = data.status_label || (connected ? '已验证接入' : '未配置');
  $('business-source-badge').className = `status-pill ${connected ? 'ready' : 'waiting'}`;
  $('business-source-key').placeholder = data.has_key ? '只读密钥已加密保存；无需重复填写' : '粘贴服务器 SHOW_READONLY_KEY.bat 显示的密钥';
  $('business-source-message').textContent = `${data.message || ''}${data.remote_as_of ? ` · 数据截止：${data.remote_as_of}` : ''}`;
  const s = data.summary || {};
  const u = s.users || {}, o = s.orders || {}, t = s.technicians || {}, p = s.partners || {}, promotion = s.promotion || {};
  const q = data.data_quality || {};
  $('business-source-summary').innerHTML = connected ? `
    <div class="analysis-values">
      ${businessStat('用户总数', u.total)}${businessStat('今日新增用户', u.new_today)}
      ${businessStat('订单总数', o.total)}${businessStat('今日订单', o.today)}${businessStat('进行中订单', o.open)}${businessStat('已完成订单', o.completed)}
      ${businessStat('师傅总数', t.total)}${businessStat('活跃师傅', t.active)}
      ${businessStat('团长总数', p.total)}${businessStat('活跃团长', p.active)}
      ${businessStat('推广记录', promotion.event_records)}${businessStat('团长归因订单', promotion.partner_attributed_orders)}
    </div>
    <div class="rate-list"><span>只读：${q.read_only === true ? '已验证' : '待验证'}</span><span>写操作：${esc(q.write_operations ?? '—')}</span><span>数据完整：${esc(q.required_documents_present ?? '—')}/${esc(q.required_documents_total ?? '—')}</span></div>`
    : '<div class="empty">连接验证通过后，这里显示生产服务器的真实经营汇总。</div>';
}

async function loadBusinessSource() {
  ensureLiveBusinessPanel();
  try {
    const data = await api('/api/business-source/status');
    renderBusinessSource(data);
    return data;
  } catch (error) {
    $('business-source-message').textContent = error.message;
    return null;
  }
}

async function saveBusinessSource() {
  const key = $('business-source-key').value.trim();
  if (!key) { toast('请粘贴服务器生成的经营数据只读密钥','error'); return; }
  const button = $('save-business-source'); button.disabled = true; button.textContent = '连接验证中…';
  try {
    const data = await api('/api/business-source/configure', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({key})});
    $('business-source-key').value = '';
    renderBusinessSource(data);
    await Promise.all([loadAnalytics(), window.loadIntegrations ? window.loadIntegrations() : Promise.resolve(), loadSummary()]);
    toast('真实经营数据已验证接入；以后每 5 分钟自动刷新');
  } catch (error) { toast(error.message,'error'); }
  finally { button.disabled = false; button.textContent = '连接并验证'; }
}

async function refreshBusinessSource() {
  const button = $('refresh-business-source'); button.disabled = true; button.textContent = '刷新中…';
  try {
    const data = await api('/api/business-source/refresh', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    renderBusinessSource(data);
    await Promise.all([loadAnalytics(), window.loadIntegrations ? window.loadIntegrations() : Promise.resolve(), loadSummary()]);
    toast('生产经营数据已刷新');
  } catch (error) { toast(error.message,'error'); }
  finally { button.disabled = false; button.textContent = '立即刷新真实数据'; }
}

async function loadAnalytics() {
  applyCoreAnalyticsLayout();
  const [data, source] = await Promise.all([api('/api/business-analytics'), api('/api/business-source/status')]);
  const connected = source?.status === 'connected' || data.status === 'verified';
  const core = source?.status === 'connected' ? coreCompleteness(source) : {present:0,total:CORE_BUSINESS_FIELDS.length,ratio_pct:0,missing_fields:[...CORE_BUSINESS_FIELDS]};
  $('analytics-status').textContent = connected
    ? `真实经营数据已验证接入 · 核心经营数据完整度 ${core.present}/${core.total}`
    : '真实经营数据尚未接入';
  $('analytics-source').textContent = connected
    ? `来源：${source?.source || data.source} · 截止：${source?.remote_as_of || data.as_of} · 核心完整度：${core.ratio_pct}%`
    : `${data.message} 核心分析只关注用户增长和订单转化；缺失项保持“未接入”。`;
  $('analytics-badge').textContent = connected ? (core.present === core.total ? '已验证·核心齐全' : '已验证·部分核心数据') : '待接入';
  $('analytics-badge').className = connected ? 'chip verified' : 'chip';
  $('analytics-truth').textContent = connected && core.missing_fields.length
    ? `只显示已验证真实数据；核心分析仍缺 ${core.missing_fields.length} 项，不会用 0、估算值或公开市场信号代替。`
    : '只显示已验证真实数据；不接收手机号、地址、身份、密钥或资金明细。';

  if (source?.status === 'connected') {
    renderCoreBusinessMetrics(source);
  } else {
    renderModule('user-growth', data.modules.user_growth);
    renderModule('order-conversion', data.modules.order_conversion);
  }
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

document.addEventListener('click', event => {
  const card = event.target.closest?.('.integration-card-action[data-integration="business_data"]');
  if (!card) return;
  event.preventDefault(); event.stopImmediatePropagation();
  openPage('analytics');
  setTimeout(() => { $('live-business-panel')?.scrollIntoView({behavior:'smooth',block:'center'}); toast('已打开真实经营数据只读连接'); }, 0);
}, true);

applyCoreAnalyticsLayout();
ensureLiveBusinessPanel();
Promise.all([loadBusinessSource(), loadAnalytics()]).catch(error => toast(error.message));

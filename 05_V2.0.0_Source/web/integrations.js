const STATUS_STYLE={ready:'ready',connected:'ready',configured:'waiting',manual:'waiting',degraded:'waiting',not_connected:'waiting',not_configured:'waiting',blocked:'blocked'};
const CONTROL_ROLE_TARGETS=['analytics','review','promotion','summary'];

function renderStatusPill(item){return `<span class="status-pill ${STATUS_STYLE[item.status]||'waiting'}">${esc(item.status_label)}</span>`}
function bridgeTime(value){return value?formatTime(value):'暂无'}

function ensureDashboardBridge(){
  let node=$('dashboard-bridge-strip');
  if(node)return node;
  const loop=$('operation-loop');
  if(!loop)return null;
  node=document.createElement('div');
  node.id='dashboard-bridge-strip';
  node.className='ai-role-grid';
  loop.insertAdjacentElement('afterend',node);
  return node;
}

function renderDashboardBridge(bridge){
  const node=ensureDashboardBridge();if(!node||!bridge)return;
  node.innerHTML=`
    <div class="ai-role ai-role-action bridge-dashboard-action" role="button" tabindex="0"><span>报</span><div><strong>本机上报</strong><small>${esc(bridge.last_report_at?'最近 '+bridgeTime(bridge.last_report_at):'等待首次同步')}</small></div><i class="${bridge.status==='connected'?'ready':'waiting'}">${bridge.status==='connected'?'自动':'本地'}</i></div>
    <div class="ai-role ai-role-action bridge-dashboard-action" role="button" tabindex="0"><span>云</span><div><strong>双向运营桥</strong><small>${esc(bridge.message)}</small></div><i class="${bridge.status==='connected'?'ready':'waiting'}">${esc(bridge.status_label)}</i></div>
    <div class="ai-role ai-role-action bridge-dashboard-action" role="button" tabindex="0"><span>令</span><div><strong>AI 指令箱</strong><small>${esc(String(bridge.pending_commands||0))} 条等待导入</small></div><i class="${bridge.pending_commands?'waiting':'ready'}">${bridge.pending_commands?'待处理':'正常'}</i></div>
    <div class="ai-role ai-role-action bridge-dashboard-action" role="button" tabindex="0"><span>离</span><div><strong>离线运行</strong><small>云端不可用时不停止本地已批准任务</small></div><i class="ready">${esc(bridge.operating_mode_label)}</i></div>`;
  node.querySelectorAll('.bridge-dashboard-action').forEach(card=>{
    const activate=()=>{openPage('connections');setTimeout(()=>{$('bridge-panel')?.scrollIntoView({behavior:'smooth',block:'center'});toast('已打开双向运营桥')},0)};
    card.addEventListener('click',activate);card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate()}});
  });
}

async function loadControlCenter(){
  const data=await api('/api/control-center');
  $('control-headline').textContent=data.headline;
  const connected=data.external_ai.status==='connected';
  $('external-ai-badge').textContent=data.bridge?.status==='connected'?'双向桥已连接':connected?'外部 AI 已连接':'本地自主运行';
  $('external-ai-badge').className=`status-pill ${(data.bridge?.status==='connected'||connected)?'ready':'waiting'}`;
  $('ai-role-grid').innerHTML=data.roles.map((role,index)=>`<div class="ai-role ai-role-action" role="button" tabindex="0" data-target="${CONTROL_ROLE_TARGETS[index]||'workflow'}"><span>${['数','策','内','营'][index]}</span><div><strong>${esc(role.name)}</strong><small>${esc(role.purpose)}</small></div><i class="${role.status}">${role.status==='ready'?'可用':'待数据'}</i></div>`).join('');
  document.querySelectorAll('#ai-role-grid .ai-role-action').forEach(card=>{
    const activate=()=>{openPage(card.dataset.target);toast(`已打开${card.querySelector('strong')?.textContent||'AI'}对应模块`)};
    card.addEventListener('click',activate);
    card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate()}});
  });
  $('operation-loop').innerHTML=data.loop.map((step,index)=>`<div><b>${index+1}</b><span>${esc(step)}</span>${index<data.loop.length-1?'<em>→</em>':''}</div>`).join('');
  renderDashboardBridge(data.bridge);
}

function integrationCard(item){
  const icons={local_engine:'本',external_ai:'AI',business_data:'数',operations_bridge:'桥',publishing:'发',finance:'禁'};
  return `<article class="integration-card integration-card-action ${esc(item.status)}" role="button" tabindex="0" data-integration="${esc(item.id)}" title="点击查看或处理 ${esc(item.name)}"><div class="integration-icon">${icons[item.id]||'连'}</div><div><strong>${esc(item.name)}</strong><p>${esc(item.message)}</p></div>${renderStatusPill(item)}</article>`;
}

function ensureBridgePanel(){
  let panel=$('bridge-panel');if(panel)return panel;
  const grid=$('integration-grid');if(!grid)return null;
  panel=document.createElement('article');
  panel.id='bridge-panel';panel.className='wide ai-command-card';
  panel.innerHTML=`<div class="article-head"><div><label>ChatGPT / 云端双向运营桥</label><h3>本机上报 · AI计划接收 · 执行回执 · 离线自主运行</h3></div><span id="bridge-badge" class="status-pill waiting">未配置</span></div>
    <div class="ai-role-grid" id="bridge-status-grid"></div>
    <div class="content-form"><label>本地同步目录 <b>*</b><input id="bridge-root" maxlength="500" placeholder="例如：D:\\Google Drive\\卡嘴子AI同步"></label><small class="form-help">可填写 Google Drive、OneDrive 或其它已在 Windows 同步的本地目录。R7 核心不绑定某一家云盘。</small><div class="button-row"><button id="save-bridge" class="primary-button">连接双向桥</button><button id="sync-bridge" class="outline-button">立即同步</button><button id="report-bridge" class="outline-button">立即上报</button><button id="disable-bridge" class="text-button">停用桥接</button></div></div>
    <div id="bridge-message" class="notice">未配置时系统仍以“本地自主运行”模式继续执行已经批准的低风险任务。</div>`;
  grid.insertAdjacentElement('afterend',panel);
  $('save-bridge').addEventListener('click',saveBridge);
  $('sync-bridge').addEventListener('click',syncBridge);
  $('report-bridge').addEventListener('click',reportBridge);
  $('disable-bridge').addEventListener('click',disableBridge);
  return panel;
}

function renderBridgePanel(bridge){
  const panel=ensureBridgePanel();if(!panel||!bridge)return;
  $('bridge-root').value=bridge.root||'';
  $('bridge-badge').textContent=bridge.status_label;
  $('bridge-badge').className=`status-pill ${bridge.status==='connected'?'ready':'waiting'}`;
  $('bridge-message').textContent=bridge.message+' '+bridge.offline_policy;
  $('bridge-status-grid').innerHTML=`
    <div class="ai-role"><span>报</span><div><strong>本机上报</strong><small>${esc(bridgeTime(bridge.last_report_at))}</small></div><i class="${bridge.last_report_at?'ready':'waiting'}">${bridge.last_report_at?'已有':'等待'}</i></div>
    <div class="ai-role"><span>同</span><div><strong>最近同步</strong><small>${esc(bridgeTime(bridge.last_sync_at))}</small></div><i class="${bridge.status==='connected'?'ready':'waiting'}">${esc(bridge.status_label)}</i></div>
    <div class="ai-role"><span>令</span><div><strong>待接收指令</strong><small>去重后等待转换的计划</small></div><i class="${bridge.pending_commands?'waiting':'ready'}">${esc(String(bridge.pending_commands||0))} 条</i></div>
    <div class="ai-role"><span>模</span><div><strong>当前运行模式</strong><small>桥断开也不会停止已批准本地任务</small></div><i class="ready">${esc(bridge.operating_mode_label)}</i></div>`;
}

function ensureEvidenceLedgerPanel(){
  let panel=$('evidence-ledger-panel');if(panel)return panel;
  const grid=$('integration-grid');if(!grid)return null;
  panel=document.createElement('article');
  panel.id='evidence-ledger-panel';panel.className='wide ai-command-card';
  panel.innerHTML=`<div class="article-head"><div><label>R8-18 平台升级底座</label><h3>版本身份与增长证据总账</h3></div><span id="evidence-ledger-badge" class="status-pill waiting">候选源码</span></div>
    <div id="release-provenance-grid" class="ai-role-grid"></div>
    <div id="evidence-ledger-summary" class="notice">正在读取已有本地证据…</div>
    <div class="button-row"><button id="refresh-evidence-ledger" class="outline-button">汇总已有证据</button></div>
    <div id="evidence-ledger-events" class="r7-audit-list friendly-empty">尚未汇总；不会自动执行搜索提交或外部发布。</div>`;
  const anchor=$('bridge-panel')||grid;
  anchor.insertAdjacentElement('afterend',panel);
  $('refresh-evidence-ledger').addEventListener('click',refreshEvidenceLedger);
  return panel;
}

function evidenceKindLabel(kind){
  return ({search_submission_receipt:'搜索提交回执',crawl_evidence:'抓取证据',index_evidence:'收录证据',geo_observation:'GEO 观察',business_snapshot:'经营只读快照',mission_receipt:'Mission 回执',search_connector_run:'搜索连接器运行记录'})[kind]||kind||'未知记录';
}

function renderEvidenceLedger(manifest, ledger){
  const panel=ensureEvidenceLedgerPanel();if(!panel)return;
  const baseline=manifest?.baseline||{};const candidate=manifest?.candidate||{};const summary=ledger?.summary||{};
  // Reaching this API proves that the R8-18 runtime is present.  The manifest is
  // deliberately source-controlled, so its package_status must not make an
  // installed candidate package look like an unbuilt source tree.
  const candidateRuntime=Boolean(candidate.release);
  $('evidence-ledger-badge').textContent=candidateRuntime?'R8-18 测试运行中':'候选源码';
  $('evidence-ledger-badge').className=`status-pill ${candidateRuntime?'ready':'waiting'}`;
  $('release-provenance-grid').innerHTML=`
    <div class="ai-role"><span>76</span><div><strong>当前已安装底座</strong><small>${esc(baseline.installed_release||'待核验')} · ${esc(baseline.commit||'')}</small></div><i class="ready">已安装</i></div>
    <div class="ai-role"><span>18</span><div><strong>当前候选升级</strong><small>${esc(candidate.scope||'待定义')}</small></div><i class="${candidateRuntime?'ready':'waiting'}">${candidateRuntime?'测试运行':'候选源码'}</i></div>
    <div class="ai-role"><span>证</span><div><strong>已汇总外部证据</strong><small>提交、抓取、收录、引用与经营快照分别统计</small></div><i class="${summary.external?'ready':'waiting'}">${esc(String(summary.external||0))} 条</i></div>
    <div class="ai-role"><span>模</span><div><strong>本地模型</strong><small>本阶段不下载、不部署、不配置密钥</small></div><i class="waiting">稍后部署</i></div>`;
  const kinds=Object.entries(summary.by_kind||{}).map(([name,count])=>`${evidenceKindLabel(name)} ${count} 条`).join(' · ')||'暂无可追溯外部证据';
  $('evidence-ledger-summary').textContent=`总账 ${summary.total||0} 条，其中外部证据 ${summary.external||0} 条。${kinds}。${ledger?.truth||''}`;
  const events=(ledger?.events||[]).slice(0,8);
  $('evidence-ledger-events').innerHTML=events.length?events.map(row=>`<div class="r7-audit-row"><i class="${row.external?'ready':'waiting'}"></i><div><strong>${esc(evidenceKindLabel(row.kind))}</strong><p>${esc(row.source||'')} · ${esc(row.reference||'无引用')}</p></div><time>${esc(formatTime(row.observed_at)||'')}</time></div>`).join(''):'尚未汇总；点击“汇总已有证据”只读取并整理本机既有记录，不会执行外部动作。';
}

async function loadEvidenceLedger(){
  try{
    const [manifest,ledger]=await Promise.all([api('/api/r8-18/release-manifest'),api('/api/r8-18/evidence-ledger')]);
    renderEvidenceLedger(manifest,ledger);
  }catch(error){
    // The R8-18 candidate API is absent on the installed #76 package. Keep the
    // normal connection screen available and avoid presenting the candidate as installed.
    const panel=ensureEvidenceLedgerPanel();if(panel){$('evidence-ledger-summary').textContent='当前安装包尚未包含 R8-18 证据总账；#76 继续正常运行，候选功能尚未打包。';}
  }
}

async function refreshEvidenceLedger(){
  const button=$('refresh-evidence-ledger');button.disabled=true;button.textContent='汇总中…';
  try{
    const data=await api('/api/r8-18/evidence-ledger/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    await loadEvidenceLedger();
    toast(`已汇总 ${data.result?.added||0} 条既有证据；未执行外部提交或发布`);
  }catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='汇总已有证据'}
}

function bindIntegrationCards(){
  document.querySelectorAll('.integration-card-action').forEach(card=>{
    const activate=async()=>{
      const id=card.dataset.integration;
      if(id==='local_engine'){toast('正在执行本地系统体检');await runDiagnostics();return}
      if(id==='external_ai'){
        if(typeof window.kzOpenModelConnectionCenter==='function'){window.kzOpenModelConnectionCenter();return}
        $('ai-base-url')?.scrollIntoView({behavior:'smooth',block:'center'});toast('已定位到外部大模型配置');return
      }
      if(id==='business_data'){openPage('analytics');setTimeout(()=>{$('business-json')?.scrollIntoView({behavior:'smooth',block:'center'});toast('真实经营数据尚未实时接入；当前支持导入已验证聚合快照')},0);return}
      if(id==='operations_bridge'){$('bridge-panel')?.scrollIntoView({behavior:'smooth',block:'center'});toast('已定位到双向运营桥');return}
      if(id==='publishing'){openPage('promotion');toast('内容发布目前仍是人工审核模式；R7 不会自动对外发布');return}
      if(id==='finance'){toast('资金操作按安全策略永久禁止自动执行','error');return}
      toast('该连接当前没有可执行操作','error');
    };
    card.addEventListener('click',activate);
    card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate()}});
  });
}

async function saveBridge(){
  const root=$('bridge-root').value.trim();if(!root){toast('请填写 Windows 本地同步目录','error');return}
  const button=$('save-bridge');button.disabled=true;button.textContent='连接中…';
  try{await api('/api/bridge/configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({root})});await Promise.all([refreshIntegrations(),loadControlCenter()]);toast('双向运营桥已连接')}
  catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='连接双向桥'}
}
async function syncBridge(){const button=$('sync-bridge');button.disabled=true;button.textContent='同步中…';try{const data=await api('/api/bridge/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await Promise.all([refreshIntegrations(),loadControlCenter()]);toast(data.synced?`同步完成，接收 ${data.imported||0} 条新计划`:'当前未连接云端桥，已保持本地自主运行',data.synced?'ok':'error')}catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='立即同步'}}
async function reportBridge(){const button=$('report-bridge');button.disabled=true;button.textContent='上报中…';try{const data=await api('/api/bridge/report',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await refreshIntegrations();toast(data.exported?'最新本机运营状态已写入桥接目录':'当前未连接双向桥',data.exported?'ok':'error')}catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='立即上报'}}
async function disableBridge(){try{await api('/api/bridge/disable',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await Promise.all([refreshIntegrations(),loadControlCenter()]);toast('双向桥已停用，本地自主运行继续保持')}catch(error){toast(error.message,'error')}}

async function refreshIntegrations(){
  try{
    const data=await api('/api/integrations');
    $('integration-grid').innerHTML=data.items.map(integrationCard).join('');
    renderBridgePanel(data.bridge);
    bindIntegrationCards();
    const ai=data.external_ai;
    $('ai-base-url').value=ai.base_url||'https://api.openai.com/v1';
    $('ai-model').value=ai.model||'';
    $('ai-api-key').placeholder=ai.has_key?'密钥已加密保存；不修改可留空':'请输入 API 密钥';
    $('ai-config-badge').textContent=ai.status_label;
    $('ai-config-badge').className=`status-pill ${ai.status==='connected'?'ready':'waiting'}`;
    $('ai-connection-message').textContent=ai.message;
    loadEvidenceLedger();
  }catch(error){toast(error.message,'error')}
}

async function runDiagnostics(){
  const button=$('run-diagnostics');button.disabled=true;button.textContent='体检中…';
  try{
    const data=await api('/api/system/diagnostics',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    $('diagnostic-summary').className='diagnostic-summary';
    $('diagnostic-summary').innerHTML=`<strong>${data.summary.failed?'发现异常':'核心服务正常'}</strong><span>${data.summary.passed} 项通过 · ${data.summary.attention} 项待配置 · ${data.summary.failed} 项失败</span>`;
    $('diagnostic-list').innerHTML=data.checks.map(x=>`<div class="diagnostic-row"><i class="${esc(x.status)}"></i><strong>${esc(x.name)}</strong><span>${esc(x.message)}</span><b>${x.status==='pass'?'通过':x.status==='attention'?'待配置':'失败'}</b></div>`).join('');
    toast('系统体检已完成');
  }catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='重新体检'}
}

$('save-ai-config').addEventListener('click',async()=>{
  const button=$('save-ai-config');button.disabled=true;button.textContent='保存中…';
  try{
    await api('/api/integrations/ai/configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({base_url:$('ai-base-url').value,model:$('ai-model').value,api_key:$('ai-api-key').value})});
    $('ai-api-key').value='';await Promise.all([refreshIntegrations(),loadControlCenter()]);toast('AI 连接配置已安全保存');
  }catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='保存配置'}
});

$('test-ai-connection').addEventListener('click',async()=>{
  const button=$('test-ai-connection');button.disabled=true;button.textContent='测试中…';
  try{await api('/api/integrations/ai/test',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await Promise.all([refreshIntegrations(),loadControlCenter()]);toast('AI 连接和鉴权测试通过')}
  catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='测试连接'}
});

$('run-diagnostics').addEventListener('click',runDiagnostics);

$('ask-ai').addEventListener('click',async()=>{
  const prompt=$('ai-command-prompt').value.trim();if(!prompt){toast('请先输入要分析的问题','error');return}
  const button=$('ask-ai');button.disabled=true;button.textContent='AI 分析中…';
  try{const result=await api('/api/ai/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt})});$('ai-command-output').className='ai-command-output';$('ai-command-output').textContent=result.content;toast('AI 建议已生成，请人工审核')}
  catch(error){toast(error.message,'error')}finally{button.disabled=false;button.textContent='请 AI 分析'}
});

window.loadIntegrations=async()=>{await Promise.all([refreshIntegrations(),runDiagnostics()])};
window.loadControlCenter=loadControlCenter;
loadControlCenter().catch(error=>toast(error.message,'error'));

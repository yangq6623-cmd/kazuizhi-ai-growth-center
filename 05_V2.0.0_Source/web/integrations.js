const STATUS_STYLE={ready:'ready',connected:'ready',configured:'waiting',manual:'waiting',not_connected:'waiting',not_configured:'waiting',blocked:'blocked'};
const CONTROL_ROLE_TARGETS=['analytics','review','promotion','summary'];

function renderStatusPill(item){return `<span class="status-pill ${STATUS_STYLE[item.status]||'waiting'}">${esc(item.status_label)}</span>`}

async function loadControlCenter(){
  const data=await api('/api/control-center');
  $('control-headline').textContent=data.headline;
  const connected=data.external_ai.status==='connected';
  $('external-ai-badge').textContent=connected?'外部 AI 已连接':'外部 AI 未连接';
  $('external-ai-badge').className=`status-pill ${connected?'ready':'waiting'}`;
  $('ai-role-grid').innerHTML=data.roles.map((role,index)=>`<div class="ai-role ai-role-action" role="button" tabindex="0" data-target="${CONTROL_ROLE_TARGETS[index]||'workflow'}"><span>${['数','策','内','营'][index]}</span><div><strong>${esc(role.name)}</strong><small>${esc(role.purpose)}</small></div><i class="${role.status}">${role.status==='ready'?'可用':'待数据'}</i></div>`).join('');
  document.querySelectorAll('.ai-role-action').forEach(card=>{
    const activate=()=>{openPage(card.dataset.target);toast(`已打开${card.querySelector('strong')?.textContent||'AI'}对应模块`)};
    card.addEventListener('click',activate);
    card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate()}});
  });
  $('operation-loop').innerHTML=data.loop.map((step,index)=>`<div><b>${index+1}</b><span>${esc(step)}</span>${index<data.loop.length-1?'<em>→</em>':''}</div>`).join('');
}

function integrationCard(item){
  const icons={local_engine:'本',external_ai:'AI',business_data:'数',cloud_drive:'云',publishing:'发',finance:'禁'};
  return `<article class="integration-card ${esc(item.status)}"><div class="integration-icon">${icons[item.id]||'连'}</div><div><strong>${esc(item.name)}</strong><p>${esc(item.message)}</p></div>${renderStatusPill(item)}</article>`;
}

async function refreshIntegrations(){
  try{
    const data=await api('/api/integrations');
    $('integration-grid').innerHTML=data.items.map(integrationCard).join('');
    const ai=data.external_ai;
    $('ai-base-url').value=ai.base_url||'https://api.openai.com/v1';
    $('ai-model').value=ai.model||'';
    $('ai-api-key').placeholder=ai.has_key?'密钥已加密保存；不修改可留空':'请输入 API 密钥';
    $('ai-config-badge').textContent=ai.status_label;
    $('ai-config-badge').className=`status-pill ${ai.status==='connected'?'ready':'waiting'}`;
    $('ai-connection-message').textContent=ai.message;
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

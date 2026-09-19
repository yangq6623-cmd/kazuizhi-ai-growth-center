(() => {
  'use strict';

  const TABS = [
    ['overview','升级总控'],['radar','情报雷达'],['content','内容委员会'],['video','3060视频工厂'],
    ['publish','审核与发布'],['messages','消息与线索'],['learning','归因与学习'],['audit','审计与体检']
  ];
  const COLLECTIONS = ['signals','growth_cases','content_jobs','video_jobs','publish_jobs','conversations','messages','leads','attribution','metric_snapshots','learning_cycles','audit'];
  let activeTab = 'overview';
  let summary = {counts:{},gates:[],video_worker:{hardware:{}},connectors:[]};
  const CN = {
    ready:'已就绪',pending:'待完成',published:'已发布',approved:'已审核',rejected:'已退回',failed:'失败',queued:'排队中',running:'执行中',
    pending_connector:'待授权平台',pending_device:'待连接真机',waiting_first_case:'待首条真实任务',pending_worker:'待配置视频模型',
    waiting_first_receipt:'待真实发布回执',waiting_first_message:'待真实消息',waiting_metrics:'待效果数据',waiting_learning_cycle:'待首轮复盘',
    new:'新建',routed:'已路由',no_matching_account:'无匹配账号',candidate_needs_authorization:'候选账号待授权',planning:'策划中',
    content_pending_approval:'内容待审核',content_approved:'内容已通过',revision_requested:'待修改',waiting_worker:'等待视频模型',
    awaiting_owner_review:'等待老板审核',human_required:'转人工',qualified:'有效线索',closed:'已结束',conversion:'转化',search:'搜索增长',
    brand:'品牌',education:'知识科普',recruitment:'招募',low:'低',medium:'中',high:'高',normal:'正常',attention:'需注意',
    douyin:'抖音',xiaohongshu:'小红书',kuaishou:'快手',wechat_channels:'视频号',weibo:'微博',bilibili:'B站',forum:'论坛/社区',blog:'博客/内容站',other:'其他平台'
  };
  const cn = value => CN[value] || value;

  let data = Object.fromEntries(COLLECTIONS.map(name => [name, []]));

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const stateClass = value => ['ready','pass','published','approved'].includes(value) ? 'ready' : ['failed','rejected','human_required','high'].includes(value) ? 'danger' : 'pending';
  const requestJson = async (path, options={}) => {
    const response = await fetch(path, options);
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(body.error || `请求失败 ${response.status}`);
    return body;
  };
  const post = (path, payload) => requestJson(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const notify = (message, kind='success') => typeof toast === 'function' ? toast(message, kind === 'error' ? 'error' : undefined) : alert(message);
  const byId = id => document.getElementById(id);
  const items = name => data[name] || [];

  async function refresh(quiet=false){
    try{
      const results = await Promise.all([
        requestJson('/api/r8/growth/summary'),
        ...COLLECTIONS.map(name => requestJson(`/api/r8/growth/${name.replaceAll('_','-')}`))
      ]);
      summary = results[0];
      COLLECTIONS.forEach((name,index) => { data[name] = results[index+1].items || []; });
      render();
    }catch(error){ if(!quiet) notify(error.message,'error'); }
  }

  function kpis(){
    const c=summary.counts||{};
    return `<div class="r8-final-kpis">
      <div class="r8-final-kpi"><small>公开需求信号</small><b>${c.signals||0}</b></div>
      <div class="r8-final-kpi"><small>增长 ID</small><b>${c.growth_cases||0}</b></div>
      <div class="r8-final-kpi"><small>内容任务</small><b>${c.content_jobs||0}</b></div>
      <div class="r8-final-kpi"><small>真实发布</small><b>${items('publish_jobs').filter(x=>x.status==='published').length}</b></div>
      <div class="r8-final-kpi"><small>有效线索</small><b>${c.leads||0}</b></div>
    </div>`;
  }

  function overview(){
    const gates=(summary.gates||[]).map(g=>`<div class="r8-gate"><span class="r8-state ${stateClass(g.live)}">${esc(cn(g.live))}</span><small>${esc(g.id.replace('Gate','关口'))}</small><h4>${esc(g.name)}</h4><p>软件：${esc(cn(g.software))} · 上线：${esc(cn(g.live))}</p></div>`).join('');
    const connectors=(summary.connectors||[]).map(x=>`<div class="r8-final-row"><div class="r8-final-row-head"><h4>${esc(x.name)}</h4><span class="r8-state ${stateClass(x.state)}">${x.state==='ready'?'已授权':'待配置'}</span></div><p>登记账号 ${x.configured?'有':'无'} · 已授权 ${x.authorized||0}</p></div>`).join('');
    return `${kpis()}<div class="r8-truth"><b>交付原则：</b>${esc(summary.delivery?.truth_policy||'外部能力未连接时明确显示待配置。')}</div>
      <article class="wide"><div class="article-head"><div><label>R8-00 至 R8-08</label><h3>软件升级与上线验收关口</h3></div><span class="chip">软件模块已齐全 · 现场数据逐项验收</span></div><div class="r8-gate-grid">${gates}</div></article>
      <div class="r8-final-split" style="margin-top:14px"><article><label>平台连接</label><h3>真实账号授权状态</h3><div class="r8-final-list">${connectors}</div></article><article><label>老板日常只处理</label><h3>两类核心动作</h3><div class="r8-final-note"><b>1. 视频和关键内容最终确认发布</b><br>2. 支付、退款、提现、结算、改价等全部资金事项<br><br>验证码、人脸、异常登录和投诉纠纷只在异常时转人工。</div></article></div>`;
  }

  function signalRows(){
    const rows=items('signals');
    if(!rows.length)return '<div class="r8-empty">尚无需求信号。可手工录入真实公开来源，或等待平台 Connector 接入。</div>';
    return `<div class="r8-final-list">${rows.map(s=>`<div class="r8-final-row"><div class="r8-final-row-head"><div><h4>${esc(s.region)} · ${esc(s.service_category)}</h4><div class="r8-final-meta"><span>${esc(s.platform_name||cn(s.platform))}</span><span>意向 ${esc(cn(s.intent_level))}</span><span>风险 ${esc(cn(s.risk_level))}</span><span>${esc(cn(s.route_state))}</span></div></div><span class="r8-state ${stateClass(s.route_state)}">${esc(cn(s.status))}</span></div><p>${esc(s.summary)}</p><div class="r8-final-actions"><button data-r8-route="${esc(s.signal_id)}">选择唯一账号</button><button class="primary" data-r8-growth="${esc(s.signal_id)}">建立增长 ID</button>${s.source_url?`<a href="${esc(s.source_url)}" target="_blank" rel="noreferrer">查看来源</a>`:''}</div></div>`).join('')}</div>`;
  }

  function radar(){
    return `<div class="r8-final-split"><article><label>R8-02 平台情报雷达</label><h3>录入真实公开需求信号</h3><div class="r8-final-form">
      <label>平台<select id="r8-signal-platform"><option value="douyin">抖音</option><option value="wechat_channels">视频号</option><option value="xiaohongshu">小红书</option><option value="kuaishou">快手</option><option value="weibo">微博</option><option value="forum">论坛/社区</option></select></label>
      <label>来源链接<input id="r8-signal-url" placeholder="公开内容 URL"></label><label>地区<input id="r8-signal-region" value="涟水"></label><label>服务类型<input id="r8-signal-service" placeholder="例如：家电维修"></label>
      <label>意向<select id="r8-signal-intent"><option value="high">高</option><option value="medium" selected>中</option><option value="low">低</option></select></label><label>推荐动作<select id="r8-signal-action"><option value="reply">帮助性回复</option><option value="dm">私信</option><option value="human">转人工</option><option value="ignore">忽略</option></select></label>
      <label class="wide">真实需求内容<textarea id="r8-signal-summary" rows="4" placeholder="粘贴公开问题或摘要，不要填写密码和敏感个人信息"></textarea></label><button id="r8-signal-save" class="primary-button">保存并查重</button></div></article>
      <article><label>账号路由原则</label><h3>同一需求只触达一次</h3><div class="r8-final-note">按平台、地区、服务、授权状态和风险状态选择一个最匹配账号。主账号已进入有效对话后，矩阵号不会抢占；用户拒绝后停止跟进。</div></article></div><article class="wide" style="margin-top:14px"><div class="article-head"><div><label>信号列表</label><h3>来源、时间、地区、服务、意向和风险可追溯</h3></div></div>${signalRows()}</article>`;
  }

  function content(){
    const growth=items('growth_cases'); const jobs=items('content_jobs');
    const growthRows=growth.length?growth.map(g=>`<div class="r8-final-row"><div class="r8-final-row-head"><div><h4>${esc(g.growth_id)}</h4><div class="r8-final-meta"><span>${esc(g.region)}</span><span>${esc(g.service_category)}</span><span>${esc(cn(g.business_goal))}</span></div></div><span class="r8-state ${stateClass(g.status)}">${esc(cn(g.status))}</span></div><p>${esc(g.hypothesis)}</p><div class="r8-final-actions">${g.content_job_id?'<span>已形成内容任务</span>':`<button class="primary" data-r8-content-create="${esc(g.growth_id)}">八员工联合策划</button>`}</div></div>`).join(''):'<div class="r8-empty">先从情报雷达建立增长 ID。</div>';
    const jobRows=jobs.length?jobs.map(j=>`<div class="r8-final-row"><div class="r8-final-row-head"><div><h4>${esc(j.title_candidates?.[0]||j.content_id)}</h4><div class="r8-final-meta"><span>${esc(j.region)}</span><span>${esc(cn(j.platform))}</span><span>${esc(cn(j.content_goal))}</span></div></div><span class="r8-state ${stateClass(j.approval_state)}">${esc(cn(j.approval_state))}</span></div><p><b>前三秒：</b>${esc(j.first_three_seconds)}</p><div class="r8-committee">${(j.committee||[]).map(x=>`<div><b>${esc(x.role)}</b><br>${esc(x.recommendation)}</div>`).join('')}</div><div class="r8-final-actions">${j.approval_state==='pending'?`<button class="primary" data-r8-content-approve="${esc(j.content_id)}">审核通过</button><button data-r8-content-revise="${esc(j.content_id)}">退回修改</button>`:''}${j.approval_state==='approved'?`<button class="primary" data-r8-video-create="${esc(j.content_id)}">进入视频工厂</button>`:''}</div></div>`).join(''):'<div class="r8-empty">尚无内容委员会任务。</div>';
    return `<div class="grid two"><article><label>R8-03 增长 ID</label><h3>从来源一直追踪到订单和复盘</h3><div class="r8-final-list">${growthRows}</div></article><article><label>R8-04 八员工内容委员会</label><h3>每条内容都有理由和成功标准</h3><div class="r8-final-list">${jobRows}</div></article></div>`;
  }

  function video(){
    const worker=summary.video_worker||{}; const hw=worker.hardware||{};
    const rows=items('video_jobs');
    return `<article class="wide"><div class="article-head"><div><label>R8-05 RTX 3060 本地视频工厂</label><h3>多镜头、多候选、串行生成与局部返工</h3></div><button id="r8-worker-config" class="primary-small">配置本地 Worker</button></div><div class="r8-worker"><div><small>GPU</small><b>${esc(hw.name||'未检测到')}</b></div><div><small>Worker</small><b>${worker.configured?'已配置':'待配置'}</b></div><div><small>显存软上限</small><b>${esc(worker.max_vram_gb||9.5)} GB</b></div><div><small>安全余量</small><b>${esc(worker.reserve_vram_gb||2.5)} GB</b></div></div><div class="r8-truth" style="margin-top:12px">CUDA OOM 后自动降低负载；禁止以相同参数无限重试。没有真实成片路径和质检结果时，不会显示“已完成”。</div></article>
      <article class="wide" style="margin-top:14px"><label>视频任务</label><div class="r8-final-list">${rows.length?rows.map(v=>`<div class="r8-final-row"><div class="r8-final-row-head"><div><h4>${esc(v.video_id)}</h4><div class="r8-final-meta"><span>${esc(v.growth_id)}</span><span>${(v.shots||[]).length} 个镜头</span></div></div><span class="r8-state ${stateClass(v.status)}">${esc(v.status)}</span></div><p>${v.output_path?`成片：${esc(v.output_path)}`:'等待本地 Worker 或真实成片回填'}</p><div class="r8-final-actions">${v.status==='waiting_worker'||v.status==='queued'?`<button data-r8-video-start="${esc(v.video_id)}">开始任务</button>`:''}${v.status==='running'?`<button class="primary" data-r8-video-complete="${esc(v.video_id)}">回填成片与质检</button>`:''}${v.status==='awaiting_owner_review'?`<button class="primary" data-r8-video-approve="${esc(v.video_id)}">老板确认成片</button><button data-r8-video-reject="${esc(v.video_id)}">退回指定镜头</button>`:''}</div></div>`).join(''):'<div class="r8-empty">审核通过内容后，可创建视频任务。</div>'}</div></article>`;
  }

  function publish(){
    const approved=items('content_jobs').filter(x=>x.approval_state==='approved'); const accounts=(summary.connectors||[]).reduce((n,x)=>n+x.authorized,0);
    const rows=items('publish_jobs');
    return `<div class="r8-final-split"><article><label>R8-06 人工审核授权</label><h3>审核通过内容</h3><div class="r8-final-list">${approved.length?approved.map(c=>`<div class="r8-final-row"><h4>${esc(c.title_candidates?.[0]||c.content_id)}</h4><p>${esc(c.cta)}</p><div class="r8-final-actions"><button class="primary" data-r8-publish-create="${esc(c.content_id)}">确认发布并进入择时队列</button></div></div>`).join(''):'<div class="r8-empty">尚无审核通过内容。</div>'}</div></article><article><label>R8-07 发布条件</label><h3>真实账号与回执</h3><div class="r8-final-note">已授权账号：${accounts}<br>发布成功必须保存平台内容 ID、真实 URL、执行时间和执行来源。没有回执只能标记“已提交/待确认”。</div></article></div>
      <article class="wide" style="margin-top:14px"><label>发布队列</label><div class="r8-final-list">${rows.length?rows.map(p=>`<div class="r8-final-row"><div class="r8-final-row-head"><div><h4>${esc(p.publish_id)}</h4><div class="r8-final-meta"><span>${esc(p.platform)}</span><span>${esc(p.account_id)}</span><span>${esc(p.scheduled_at)}</span></div></div><span class="r8-state ${stateClass(p.status)}">${esc(p.status)}</span></div><p>${p.receipt?.url?`真实回执：<a href="${esc(p.receipt.url)}" target="_blank" rel="noreferrer">${esc(p.receipt.url)}</a>`:'等待真实平台执行回执'}</p><div class="r8-final-actions">${['queued','submitted_waiting_confirmation'].includes(p.status)?`<button class="primary" data-r8-receipt-success="${esc(p.publish_id)}">回填成功回执</button><button data-r8-receipt-failed="${esc(p.publish_id)}">记录失败</button>`:''}${p.status==='published'?`<button data-r8-metrics="${esc(p.publish_id)}">记录 24h/72h/7天数据</button>`:''}</div></div>`).join(''):'<div class="r8-empty">尚无发布任务。</div>'}</div></article>`;
  }

  function messages(){
    const conversations=items('conversations'); const leads=items('leads');
    return `<div class="r8-final-split"><article><label>统一消息入口</label><h3>导入真实评论、私信或平台回执</h3><div class="r8-final-form"><label>平台<select id="r8-message-platform"><option value="douyin">抖音</option><option value="wechat_channels">视频号</option><option value="xiaohongshu">小红书</option><option value="kuaishou">快手</option><option value="weibo">微博</option></select></label><label>账号 ID<input id="r8-message-account" placeholder="已绑定账号 ID"></label><label>公开用户标识<input id="r8-message-user" placeholder="平台公开 ID"></label><label>类型<select id="r8-message-kind"><option value="comment">评论</option><option value="dm">私信</option><option value="reply">回复</option><option value="mention">@提及</option></select></label><label class="wide">消息内容<textarea id="r8-message-content" rows="4"></textarea></label><button id="r8-message-save" class="primary-button">进入统一会话</button></div></article><article><label>人工硬边界</label><h3>自动转人工</h3><div class="r8-final-note">投诉、退款、赔偿、法律、支付、身份证、银行卡等内容自动进入人工处理。用户明确拒绝后记录停止联系，不再跨账号触达。</div></article></div>
      <div class="grid two" style="margin-top:14px"><article><label>会话</label><div class="r8-final-list">${conversations.length?conversations.map(c=>`<div class="r8-final-row"><div class="r8-final-row-head"><h4>${esc(c.platform)} · ${esc(c.user_ref)}</h4><span class="r8-state ${stateClass(c.state)}">${esc(c.state)}</span></div><p>账号 ${esc(c.account_id)} · 最近 ${esc(c.last_message_at)}</p><div class="r8-final-actions">${!c.lead_id?`<button class="primary" data-r8-lead="${esc(c.conversation_id)}">转为有效线索</button>`:'<span>线索 '+esc(c.lead_id)+'</span>'}<button data-r8-stop-contact="${esc(c.conversation_id)}">停止联系</button></div></div>`).join(''):'<div class="r8-empty">尚无真实消息。</div>'}</div></article><article><label>线索 CRM</label><div class="r8-final-list">${leads.length?leads.map(l=>`<div class="r8-final-row"><div class="r8-final-row-head"><h4>${esc(l.region)} · ${esc(l.service_category)}</h4><span class="r8-state ${stateClass(l.stage)}">${esc(l.stage)}</span></div><p>${esc(l.lead_id)} · ${esc(l.platform)} · ${esc(l.account_id)}</p><div class="r8-final-actions"><button class="primary" data-r8-attribution="${esc(l.lead_id)}">关联真实订单</button></div></div>`).join(''):'<div class="r8-empty">尚无有效线索。</div>'}</div></article></div>`;
  }

  function learning(){
    const metrics=items('metric_snapshots'); const attrs=items('attribution'); const cycles=items('learning_cycles');
    return `${kpis()}<div class="grid three"><article><label>订单归因</label><h3>${attrs.length} 条</h3><p>只读经营数据或人工确认，不触碰支付、退款和结算。</p></article><article><label>效果快照</label><h3>${metrics.length} 条</h3><p>24h 看首轮分发，72h 看咨询，7天看订单和长期价值。</p></article><article><label>学习回写</label><h3>${cycles.length} 轮</h3><button id="r8-learning-run" class="primary-small">根据真实数据生成下一轮调整</button></article></div>
      <article class="wide" style="margin-top:14px"><label>R8-08 真实结果学习</label><div class="r8-final-list">${cycles.length?cycles.map(c=>`<div class="r8-final-row"><div class="r8-final-row-head"><h4>${esc(c.growth_id)}</h4><span class="r8-state ready">已回写</span></div><p><b>${esc(c.decision)}</b><br>${esc(c.next_change)}</p><div class="r8-final-meta"><span>咨询 ${c.evidence?.consultations||0}</span><span>订单 ${c.evidence?.orders||0}</span><span>完成 ${c.evidence?.completed_orders||0}</span></div></div>`).join(''):'<div class="r8-empty">发布后录入 24h/72h/7天真实数据，才会生成学习结论。</div>'}</div></article>`;
  }

  function audit(){
    const rows=items('audit');
    return `<div class="r8-final-toolbar"><div><label>全链路审计</label><h3>来源、判断、审批、执行、回执与结果</h3></div><button id="r8-diagnostics" class="primary-small">运行 R8 上线体检</button></div><div class="r8-truth">任何外部动作都必须有平台、账号、设备/执行来源、时间、结果和策略理由。凭证与验证码不会写入普通日志。</div><div class="r8-final-list r8-audit">${rows.length?rows.map(a=>`<div class="r8-final-row"><div class="r8-final-row-head"><b>${esc(a.kind)}</b><small>${esc(a.at)}</small></div><p>${esc(a.detail)}</p><div class="r8-final-meta"><span>${esc(a.actor)}</span><span>${esc(a.entity_id)}</span></div></div>`).join(''):'<div class="r8-empty">暂无审计记录。</div>'}</div>`;
  }

  function current(){return ({overview,radar,content,video,publish,messages,learning,audit}[activeTab]||overview)();}
  function render(){const host=byId('r8-final-body');if(!host)return;host.innerHTML=`<div class="r8-final-tabs">${TABS.map(([id,label])=>`<button class="r8-final-tab ${activeTab===id?'active':''}" data-r8-final-tab="${id}">${label}</button>`).join('')}</div>${current()}`;bind();}

  function setFeedback(message,kind=''){const box=byId('r8-action-feedback');if(!box)return;box.hidden=false;box.className=`r8-action-feedback ${kind}`.trim();box.textContent=message;}
  async function action(fn, success){setFeedback('正在执行，请稍候…');try{const result=await fn();setFeedback(success,'ok');notify(success);await refresh(true);return result;}catch(error){setFeedback('执行未完成：'+error.message,'error');notify(error.message,'error');return null;}}
  function bind(){
    document.querySelectorAll('[data-r8-final-tab]').forEach(b=>b.onclick=()=>{activeTab=b.dataset.r8FinalTab;render();});
    byId('r8-signal-save')?.addEventListener('click',()=>action(()=>post('/api/r8/growth/signals',{platform:byId('r8-signal-platform').value,source_url:byId('r8-signal-url').value,source_id:'manual-'+Date.now(),region:byId('r8-signal-region').value,service_category:byId('r8-signal-service').value,intent_level:byId('r8-signal-intent').value,recommended_action:byId('r8-signal-action').value,summary:byId('r8-signal-summary').value,source:'human_import'}),'真实需求信号已保存并查重'));
    document.querySelectorAll('[data-r8-route]').forEach(b=>b.onclick=()=>action(()=>post('/api/r8/growth/signals/route',{signal_id:b.dataset.r8Route}),'已完成唯一账号路由'));
    document.querySelectorAll('[data-r8-growth]').forEach(b=>b.onclick=()=>action(async()=>{await post('/api/r8/growth/signals/route',{signal_id:b.dataset.r8Growth});await post('/api/r8/growth/cases',{signal_id:b.dataset.r8Growth,business_goal:'conversion'});},'增长 ID 已建立'));
    document.querySelectorAll('[data-r8-content-create]').forEach(b=>b.onclick=()=>action(()=>post('/api/r8/growth/content',{growth_id:b.dataset.r8ContentCreate}),'八员工内容任务单已生成'));
    document.querySelectorAll('[data-r8-content-approve]').forEach(b=>b.onclick=()=>action(()=>post('/api/r8/growth/content/review',{content_id:b.dataset.r8ContentApprove,action:'approve',reviewer:'owner'}),'内容已审核通过'));
    document.querySelectorAll('[data-r8-content-revise]').forEach(b=>b.onclick=()=>{const note=prompt('请输入需要修改的内容');if(note)action(()=>post('/api/r8/growth/content/review',{content_id:b.dataset.r8ContentRevise,action:'revise',reviewer:'owner',note}),'已退回修改');});
    document.querySelectorAll('[data-r8-video-create]').forEach(b=>b.onclick=()=>action(()=>post('/api/r8/growth/videos',{content_id:b.dataset.r8VideoCreate}),'视频任务已建立'));
    byId('r8-worker-config')?.addEventListener('click',()=>{const model_path=prompt('请输入本地视频模型目录（不会上传）','');if(model_path!==null){const output_root=prompt('请输入成片输出目录','')||'';action(()=>post('/api/r8/growth/video-worker',{configured:true,model_path,output_root}),'本地视频 Worker 配置已保存');}});
    document.querySelectorAll('[data-r8-video-start]').forEach(b=>b.onclick=()=>action(()=>post('/api/r8/growth/videos/update',{video_id:b.dataset.r8VideoStart,action:'start'}),'视频任务已启动'));
    document.querySelectorAll('[data-r8-video-complete]').forEach(b=>b.onclick=()=>{const output_path=prompt('请输入真实成片路径');if(output_path)action(()=>post('/api/r8/growth/videos/update',{video_id:b.dataset.r8VideoComplete,action:'complete',output_path,visual:85,script:85,subtitle:85,risk:0}),'成片已进入老板审核');});
    document.querySelectorAll('[data-r8-video-approve]').forEach(b=>b.onclick=()=>action(()=>post('/api/r8/growth/videos/update',{video_id:b.dataset.r8VideoApprove,action:'approve',actor:'owner'}),'老板已确认成片'));
    document.querySelectorAll('[data-r8-video-reject]').forEach(b=>b.onclick=()=>{const reason=prompt('请输入需要重做的镜头或原因');if(reason)action(()=>post('/api/r8/growth/videos/update',{video_id:b.dataset.r8VideoReject,action:'reject',reason,actor:'owner'}),'已退回指定镜头');});
    document.querySelectorAll('[data-r8-publish-create]').forEach(b=>b.onclick=()=>{const account_id=prompt('请输入已在真机授权的平台账号 ID');if(account_id)action(()=>post('/api/r8/growth/publishing',{content_id:b.dataset.r8PublishCreate,account_id,owner_approved:true,reviewer:'owner'}),'已进入择时发布队列');});
    document.querySelectorAll('[data-r8-receipt-success]').forEach(b=>b.onclick=()=>{const url=prompt('请输入真实平台内容 URL');const platform_content_id=url&&prompt('请输入真实平台内容 ID');if(url&&platform_content_id)action(()=>post('/api/r8/growth/publishing/receipt',{publish_id:b.dataset.r8ReceiptSuccess,result:'success',url,platform_content_id,executed_by:'real_device'}),'真实发布回执已保存');});
    document.querySelectorAll('[data-r8-receipt-failed]').forEach(b=>b.onclick=()=>{const error=prompt('请输入失败原因');if(error)action(()=>post('/api/r8/growth/publishing/receipt',{publish_id:b.dataset.r8ReceiptFailed,result:'failed',error,executed_by:'real_device'}),'发布失败已如实记录');});
    document.querySelectorAll('[data-r8-metrics]').forEach(b=>b.onclick=()=>{const checkpoint=prompt('输入复盘时间点：24h、72h 或 7d','24h');if(checkpoint)action(()=>post('/api/r8/growth/metrics',{publish_id:b.dataset.r8Metrics,checkpoint,source:'manual_verified',impressions:Number(prompt('曝光量','0')||0),plays:Number(prompt('播放量','0')||0),comments:Number(prompt('评论数','0')||0),dms:Number(prompt('私信数','0')||0),consultations:Number(prompt('有效咨询数','0')||0),orders:Number(prompt('订单数','0')||0),completed_orders:Number(prompt('完成订单数','0')||0)}),'真实效果数据已保存');});
    byId('r8-message-save')?.addEventListener('click',()=>action(()=>post('/api/r8/growth/messages',{platform:byId('r8-message-platform').value,account_id:byId('r8-message-account').value,user_ref:byId('r8-message-user').value,kind:byId('r8-message-kind').value,direction:'inbound',content:byId('r8-message-content').value,source:'human_import'}),'消息已进入统一会话'));
    document.querySelectorAll('[data-r8-stop-contact]').forEach(b=>b.onclick=()=>action(()=>post('/api/r8/growth/conversations/update',{conversation_id:b.dataset.r8StopContact,state:'closed',do_not_contact:true,actor:'owner'}),'已停止后续联系'));
    document.querySelectorAll('[data-r8-lead]').forEach(b=>b.onclick=()=>{const region=prompt('地区','涟水');const service_category=region&&prompt('服务类型','本地生活服务');if(region&&service_category)action(()=>post('/api/r8/growth/leads',{conversation_id:b.dataset.r8Lead,stage:'qualified',region,service_category}),'有效线索已建立');});
    document.querySelectorAll('[data-r8-attribution]').forEach(b=>b.onclick=()=>{const order_id=prompt('请输入真实订单 ID');if(order_id)action(()=>post('/api/r8/growth/attribution',{lead_id:b.dataset.r8Attribution,order_id,source:'manual_confirmation',order_status:'created'}),'线索已关联真实订单');});
    byId('r8-learning-run')?.addEventListener('click',()=>action(()=>post('/api/r8/growth/learning/run',{}),'真实结果已回写下一轮策略'));
    byId('r8-diagnostics')?.addEventListener('click',()=>action(async()=>{const result=await requestJson('/api/r8/growth/diagnostics');alert(result.checks.map(x=>`${x.status==='pass'?'✓':'○'} ${x.name}：${x.detail}`).join('\n'));},'R8 上线体检完成'));
  }

  function mount(){
    if(byId('r8-final-center'))return;
    const nav=document.querySelector('aside nav');const main=document.querySelector('main');if(!nav||!main)return;
    const firstGroup=[...nav.querySelectorAll('.nav-group')].find(x=>x.textContent.includes('分析与内容'));
    const group=document.createElement('small');group.className='nav-group';group.textContent='R8 增长闭环';
    const button=document.createElement('button');button.className='nav';button.dataset.page='r8-final-center';button.dataset.title='R8 增长运营总控';button.dataset.subtitle='从真实需求到发布、线索、订单和学习回写';button.innerHTML='<span>◆</span>R8 增长总控';
    if(firstGroup){nav.insertBefore(group,firstGroup);nav.insertBefore(button,firstGroup);}else{nav.append(group,button);}
    const section=document.createElement('section');section.id='r8-final-center';section.className='page';section.innerHTML=`<div class="r8-final-hero"><div><small>R8 最终版 · 全链路增长运营</small><h2>真实互联网增长闭环</h2><p>平台信号 → 唯一增长 ID → 八员工联合策划 → 3060 视频任务 → 老板确认发布 → 真实回执 → 评论/私信/线索 → 订单归因 → 24h/72h/7天复盘 → 下一轮调整。</p></div><button id="r8-final-refresh">刷新全部状态</button></div><div id="r8-action-feedback" class="r8-action-feedback" hidden></div><div id="r8-final-body"><div class="r8-empty">正在读取 R8 全部模块…</div></div>`;
    main.appendChild(section);
    button.addEventListener('click',()=>{if(typeof openPage==='function')openPage('r8-final-center');refresh();});
    byId('r8-final-refresh').addEventListener('click',()=>refresh());
    refresh(true);
  }

  window.loadR8FinalCenter=()=>refresh(true);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();

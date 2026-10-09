/* Public DEMO fixture only. No secrets, no network API calls, no real mutations. */
(()=>{
 'use strict';
 const demoTag='仅供界面验收的模拟数据，并非真实发布、收录或外部 AI 验证';
 const now=new Date().toISOString();
 const seo={
  summary:{keyword_total:17,public_pages:20,submitted_urls:20,crawled_urls:0,indexed_urls:0,ranked_urls:0,conversions:0,
   today_opportunities:0,today_planned:0,today_published_verified:0,today_submitted_receipted:0},
  evidence_summary:{today_generated:0,today_qc_passed:0,qc_passed_total:20,staged_files:20,canonical_files:20,schema_files:20,asset_total:20},
  funnel:{generated:20,published:20,submitted:20,crawled:0,indexed:0},
  geo:{questions:50,tested_questions:2,mentioned:0,cited:0,observations:0,mention_rate:0,citation_rate:0,truth_source:'r8-19-official-evidence'},
  opportunities:[
   {region:'涟水县',service:'水电维修',keyword:'涟水县水电维修师傅',intent:'local_discovery',priority:'S',status:'DISCOVERED'},
   {region:'涟水县',service:'空调维修',keyword:'涟水县空调维修电话',intent:'local_discovery',priority:'S',status:'PLANNED'},
   {region:'淮安市',service:'管道疏通',keyword:'附近管道疏通服务',intent:'user_service',priority:'A',status:'GENERATED'}],
  assets:[
   {region:'涟水县',page_type:'地区服务页',keyword:'水电维修',stage:'SUBMITTED',public_url:'https://example.com/demo/seo/water-repair'},
   {region:'涟水县',page_type:'FAQ',keyword:'空调清洗',stage:'PUBLISHED',public_url:'https://example.com/demo/seo/air-conditioner'},
   {region:'淮安市',page_type:'地区×服务页',keyword:'管道疏通',stage:'QC_PASSED',public_url:''}],
  technical:{staging:{robots_generated:true,sitemap_generated:true},
   public_site:{latest_audit:{result:'unverified',homepage_status:0}},
   public_deploy:{configured:false,ready:false,reason:'演示状态，不执行公网部署'},
   observability:{checked_at:now},
   connectors:{
    baidu:{label:'百度搜索资源平台',configured:true,ready:false,reason:'演示连接器，不提交',setup_state:'演示',authorization_state:'未联机',automation_state:'预览'},
    bing:{label:'Bing / IndexNow',configured:true,ready:false,reason:'演示连接器',setup_state:'演示',authorization_state:'无真实授权',automation_state:'预览'},
    google:{label:'Google Search Console',configured:true,ready:false,reason:'演示连接器',setup_state:'演示',authorization_state:'未联机',automation_state:'预览'},
    so360:{label:'360 搜索站长平台',configured:false,ready:false,reason:'演示连接器',portal_url:'',setup_state:'待接入'},
    doubao_search:{label:'豆包 AI 可见性',configured:true,ready:false,monitoring_only:true,reason:'展示原版 UI',extra_paid_api:false},
    douyin_search:{label:'抖音搜索',configured:false,ready:false,monitoring_only:true,reason:'仅预览'}
   }},
  search_submit:{automation_summary:{auto_submit_enabled:true,pending_unique_urls:0,submitted_unique_urls:20,failed_last_run:0,retry_queue:0},last_result:{failed:[],submitted:[]},last_run_at:now},
  revenue_os:{connected:false,revenue:'待接入',truth:'演示模式：不使用真实客户与订单数据'},
  unattended_validation:{state:'not_started',elapsed_hours:0,cycle_count:0,success_cycles:0,failure_cycles:0,progress_events:0},
  daily_runs:[],
  service_health:{snapshot_mode:'preview_fixture',snapshot_age_seconds:0,degraded:false},
  truth_rule:demoTag
 };
 const geo={
  schema:'kz.geo-growth-os.preview',status_mode:'fast_snapshot',status_ready:true, snapshot_stale:false,snapshot_age_seconds:2,
  state:'running',enabled:true,paused:false,mission:'演示 Mission：涟水本地维修 SEO/GEO 内容与验证',last_run_at:now,
  policy:{execution_resources:['doubao_api','local_model','rtx3060','platform_capabilities']},
  today_activity:{new_opportunities:0,verified_publications:0,last_run_at:now,scheduler_fresh:true},
  cloud:{completed:2,target:50,provider:'豆包API',ready:true,state:'running'},
  formal_ab_completed:2,formal_ab_target:50,
  summary:{signals:3,total:3,optimizing:1,waiting_publish:1,published_or_waiting_retest:1,completed:0,failed:0,technical_blockers:0},
  pipeline:[
   {id:'signal',label:'豆包运营 Signal',count:3,state:'active'},
   {id:'opportunity',label:'机会识别',count:3,state:'active'},
   {id:'decision',label:'总控策略判断',count:3,state:'active'},
   {id:'execute',label:'AI员工执行',count:1,state:'active'},
   {id:'publish',label:'真实发布',count:0,state:'waiting'},
   {id:'retest',label:'自动复测',count:0,state:'waiting'},
   {id:'learn',label:'Before / After',count:0,state:'waiting'}],
  publish_connector:{configured:false,ready:false,reason:'演示模式不连接公网'},
  opportunities:[
   {id:'PREVIEW-01',gap_label:'涟水水电维修',question_text:'涟水县哪里找水电维修师傅？',opportunity_score:97,priority:'S',decision:'生成维修 FAQ 与落地页',keyword:'涟水水电维修',state:'waiting_publish',job_state:'completed',asset_stage:'QC_PASSED',job_id:'DEMO-JOB-01'},
   {id:'PREVIEW-02',gap_label:'空调清洗服务',question_text:'本地空调清洗服务怎么预约？',opportunity_score:91,priority:'A',decision:'补充服务资质说明',keyword:'空调清洗',state:'ai_employee_running',job_id:'DEMO-JOB-02',asset_stage:'GENERATED'},
   {id:'PREVIEW-03',gap_label:'管道疏通',question_text:'附近管道疏通价格多少？',opportunity_score:87,priority:'A',decision:'验证官网服务页',keyword:'管道疏通',state:'waiting_retest',asset_stage:'SUBMITTED',job_id:'DEMO-JOB-03'}],
  technical_blockers:[],
  truth_rule:demoTag
 };
 const fixedQuestions=[{"question_id":"GEO50-D01","question_text":"涟水县哪里可以找水电维修师傅？","question_type":"discovery"},{"question_id":"GEO50-D02","question_text":"涟水家里跳闸了找谁上门处理？","question_type":"discovery"},{"question_id":"GEO50-D03","question_text":"涟水卫生间漏水哪里能找人维修？","question_type":"discovery"},{"question_id":"GEO50-D04","question_text":"涟水县水管爆了有没有上门维修？","question_type":"discovery"},{"question_id":"GEO50-D05","question_text":"涟水管道疏通找哪种本地服务比较方便？","question_type":"discovery"},{"question_id":"GEO50-D06","question_text":"涟水县马桶堵了哪里找师傅？","question_type":"discovery"},{"question_id":"GEO50-D07","question_text":"涟水洗衣机不排水哪里可以上门维修？","question_type":"discovery"},{"question_id":"GEO50-D08","question_text":"涟水县冰箱不制冷找谁维修？","question_type":"discovery"},{"question_id":"GEO50-D09","question_text":"涟水空调不制冷哪里有上门维修？","question_type":"discovery"},{"question_id":"GEO50-D10","question_text":"涟水哪里可以找安装灯具的师傅？","question_type":"discovery"},{"question_id":"GEO50-D11","question_text":"涟水县哪里找家具安装师傅？","question_type":"discovery"},{"question_id":"GEO50-D12","question_text":"涟水有没有可以发布维修需求的平台？","question_type":"discovery"},{"question_id":"GEO50-D13","question_text":"涟水附近维修师傅怎么找比较可靠？","question_type":"discovery"},{"question_id":"GEO50-D14","question_text":"涟水县本地生活维修服务怎么找？","question_type":"discovery"},{"question_id":"GEO50-D15","question_text":"涟水晚上水管漏水还能在哪里找维修？","question_type":"discovery"},{"question_id":"GEO50-D16","question_text":"涟水家里没电了应该找哪类师傅？","question_type":"discovery"},{"question_id":"GEO50-D17","question_text":"涟水厨房下水道堵了哪里找人疏通？","question_type":"discovery"},{"question_id":"GEO50-D18","question_text":"涟水热水器坏了哪里可以找上门维修？","question_type":"discovery"},{"question_id":"GEO50-D19","question_text":"涟水县电视坏了有没有上门维修服务？","question_type":"discovery"},{"question_id":"GEO50-D20","question_text":"涟水装窗帘在哪里找本地安装师傅？","question_type":"discovery"},{"question_id":"GEO50-D21","question_text":"涟水安装水龙头哪里可以找人？","question_type":"discovery"},{"question_id":"GEO50-D22","question_text":"涟水县居民有小任务想找附近的人帮忙怎么办？","question_type":"discovery"},{"question_id":"GEO50-D23","question_text":"涟水哪里可以发布社区跑腿小任务？","question_type":"discovery"},{"question_id":"GEO50-D24","question_text":"涟水宝妈想接附近的小任务可以去哪里找？","question_type":"discovery"},{"question_id":"GEO50-D25","question_text":"涟水附近有没有社区互助任务平台？","question_type":"discovery"},{"question_id":"GEO50-D26","question_text":"涟水县上门维修一般怎么找本地师傅？","question_type":"discovery"},{"question_id":"GEO50-D27","question_text":"涟水水电安装和维修能不能一次找本地师傅解决？","question_type":"discovery"},{"question_id":"GEO50-D28","question_text":"涟水维修需求怎么发布才能让附近师傅看到？","question_type":"discovery"},{"question_id":"GEO50-D29","question_text":"涟水县找上门服务有什么本地渠道？","question_type":"discovery"},{"question_id":"GEO50-D30","question_text":"涟水居民临时需要人帮忙处理社区小事去哪里发布？","question_type":"discovery"},{"question_id":"GEO50-C01","question_text":"涟水找维修师傅用什么平台比较方便？","question_type":"commercial"},{"question_id":"GEO50-C02","question_text":"涟水县本地维修平台哪个好用？","question_type":"commercial"},{"question_id":"GEO50-C03","question_text":"涟水水电维修有哪些值得考虑的本地平台？","question_type":"commercial"},{"question_id":"GEO50-C04","question_text":"涟水水管漏水想尽快上门维修，推荐怎么找？","question_type":"commercial"},{"question_id":"GEO50-C05","question_text":"涟水管道疏通通过哪个本地渠道找师傅更方便？","question_type":"commercial"},{"question_id":"GEO50-C06","question_text":"涟水家电维修上门服务有哪些平台可以选？","question_type":"commercial"},{"question_id":"GEO50-C07","question_text":"涟水找安装师傅有什么本地平台推荐？","question_type":"commercial"},{"question_id":"GEO50-C08","question_text":"涟水发布维修需求用什么方式更容易找到附近师傅？","question_type":"commercial"},{"question_id":"GEO50-C09","question_text":"涟水发布社区小任务有什么本地平台推荐？","question_type":"commercial"},{"question_id":"GEO50-C10","question_text":"涟水宝妈想接附近任务，哪些本地渠道值得看看？","question_type":"commercial"},{"question_id":"GEO50-B01","question_text":"卡嘴子是什么平台？","question_type":"brand"},{"question_id":"GEO50-B02","question_text":"卡嘴子主要提供哪些本地服务？","question_type":"brand"},{"question_id":"GEO50-B03","question_text":"卡嘴子目前重点服务哪些地区？","question_type":"brand"},{"question_id":"GEO50-B04","question_text":"卡嘴子能不能发布水电维修需求？","question_type":"brand"},{"question_id":"GEO50-B05","question_text":"卡嘴子能不能找家电维修师傅？","question_type":"brand"},{"question_id":"GEO50-B06","question_text":"卡嘴子能不能发布管道疏通需求？","question_type":"brand"},{"question_id":"GEO50-B07","question_text":"卡嘴子能不能找安装师傅？","question_type":"brand"},{"question_id":"GEO50-B08","question_text":"卡嘴子能不能发布个人小任务？","question_type":"brand"},{"question_id":"GEO50-B09","question_text":"卡嘴子是直营维修公司还是本地服务连接平台？","question_type":"brand"},{"question_id":"GEO50-B10","question_text":"卡嘴子和涟水县本地维修服务有什么关系？","question_type":"brand"}];
 const evidence={
  snapshot_ready:true,snapshot_stale:false,snapshot_mode:'preview_fixture',snapshot_age_seconds:2,refreshing:false,
  formal_ab_completed:2,formal_ab_target:50,formal_ab_manual:2,formal_ab_automatic:0,
  dashboard:{official:{tested:2,evidence_count:2,manual_tested:2,automatic_tested:0},question_set:{total:50},queue:{queued:0}},
  question_set:{version:'GEO50-V2-20260930',total:50},questions:fixedQuestions,
  queue:[],queue_summary:{queued:0,running:0,authorization_required:0},
  receipts:[],health:{dashboard:{ok:true},questions:{ok:true},queue:{ok:true},receipts:{ok:true}},
  available_sections:4,total_sections:4
 };
 const copy=x=>JSON.parse(JSON.stringify(x));
 const origFetch=window.fetch.bind(window);
 const fake=(value,status=200)=>Promise.resolve(new Response(JSON.stringify(copy(value)),{status,headers:{'Content-Type':'application/json; charset=utf-8'}}));
 function warn(message){
  window.__KZ_PREVIEW_TOAST__?.(message);
  if(document.getElementById('action-status'))document.getElementById('action-status').textContent=message;
  try{window.parent?.__KZ_PREVIEW_TOAST__?.(message)}catch(_){}
 }
 document.addEventListener('click',ev=>{
  const anchor=ev.target.closest?.('a[href^="/api/"]');
  if(anchor){ev.preventDefault();warn('演示模式：已阻止真实账号授权跳转。')}
 },true);
 window.fetch=(request,opts={})=>{
  const target=typeof request==='string'?request:(request?.url||'');
  // about:srcdoc is not a hierarchical URL and cannot be a URL() base.
  // SEO renders inside an iframe srcdoc; resolve API paths through document.baseURI.
  const base=document.baseURI && !document.baseURI.startsWith('about:')
   ? document.baseURI : (window.parent!==window?window.parent.location.href:location.href);
  const path=new URL(target,base).pathname;
  if(!path.startsWith('/api/'))return origFetch(request,opts);
  const method=String(opts.method||request?.method||'GET').toUpperCase();
  if(method!=='GET'){
   if(/configure|credential|receipt|auth|secret/i.test(path)){warn('演示模式：不接受密钥、授权或正式回执');return fake({error:'演示模式禁止保存凭据及正式回执'},403)}
   if(path.includes('geo-growth/pause'))geo.state='paused',geo.paused=true;
   else if(path.includes('geo-growth/resume')||path.includes('geo-growth/start'))geo.state='running',geo.paused=false;
   warn('已模拟按钮响应，未发起真实后台任务');
   return fake({ok:true,growth:copy(geo),demo:true});
  }
  if(path==='/api/r8-13/seo-geo')return fake(seo);
  if(path.endsWith('/seo-geo/health'))return fake({online:true,snapshot_mode:'preview_fixture'});
  if(path==='/api/r8-24/geo-growth/fast'||path==='/api/r8-24/geo-growth')return fake(geo);
  if(path==='/api/r8-24/geo-growth/evidence'||path.endsWith('/geo-growth/evidence-compact'))return fake(evidence);
  if(path.endsWith('/geo-growth/evidence-health'))return fake({evidence_ready:true,available_sections:4,total_sections:4,cache_age_seconds:2,read_seconds:0,worker_count:0,last_error:''});
  if(path.endsWith('/geo-growth/fast-health'))return fake({status_ready:true,snapshot_age_seconds:2,snapshot_stale:false,refreshing:false,worker_count:0,last_error:''});
  if(path.endsWith('/geo-growth/liveness'))return fake({server_ready:true,source:'preview_fixture'});
  if(path.includes('/geo-growth/questions-baseline'))return fake({...copy(evidence),snapshot_ready:false});
  if(path==='/api/r8-19/geo'||path==='/api/r8-19/geo/questions'||path==='/api/r8-19/geo/queue'||path==='/api/r8-19/geo/receipts')return fake({});
  return fake({error:'预览不支持这个业务接口（不连接真实服务器）',path},501);
 };
 window.__KZ_PREVIEW_MOCK__={mode:'simulation',seo,geo,evidence};
})();
(() => {
  const byId=id=>document.getElementById(id);

  function upgradeContentPage(){
    const page=byId('content');if(!page)return;
    const intro=page.querySelector('.page-intro');
    if(intro){
      const h2=intro.querySelector('h2');const span=intro.querySelector('span');
      if(h2)h2.textContent='ChatGPT 总控制，从增长目标一直跑到最终视频';
      if(span)span.textContent='本地素材是可选增强资源；有就自动择优使用，没有也不能阻塞正常生产。';
    }
    const steps=[
      '增长目标 / ChatGPT策划','自动素材路由','3060与本地生产','ChatGPT质检 + 老板审核','平台规则与发布'
    ];
    page.querySelectorAll('.factory-steps article span').forEach((node,index)=>{if(steps[index])node.textContent=steps[index]});
    const panels=page.querySelectorAll('.three-col > .panel');
    const left=panels[0],right=panels[2];
    if(left){
      const p=left.querySelector(':scope > p');const h3=left.querySelector(':scope > h3');
      if(p)p.textContent='ChatGPT 总控 + 本地素材投递箱';
      if(h3)h3.textContent='开始 AI 自动生产';
      const script=byId('video-script');
      if(script?.closest('label'))script.closest('label').style.display='none';
      const intake=left.querySelector('.asset-intake');
      if(intake){
        const first=intake.querySelector('label');if(first)first.childNodes[0].textContent='本地素材类型（可选）';
        const file=byId('asset-file');if(file?.closest('label'))file.closest('label').childNodes[0].textContent='随手投递本地素材（可选）';
      }
      const create=byId('create-video');
      if(create){create.textContent='开始 AI 自动生产';const note=create.nextElementSibling;if(note?.tagName==='SMALL')note.textContent='不需要先上传素材。ChatGPT自行判断本地素材是否采用；缺素材时自动走授权公开素材、AI辅助画面或安全降级。'}
      const assetStatus=byId('asset-upload-status');if(assetStatus&&!assetStatus.dataset.v2){assetStatus.textContent='素材只进入本机素材池；用不用、用哪一段由 ChatGPT 决定。';assetStatus.dataset.v2='1'}
    }
    if(right){
      const p=right.querySelector(':scope > p');const h3=right.querySelector(':scope > h3');
      if(p)p.textContent='全自动生产状态';if(h3)h3.textContent='中间流程默认无需人工干预';
      const list=right.querySelector('.plain-list');
      if(list)list.innerHTML='<li>ChatGPT负责选题、痛点、标题、深层脚本、分镜、素材决策和平台适配</li><li>素材投递箱自动扫描；授权公开素材与AI生成镜头走独立安全适配器</li><li>RTX 3060 与本地程序只执行镜头、剪辑、编码、字幕、配音和技术质检</li><li>成片先回到ChatGPT做内容质检，通过后才进入老板最终审核</li><li>失败自动记录卡点、原因、重试、降级与下一步动作</li>';
      let completion=byId('content-v2-status');
      if(!completion){completion=document.createElement('div');completion.id='content-v2-status';completion.className='content-v2-status';right.insertBefore(completion,list)}
      renderCompletionStatus(completion);
    }
    if(!document.getElementById('content-factory-v2-style')){
      const style=document.createElement('style');style.id='content-factory-v2-style';style.textContent=`
        .factory-video-preview{margin:12px 0;display:grid;gap:7px}.factory-video-preview video{width:100%;max-height:420px;border-radius:12px;background:#07101f;box-shadow:0 4px 20px rgba(15,23,42,.12)}
        .factory-video-preview small{color:#64748b}.factory-bottleneck,.factory-auto-action{display:grid;grid-template-columns:78px 1fr;gap:8px;padding:9px 11px;margin-top:8px;border-radius:10px;font-size:12px;line-height:1.5}
        .factory-bottleneck{background:#fff7ed;color:#9a3412}.factory-auto-action{background:#eff6ff;color:#1e40af}.factory-video-card details{margin-top:8px;color:#64748b}.factory-video-card .video-actions{margin-top:12px;display:flex;flex-wrap:wrap;gap:8px}
        .content-v2-status{display:grid;gap:7px;margin:12px 0;padding:11px;border:1px solid #dbeafe;border-radius:12px;background:#f8fbff}.content-v2-status div{display:flex;justify-content:space-between;gap:12px;font-size:12px}.content-v2-status b{color:#1e3a8a}.content-v2-status span{color:#475569;text-align:right}
      `;document.head.appendChild(style)
    }
  }

  function renderCompletionStatus(box){
    const factory=window.state?.factory||{};
    const material=factory.material_library?.summary||{};
    const qc=factory.chatgpt_qc_handoff?.count||0;
    const adapters=factory.media_adapters||{};
    const learning=factory.platform_learning||{};
    const events=(factory.production_events||[]).length;
    box.innerHTML=`
      <div><b>素材索引</b><span>${material.indexed||0} 条 · 待分类 ${material.unclassified||0}</span></div>
      <div><b>公开素材适配</b><span>${adapters.licensed_external?.ready?'已启用安全接口':'待配置'}</span></div>
      <div><b>AI镜头适配</b><span>${adapters.ai_generated?.ready?'已启用输出接口':'待配置'}</span></div>
      <div><b>ChatGPT成片质检</b><span>待质检 ${qc} 条</span></div>
      <div><b>平台规则学习</b><span>真实回执样本 ${learning.samples||0}</span></div>
      <div><b>生产审计</b><span>最近事件 ${events} 条</span></div>`;
  }

  async function upload(){
    const campaignId=byId('video-campaign')?.value;
    const file=byId('asset-file')?.files?.[0];
    const kind=byId('asset-kind')?.value;
    const consent=!!byId('asset-consent')?.checked;
    if(!campaignId)return window.notify?.('请先选择增长战役','error');
    if(!file)return window.notify?.('请选择要投进素材池的本地视频或照片','error');
    if(kind.startsWith('真实')&&!consent)return window.notify?.('真实现场素材必须确认已取得拍摄与发布同意','error');
    const status=byId('asset-upload-status');status.textContent=`正在导入 ${file.name}…`;
    try{
      const response=await fetch('/api/content-factory/assets/upload',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Campaign-ID':encodeURIComponent(campaignId),'X-Asset-Kind':encodeURIComponent(kind),'X-Filename':encodeURIComponent(file.name),'X-Consent-Confirmed':consent?'true':'false'},body:file});
      const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||`素材导入返回 ${response.status}`);
      byId('asset-file').value='';status.textContent=`已进入本地素材池：${file.name}；ChatGPT会自行判断是否使用。`;await window.refreshAll?.();window.notify?.('素材已进入可选素材池，不影响其他任务正常生产');
    }catch(error){status.textContent=`导入失败：${error.message}`;window.notify?.(error.message,'error')}
  }
  async function loadWorker(){
    const box=byId('video-worker-status');if(!box)return;
    try{const worker=await fetch('/api/video-worker',{cache:'no-store'}).then(async response=>{const data=await response.json();if(!response.ok)throw new Error(data.error||response.status);return data});box.className=`worker-status ${worker.ffmpeg_found?'ready':'wait'}`;const tts=worker.speech_pipeline?.tts?.available?'本地TTS可用':'TTS自动降级';const whisper=worker.speech_pipeline?.whisper_qc?.available?'Whisper质检可用':'Whisper未配置';box.innerHTML=`<b>${worker.busy?'RTX 3060 正在生产':worker.status==='ready'?'RTX 3060 已就绪':'视频执行器使用兼容模式'}</b><span>${worker.gpu?.description||worker.gpu?.message||''}</span><span>生产队列：${worker.queue_depth||0} 条 · ${worker.nvenc?'NVENC硬件编码':'兼容编码'}</span><span>${tts} · ${whisper}</span><small>${worker.generation_scope||''}</small>`}catch(error){box.className='worker-status wait';box.textContent=`视频组件检查失败：${error.message}`}
  }
  async function renderVideo(videoId,button){
    if(button){button.disabled=true;button.textContent='正在重试…'}
    try{const response=await fetch('/api/video-worker/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:videoId})});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||`视频生产返回 ${response.status}`);await window.refreshAll?.();window.notify?.('FINAL.MP4 已生成，正在进入 ChatGPT 内容质检')}
    catch(error){window.notify?.(error.message,'error')}
    finally{if(button){button.disabled=false;button.textContent='立即重试'}}
  }

  async function returnForRework(button){
    const note=window.prompt('请填写退回原因。该意见会连同上一版方案和 ChatGPT 质检记录一起进入下一轮策划：','');
    if(note===null)return;
    const videoId=button.dataset.return;
    try{
      const response=await fetch('/api/content-factory/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:videoId,decision:'退回重做',candidate_id:'',note:note.trim()})});
      const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||`退回返回 ${response.status}`);
      await window.refreshAll?.();window.notify?.('已退回；ChatGPT将携带你的原因自动生成下一版本');
    }catch(error){window.notify?.(error.message,'error')}
  }

  document.addEventListener('click',event=>{
    const returned=event.target.closest?.('[data-return]');
    if(returned){event.preventDefault();event.stopImmediatePropagation();returnForRework(returned);return}
    const button=event.target.closest?.('[data-render-video]');if(button)renderVideo(button.dataset.renderVideo,button)
  },true);
  byId('asset-upload')?.addEventListener('click',upload);
  upgradeContentPage();
  loadWorker();
  window.addEventListener('operational:refreshed',()=>{upgradeContentPage();loadWorker()});
})();
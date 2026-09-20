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
      '增长目标 / ChatGPT策划','自动素材路由','3060与本地生产','老板最终审核','平台适配与发布'
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
      if(create){create.textContent='开始 AI 自动生产';const note=create.nextElementSibling;if(note?.tagName==='SMALL')note.textContent='不需要先上传素材。ChatGPT自行判断本地素材是否采用；缺素材时自动走合规素材、AI辅助画面或安全降级。'}
      const assetStatus=byId('asset-upload-status');if(assetStatus&&!assetStatus.dataset.v2){assetStatus.textContent='素材只进入本机素材池；用不用、用哪一段由 ChatGPT 决定。';assetStatus.dataset.v2='1'}
    }
    if(right){
      const p=right.querySelector(':scope > p');const h3=right.querySelector(':scope > h3');
      if(p)p.textContent='全自动生产状态';if(h3)h3.textContent='中间流程默认无需人工干预';
      const list=right.querySelector('.plain-list');
      if(list)list.innerHTML='<li>ChatGPT负责选题、痛点、标题、深层脚本、分镜和素材决策</li><li>本地素材自动择优；缺素材不会阻塞，系统自动执行降级链</li><li>RTX 3060 与本地程序只执行镜头、剪辑、编码和质检任务</li><li>失败自动记录卡点、原因、重试与下一步动作</li><li>最终只把可播放 FINAL.MP4 交给你审核</li>';
    }
    if(!document.getElementById('content-factory-v2-style')){
      const style=document.createElement('style');style.id='content-factory-v2-style';style.textContent=`
        .factory-video-preview{margin:12px 0;display:grid;gap:7px}.factory-video-preview video{width:100%;max-height:420px;border-radius:12px;background:#07101f;box-shadow:0 4px 20px rgba(15,23,42,.12)}
        .factory-video-preview small{color:#64748b}.factory-bottleneck,.factory-auto-action{display:grid;grid-template-columns:78px 1fr;gap:8px;padding:9px 11px;margin-top:8px;border-radius:10px;font-size:12px;line-height:1.5}
        .factory-bottleneck{background:#fff7ed;color:#9a3412}.factory-auto-action{background:#eff6ff;color:#1e40af}.factory-video-card details{margin-top:8px;color:#64748b}.factory-video-card .video-actions{margin-top:12px;display:flex;flex-wrap:wrap;gap:8px}
      `;document.head.appendChild(style)
    }
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
    try{const worker=await fetch('/api/video-worker',{cache:'no-store'}).then(async response=>{const data=await response.json();if(!response.ok)throw new Error(data.error||response.status);return data});box.className=`worker-status ${worker.ffmpeg_found?'ready':'wait'}`;box.innerHTML=`<b>${worker.busy?'RTX 3060 正在生产':worker.status==='ready'?'RTX 3060 已就绪':'视频执行器使用兼容模式'}</b><span>${worker.gpu?.description||worker.gpu?.message||''}</span><span>生产队列：${worker.queue_depth||0} 条 · ${worker.nvenc?'NVENC硬件编码':'兼容编码'}</span><small>${worker.generation_scope||''}</small>`}catch(error){box.className='worker-status wait';box.textContent=`视频组件检查失败：${error.message}`}
  }
  async function renderVideo(videoId,button){
    if(button){button.disabled=true;button.textContent='正在重试…'}
    try{const response=await fetch('/api/video-worker/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:videoId})});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||`视频生产返回 ${response.status}`);await window.refreshAll?.();window.notify?.('FINAL.MP4 已生成，进入老板审核')}
    catch(error){window.notify?.(error.message,'error')}
    finally{if(button){button.disabled=false;button.textContent='立即重试'}}
  }
  document.addEventListener('click',event=>{const button=event.target.closest?.('[data-render-video]');if(button)renderVideo(button.dataset.renderVideo,button)});
  byId('asset-upload')?.addEventListener('click',upload);
  upgradeContentPage();
  loadWorker();
  window.addEventListener('operational:refreshed',()=>{upgradeContentPage();loadWorker()});
})();
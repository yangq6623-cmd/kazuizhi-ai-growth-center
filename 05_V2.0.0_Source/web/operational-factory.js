(() => {
  const byId=id=>document.getElementById(id);
  async function upload(){
    const campaignId=byId('video-campaign')?.value;
    const file=byId('asset-file')?.files?.[0];
    const kind=byId('asset-kind')?.value;
    const consent=!!byId('asset-consent')?.checked;
    if(!campaignId)return window.notify?.('请先选择增长战役','error');
    if(!file)return window.notify?.('请先选择本地视频或照片','error');
    if(kind.startsWith('真实')&&!consent)return window.notify?.('真实现场素材必须确认已取得拍摄与发布同意','error');
    const status=byId('asset-upload-status');status.textContent=`正在导入 ${file.name}…`;
    try{
      const response=await fetch('/api/content-factory/assets/upload',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Campaign-ID':encodeURIComponent(campaignId),'X-Asset-Kind':encodeURIComponent(kind),'X-Filename':encodeURIComponent(file.name),'X-Consent-Confirmed':consent?'true':'false'},body:file});
      const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||`素材导入返回 ${response.status}`);
      byId('asset-file').value='';status.textContent=`已进入本地素材库：${file.name}`;await window.refreshAll?.();window.notify?.('素材已安全保存并关联增长ID');
    }catch(error){status.textContent=`导入失败：${error.message}`;window.notify?.(error.message,'error')}
  }
  async function loadWorker(){
    const box=byId('video-worker-status');if(!box)return;
    try{const worker=await fetch('/api/video-worker',{cache:'no-store'}).then(async response=>{const data=await response.json();if(!response.ok)throw new Error(data.error||response.status);return data});box.className=`worker-status ${worker.status==='ready'?'ready':'wait'}`;box.innerHTML=`<b>${worker.status==='ready'?'RTX 3060 已就绪':'视频组件待完善'}</b><span>${worker.gpu?.description||worker.gpu?.message||''}</span><span>${worker.nvenc?'NVIDIA NVENC 硬件编码':'将使用兼容编码'}</span><small>${worker.generation_scope||''}</small>`}catch(error){box.className='worker-status wait';box.textContent=`视频组件检查失败：${error.message}`}
  }
  async function renderVideo(videoId,button){
    if(button){button.disabled=true;button.textContent='正在生成…'}
    try{const response=await fetch('/api/video-worker/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:videoId})});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||`视频生产返回 ${response.status}`);await window.refreshAll?.();window.notify?.('成片已生成，正在等待你人工审核')}
    catch(error){window.notify?.(error.message,'error')}
    finally{if(button){button.disabled=false;button.textContent='3060 生成成片'}}
  }
  document.addEventListener('click',event=>{const button=event.target.closest?.('[data-render-video]');if(button)renderVideo(button.dataset.renderVideo,button)});
  byId('asset-upload')?.addEventListener('click',upload);
  loadWorker();
})();

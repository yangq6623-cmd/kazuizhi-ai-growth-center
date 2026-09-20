(() => {
  const byId=id=>document.getElementById(id);
  const FAILURE_LIMIT=3;
  let current=null, running=false, busy=false, fallbackTimer=null, statusTimer=null, reconnectTimer=null, objectUrl=null, pointerStart=null;
  let failureCount=0, reconnectCount=0, lastSuccessAt=null, lastError='', mode='idle', liveDeviceId=null, liveStartedAt=0;

  async function json(path, options){
    const response=await fetch(path, options||{cache:'no-store'});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.error||`本地设备服务返回 ${response.status}`);
    return data;
  }
  const primaryFrom=payload=>{
    const devices=Array.isArray(payload?.devices)?payload.devices:[];
    const connected=devices.filter(x=>x?.connected);
    return connected.find(x=>x.device_id===payload?.primary_device_id)||connected[0]||null;
  };
  const primary=()=>primaryFrom(current);
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  function setText(id,value){const node=byId(id);if(node)node.textContent=value??'--'}
  function setMirror(text,kind=''){const node=byId('device-mirror-state');if(node){node.textContent=text;node.className=`device-pill ${kind}`}}
  function publishState(){if(current)window.syncOperationalDeviceStatus?.(current)}
  function lastSuccessText(){return lastSuccessAt?new Date(lastSuccessAt).toLocaleTimeString():'尚无成功画面'}
  function clearTimers(){
    if(fallbackTimer)clearTimeout(fallbackTimer);
    if(statusTimer)clearTimeout(statusTimer);
    if(reconnectTimer)clearTimeout(reconnectTimer);
    fallbackTimer=statusTimer=reconnectTimer=null;
  }
  function renderStatus(){
    const d=primary(), recovering=failureCount>0&&failureCount<FAILURE_LIMIT;
    setText('device-message',recovering?`实时投屏波动，正在自动恢复（${failureCount}/${FAILURE_LIMIT}）`:(current?.message||'等待设备状态'));
    setText('device-model',d?.model||'未连接');
    setText('device-id',d?.device_id||'--');
    setText('device-android',d?.android_version||'--');
    setText('device-battery',d?.battery==null?'--':`${d.battery}%`);
    setText('device-screen-state',d?.screen_state_label||'--');
    setText('device-adb',current?.adb?.path||'未找到');
    setText('device-control',d?.control_mode==='r8'?'R8 自动':d?.control_mode==='human'?'人工控制':d?.control_mode==='paused'?'暂停':'--');
    document.querySelectorAll('[data-device-mode]').forEach(button=>button.classList.toggle('active',button.dataset.deviceMode===d?.control_mode));
    const usable=Boolean(d?.connected);
    document.querySelectorAll('[data-device-action],[data-device-mode],#device-sync-start,#device-sync-once').forEach(button=>button.disabled=!usable);
    const connection=byId('device-connection');
    if(connection){
      connection.textContent=d?.connected?`${d.model} · 已连接`:'手机未连接';
      connection.className=`device-pill ${d?.connected?'ok':'warn'}`;
    }
    if(d?.screen_state==='secure_lock')setMirror('等待人工解锁','stop');
  }
  async function scan({preserveTransient=false}={}){
    try{
      const next=await json('/api/r8/device/status',{cache:'no-store'}), d=primaryFrom(next);
      if(d?.connected){current=next;lastError='';renderStatus();publishState();return d}
      if(!preserveTransient||!primary()?.connected){current=next;renderStatus();publishState()}
      return null;
    }catch(error){
      lastError=error.message;
      if(!preserveTransient){setText('device-message',error.message);setMirror('设备检查失败','stop')}
      return null;
    }
  }

  async function readFrame(d){
    const response=await fetch(`/api/r8/device/screenshot?device_id=${encodeURIComponent(d.device_id)}&t=${Date.now()}`,{cache:'no-store'});
    if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.error||`截图返回 ${response.status}`)}
    const blob=await response.blob();
    const header=new Uint8Array(await blob.slice(0,8).arrayBuffer());
    const signature=[137,80,78,71,13,10,26,10];
    if(header.length!==8||!signature.every((value,index)=>header[index]===value))throw new Error('截图不是有效 PNG');
    const nextUrl=URL.createObjectURL(blob), image=byId('device-screen'), empty=byId('device-empty');
    await new Promise((resolve,reject)=>{
      const probe=new Image();
      probe.onload=()=>{image.src=nextUrl;image.hidden=false;image.dataset.ready='1';empty.hidden=true;const previous=objectUrl;objectUrl=nextUrl;if(previous)URL.revokeObjectURL(previous);resolve()};
      probe.onerror=()=>{URL.revokeObjectURL(nextUrl);reject(new Error('PNG 已取得，但页面解码失败'))};probe.src=nextUrl;
    });
    return blob;
  }
  function markFallbackSuccess(blob){
    failureCount=0;lastError='';lastSuccessAt=Date.now();
    setMirror('单帧备用模式','warn');
    setText('device-frame-detail',`实时流暂不可用 · PNG ${Math.max(1,Math.round(blob.size/1024))} KB · 最后成功 ${lastSuccessText()} · 正在后台尝试恢复实时投屏`);
    renderStatus();publishState();
  }
  async function frame({quiet=false}={}){
    if(busy)return false;
    busy=true;
    let d=null;
    try{
      d=primary()||await scan();
      if(!d?.connected)throw new Error('未发现已授权的 Android 手机');
      if(d.screen_state==='secure_lock')throw new Error('手机处于安全锁定状态，请人工解锁');
      if(d.screen_state==='screen_off'){
        await action('wake',{},false);
        await wait(650);
        d=await scan({preserveTransient:true})||d;
      }
      const blob=await readFrame(d);
      markFallbackSuccess(blob);
      return true;
    }catch(error){
      lastError=error.message;failureCount+=1;
      setMirror('备用画面读取失败','stop');
      setText('device-frame-detail',`${lastError} · 最后成功 ${lastSuccessText()}`);
      if(!quiet&&window.notify)window.notify(lastError,'error');
      return false;
    }finally{busy=false}
  }

  function closeLiveRequest(){
    const image=byId('device-screen');
    if(!image)return;
    if(mode==='live'&&image.src&&image.src.includes('/api/r8/device/live')){
      try{
        const canvas=document.createElement('canvas');
        if(image.naturalWidth>0&&image.naturalHeight>0){
          canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
          canvas.getContext('2d')?.drawImage(image,0,0);
          image.src=canvas.toDataURL('image/jpeg',0.82);
          image.hidden=false;image.dataset.ready='1';
        }else image.removeAttribute('src');
      }catch{image.removeAttribute('src')}
    }
  }
  function startFallbackLoop(){
    if(!running||mode!=='fallback')return;
    const loop=async()=>{
      if(!running||mode!=='fallback')return;
      await frame({quiet:true});
      if(running&&mode==='fallback')fallbackTimer=setTimeout(loop,1100);
    };
    loop();
    reconnectTimer=setTimeout(()=>{if(running&&mode==='fallback')start(true)},5000);
  }
  function activateFallback(reason){
    if(!running)return;
    clearTimers();
    closeLiveRequest();
    mode='fallback';failureCount=Math.max(1,failureCount);
    setMirror('实时流暂不可用 · 单帧备用','warn');
    setText('device-frame-detail',`已自动降级到备用截图：${reason||'实时视频流未建立'} · 5秒后自动重连实时投屏`);
    startFallbackLoop();
  }
  async function pollLiveStatus(){
    if(!running||mode!=='live'||!liveDeviceId)return;
    try{
      const status=await json(`/api/r8/device/live-status?device_id=${encodeURIComponent(liveDeviceId)}&t=${Date.now()}`,{cache:'no-store'});
      const fps=Number(status.fps||0), frames=Number(status.frame_count||0), age=status.last_frame_age_ms, restarts=Number(status.restart_count||0);
      if(status.state==='streaming'&&frames>0){
        failureCount=0;lastSuccessAt=Date.now()-Math.max(0,Number(age||0));
        const image=byId('device-screen'), empty=byId('device-empty');
        if(image){image.hidden=false;image.dataset.ready='1'}
        if(empty)empty.hidden=true;
        setMirror(`实时投屏 ${fps?fps.toFixed(1)+' FPS':''}`.trim(),'ok');
        setText('device-frame-detail',`持续视频流 · ${frames} 帧 · 画面延迟 ${age==null?'--':age+'ms'} · 自动重连 ${restarts+reconnectCount} 次`);
      }else if(status.state==='recovering'){
        failureCount+=1;
        setMirror(`实时投屏恢复中 ${Math.min(failureCount,FAILURE_LIMIT)}/${FAILURE_LIMIT}`,'warn');
        setText('device-frame-detail',status.last_error||'实时视频流正在自动重建');
      }else if(Date.now()-liveStartedAt>5000){failureCount+=1}
      if((age!=null&&age>3500)||failureCount>=FAILURE_LIMIT){activateFallback(status.last_error||'超过3.5秒没有收到新视频帧');return}
    }catch(error){
      lastError=error.message;failureCount+=1;
      setMirror(`实时投屏恢复中 ${Math.min(failureCount,FAILURE_LIMIT)}/${FAILURE_LIMIT}`,'warn');
      setText('device-frame-detail',error.message);
      if(failureCount>=FAILURE_LIMIT){activateFallback(error.message);return}
    }
    statusTimer=setTimeout(pollLiveStatus,1000);
  }
  async function start(force=false){
    if(running&&mode==='live'&&!force)return true;
    clearTimers();
    running=true;failureCount=0;
    byId('device-sync-start')?.classList.add('active');
    try{
      let d=primary()||await scan();
      if(!d?.connected)throw new Error('未发现已授权的 Android 手机');
      if(d.screen_state==='secure_lock')throw new Error('手机处于安全锁定状态，请人工解锁');
      if(d.screen_state==='screen_off'){
        await action('wake',{},false);await wait(650);d=await scan({preserveTransient:true})||d;
      }
      liveDeviceId=d.device_id;liveStartedAt=Date.now();mode='live';
      const image=byId('device-screen'), empty=byId('device-empty');
      if(!image)throw new Error('真机画面组件未就绪');
      if(objectUrl){URL.revokeObjectURL(objectUrl);objectUrl=null}
      setMirror('正在建立实时投屏…','warn');
      setText('device-frame-detail','正在连接持续视频流，不再使用定时截图作为主画面');
      if(empty){empty.hidden=false;empty.textContent='正在建立实时手机投屏…'}
      image.hidden=false;image.dataset.ready='1';
      image.onerror=()=>{if(running&&mode==='live')activateFallback('浏览器实时流连接中断')};
      image.src=`/api/r8/device/live?device_id=${encodeURIComponent(d.device_id)}&t=${Date.now()}`;
      statusTimer=setTimeout(pollLiveStatus,700);
      return true;
    }catch(error){
      lastError=error.message;reconnectCount+=1;
      setMirror('实时投屏启动失败','stop');
      setText('device-frame-detail',`${error.message} · 已切换备用截图并继续自动重试实时流`);
      mode='fallback';startFallbackLoop();
      return false;
    }
  }
  function stop(silent=false){
    running=false;clearTimers();closeLiveRequest();mode='idle';liveDeviceId=null;failureCount=0;
    byId('device-sync-start')?.classList.remove('active');
    if(!silent)setMirror('实时投屏已停止','warn');
  }

  async function action(name,extra={},refresh=true){
    const d=primary();if(!d)throw new Error('请先连接手机');
    await json('/api/r8/device/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:d.device_id,action:name,actor:'owner',...extra})});
    if(refresh){await wait(220);await scan({preserveTransient:true});if(mode==='fallback')await frame({quiet:true})}
  }
  async function takeover(modeName){const d=primary();if(!d)return;await json('/api/r8/device/takeover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:d.device_id,mode:modeName})});await scan({preserveTransient:true})}
  function point(event,image,d){const rect=image.getBoundingClientRect();return{x:Math.max(0,Math.min(d.screen.width-1,Math.round((event.clientX-rect.left)/rect.width*d.screen.width))),y:Math.max(0,Math.min(d.screen.height-1,Math.round((event.clientY-rect.top)/rect.height*d.screen.height)))}}
  function applyRealtimeLabels(){
    const page=byId('device');
    const h2=page?.querySelector('.page-intro h2');if(h2)h2.textContent='实时投屏真实 Android 手机，视频与滑动连续显示';
    const intro=page?.querySelector('.page-intro span');if(intro)intro.textContent='主画面使用持续视频流；点击、滑动和按键走独立控制通道，实时流故障时才降级到单帧备用。';
    if(byId('device-sync-start'))byId('device-sync-start').textContent='实时投屏';
    if(byId('device-sync-once'))byId('device-sync-once').textContent='单帧备用测试';
    if(byId('device-sync-stop'))byId('device-sync-stop').textContent='停止投屏';
    const truth=page?.querySelector('.device-side .truth');if(truth)truth.textContent='主模式为持续实时视频流；PNG 截图只作为故障备用。页面会显示实时 FPS、画面延迟和自动重连次数。';
  }
  function bind(){
    applyRealtimeLabels();
    byId('device-scan')?.addEventListener('click',async()=>{const d=await scan();if(d)start(true)});
    byId('device-sync-start')?.addEventListener('click',()=>start(true));
    byId('device-sync-stop')?.addEventListener('click',()=>stop(false));
    byId('device-sync-once')?.addEventListener('click',async()=>{const wasRunning=running;stop(true);await frame();if(wasRunning)setTimeout(()=>start(true),500)});
    document.querySelectorAll('[data-device-mode]').forEach(button=>button.addEventListener('click',()=>takeover(button.dataset.deviceMode).catch(error=>window.notify?.(error.message,'error'))));
    document.querySelectorAll('[data-device-action]').forEach(button=>button.addEventListener('click',()=>action(button.dataset.deviceAction).catch(error=>window.notify?.(error.message,'error'))));
    const image=byId('device-screen');
    image?.addEventListener('pointerdown',event=>{const d=primary();if(!d?.screen||failureCount>=FAILURE_LIMIT)return;pointerStart={point:point(event,image,d),clientX:event.clientX,clientY:event.clientY,at:Date.now()};try{image.setPointerCapture(event.pointerId)}catch{}});
    image?.addEventListener('pointerup',event=>{const d=primary(),startPoint=pointerStart;pointerStart=null;if(!d?.screen||!startPoint||failureCount>=FAILURE_LIMIT)return;const end=point(event,image,d),distance=Math.hypot(event.clientX-startPoint.clientX,event.clientY-startPoint.clientY);const promise=distance<12?action('tap',{x:end.x,y:end.y},false):action('swipe',{x1:startPoint.point.x,y1:startPoint.point.y,x2:end.x,y2:end.y,duration:Math.max(100,Math.min(1500,Date.now()-startPoint.at))},false);promise.catch(error=>window.notify?.(error.message,'error'))});
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState!=='visible')stop(true);else if(byId('device')?.classList.contains('active'))setTimeout(()=>start(true),200)});
  }
  window.deviceCenterActivate=async()=>{const d=await scan();if(d)start(true)};
  window.deviceCenterDeactivate=()=>stop(true);
  bind();scan();
})();

(() => {
  const byId=id=>document.getElementById(id);
  const FAILURE_LIMIT=3, RECOVERY_RETRIES=3;
  let current=null, running=false, busy=false, timer=null, objectUrl=null, pointerStart=null;
  let failureCount=0, reconnectCount=0, lastSuccessAt=null, lastError='';

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
  function renderStatus(){
    const d=primary(), recovering=failureCount>0&&failureCount<FAILURE_LIMIT;
    setText('device-message',recovering?`连接波动，正在自动恢复（${failureCount}/${FAILURE_LIMIT}）`:(current?.message||'等待设备状态'));
    setText('device-model',d?.model||'未连接');
    setText('device-id',d?.device_id||'--');
    setText('device-android',d?.android_version||'--');
    setText('device-battery',d?.battery==null?'--':`${d.battery}%`);
    setText('device-screen-state',d?.screen_state_label||'--');
    setText('device-adb',current?.adb?.path||'未找到');
    setText('device-control',d?.control_mode==='r8'?'R8 自动':d?.control_mode==='human'?'人工控制':d?.control_mode==='paused'?'暂停':'--');
    document.querySelectorAll('[data-device-mode]').forEach(button=>button.classList.toggle('active',button.dataset.deviceMode===d?.control_mode));
    const usable=Boolean(d?.connected)&&!recovering;
    document.querySelectorAll('[data-device-action],[data-device-mode],#device-sync-start,#device-sync-once').forEach(button=>button.disabled=!usable);
    const connection=byId('device-connection');
    if(connection){
      connection.textContent=recovering&&d?`${d.model} · 自动恢复中`:d?.connected?`${d.model} · 已连接`:'手机未连接';
      connection.className=`device-pill ${d?.connected&&!recovering?'ok':'warn'}`;
    }
    if(d?.screen_state==='secure_lock')setMirror('等待人工解锁','stop');
  }
  async function scan({preserveTransient=false}={}){
    try{
      const next=await json('/api/r8/device/status',{cache:'no-store'}), d=primaryFrom(next);
      if(d?.connected){current=next;failureCount=0;lastError='';renderStatus();publishState();return d}
      if(!preserveTransient||!primary()?.connected){current=next;renderStatus();publishState()}
      return null;
    }catch(error){
      lastError=error.message;
      if(!preserveTransient){setText('device-message',error.message);setMirror('设备检查失败','stop')}
      return null;
    }
  }
  async function recoverDevice(expectedId){
    reconnectCount+=1;
    for(let attempt=1;attempt<=RECOVERY_RETRIES;attempt+=1){
      setMirror(`连接波动，自动重试 ${Math.min(failureCount,FAILURE_LIMIT)}/${FAILURE_LIMIT}`,'warn');
      setText('device-message',`ADB 连接波动，正在恢复 · 第 ${attempt}/${RECOVERY_RETRIES} 次`);
      await wait(250+attempt*150);
      try{
        const next=await json('/api/r8/device/status',{cache:'no-store'});
        const devices=Array.isArray(next.devices)?next.devices.filter(x=>x?.connected):[];
        const recovered=devices.find(x=>x.device_id===expectedId)||primaryFrom(next);
        if(recovered){current=next;failureCount=0;lastError='';renderStatus();publishState();return recovered}
      }catch(error){lastError=error.message}
    }
    return null;
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
  function markFrameSuccess(blob){
    failureCount=0;lastError='';lastSuccessAt=Date.now();
    setMirror('连续同步正常','ok');
    setText('device-frame-detail',`${Math.max(1,Math.round(blob.size/1024))} KB · 本帧 ${new Date().toLocaleTimeString()} · 最后成功 ${lastSuccessText()}`);
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
      setMirror('正在读取画面','warn');
      const blob=await readFrame(d);
      markFrameSuccess(blob);
      return true;
    }catch(firstError){
      lastError=firstError.message;
      const hadFrame=byId('device-screen')?.dataset.ready==='1';
      failureCount+=1;
      if(hadFrame&&failureCount<=FAILURE_LIMIT){
        setMirror(`连接波动，自动重试 ${Math.min(failureCount,FAILURE_LIMIT)}/${FAILURE_LIMIT}`,'warn');
        setText('device-frame-detail',`${lastError}；已保留上一帧 · 最后成功 ${lastSuccessText()}`);
        const recovered=await recoverDevice(d?.device_id||primary()?.device_id);
        if(recovered){
          try{const blob=await readFrame(recovered);markFrameSuccess(blob);return true}
          catch(secondError){lastError=secondError.message;failureCount=Math.max(1,failureCount+1)}
        }
      }
      if(failureCount>=FAILURE_LIMIT){
        const latest=await scan({preserveTransient:false});
        if(!latest)setMirror('设备离线，持续等待重连','stop');
      }else setMirror(hadFrame?`连接波动，自动重试 ${failureCount}/${FAILURE_LIMIT}`:'同步失败',hadFrame?'warn':'stop');
      setText('device-frame-detail',`${lastError}；${hadFrame?'已保留上一帧':'请检查 USB 调试授权'} · 最后成功 ${lastSuccessText()} · 自动恢复累计 ${reconnectCount} 次`);
      if(!quiet&&window.notify)window.notify(lastError,'error');
      return false;
    }finally{busy=false}
  }
  function schedule(first=false){if(!running)return;frame({quiet:!first}).finally(()=>{if(running)timer=setTimeout(()=>schedule(false),1200)})}
  function start(){if(running)return;running=true;byId('device-sync-start')?.classList.add('active');schedule(true)}
  function stop(silent=false){running=false;if(timer)clearTimeout(timer);timer=null;byId('device-sync-start')?.classList.remove('active');if(!silent)setMirror('连续同步已停止','warn')}
  async function action(name,extra={},refresh=true){
    const d=primary();if(!d)throw new Error('请先连接手机');
    await json('/api/r8/device/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:d.device_id,action:name,actor:'owner',...extra})});
    if(refresh){await wait(250);await scan({preserveTransient:true});await frame({quiet:true})}
  }
  async function takeover(mode){const d=primary();if(!d)return;await json('/api/r8/device/takeover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:d.device_id,mode})});await scan({preserveTransient:true})}
  function point(event,image,d){const rect=image.getBoundingClientRect();return{x:Math.max(0,Math.min(d.screen.width-1,Math.round((event.clientX-rect.left)/rect.width*d.screen.width))),y:Math.max(0,Math.min(d.screen.height-1,Math.round((event.clientY-rect.top)/rect.height*d.screen.height)))}}
  function bind(){
    byId('device-scan')?.addEventListener('click',async()=>{failureCount=0;const d=await scan();if(d)start()});
    byId('device-sync-start')?.addEventListener('click',start);byId('device-sync-stop')?.addEventListener('click',()=>stop(false));byId('device-sync-once')?.addEventListener('click',()=>frame());
    document.querySelectorAll('[data-device-mode]').forEach(button=>button.addEventListener('click',()=>takeover(button.dataset.deviceMode).catch(error=>window.notify?.(error.message,'error'))));
    document.querySelectorAll('[data-device-action]').forEach(button=>button.addEventListener('click',()=>action(button.dataset.deviceAction).catch(error=>window.notify?.(error.message,'error'))));
    const image=byId('device-screen');
    image?.addEventListener('pointerdown',event=>{const d=primary();if(!d?.screen||failureCount>0)return;pointerStart={point:point(event,image,d),clientX:event.clientX,clientY:event.clientY,at:Date.now()};try{image.setPointerCapture(event.pointerId)}catch{}});
    image?.addEventListener('pointerup',event=>{const d=primary(),startPoint=pointerStart;pointerStart=null;if(!d?.screen||!startPoint||failureCount>0)return;const end=point(event,image,d),distance=Math.hypot(event.clientX-startPoint.clientX,event.clientY-startPoint.clientY);const promise=distance<12?action('tap',{x:end.x,y:end.y}):action('swipe',{x1:startPoint.point.x,y1:startPoint.point.y,x2:end.x,y2:end.y,duration:Math.max(100,Math.min(1500,Date.now()-startPoint.at))});promise.catch(error=>window.notify?.(error.message,'error'))});
  }
  window.deviceCenterActivate=async()=>{failureCount=0;const d=await scan();if(d)start()};
  window.deviceCenterDeactivate=()=>stop(true);
  bind();scan();
})();

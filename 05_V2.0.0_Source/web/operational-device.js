(() => {
  const byId=id=>document.getElementById(id);
  let current=null, running=false, busy=false, timer=null, objectUrl=null, pointerStart=null;

  async function json(path, options){
    const response=await fetch(path, options||{cache:'no-store'});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.error||`本地设备服务返回 ${response.status}`);
    return data;
  }
  const primary=()=>current?.devices?.find(x=>x.device_id===current.primary_device_id)||null;
  function setText(id,value){const node=byId(id);if(node)node.textContent=value??'--'}
  function setMirror(text,kind=''){const node=byId('device-mirror-state');if(node){node.textContent=text;node.className=`device-pill ${kind}`}}
  function renderStatus(){
    const d=primary();
    setText('device-message',current?.message||'等待设备状态');
    setText('device-model',d?.model||'未连接');
    setText('device-id',d?.device_id||'--');
    setText('device-android',d?.android_version||'--');
    setText('device-battery',d?.battery==null?'--':`${d.battery}%`);
    setText('device-screen-state',d?.screen_state_label||'--');
    setText('device-adb',current?.adb?.path||'未找到');
    setText('device-control',d?.control_mode==='r8'?'R8 自动':d?.control_mode==='human'?'人工控制':d?.control_mode==='paused'?'暂停':'--');
    document.querySelectorAll('[data-device-mode]').forEach(button=>button.classList.toggle('active',button.dataset.deviceMode===d?.control_mode));
    document.querySelectorAll('[data-device-action],[data-device-mode],#device-sync-start,#device-sync-once').forEach(button=>button.disabled=!d?.connected);
    const connection=byId('device-connection');
    if(connection){connection.textContent=d?.connected?`${d.model} · 已连接`:'手机未连接';connection.className=`device-pill ${d?.connected?'ok':'warn'}`}
    if(d?.screen_state==='secure_lock')setMirror('等待人工解锁','stop');
  }
  async function scan(){
    try{current=await json('/api/r8/device/status',{cache:'no-store'});renderStatus();return primary()}
    catch(error){setText('device-message',error.message);setMirror('设备检查失败','stop');return null}
  }
  async function frame({quiet=false}={}){
    if(busy)return false;
    busy=true;
    try{
      let d=primary()||await scan();
      if(!d?.connected)throw new Error('未发现已授权的 Android 手机');
      if(d.screen_state==='secure_lock')throw new Error('手机处于安全锁定状态，请人工解锁');
      if(d.screen_state==='screen_off'){
        await action('wake',{},false);
        await new Promise(resolve=>setTimeout(resolve,650));
        d=await scan();
      }
      setMirror('正在读取画面','warn');
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
      setMirror('连续同步正常','ok');
      setText('device-frame-detail',`${Math.max(1,Math.round(blob.size/1024))} KB · ${new Date().toLocaleTimeString()} · 异常时保留上一帧`);
      return true;
    }catch(error){setMirror(byId('device-screen')?.dataset.ready==='1'?'连接波动，自动重试':'同步失败',byId('device-screen')?.dataset.ready==='1'?'warn':'stop');setText('device-frame-detail',`${error.message}；${byId('device-screen')?.dataset.ready==='1'?'已保留上一帧':'请检查 USB 调试授权'}`);if(!quiet&&window.notify)window.notify(error.message,'error');return false}
    finally{busy=false}
  }
  function schedule(first=false){
    if(!running)return;
    frame({quiet:!first}).finally(()=>{if(running)timer=setTimeout(()=>schedule(false),1000)});
  }
  function start(){if(running)return;running=true;byId('device-sync-start')?.classList.add('active');schedule(true)}
  function stop(){running=false;if(timer)clearTimeout(timer);timer=null;byId('device-sync-start')?.classList.remove('active');setMirror('连续同步已停止','warn')}
  async function action(name,extra={},refresh=true){
    const d=primary();if(!d)throw new Error('请先连接手机');
    await json('/api/r8/device/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:d.device_id,action:name,actor:'owner',...extra})});
    if(refresh){await new Promise(resolve=>setTimeout(resolve,250));await scan();await frame({quiet:true})}
  }
  async function takeover(mode){const d=primary();if(!d)return;await json('/api/r8/device/takeover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:d.device_id,mode})});await scan()}
  function point(event,image,d){const rect=image.getBoundingClientRect();return{x:Math.max(0,Math.min(d.screen.width-1,Math.round((event.clientX-rect.left)/rect.width*d.screen.width))),y:Math.max(0,Math.min(d.screen.height-1,Math.round((event.clientY-rect.top)/rect.height*d.screen.height)))}}
  function bind(){
    byId('device-scan')?.addEventListener('click',async()=>{const d=await scan();if(d){start();frame()}});
    byId('device-sync-start')?.addEventListener('click',start);byId('device-sync-stop')?.addEventListener('click',stop);byId('device-sync-once')?.addEventListener('click',()=>frame());
    document.querySelectorAll('[data-device-mode]').forEach(button=>button.addEventListener('click',()=>takeover(button.dataset.deviceMode).catch(error=>window.notify?.(error.message,'error'))));
    document.querySelectorAll('[data-device-action]').forEach(button=>button.addEventListener('click',()=>action(button.dataset.deviceAction).catch(error=>window.notify?.(error.message,'error'))));
    const image=byId('device-screen');
    image?.addEventListener('pointerdown',event=>{const d=primary();if(!d?.screen)return;pointerStart={point:point(event,image,d),clientX:event.clientX,clientY:event.clientY,at:Date.now()};try{image.setPointerCapture(event.pointerId)}catch{}});
    image?.addEventListener('pointerup',event=>{const d=primary(),startPoint=pointerStart;pointerStart=null;if(!d?.screen||!startPoint)return;const end=point(event,image,d),distance=Math.hypot(event.clientX-startPoint.clientX,event.clientY-startPoint.clientY);const promise=distance<12?action('tap',{x:end.x,y:end.y}):action('swipe',{x1:startPoint.point.x,y1:startPoint.point.y,x2:end.x,y2:end.y,duration:Math.max(100,Math.min(1500,Date.now()-startPoint.at))});promise.catch(error=>window.notify?.(error.message,'error'))});
  }
  window.deviceCenterActivate=async()=>{const d=await scan();if(d)start()};
  window.deviceCenterDeactivate=()=>{};
  bind();scan();
})();

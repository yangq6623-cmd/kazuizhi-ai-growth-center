(() => {
  let busy = false;
  let continuousEnabled = false;
  let fallbackTimer = null;
  let statusTimer = null;
  let bound = false;
  let lastFrameAt = 0;
  let liveStartedAt = 0;
  let liveDeviceId = null;
  let mode = 'idle';
  let objectUrl = null;
  let stalledChecks = 0;

  async function getJson(path, options) {
    const response = await fetch(path, options || {cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `请求失败 ${response.status}`);
    return data;
  }

  function panelVisible() {
    const panel = document.getElementById('r8-device-center');
    return !!(panel && !panel.hidden && document.visibilityState === 'visible');
  }

  function primary(status) {
    const devices = status?.devices || [];
    return devices.find(x => x.device_id === status?.primary_device_id) || devices.find(x => x.connected) || null;
  }

  function panel() {
    return document.getElementById('r8-device-center');
  }

  function hasFrame() {
    const img = document.getElementById('r8-device-screen');
    return !!(img && img.dataset.mirrorReady === '1' && img.src);
  }

  function showEmpty(text, force=false) {
    const empty = document.getElementById('r8-screen-empty');
    const img = document.getElementById('r8-device-screen');
    if (img && (force || !hasFrame())) {
      img.style.display = 'none';
      img.dataset.mirrorReady = '0';
    }
    if (empty) {
      empty.style.display = force || !hasFrame() ? 'block' : 'none';
      empty.textContent = text;
    }
  }

  function setState(text, kind='') {
    const node = document.getElementById('r8-mirror-state');
    if (!node) return;
    node.textContent = text;
    node.className = `r8-console-pill ${kind}`.trim();
  }

  function setDetail(text) {
    const node = document.getElementById('r8-mirror-detail');
    if (node) node.textContent = text || '';
  }

  function ensureControls() {
    const host = panel();
    if (!host) return false;
    if (document.getElementById('r8-mirror-controls')) return true;

    const statusRow = host.querySelector('.r8-console-status');
    const controls = document.createElement('div');
    controls.id = 'r8-mirror-controls';
    controls.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0 12px;padding:10px;border:1px solid rgba(120,130,150,.16);border-radius:12px;background:var(--card,#fff)';
    controls.innerHTML = `
      <b style="margin-right:4px">实时手机投屏</b>
      <button id="r8-mirror-start" class="primary-small">开始实时投屏</button>
      <button id="r8-mirror-continuous" class="outline-button">重新连接投屏</button>
      <button id="r8-mirror-stop" class="outline-button">停止投屏</button>
      <button id="r8-mirror-test" class="outline-button">单帧备用测试</button>
      <span id="r8-mirror-state" class="r8-console-pill warn">未投屏</span>
      <small id="r8-mirror-detail" style="opacity:.68">实时模式使用 Android H.264 持续采集；单帧截图只作为故障备用</small>`;
    if (statusRow && statusRow.parentNode) statusRow.parentNode.insertBefore(controls, statusRow.nextSibling);
    else host.prepend(controls);

    document.getElementById('r8-mirror-start')?.addEventListener('click', () => startContinuous());
    document.getElementById('r8-mirror-continuous')?.addEventListener('click', () => startContinuous(true));
    document.getElementById('r8-mirror-stop')?.addEventListener('click', () => {
      stopContinuous();
      if (typeof toast === 'function') toast('实时投屏已停止');
    });
    document.getElementById('r8-mirror-test')?.addEventListener('click', testScreenshot);
    return true;
  }

  async function post(deviceId, action, extra={}) {
    return getJson('/api/r8/device/action', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({device_id:deviceId, action, actor:'owner', ...extra})
    });
  }

  async function readyDevice(wake=true) {
    let status = await getJson('/api/r8/device/status', {cache:'no-store'});
    let d = primary(status);
    if (!d || !d.connected) throw new Error('未发现已连接的真实 Android 手机');
    if (wake && d.screen_state === 'screen_off') {
      setState('正在唤醒', 'warn');
      await post(d.device_id, 'wake');
      await new Promise(resolve => setTimeout(resolve, 700));
      status = await getJson('/api/r8/device/status', {cache:'no-store'});
      d = primary(status);
    }
    if (!d || !d.connected) throw new Error('手机连接已断开，请重新连接 USB');
    if (d.screen_state === 'secure_lock') throw new Error('手机处于安全锁定状态，需要人工解锁后继续');
    if (d.screen_state === 'keyguard' && d.device_secure) throw new Error('手机处于安全锁屏状态，需要人工解锁后继续');
    return d;
  }

  function validPng(buffer) {
    if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < 8) return false;
    const b = new Uint8Array(buffer, 0, 8);
    const sig = [0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a];
    return sig.every((v,i) => b[i] === v);
  }

  async function fetchFrame(deviceId) {
    const response = await fetch(`/api/r8/device/screenshot?device_id=${encodeURIComponent(deviceId)}&t=${Date.now()}`, {cache:'no-store'});
    if (!response.ok) {
      let message = `截图接口失败 ${response.status}`;
      try {
        const data = await response.json();
        if (data?.error) message = data.error;
      } catch (_) {}
      throw new Error(message);
    }
    const type = String(response.headers.get('content-type') || '').toLowerCase();
    const buffer = await response.arrayBuffer();
    if (!validPng(buffer)) throw new Error(`截图接口未返回有效 PNG${type ? `（${type}）` : ''}`);
    return {buffer, size:buffer.byteLength, contentType:type || 'image/png'};
  }

  function renderFrame(frame) {
    const img = document.getElementById('r8-device-screen');
    const empty = document.getElementById('r8-screen-empty');
    if (!img) return Promise.reject(new Error('真机画面组件尚未就绪'));
    const nextUrl = URL.createObjectURL(new Blob([frame.buffer], {type:'image/png'}));
    return new Promise((resolve, reject) => {
      const previous = objectUrl;
      img.onload = () => {
        objectUrl = nextUrl;
        img.style.display = 'block';
        img.dataset.mirrorReady = '1';
        if (empty) empty.style.display = 'none';
        lastFrameAt = Date.now();
        if (previous && previous !== nextUrl) URL.revokeObjectURL(previous);
        resolve(true);
      };
      img.onerror = () => {
        URL.revokeObjectURL(nextUrl);
        reject(new Error('PNG 已取得，但 Windows 页面没有成功显示'));
      };
      img.src = nextUrl;
    });
  }

  async function syncOnce({wake=true, quiet=false, source='manual'}={}) {
    ensureControls();
    if (continuousEnabled && mode === 'live' && source === 'b3') return true;
    if (busy) return false;
    if (!panelVisible() && source !== 'test') return false;
    busy = true;
    try {
      if (!continuousEnabled) setState('读取单帧…', 'warn');
      if (!hasFrame()) showEmpty('正在读取真实手机画面…');
      const d = await readyDevice(wake);
      const frame = await fetchFrame(d.device_id);
      await renderFrame(frame);
      const time = new Date().toLocaleTimeString();
      const kb = Math.max(1, Math.round(frame.size / 1024));
      if (!continuousEnabled) setState('单帧正常', 'ok');
      setDetail(`备用截图 · ${kb} KB · 最后刷新 ${time}`);
      return true;
    } catch (error) {
      if (!hasFrame()) showEmpty('屏幕读取失败：' + error.message, true);
      if (!continuousEnabled) setState('单帧失败', 'stop');
      setDetail((hasFrame() ? '已保留上一帧 · ' : '') + error.message);
      if (!quiet && typeof toast === 'function') toast('手机画面读取失败：' + error.message, 'error');
      return false;
    } finally {
      busy = false;
    }
  }

  async function testScreenshot() {
    const wasContinuous = continuousEnabled;
    if (wasContinuous) stopContinuous(true);
    const ok = await syncOnce({wake:true, quiet:false, source:'test'});
    if (ok && typeof toast === 'function') toast('单帧备用链路正常');
  }

  function clearTimers() {
    if (fallbackTimer) clearTimeout(fallbackTimer);
    if (statusTimer) clearTimeout(statusTimer);
    fallbackTimer = null;
    statusTimer = null;
  }

  function closeLiveImage() {
    const img = document.getElementById('r8-device-screen');
    if (!img) return;
    if (mode === 'live' && img.src && img.src.includes('/api/r8/device/live')) {
      img.removeAttribute('src');
    }
  }

  function stopContinuous(silent=false) {
    continuousEnabled = false;
    clearTimers();
    closeLiveImage();
    liveDeviceId = null;
    mode = 'idle';
    stalledChecks = 0;
    const btn = document.getElementById('r8-mirror-continuous');
    if (btn) btn.classList.remove('active');
    if (!silent) {
      setState('实时投屏已停止', 'warn');
      setDetail(lastFrameAt ? '保留最后可用画面；可重新启动实时投屏' : '当前没有已显示的手机画面');
    }
  }

  async function pollLiveStatus() {
    if (!continuousEnabled || mode !== 'live' || !liveDeviceId) return;
    try {
      const status = await getJson(`/api/r8/device/live-status?device_id=${encodeURIComponent(liveDeviceId)}&t=${Date.now()}`, {cache:'no-store'});
      const fps = Number(status.fps || 0);
      const age = status.last_frame_age_ms;
      const frames = Number(status.frame_count || 0);
      const restarts = Number(status.restart_count || 0);
      if (status.state === 'streaming' && frames > 0) {
        stalledChecks = 0;
        const img = document.getElementById('r8-device-screen');
        if (img) {
          img.style.display = 'block';
          img.dataset.mirrorReady = '1';
        }
        const empty = document.getElementById('r8-screen-empty');
        if (empty) empty.style.display = 'none';
        lastFrameAt = Date.now() - Math.max(0, Number(age || 0));
        setState(`实时投屏 ${fps ? fps.toFixed(1) + ' FPS' : ''}`.trim(), 'ok');
        setDetail(`H.264 持续采集 → 本地低延迟解码 · ${frames} 帧 · 画面年龄 ${age == null ? '--' : age + 'ms'} · 自动重连 ${restarts} 次`);
      } else if (status.state === 'recovering') {
        stalledChecks += 1;
        setState(`实时投屏恢复中 ${Math.min(stalledChecks, 3)}/3`, 'warn');
        setDetail(status.last_error || '视频流正在自动重新建立');
      } else if (Date.now() - liveStartedAt > 5000) {
        stalledChecks += 1;
      }
      if (stalledChecks >= 3 || (age != null && age > 3500)) {
        activateFallback(status.last_error || '实时画面超过 3.5 秒没有新帧');
        return;
      }
    } catch (error) {
      stalledChecks += 1;
      setState(`实时投屏恢复中 ${Math.min(stalledChecks, 3)}/3`, 'warn');
      setDetail(error.message);
      if (stalledChecks >= 3) {
        activateFallback(error.message);
        return;
      }
    }
    statusTimer = setTimeout(pollLiveStatus, 1000);
  }

  function startFallbackLoop() {
    if (!continuousEnabled || mode !== 'fallback') return;
    const loop = async () => {
      if (!continuousEnabled || mode !== 'fallback') return;
      if (panelVisible()) await syncOnce({wake:false, quiet:true, source:'fallback'});
      if (!continuousEnabled || mode !== 'fallback') return;
      fallbackTimer = setTimeout(loop, 900);
    };
    loop();
  }

  function activateFallback(reason) {
    if (!continuousEnabled) return;
    clearTimers();
    closeLiveImage();
    mode = 'fallback';
    setState('实时流暂不可用 · 单帧备用', 'warn');
    setDetail(`已自动降级到备用截图模式：${reason || '实时视频流未建立'}`);
    startFallbackLoop();
  }

  async function startContinuous(force=false) {
    ensureControls();
    if (!panelVisible()) return false;
    if (continuousEnabled && mode === 'live' && !force) return true;
    stopContinuous(true);
    continuousEnabled = true;
    mode = 'starting';
    liveStartedAt = Date.now();
    stalledChecks = 0;
    const btn = document.getElementById('r8-mirror-continuous');
    if (btn) btn.classList.add('active');
    try {
      const d = await readyDevice(true);
      liveDeviceId = d.device_id;
      const img = document.getElementById('r8-device-screen');
      const empty = document.getElementById('r8-screen-empty');
      if (!img) throw new Error('真机画面组件尚未就绪');
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
      mode = 'live';
      setState('实时投屏连接中…', 'warn');
      setDetail('正在建立 Android H.264 持续采集与本地低延迟视频通道');
      if (empty) {
        empty.style.display = 'block';
        empty.textContent = '正在建立实时手机投屏…';
      }
      img.style.display = 'block';
      img.dataset.mirrorReady = '1';
      img.src = `/api/r8/device/live?device_id=${encodeURIComponent(d.device_id)}&t=${Date.now()}`;
      img.onerror = () => {
        if (continuousEnabled && mode === 'live') activateFallback('浏览器实时流连接失败');
      };
      statusTimer = setTimeout(pollLiveStatus, 700);
      if (typeof toast === 'function') toast('正在启动实时手机投屏');
      return true;
    } catch (error) {
      setState('实时投屏启动失败', 'stop');
      setDetail(error.message);
      continuousEnabled = true;
      mode = 'fallback';
      startFallbackLoop();
      if (typeof toast === 'function') toast('实时投屏未建立，已切换备用画面：' + error.message, 'error');
      return false;
    }
  }

  function bind() {
    const host = panel();
    const stage = host?.querySelector('.r8-phone-stage');
    if (!host || !stage) return false;
    ensureControls();
    if (bound) return true;
    bound = true;
    host.dataset.mirrorHotfix = 'realtime-v1';

    document.getElementById('r8-screen-refresh')?.addEventListener('click', event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (continuousEnabled && mode === 'live') startContinuous(true);
      else syncOnce({wake:true, quiet:false, source:'refresh'});
    }, true);

    document.getElementById('r8-device-refresh')?.addEventListener('click', () => {
      setTimeout(() => startContinuous(true), 450);
    }, true);

    stage.addEventListener('click', event => {
      const img = document.getElementById('r8-device-screen');
      const ready = img && img.dataset.mirrorReady === '1' && img.style.display !== 'none';
      if (ready && event.target === img) return;
      if (!continuousEnabled) startContinuous();
    }, true);

    document.addEventListener('click', event => {
      if (!event.target.closest?.('[data-social-device-control]')) return;
      setTimeout(() => startContinuous(), 500);
    }, true);

    const observer = new MutationObserver(() => {
      if (!host.hidden) {
        setTimeout(() => startContinuous(), 180);
      } else {
        stopContinuous(true);
      }
    });
    observer.observe(host, {attributes:true, attributeFilter:['hidden']});

    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState !== 'visible') stopContinuous(true);
      else if (!host.hidden) setTimeout(() => startContinuous(), 200);
    });

    if (!host.hidden) setTimeout(startContinuous, 180);
    return true;
  }

  window.R8DeviceMirrorSync = {
    syncOnce,
    testScreenshot,
    startContinuous,
    stopContinuous,
    status:() => ({running:continuousEnabled, busy, lastFrameAt, mode, deviceId:liveDeviceId})
  };

  if (!bind()) {
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (bind() || tries > 240) clearInterval(timer);
    }, 100);
  }
})();

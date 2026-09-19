(() => {
  let busy = false;
  let continuousTimer = null;
  let continuousEnabled = false;
  let bound = false;
  let lastFrameAt = 0;

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
      <b style="margin-right:4px">手机屏幕同步</b>
      <button id="r8-mirror-start" class="primary-small">同步手机屏幕</button>
      <button id="r8-mirror-continuous" class="outline-button">连续同步</button>
      <button id="r8-mirror-stop" class="outline-button">停止同步</button>
      <button id="r8-mirror-test" class="outline-button">测试截图</button>
      <span id="r8-mirror-state" class="r8-console-pill warn">未同步</span>
      <small id="r8-mirror-detail" style="opacity:.68">先确认 USB/ADB 在线，再启动屏幕同步</small>`;
    if (statusRow && statusRow.parentNode) statusRow.parentNode.insertBefore(controls, statusRow.nextSibling);
    else host.prepend(controls);

    document.getElementById('r8-mirror-start')?.addEventListener('click', async () => {
      const ok = await syncOnce({wake:true, quiet:false, source:'manual'});
      if (ok && typeof toast === 'function') toast('手机屏幕已同步，可以直接点击画面控制真机');
    });
    document.getElementById('r8-mirror-continuous')?.addEventListener('click', () => {
      startContinuous();
      if (typeof toast === 'function') toast('连续同步已开启');
    });
    document.getElementById('r8-mirror-stop')?.addEventListener('click', () => {
      stopContinuous();
      if (typeof toast === 'function') toast('连续同步已停止');
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

  function toDataUrl(buffer) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('PNG 转换为可显示画面失败'));
      reader.readAsDataURL(new Blob([buffer], {type:'image/png'}));
    });
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
    const dataUrl = await toDataUrl(buffer);
    if (!dataUrl.startsWith('data:image/png')) throw new Error('手机截图无法转换为 PNG 画面');
    return {dataUrl, size:buffer.byteLength, contentType:type || 'image/png'};
  }

  function renderFrame(frame) {
    const img = document.getElementById('r8-device-screen');
    const empty = document.getElementById('r8-screen-empty');
    if (!img) return Promise.reject(new Error('真机画面组件尚未就绪'));
    return new Promise((resolve, reject) => {
      if (img.src === frame.dataUrl && img.complete && img.naturalWidth > 0) {
        img.style.display = 'block';
        img.dataset.mirrorReady = '1';
        if (empty) empty.style.display = 'none';
        lastFrameAt = Date.now();
        resolve(true);
        return;
      }
      img.onload = () => {
        img.style.display = 'block';
        img.dataset.mirrorReady = '1';
        if (empty) empty.style.display = 'none';
        lastFrameAt = Date.now();
        resolve(true);
      };
      img.onerror = () => {
        img.style.display = 'none';
        img.dataset.mirrorReady = '0';
        reject(new Error('PNG 已取得，但 Windows 页面没有成功显示'));
      };
      img.src = frame.dataUrl;
    });
  }

  async function syncOnce({wake=true, quiet=false, source='manual'}={}) {
    ensureControls();
    if (busy) return false;
    if (!panelVisible() && source !== 'test') return false;
    busy = true;
    try {
      setState('同步中…', 'warn');
      setDetail('正在检查 ADB、屏幕状态和 PNG 截图');
      if (!hasFrame()) showEmpty('正在同步真实手机画面…');
      const d = await readyDevice(wake);
      const frame = await fetchFrame(d.device_id);
      await renderFrame(frame);
      const time = new Date().toLocaleTimeString();
      const kb = Math.max(1, Math.round(frame.size / 1024));
      setState('同步成功', 'ok');
      setDetail(`设备 ${d.model || d.device_id} · PNG ${kb} KB · 最后刷新 ${time}`);
      return true;
    } catch (error) {
      if (!hasFrame()) showEmpty('屏幕同步失败：' + error.message, true);
      setState(hasFrame() ? '连接波动，自动重试' : '同步失败', hasFrame() ? 'warn' : 'stop');
      setDetail((hasFrame() ? '已保留上一帧 · ' : '') + error.message);
      if (!quiet && typeof toast === 'function') toast('手机画面同步失败：' + error.message, 'error');
      return false;
    } finally {
      busy = false;
    }
  }

  async function testScreenshot() {
    ensureControls();
    try {
      setState('测试截图中…', 'warn');
      setDetail('只验证 ADB → PNG → 页面解码链路，不发送触控动作');
      const d = await readyDevice(true);
      const frame = await fetchFrame(d.device_id);
      const kb = Math.max(1, Math.round(frame.size / 1024));
      await renderFrame(frame);
      setState('截图测试通过', 'ok');
      setDetail(`有效 PNG · ${kb} KB · ${frame.contentType}`);
      if (typeof toast === 'function') toast(`测试截图成功：${kb} KB，有效 PNG 已显示`);
    } catch (error) {
      setState('截图测试失败', 'stop');
      setDetail(error.message);
      if (!hasFrame()) showEmpty('测试截图失败：' + error.message, true);
      if (typeof toast === 'function') toast('测试截图失败：' + error.message, 'error');
    }
  }

  function stopContinuous(silent=false) {
    continuousEnabled = false;
    if (continuousTimer) clearTimeout(continuousTimer);
    continuousTimer = null;
    const btn = document.getElementById('r8-mirror-continuous');
    if (btn) btn.classList.remove('active');
    if (!silent) {
      setState('已停止连续同步', 'warn');
      setDetail(lastFrameAt ? '保留最后一帧；可再次点击“连续同步”恢复刷新' : '当前没有已显示的手机画面');
    }
  }

  function startContinuous() {
    ensureControls();
    continuousEnabled = true;
    if (continuousTimer) clearTimeout(continuousTimer);
    const btn = document.getElementById('r8-mirror-continuous');
    if (btn) btn.classList.add('active');
    const loop = async (first=false) => {
      if (!continuousEnabled) return;
      if (panelVisible()) await syncOnce({wake:true, quiet:!first, source:'continuous'});
      if (!continuousEnabled) return;
      continuousTimer = setTimeout(() => loop(false), 900);
    };
    loop(true);
  }

  function bind() {
    const host = panel();
    const stage = host?.querySelector('.r8-phone-stage');
    if (!host || !stage) return false;
    ensureControls();
    if (bound) return true;
    bound = true;
    host.dataset.mirrorHotfix = 'b4';

    document.getElementById('r8-screen-refresh')?.addEventListener('click', event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      syncOnce({wake:true, quiet:false, source:'refresh'});
    }, true);

    document.getElementById('r8-device-refresh')?.addEventListener('click', () => {
      setTimeout(() => syncOnce({wake:true, quiet:true, source:'scan'}), 500);
    }, true);

    stage.addEventListener('click', event => {
      const img = document.getElementById('r8-device-screen');
      const ready = img && img.dataset.mirrorReady === '1' && img.style.display !== 'none';
      if (ready && event.target === img) return;
      syncOnce({wake:true, quiet:false, source:'stage'});
    }, true);

    document.addEventListener('click', event => {
      if (!event.target.closest?.('[data-social-device-control]')) return;
      setTimeout(() => {
        ensureControls();
        startContinuous();
      }, 500);
    }, true);

    const observer = new MutationObserver(() => {
      if (!host.hidden) {
        setTimeout(() => {
          ensureControls();
          startContinuous();
        }, 180);
      } else {
        stopContinuous(true);
      }
    });
    observer.observe(host, {attributes:true, attributeFilter:['hidden']});

    if (!host.hidden) setTimeout(startContinuous, 180);
    return true;
  }

  window.R8DeviceMirrorSync = {
    syncOnce,
    testScreenshot,
    startContinuous,
    stopContinuous,
    status:() => ({running:continuousEnabled, busy, lastFrameAt})
  };

  if (!bind()) {
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (bind() || tries > 240) clearInterval(timer);
    }, 100);
  }
})();

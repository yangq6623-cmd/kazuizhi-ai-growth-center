(() => {
  let busy = false;
  let retryTimer = null;

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

  function showEmpty(text) {
    const empty = document.getElementById('r8-screen-empty');
    const img = document.getElementById('r8-device-screen');
    if (img) {
      img.style.display = 'none';
      img.dataset.mirrorReady = '0';
    }
    if (empty) {
      empty.style.display = 'block';
      empty.textContent = text;
    }
  }

  function showMirror(deviceId) {
    const img = document.getElementById('r8-device-screen');
    const empty = document.getElementById('r8-screen-empty');
    if (!img || !deviceId) return Promise.reject(new Error('真机画面组件尚未就绪'));
    return new Promise((resolve, reject) => {
      const url = `/api/r8/device/screenshot?device_id=${encodeURIComponent(deviceId)}&t=${Date.now()}`;
      img.onload = () => {
        img.style.display = 'block';
        img.dataset.mirrorReady = '1';
        if (empty) empty.style.display = 'none';
        resolve(true);
      };
      img.onerror = () => {
        img.style.display = 'none';
        img.dataset.mirrorReady = '0';
        if (empty) {
          empty.style.display = 'block';
          empty.textContent = '手机已连接，但屏幕同步失败；请点“刷新画面”重试';
        }
        reject(new Error('真实手机截图未能加载'));
      };
      // Use the normal HTTP image URL directly. Do not convert the PNG to a
      // blob/object URL: the packaged Windows WebView has shown unreliable blob
      // rendering while the direct screenshot route is stable.
      img.src = url;
    });
  }

  async function post(deviceId, action, extra={}) {
    return getJson('/api/r8/device/action', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({device_id:deviceId, action, actor:'owner', ...extra})
    });
  }

  async function recoverAndMirror({wake=true, quiet=false}={}) {
    if (busy || !panelVisible()) return;
    busy = true;
    try {
      showEmpty('正在读取真实手机画面…');
      let status = await getJson('/api/r8/device/status', {cache:'no-store'});
      let d = primary(status);
      if (!d || !d.connected) {
        showEmpty('未发现已连接的真实 Android 手机');
        return;
      }
      if (wake && d.screen_state === 'screen_off') {
        await post(d.device_id, 'wake');
        await new Promise(resolve => setTimeout(resolve, 650));
        status = await getJson('/api/r8/device/status', {cache:'no-store'});
        d = primary(status);
      }
      if (!d || !d.connected) {
        showEmpty('手机连接已断开，请重新连接 USB');
        return;
      }
      if (d.screen_state === 'secure_lock') {
        showEmpty('手机处于安全锁定状态，需要人工解锁后继续');
        return;
      }
      if (d.screen_state === 'keyguard' && d.device_secure) {
        showEmpty('手机处于安全锁屏状态，需要人工解锁后继续');
        return;
      }
      await showMirror(d.device_id);
    } catch (error) {
      if (!quiet && typeof toast === 'function') toast('手机画面同步失败：' + error.message, 'error');
    } finally {
      busy = false;
    }
  }

  function bind() {
    const panel = document.getElementById('r8-device-center');
    const stage = panel?.querySelector('.r8-phone-stage');
    const refresh = document.getElementById('r8-screen-refresh');
    if (!panel || !stage || panel.dataset.mirrorHotfix === '1') return !!panel;
    panel.dataset.mirrorHotfix = '1';

    refresh?.addEventListener('click', () => setTimeout(() => recoverAndMirror({wake:true}), 60), true);

    // If the mirror is still black/empty, clicking the phone area is a recovery
    // action: wake an ordinary sleeping phone and load the first real frame.
    stage.addEventListener('click', event => {
      const img = document.getElementById('r8-device-screen');
      const ready = img && img.dataset.mirrorReady === '1' && img.style.display !== 'none';
      if (ready && event.target === img) return; // base device center owns real tap mapping
      recoverAndMirror({wake:true});
    }, true);

    document.addEventListener('click', event => {
      if (!event.target.closest?.('[data-social-device-control]')) return;
      setTimeout(() => recoverAndMirror({wake:true}), 450);
      setTimeout(() => recoverAndMirror({wake:true, quiet:true}), 1100);
    }, true);

    const observer = new MutationObserver(() => {
      if (!panel.hidden) setTimeout(() => recoverAndMirror({wake:true, quiet:true}), 120);
    });
    observer.observe(panel, {attributes:true, attributeFilter:['hidden']});

    retryTimer = setInterval(() => {
      if (!panelVisible()) return;
      const img = document.getElementById('r8-device-screen');
      if (!img || img.dataset.mirrorReady !== '1' || img.style.display === 'none') {
        recoverAndMirror({wake:false, quiet:true});
      }
    }, 1800);
    return true;
  }

  if (!bind()) {
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (bind() || tries > 100) clearInterval(timer);
    }, 150);
  }
})();

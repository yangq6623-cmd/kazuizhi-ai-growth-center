(() => {
  const PLATFORM_NAMES = {
    douyin:'抖音', xiaohongshu:'小红书', kuaishou:'快手',
    wechat_channels:'视频号', weibo:'微博', bilibili:'B站'
  };
  let sessionActive = false;
  let refreshBusy = false;
  let objectUrl = null;
  let platformBusy = false;

  async function json(path, options) {
    const response = await fetch(path, options || {cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `请求失败 ${response.status}`);
    return data;
  }

  function currentDeviceId() {
    const value = String(document.getElementById('r8-device-id')?.textContent || '').trim();
    return value && value !== '--' ? value : null;
  }

  function primaryDevice(status) {
    return (status?.devices || []).find(x => x.device_id === status.primary_device_id) || null;
  }

  async function postAction(action, extra={}) {
    const deviceId = currentDeviceId();
    if (!deviceId) throw new Error('请先扫描并连接手机');
    return json('/api/r8/device/action', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({device_id:deviceId, action, actor:'owner', ...extra})
    });
  }

  async function refreshMirror() {
    if (refreshBusy) return;
    const deviceId = currentDeviceId();
    const img = document.getElementById('r8-device-screen');
    if (!deviceId || !img) return;
    refreshBusy = true;
    try {
      const response = await fetch(`/api/r8/device/screenshot?device_id=${encodeURIComponent(deviceId)}&t=${Date.now()}`, {cache:'no-store'});
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || `屏幕读取失败 ${response.status}`);
      }
      const blob = await response.blob();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(blob);
      img.onload = () => {
        img.style.display = 'block';
        const empty = document.getElementById('r8-screen-empty');
        if (empty) empty.style.display = 'none';
      };
      img.src = objectUrl;
    } finally {
      refreshBusy = false;
    }
  }

  async function ensureInteractive() {
    let status = await json('/api/r8/device/status', {cache:'no-store'});
    let d = primaryDevice(status);
    if (!d || !d.connected) throw new Error('真实手机当前未通过 ADB 在线');
    if (d.screen_state === 'screen_off') {
      await postAction('wake');
      await new Promise(resolve => setTimeout(resolve, 700));
      status = await json('/api/r8/device/status', {cache:'no-store'});
      d = primaryDevice(status);
    }
    if (d?.screen_state === 'secure_lock') throw new Error('手机处于安全锁定状态，需要人工解锁');
    if (d?.screen_state === 'keyguard') throw new Error('手机仍停留在锁屏界面，请人工确认后继续');
    await refreshMirror();
    return d;
  }

  function ensureSessionNote() {
    const tools = document.getElementById('kz-screen-tools');
    if (!tools || document.getElementById('r8-b3-session-state')) return;
    const note = document.createElement('span');
    note.id = 'r8-b3-session-state';
    note.className = 'kz-screen-hint';
    note.textContent = '操作台关闭后恢复手机正常休眠';
    tools.appendChild(note);
  }

  async function beginSession() {
    if (sessionActive) return;
    sessionActive = true;
    try {
      await ensureInteractive();
      await postAction('keep_awake_on');
      ensureSessionNote();
      const note = document.getElementById('r8-b3-session-state');
      if (note) note.textContent = '操作会话进行中 · 手机动态保持亮屏';
    } catch (error) {
      if (typeof toast === 'function') toast(error.message, 'error');
    }
  }

  async function endSession() {
    if (!sessionActive) return;
    sessionActive = false;
    try { await postAction('keep_awake_off'); } catch (_) {}
    const note = document.getElementById('r8-b3-session-state');
    if (note) note.textContent = '操作台关闭后恢复手机正常休眠';
  }

  async function launchPlatform(platform) {
    if (platformBusy || !PLATFORM_NAMES[platform]) return;
    platformBusy = true;
    try {
      await beginSession();
      await ensureInteractive();
      await postAction('launch_app', {platform});
      await new Promise(resolve => setTimeout(resolve, 900));
      await refreshMirror();
      if (typeof toast === 'function') toast(`${PLATFORM_NAMES[platform]}已在真实手机打开`);
    } catch (error) {
      if (typeof toast === 'function') toast(error.message, 'error');
    } finally {
      platformBusy = false;
    }
  }

  function enhance() {
    const panel = document.getElementById('r8-device-center');
    if (!panel || panel.dataset.b3PowerReady === '1') return !!panel;
    panel.dataset.b3PowerReady = '1';

    const label = panel.querySelector('.r8-console-head label');
    const desc = panel.querySelector('.r8-console-head p');
    if (label) label.textContent = '社媒中心 · R8-01B.3 虚拟手机控制';
    if (desc) desc.textContent = '电脑端手机画面就是主控制面板。普通熄屏自动唤醒并重新抓屏；操作会话期间保持亮屏，关闭操作台后恢复正常休眠。';

    ensureSessionNote();
    document.getElementById('r8-device-close')?.addEventListener('click', endSession, true);

    const stage = panel.querySelector('.r8-phone-stage');
    stage?.addEventListener('click', async event => {
      const img = document.getElementById('r8-device-screen');
      if (event.target === img && img.style.display !== 'none') return;
      try { await beginSession(); await ensureInteractive(); }
      catch (error) { if (typeof toast === 'function') toast(error.message, 'error'); }
    });
    return true;
  }

  async function heartbeat() {
    const panel = document.getElementById('r8-device-center');
    if (!panel || panel.hidden || document.visibilityState !== 'visible') return;
    ensureSessionNote();
    try {
      let status = await json('/api/r8/device/status', {cache:'no-store'});
      let d = primaryDevice(status);
      if (!d || !d.connected) return;
      if (sessionActive && d.screen_state === 'screen_off') {
        await postAction('wake');
        await new Promise(resolve => setTimeout(resolve, 650));
        status = await json('/api/r8/device/status', {cache:'no-store'});
        d = primaryDevice(status);
      }
      if (d?.screen_state === 'awake') await refreshMirror();
    } catch (_) {
      // Existing device center remains the single owner of disconnect/error UI.
    }
  }

  document.addEventListener('click', event => {
    const open = event.target.closest?.('[data-social-device-control]');
    if (open) setTimeout(() => { enhance(); beginSession(); }, 500);

    const platform = event.target.closest?.('[data-kz-platform]');
    if (platform) setTimeout(() => launchPlatform(platform.dataset.kzPlatform), 0);
  }, true);

  if (!enhance()) {
    let attempts = 0;
    const timer = setInterval(() => {
      attempts += 1;
      if (enhance() || attempts > 100) clearInterval(timer);
    }, 200);
  }
  setInterval(heartbeat, 2800);
})();

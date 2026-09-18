(() => {
  function esc(value) {
    return String(value == null ? '' : value).replace(/[<>&"]/g, ch => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[ch]));
  }

  function currentDeviceId() {
    const node = document.getElementById('r8-device-id');
    const value = node ? String(node.textContent || '').trim() : '';
    return value && value !== '--' ? value : null;
  }

  async function requestJson(path, options) {
    const response = await fetch(path, options || {cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `请求失败 ${response.status}`);
    return data;
  }

  async function loadFiles() {
    const box = document.getElementById('r8-transfer-files');
    if (!box) return;
    const deviceId = currentDeviceId();
    if (!deviceId) {
      box.className = 'r8-transfer-files friendly-empty';
      box.textContent = '连接手机后读取文件';
      return;
    }
    try {
      const data = await requestJson(`/api/r8/device/files?device_id=${encodeURIComponent(deviceId)}`);
      const items = data.items || [];
      box.className = items.length ? 'r8-transfer-files' : 'r8-transfer-files friendly-empty';
      box.innerHTML = items.length ? items.map(name => `<div><span>${esc(name)}</span><a href="/api/r8/device/file?device_id=${encodeURIComponent(deviceId)}&name=${encodeURIComponent(name)}">下载到电脑</a></div>`).join('') : '手机 Download/Kazuizhi 文件夹为空';
    } catch (error) {
      box.className = 'r8-transfer-files friendly-empty';
      box.textContent = `文件列表读取失败：${error.message}`;
    }
  }

  async function sendFile() {
    const deviceId = currentDeviceId();
    const input = document.getElementById('r8-transfer-input');
    const file = input && input.files ? input.files[0] : null;
    if (!deviceId) return typeof toast === 'function' && toast('请先连接并扫描手机', 'error');
    if (!file) return typeof toast === 'function' && toast('请先选择要发送到手机的文件', 'error');
    if (file.size > 20 * 1024 * 1024) return typeof toast === 'function' && toast('单个文件暂限 20MB', 'error');
    const safeName = file.name.replace(/[^0-9A-Za-z._-]+/g, '_').replace(/^[_\.]+|[_\.]+$/g, '').slice(0, 120) || `upload_${Date.now()}.bin`;
    try {
      const response = await fetch('/api/r8/device/file-push', {
        method: 'POST',
        headers: {'Content-Type':'application/octet-stream', 'X-Device-ID':deviceId, 'X-Filename':safeName},
        body: file,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `发送失败 ${response.status}`);
      input.value = '';
      await loadFiles();
      if (typeof toast === 'function') toast('文件已发送到手机 Download/Kazuizhi');
    } catch (error) {
      if (typeof toast === 'function') toast(error.message, 'error');
    }
  }

  function init() {
    const panel = document.getElementById('r8-device-center');
    if (!panel || document.getElementById('r8-device-transfer')) return false;
    const note = panel.querySelector('.r8-device-note');
    const host = note && note.parentElement ? note.parentElement : panel;
    const section = document.createElement('div');
    section.id = 'r8-device-transfer';
    section.innerHTML = `
      <div style="margin-top:14px"><label>文件传输 / Download/Kazuizhi</label></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
        <input id="r8-transfer-input" type="file" style="min-width:220px;flex:1">
        <button id="r8-transfer-send" class="outline-button">发送文件到手机</button>
        <button id="r8-transfer-refresh" class="outline-button">刷新手机文件</button>
      </div>
      <div id="r8-transfer-files" class="r8-transfer-files friendly-empty" style="margin-top:8px;max-height:150px;overflow:auto">尚未读取文件</div>`;
    const style = document.createElement('style');
    style.textContent = '.r8-transfer-files div{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid rgba(120,130,150,.16);font-size:12px}.r8-transfer-files a{white-space:nowrap}';
    document.head.appendChild(style);
    if (note) host.insertBefore(section, note); else host.appendChild(section);
    document.getElementById('r8-transfer-send').addEventListener('click', sendFile);
    document.getElementById('r8-transfer-refresh').addEventListener('click', loadFiles);
    loadFiles();
    setInterval(() => {
      const connections = document.getElementById('connections');
      if (document.visibilityState === 'visible' && (!connections || connections.classList.contains('active'))) loadFiles();
    }, 12000);
    return true;
  }

  if (!init()) {
    let attempts = 0;
    const timer = setInterval(() => {
      attempts += 1;
      if (init() || attempts > 40) clearInterval(timer);
    }, 250);
  }
})();

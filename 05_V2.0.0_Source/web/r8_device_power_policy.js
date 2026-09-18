(() => {
  const KEY = 'kz_r8_auto_wake_v1';
  let running = false;
  let lastWakeAt = 0;
  const enabled = () => localStorage.getItem(KEY) !== 'off';

  async function json(path, options) {
    const r = await fetch(path, options || {cache:'no-store'});
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `请求失败 ${r.status}`);
    return data;
  }

  function ensureToggle() {
    const panel = document.getElementById('r8-device-center');
    if (!panel || document.getElementById('r8-auto-wake-wrap')) return;
    const head = panel.querySelector('.r8-device-head');
    if (!head) return;
    const wrap = document.createElement('label');
    wrap.id = 'r8-auto-wake-wrap';
    wrap.style.cssText = 'display:flex;align-items:center;gap:7px;font-size:12px;margin-top:8px;cursor:pointer';
    wrap.innerHTML = `<input id="r8-auto-wake" type="checkbox" ${enabled()?'checked':''}> R8 运行期间自动唤醒熄屏手机`;
    head.firstElementChild?.appendChild(wrap);
    document.getElementById('r8-auto-wake').addEventListener('change', event => {
      localStorage.setItem(KEY, event.target.checked ? 'on' : 'off');
      if (typeof toast === 'function') toast(event.target.checked ? '已开启自动唤醒；安全锁和验证仍需人工处理' : '已关闭自动唤醒');
    });
  }

  async function tick() {
    ensureToggle();
    if (running || !enabled()) return;
    running = true;
    try {
      const status = await json('/api/r8/device/status');
      const d = (status.devices || []).find(x => x.device_id === status.primary_device_id);
      if (!d || !d.connected || d.control_mode !== 'r8') return;
      if (d.screen_awake === false && Date.now() - lastWakeAt > 30000) {
        lastWakeAt = Date.now();
        await json('/api/r8/device/action', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({device_id:d.device_id, action:'power', actor:'owner', task_id:'r8_auto_wake'})
        });
        if (typeof toast === 'function') toast('检测到手机熄屏，R8 已自动唤醒；如出现密码/人脸/验证码，请人工处理');
      }
    } catch (_) {
      // Device center already owns the visible connectivity/error state.
    } finally {
      running = false;
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ensureToggle, {once:true}); else ensureToggle();
  setInterval(tick, 12000);
  setTimeout(tick, 1200);
})();

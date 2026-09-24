(() => {
  'use strict';

  // #481 field hotfix: the owner execution tabs were visually present but the
  // parent shell silently no-op'd when #operational-frame was absent or the
  // embedded runtime had not exposed changeOperationalPage yet. Keep one
  // authoritative embedded operational surface and make every tab routable.
  const PAGES = new Set(['dashboard','content','search','accounts','device','conversion','health']);
  const FRAME_ID = 'operational-frame';
  const FRAME_SRC = '/operational.html?embedded=1';

  function notify(message, kind='error') {
    if (typeof window.toast === 'function') {
      window.toast(message, kind === 'error' ? 'error' : undefined);
      return;
    }
    let node = document.getElementById('r811-execution-route-status');
    const hub = document.getElementById('operational-hub');
    if (!node && hub) {
      node = document.createElement('div');
      node.id = 'r811-execution-route-status';
      node.style.cssText = 'margin:10px 0;padding:10px 12px;border-radius:9px;background:#fff4e4;color:#9b641a;font-size:11px;';
      hub.querySelector('.operational-hub-intro')?.insertAdjacentElement('afterend', node);
    }
    if (node) node.textContent = message;
  }

  async function requestJson(path, options={}) {
    const response = await fetch(path, options);
    const data = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(data.error || `本地服务返回 ${response.status}`);
    return data;
  }

  function setActiveButton(page, button) {
    document.querySelectorAll('.r810-execution-tabs [data-execution-page]').forEach(item => {
      item.classList.toggle('active', item === button || item.dataset.executionPage === page && !button);
    });
  }

  function showExecutionHub() {
    if (typeof window.openPage === 'function') {
      window.openPage('operational-hub');
      return;
    }
    document.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node.id === 'operational-hub'));
  }

  function ensureFrame() {
    const hub = document.getElementById('operational-hub');
    if (!hub) return null;
    let frame = document.getElementById(FRAME_ID);
    if (!frame) {
      frame = document.createElement('iframe');
      frame.id = FRAME_ID;
      frame.src = FRAME_SRC;
      frame.title = '卡嘴子 AI 执行中心';
      frame.loading = 'eager';
      frame.setAttribute('scrolling', 'no');
      frame.style.cssText = 'display:block;width:100%;min-height:720px;border:0;background:transparent;';
      const intro = hub.querySelector('.operational-hub-intro');
      if (intro) intro.insertAdjacentElement('afterend', frame);
      else hub.appendChild(frame);
    } else if (!String(frame.getAttribute('src') || '').includes('operational.html')) {
      frame.src = FRAME_SRC;
    }
    return frame;
  }

  function makeFrameAuthoritative(frame) {
    const hub = document.getElementById('operational-hub');
    if (!hub || !frame) return;
    [...hub.children].forEach(child => {
      if (child === frame || child.classList?.contains('operational-hub-intro') || child.id === 'r811-execution-route-status') return;
      child.hidden = true;
    });
    frame.hidden = false;
  }

  function currentFactoryAccount(frame) {
    try {
      const accounts = frame?.contentWindow?.state?.factory?.accounts || [];
      return accounts.find(x => x?.connection_status !== '已验证可发布') || accounts[0] || null;
    } catch (_) {
      return null;
    }
  }

  async function refreshEmbedded(frame) {
    try {
      await frame?.contentWindow?.refreshAll?.();
    } catch (_) {}
    patchAccountVerifier(frame);
  }

  async function machineVerify(frame, button) {
    const original = button?.textContent || '系统重新验证';
    if (button) { button.disabled = true; button.textContent = '正在验证…'; }
    try {
      const result = await requestJson('/api/r8-11/social/verify', {method:'POST'});
      const rows = Array.isArray(result.results) ? result.results : [];
      const authorized = rows.find(x => x.status === 'authorized');
      const blocker = rows.find(x => x.status === 'needs_human' || x.status === 'logged_out');
      const inconclusive = rows.find(x => x.status === 'inconclusive');
      if (authorized) notify(authorized.detail || '真实账号登录状态已验证', 'ok');
      else if (blocker) notify(blocker.detail || '当前需要人工完成平台验证');
      else notify(inconclusive?.detail || '系统仍未取得足够账号文本证据；可在确认真机画面无误后使用人工确认。');
      await refreshEmbedded(frame);
    } catch (error) {
      notify(error.message || '登录验证失败');
    } finally {
      if (button) { button.disabled = false; button.textContent = original; }
    }
  }

  async function ownerConfirm(frame, button) {
    const account = currentFactoryAccount(frame);
    if (!account) {
      notify('未找到已绑定账号，请先保存账号并绑定真机。');
      return;
    }
    let social;
    try {
      social = await requestJson('/api/r8/social', {cache:'no-store'});
    } catch (error) {
      notify(error.message || '读取真实账号绑定失败');
      return;
    }
    const controlAccounts = Array.isArray(social.accounts) ? social.accounts : [];
    const accountId = String(account.social_account_id || '').trim();
    const control = controlAccounts.find(x => x.account_id === accountId)
      || controlAccounts.find(x => x.platform_name === account.platform && x.alias === account.account_name)
      || controlAccounts[0];
    if (!control?.account_id) {
      notify('没有找到对应的真实终端账号绑定。');
      return;
    }
    const label = control.alias || account.account_name || '当前绑定账号';
    const ok = window.confirm(`请只在手机当前抖音主页确实显示“${label}”时确认。\n\n系统只会把该账号标记为“已验证可发布”，不会自动发布任何内容。`);
    if (!ok) return;
    const original = button?.textContent || '我已确认当前账号';
    if (button) { button.disabled = true; button.textContent = '正在写入验证…'; }
    try {
      const result = await requestJson('/api/r8-11/social/confirm-login', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({account_id:control.account_id})
      });
      if (result.status === 'authorized') {
        notify(result.detail || '真实账号已完成一次性登录确认', 'ok');
      } else {
        notify(result.detail || '当前条件不足，未写入已验证状态');
      }
      await refreshEmbedded(frame);
    } catch (error) {
      notify(error.message || '人工确认登录失败');
    } finally {
      if (button) { button.disabled = false; button.textContent = original; }
    }
  }

  function patchAccountVerifier(frame) {
    try {
      const doc = frame?.contentDocument;
      const win = frame?.contentWindow;
      if (!doc || !win) return;
      const page = doc.getElementById('accounts');
      const form = doc.getElementById('account-form');
      if (!page || !form) return;
      const account = currentFactoryAccount(frame);
      let box = doc.getElementById('r811-field-login-verify');
      if (!box) {
        box = doc.createElement('div');
        box.id = 'r811-field-login-verify';
        box.style.cssText = 'grid-column:1/-1;margin-top:8px;padding:12px;border:1px solid #d9e3f2;border-radius:10px;background:#f7faff;font-size:12px;line-height:1.6;';
        const submit = form.querySelector('button[type="submit"]');
        submit?.insertAdjacentElement('beforebegin', box);
      }
      if (!account) {
        box.innerHTML = '<b>真实登录验证</b><div>先保存账号并绑定真机，再进行登录验证。</div>';
        return;
      }
      const verified = account.connection_status === '已验证可发布';
      if (verified) {
        box.innerHTML = `<b style="color:#13865f">真实登录验证：已通过</b><div>账号“${String(account.account_name||'').replace(/[&<>"']/g,'')}”已进入“已验证可发布”。这不代表内容已经发布；真实 URL / Post ID / Receipt 才算发布成功。</div>`;
        return;
      }
      box.innerHTML = `<b>真实登录验证</b><div>当前仍为“${String(account.connection_status||'待验证').replace(/[&<>"']/g,'')}”。先让手机停留在绑定账号的抖音主页，再点“系统重新验证”。如果抖音没有向 Android 页面结构暴露账号文字，但你能在真机画面明确看到绑定账号，可使用一次性人工确认。</div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px"><button type="button" data-r811-machine-verify style="padding:7px 10px;border:1px solid #cfd9e8;border-radius:8px;background:#fff;cursor:pointer">系统重新验证</button><button type="button" data-r811-owner-confirm style="padding:7px 10px;border:0;border-radius:8px;background:#2563eb;color:#fff;cursor:pointer">我已确认当前账号</button></div><small style="display:block;margin-top:6px;color:#68778d">不会读取密码、不会绕过验证码/人脸、不会自动发布。</small>`;
      box.querySelector('[data-r811-machine-verify]')?.addEventListener('click', event => machineVerify(frame, event.currentTarget));
      box.querySelector('[data-r811-owner-confirm]')?.addEventListener('click', event => ownerConfirm(frame, event.currentTarget));
    } catch (_) {}
  }

  function routeInsideFrame(frame, page) {
    try {
      const win = frame?.contentWindow;
      const doc = frame?.contentDocument;
      if (!win || !doc) return false;
      if (typeof win.changeOperationalPage === 'function') {
        win.changeOperationalPage(page);
        if (page === 'accounts') window.setTimeout(()=>patchAccountVerifier(frame), 120);
        return true;
      }
      const nav = doc.querySelector(`.nav[data-page="${page}"]`);
      if (nav) {
        nav.click();
        if (page === 'accounts') window.setTimeout(()=>patchAccountVerifier(frame), 120);
        return true;
      }
      const target = doc.getElementById(page);
      if (target) {
        doc.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node === target));
        if (page === 'accounts') window.setTimeout(()=>patchAccountVerifier(frame), 120);
        return true;
      }
    } catch (_) {
      return false;
    }
    return false;
  }

  function route(page, button) {
    if (!PAGES.has(page)) return;
    showExecutionHub();
    setActiveButton(page, button);
    const frame = ensureFrame();
    if (!frame) {
      notify('执行中心容器未初始化，请刷新后重试。');
      return;
    }
    makeFrameAuthoritative(frame);

    let attempts = 0;
    const apply = () => {
      attempts += 1;
      if (routeInsideFrame(frame, page)) {
        makeFrameAuthoritative(frame);
        const status = document.getElementById('r811-execution-route-status');
        if (status) status.remove();
        if (page === 'accounts') patchAccountVerifier(frame);
        return;
      }
      if (attempts < 30) {
        window.setTimeout(apply, 100);
        return;
      }
      notify(`执行中心“${button?.textContent?.trim() || page}”未能完成页面切换，请安装最新 Candidate 后重试。`);
    };

    if (frame.contentDocument?.readyState === 'complete') apply();
    else {
      frame.addEventListener('load', () => { apply(); patchAccountVerifier(frame); }, {once:true});
      window.setTimeout(apply, 120);
    }
  }

  // Capture phase deliberately runs before the original #481 bubble handler,
  // preventing its silent optional-chaining no-op from swallowing owner clicks.
  document.addEventListener('click', event => {
    const button = event.target.closest?.('.r810-execution-tabs [data-execution-page]');
    if (!button) return;
    const page = String(button.dataset.executionPage || '').trim();
    if (!PAGES.has(page)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    route(page, button);
  }, true);

  // If the unified shell already shows execution center at boot, prepare the
  // embedded runtime without changing the selected page.
  function boot() {
    if (!document.getElementById('operational-hub')) return;
    const active = document.querySelector('.r810-execution-tabs button.active[data-execution-page]');
    if (active) route(String(active.dataset.executionPage || 'dashboard'), active);
    const frame = ensureFrame();
    if (frame) {
      frame.addEventListener('load', () => {
        patchAccountVerifier(frame);
        try { frame.contentWindow?.addEventListener('operational:refreshed', () => patchAccountVerifier(frame)); } catch (_) {}
      });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 0), {once:true});
  else setTimeout(boot, 0);
})();

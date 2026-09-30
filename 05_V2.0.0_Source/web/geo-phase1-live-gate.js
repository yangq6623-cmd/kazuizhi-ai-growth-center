(() => {
  'use strict';
  if (window.__KZ_R819_GEO_LIVE_GATE__) return;
  window.__KZ_R819_GEO_LIVE_GATE__ = true;

  const byId = id => document.getElementById(id);
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  async function json(path, options) {
    const response = await fetch(path, {cache: 'no-store', ...(options || {})});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `GEO 服务返回 ${response.status}`);
    return data;
  }

  async function post(path, body = {}) {
    return json(path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
  }

  function notify(message, level) {
    if (typeof window.notify === 'function') window.notify(message, level);
    else console[level === 'error' ? 'error' : 'log'](message);
  }

  async function refreshGeo() {
    if (typeof window.searchGrowthActivate === 'function') {
      await window.searchGrowthActivate();
      return;
    }
    await sleep(80);
  }

  function installButtons() {
    const round = byId('geo-run-round');
    if (!round) return false;

    round.textContent = '执行本轮 10 题';
    round.classList.remove('geo-primary');
    round.classList.add('geo-secondary');
    round.dataset.geoSafeRun = '10';

    if (!byId('geo-run-one')) {
      const one = document.createElement('button');
      one.id = 'geo-run-one';
      one.type = 'button';
      one.className = 'geo-primary';
      one.dataset.geoSafeRun = '1';
      one.textContent = '先验证 1 题';
      round.parentNode?.insertBefore(one, round);
    }
    return true;
  }

  async function safeRun(limit, button) {
    const original = button.textContent;
    button.disabled = true;
    try {
      const preflight = await json('/api/r8-19/geo/preflight');
      const executor = preflight.executor || {};
      if (!preflight.ready) {
        await refreshGeo();
        notify(`暂不执行真实 GEO：${executor.reason || '外部验证执行器尚未就绪'}。请先在“系统状态与连接”完成外部 AI 配置与连接验证；本地模型不能冒充正式 GEO 证据。`, 'error');
        return;
      }

      await post('/api/r8-19/geo/bootstrap', {});
      const before = await json('/api/r8-19/geo');
      const decision = before.decision || {};
      const queue = before.queue || {};
      let available = Number(queue.queued || 0);

      if (available < limit) {
        const needed = Math.max(0, limit - available);
        if (needed) {
          const planReply = await post('/api/r8-19/geo/plan', {
            limit: needed,
            provider: 'openai_web_search',
            test_method: 'api',
            mission_id: decision.mission_id || '',
            require_executor_ready: true,
          });
          available += Number(planReply.result?.created || 0);
        }
      }

      const executions = Math.min(limit, available);
      if (!executions) {
        await refreshGeo();
        notify('当前没有新的固定基准问题需要真实验证。');
        return;
      }

      let completed = 0;
      let failed = 0;
      for (let index = 0; index < executions; index += 1) {
        button.textContent = limit === 1 ? '正在验证 1 / 1' : `真实验证中 ${index + 1} / ${executions}`;
        const reply = await post('/api/r8-19/geo/run', {mode: 'openai_web_search'});
        const result = reply.result || {};
        if (result.receipt?.official_truth) completed += 1;
        else if (!result.ok) failed += 1;
        await refreshGeo();
        if (result.task?.state === 'authorization_required') {
          notify(result.error || '外部 AI 授权失效，已转入“待我处理”。', 'error');
          break;
        }
      }

      await refreshGeo();
      if (completed) {
        notify(`已取得 ${completed} 份真实外部 GEO Receipt${failed ? `，另有 ${failed} 项失败并已保留原因` : ''}。`);
      } else if (failed) {
        notify(`本轮没有取得正式证据，${failed} 项失败已保留真实失败原因。`, 'error');
      } else {
        notify('本轮没有取得新的正式 GEO Evidence / Receipt。', 'error');
      }
    } catch (error) {
      await refreshGeo().catch(() => {});
      notify(error.message || String(error), 'error');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest?.('[data-geo-safe-run]');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const limit = Number(button.dataset.geoSafeRun || 1) === 10 ? 10 : 1;
    safeRun(limit, button);
  }, true);

  function install() {
    if (installButtons()) return;
    setTimeout(install, 120);
  }

  install();
  window.addEventListener('kz:app-ready', install);
  window.addEventListener('r810:workbench-ready', install);
})();

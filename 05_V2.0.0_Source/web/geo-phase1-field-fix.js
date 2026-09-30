(() => {
  'use strict';
  if (window.__KZ_R819_GEO_FIELD_FIX__) return;
  window.__KZ_R819_GEO_FIELD_FIX__ = true;

  const byId = id => document.getElementById(id);
  let busy = false;

  const PLATFORM_URLS = {
    chatgpt_web: 'https://chatgpt.com/',
    gemini_web: 'https://gemini.google.com/app',
    copilot_web: 'https://copilot.microsoft.com/',
    qwen_web: 'https://www.tongyi.com/',
    deepseek_web: 'https://chat.deepseek.com/',
    doubao_web: 'https://www.doubao.com/chat/',
  };

  async function json(path, options) {
    const response = await fetch(path, {cache: 'no-store', ...(options || {})});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `GEO 服务返回 ${response.status}`);
    return data;
  }

  function post(path, body = {}) {
    return json(path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
  }

  function feedback(message, level = 'info') {
    let box = byId('geo-action-feedback');
    if (!box) {
      const host = document.querySelector('.geo-command-deck') || document.querySelector('#geo-growth-pane .geo-mode-grid');
      if (host) {
        box = document.createElement('div');
        box.id = 'geo-action-feedback';
        host.insertAdjacentElement('afterend', box);
      }
    }
    if (box) {
      box.className = `geo-action-feedback is-${level}`;
      box.setAttribute('role', 'status');
      box.setAttribute('aria-live', 'polite');
      box.textContent = message;
    }
    if (typeof window.notify === 'function') window.notify(message, level === 'error' ? 'error' : undefined);
  }

  async function refreshGeo() {
    if (typeof window.searchGrowthActivate === 'function') await window.searchGrowthActivate();
    setTimeout(syncUi, 0);
  }

  async function run(button, busyText, work) {
    if (busy) {
      feedback('已有 GEO 操作正在执行，请等待当前操作完成。', 'warning');
      return;
    }
    busy = true;
    const old = button?.textContent || '';
    if (button) {
      button.disabled = true;
      button.textContent = busyText;
    }
    try {
      await work();
    } catch (error) {
      feedback(error?.message || String(error), 'error');
    } finally {
      busy = false;
      if (button) {
        button.disabled = false;
        button.textContent = old;
      }
      setTimeout(syncUi, 0);
    }
  }

  function currentTaskId() {
    return byId('geo-browser-task-id')?.value?.trim() || '';
  }

  function currentQuestion() {
    return byId('geo-browser-question')?.value?.trim() || '';
  }

  async function copyText(text) {
    if (!text) throw new Error('当前任务没有可复制的问题。');
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  }

  async function openExternalAi() {
    const question = currentQuestion();
    if (!question) throw new Error('当前任务没有原始问题，请先领取网页验证任务。');
    await copyText(question);
    const platform = byId('geo-browser-platform')?.value || 'chatgpt_web';
    const url = PLATFORM_URLS[platform];
    if (!url) {
      feedback('问题已经复制。当前为“其他外部AI”，请手动打开目标AI网页并粘贴问题。', 'success');
      return;
    }
    const win = window.open(url, '_blank', 'noopener,noreferrer');
    if (!win) {
      feedback('问题已经复制，但浏览器阻止了新窗口。请允许弹窗后重试，或手动打开外部AI网页。', 'warning');
      return;
    }
    feedback('已复制当前问题并打开外部AI网页。完成提问后，把真实会话URL和原始回答保存回来。', 'success');
  }

  async function prepare(button, limit) {
    if (currentTaskId()) {
      await openExternalAi();
      document.querySelector('.geo-browser-workbench')?.scrollIntoView({behavior: 'smooth', block: 'start'});
      return;
    }
    await run(button, limit === 1 ? '正在领取第1题…' : '正在准备10题…', async () => {
      await post('/api/r8-19/geo/bootstrap', {});
      const platform = byId('geo-browser-platform')?.value || 'chatgpt_web';
      const reply = await post('/api/r8-19/geo/browser/prepare', {limit, platform});
      await refreshGeo();
      const task = reply.result?.claim?.task || {};
      if (!task.task_id) throw new Error('没有取得可执行的网页验证任务，请刷新后重试。');
      feedback(limit === 1
        ? `已领取 ${task.question_id || task.task_id}。主按钮现在会直接打开外部AI网页并复制问题。`
        : `已准备本轮网页队列，并激活 ${task.question_id || task.task_id}。请先完成当前题。`, 'success');
      document.querySelector('.geo-browser-workbench')?.scrollIntoView({behavior: 'smooth', block: 'start'});
    });
  }

  async function localPrecheck(button, limit) {
    await run(button, `本地预检 ${limit} 题中…`, async () => {
      const reply = await post('/api/r8-19/geo/local-precheck/run', {limit});
      await refreshGeo();
      feedback(`本地预检完成 ${Number(reply.result?.completed || 0)} 题；结果固定为 C 级辅助，不计正式 GEO。`, 'success');
    });
  }

  async function saveReceipt(button) {
    await run(button, '正在保存 Receipt…', async () => {
      const taskId = currentTaskId();
      const sessionUrl = byId('geo-browser-url')?.value?.trim();
      const rawAnswer = byId('geo-browser-answer')?.value?.trim();
      if (!taskId) throw new Error('当前没有网页验证任务。');
      if (!sessionUrl) throw new Error('请填写真实外部 AI 网页会话地址。');
      if (!rawAnswer) throw new Error('请填写真实外部 AI 的完整原始回答。');
      const citationUrls = (byId('geo-browser-citations')?.value || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
      const reply = await post('/api/r8-19/geo/browser/receipt', {
        task_id: taskId,
        platform: byId('geo-browser-platform')?.value || 'custom_web',
        session_url: sessionUrl,
        raw_answer: rawAnswer,
        citation_urls: citationUrls,
      });
      await refreshGeo();
      feedback(`已保存 ${reply.result?.evidence_level || 'A'} 级 GEO Evidence / Receipt。`, 'success');
    });
  }

  async function bootstrap(button) {
    await run(button, '正在核验50问…', async () => {
      await post('/api/r8-19/geo/bootstrap', {});
      await refreshGeo();
      feedback('固定50问已核验：30自然发现 + 10商业推荐 + 10品牌认知。', 'success');
    });
  }

  async function repairRunning(button) {
    await run(button, '正在修复运行状态…', async () => {
      const queue = await json('/api/r8-19/geo/queue');
      const running = (queue.tasks || []).filter(item => item.state === 'running' && item.test_method === 'browser');
      if (running.length <= 1) {
        feedback('当前运行状态正常，只保留了 1 个网页验证任务。', 'success');
        return;
      }
      const current = currentTaskId();
      const keep = running.find(item => item.task_id === current) || running[running.length - 1];
      let paused = 0;
      for (const task of running) {
        if (task.task_id === keep.task_id) continue;
        await post('/api/r8-19/geo/pause', {task_id: task.task_id});
        paused += 1;
      }
      await refreshGeo();
      feedback(`已修复运行状态：保留当前任务，暂停 ${paused} 个重复运行任务。`, 'success');
    });
  }

  function activateFilter(state) {
    const button = document.querySelector(`#geo-state-filters [data-geo-state="${state}"]`);
    button?.click();
    document.querySelector('.geo-questions-panel')?.scrollIntoView({behavior: 'smooth', block: 'start'});
  }

  function bindKpis() {
    const cards = [...document.querySelectorAll('#geo-growth-pane .geo-kpis article')];
    if (cards.length !== 6) return;
    const actions = [
      () => activateFilter('succeeded'),
      () => activateFilter('unstarted'),
      () => activateFilter('running'),
      () => document.querySelector('.geo-grid.lower')?.scrollIntoView({behavior: 'smooth', block: 'start'}),
      () => activateFilter('failed'),
      () => activateFilter('authorization_required'),
    ];
    const titles = ['查看已验证问题', '查看待测试问题', '查看正在执行任务', '查看 Evidence / Receipt', '查看失败问题', '查看待授权问题'];
    cards.forEach((card, index) => {
      if (card.dataset.kpiBound === '1') return;
      card.dataset.kpiBound = '1';
      card.classList.add('geo-kpi-action');
      card.tabIndex = 0;
      card.setAttribute('role', 'button');
      card.setAttribute('title', titles[index]);
      const go = () => actions[index]?.();
      card.addEventListener('click', go);
      card.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          go();
        }
      });
    });
  }

  function ensureTaskToolbar() {
    const workbench = document.querySelector('#geo-growth-pane .geo-browser-workbench');
    if (!workbench || workbench.querySelector('.geo-task-actions')) return;
    const head = workbench.querySelector('.panel-head');
    if (!head) return;
    const tools = document.createElement('div');
    tools.className = 'geo-task-actions';
    tools.innerHTML = `
      <button type="button" data-geo-field-action="copy">复制当前问题</button>
      <button type="button" data-geo-field-action="open" class="primary">打开外部AI网页</button>
      <button type="button" data-geo-field-action="repair" class="warning">修复重复运行任务</button>`;
    head.insertAdjacentElement('afterend', tools);
  }

  function compactRunner() {
    const pane = byId('geo-growth-pane');
    const modes = pane?.querySelector('.geo-mode-grid');
    const deck = pane?.querySelector('.geo-command-deck');
    const truth = pane?.querySelector('.geo-truth-banner');
    if (!pane || !modes || !deck || pane.querySelector('.geo-runner-shell')) return;
    const shell = document.createElement('section');
    shell.className = 'geo-runner-shell';
    modes.parentNode?.insertBefore(shell, modes);
    shell.append(modes, deck);
    if (truth) shell.append(truth);
  }

  function syncUi() {
    bindKpis();
    ensureTaskToolbar();
    compactRunner();
    const active = Boolean(currentTaskId());
    const one = byId('geo-browser-one');
    const ten = byId('geo-browser-ten');
    if (one) one.textContent = active ? '打开AI网页并复制问题' : '开始网页验证 · 1题';
    if (ten) {
      ten.disabled = false;
      ten.textContent = active ? '当前题完成后再准备10题' : '准备10题 · 从第1题开始';
      ten.title = active ? '当前已有网页验证任务，点击会提示先完成当前题' : '';
    }
    const tools = document.querySelector('.geo-task-actions');
    tools?.classList.toggle('is-active', active);
    const running = Number(byId('geo-running')?.textContent || 0);
    const repair = tools?.querySelector('[data-geo-field-action="repair"]');
    if (repair) repair.hidden = running <= 1;
  }

  document.addEventListener('click', event => {
    const action = event.target.closest?.('[data-geo-field-action]');
    if (action && action.closest('#geo-growth-pane')) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (action.dataset.geoFieldAction === 'copy') {
        copyText(currentQuestion()).then(() => feedback('当前问题已复制。', 'success')).catch(error => feedback(error.message, 'error'));
      } else if (action.dataset.geoFieldAction === 'open') {
        openExternalAi().catch(error => feedback(error.message, 'error'));
      } else if (action.dataset.geoFieldAction === 'repair') {
        repairRunning(action);
      }
      return;
    }

    const button = event.target.closest?.('#geo-browser-one,#geo-browser-ten,#geo-local-one,#geo-local-ten,#geo-browser-submit,#geo-bootstrap,#geo-refresh');
    if (!button || !button.closest('#geo-growth-pane')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (button.id === 'geo-browser-one') prepare(button, 1);
    else if (button.id === 'geo-browser-ten') {
      if (currentTaskId()) {
        feedback('当前已有网页验证任务。请先完成当前题并保存 Receipt，再准备10题队列。', 'warning');
        document.querySelector('.geo-browser-workbench')?.scrollIntoView({behavior: 'smooth', block: 'start'});
      } else prepare(button, 10);
    }
    else if (button.id === 'geo-local-one') localPrecheck(button, 1);
    else if (button.id === 'geo-local-ten') localPrecheck(button, 10);
    else if (button.id === 'geo-browser-submit') saveReceipt(button);
    else if (button.id === 'geo-bootstrap') bootstrap(button);
    else if (button.id === 'geo-refresh') run(button, '刷新中…', async () => { await refreshGeo(); feedback('GEO 状态已刷新。', 'success'); });
  }, true);

  const observer = new MutationObserver(() => syncUi());
  function install() {
    const pane = byId('geo-growth-pane');
    if (!pane) {
      setTimeout(install, 80);
      return;
    }
    syncUi();
    observer.observe(pane, {subtree: true, childList: true, attributes: true});
  }

  install();
})();

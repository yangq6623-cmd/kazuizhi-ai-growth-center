(() => {
  'use strict';
  if (window.__KZ_R819_GEO_UI_POLISH__) return;
  window.__KZ_R819_GEO_UI_POLISH__ = true;

  const byId = id => document.getElementById(id);
  let actionBusy = false;

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

  function addSeoCrossLink(card) {
    if (!card || card.querySelector('.geo-legacy-link')) return;
    const wrap = document.createElement('div');
    wrap.className = 'geo-legacy-link';
    const note = document.createElement('span');
    note.textContent = '正式 GEO 验证已移到上方“GEO增长”工作区；这里仅保留旧摘要，避免重复操作。';
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = '进入 GEO 增长';
    button.addEventListener('click', () => document.querySelector('[data-growth-tab="geo"]')?.click());
    wrap.append(note, button);
    card.appendChild(wrap);
  }

  function polishSeo() {
    const pane = byId('seo-growth-pane');
    if (!pane) return;
    pane.classList.add('seo-polished');

    const legacyGeo = pane.querySelector('#geo');
    if (legacyGeo) {
      legacyGeo.classList.add('legacy-geo-summary');
      const title = legacyGeo.querySelector('h3');
      if (title) title.textContent = 'GEO 联动摘要（只读）';
      const sub = legacyGeo.querySelector('.sub');
      if (sub) sub.textContent = '这里只查看历史/联动摘要；真实网页验证、Evidence 与 Receipt 请进入独立 GEO 工作区。';
      addSeoCrossLink(legacyGeo);
    }

    pane.querySelectorAll('.tabs button').forEach(button => {
      if (button.dataset.to === 'geo') button.textContent = 'GEO联动摘要';
    });

    pane.querySelectorAll('h3').forEach(title => {
      if (title.textContent.trim() === 'SEO/GEO 自治运行') {
        title.textContent = 'SEO 自治运行';
        const card = title.closest('.card');
        if (card && !card.querySelector('.seo-split-note')) {
          const note = document.createElement('div');
          note.className = 'seo-split-note';
          note.textContent = 'GEO 已拆到独立工作区；本区继续负责 SEO 规划、公开、提交、抓取与收录。';
          title.parentElement?.appendChild(note);
        }
      }
    });
  }

  function ensureActionFeedback() {
    let box = byId('geo-action-feedback');
    if (box) return box;
    const deck = document.querySelector('.geo-command-deck');
    if (!deck) return null;
    box = document.createElement('div');
    box.id = 'geo-action-feedback';
    box.className = 'geo-action-feedback is-info';
    box.setAttribute('role', 'status');
    box.setAttribute('aria-live', 'polite');
    box.textContent = '操作状态：就绪。点击主按钮后，这里会显示执行结果。';
    deck.appendChild(box);
    return box;
  }

  function feedback(message, level = 'info') {
    const box = ensureActionFeedback();
    if (box) {
      box.className = `geo-action-feedback is-${level}`;
      box.textContent = message;
    }
    if (typeof window.notify === 'function') window.notify(message, level === 'error' ? 'error' : undefined);
  }

  function makeCommandDeck() {
    const actionbar = document.querySelector('#geo-growth-pane .geo-actionbar');
    if (!actionbar || document.querySelector('.geo-command-deck')) return;

    const deck = document.createElement('div');
    deck.className = 'geo-command-deck';
    deck.innerHTML = `
      <div class="geo-command-main">
        <div class="geo-command-copy">
          <span>今日建议</span>
          <strong>先完成 1 题网页真实验证</strong>
          <small>确认真实外部回答生成 A 级 Receipt 后，再扩大到 10 题。API 当前不是必需项。</small>
        </div>
        <div class="geo-command-actions" data-slot="main"></div>
      </div>
      <div class="geo-command-tools">
        <details>
          <summary>本地辅助预检</summary>
          <div class="geo-command-actions" data-slot="local"></div>
        </details>
        <details>
          <summary>高级工具</summary>
          <div class="geo-command-actions" data-slot="advanced"></div>
        </details>
      </div>`;

    actionbar.parentNode?.insertBefore(deck, actionbar);
    const main = deck.querySelector('[data-slot="main"]');
    const local = deck.querySelector('[data-slot="local"]');
    const advanced = deck.querySelector('[data-slot="advanced"]');
    const browserOne = byId('geo-browser-one');
    const browserTen = byId('geo-browser-ten');
    const localOne = byId('geo-local-one');
    const localTen = byId('geo-local-ten');
    const api = byId('geo-run-round');
    const bootstrap = byId('geo-bootstrap');
    const refresh = byId('geo-refresh');
    const state = byId('geo-executor-state');

    if (browserOne) {
      browserOne.textContent = '开始网页验证 · 1题';
      main?.appendChild(browserOne);
    }
    if (browserTen) {
      browserTen.textContent = '准备10题 · 从第1题开始';
      main?.appendChild(browserTen);
    }
    if (state) main?.appendChild(state);
    if (localOne) local?.appendChild(localOne);
    if (localTen) local?.appendChild(localTen);
    if (api) {
      api.textContent = 'API验证（后期可选）';
      advanced?.appendChild(api);
    }
    if (bootstrap) advanced?.appendChild(bootstrap);
    if (refresh) advanced?.appendChild(refresh);
    actionbar.remove();
    ensureActionFeedback();
  }

  function makeProgress() {
    const kpis = document.querySelector('#geo-growth-pane .geo-kpis');
    if (!kpis || byId('geo-baseline-progress')) return;
    const progress = document.createElement('div');
    progress.id = 'geo-baseline-progress';
    progress.className = 'geo-baseline-progress';
    progress.innerHTML = `
      <div><span>第一轮真实基线</span><b id="geo-progress-label">0 / 50</b></div>
      <div class="geo-progress-track"><i id="geo-progress-fill"></i></div>
      <small>只计算真实外部 AI 的 A/B 级证据；本地预检不计分。</small>`;
    kpis.insertAdjacentElement('afterend', progress);
  }

  function updateProgress() {
    const tested = byId('geo-tested');
    const label = byId('geo-progress-label');
    const fill = byId('geo-progress-fill');
    if (!tested || !label || !fill) return;
    const match = tested.textContent.match(/(\d+)\s*\/\s*(\d+)/);
    const done = Number(match?.[1] || 0);
    const total = Math.max(1, Number(match?.[2] || 50));
    label.textContent = `${done} / ${total}`;
    fill.style.width = `${Math.min(100, Math.round(done / total * 100))}%`;
  }

  function decorateModes() {
    const cards = document.querySelectorAll('#geo-growth-pane .geo-mode-grid article');
    if (cards.length < 3) return;
    cards[0].classList.add('mode-local');
    cards[1].classList.add('mode-browser', 'mode-active');
    cards[2].classList.add('mode-api');
  }

  function decorateWorkbenchFields(workbench) {
    if (!workbench || workbench.dataset.layoutReady === '1') return;
    const grids = workbench.querySelectorAll(':scope > .geo-browser-form-grid');
    if (grids[0]) grids[0].classList.add('geo-browser-meta-grid');
    if (grids[1]) grids[1].classList.add('geo-browser-proof-grid');
    const labels = [...workbench.children].filter(node => node.tagName === 'LABEL');
    if (labels[0]) labels[0].classList.add('geo-browser-question-field');
    if (labels[1]) labels[1].classList.add('geo-browser-answer-field');
    workbench.dataset.layoutReady = '1';
  }

  function ensureWorkbenchIdleHint(workbench) {
    if (!workbench || workbench.querySelector('.geo-workbench-idle')) return;
    const hint = document.createElement('div');
    hint.className = 'geo-workbench-idle';
    hint.innerHTML = '<b>还没有正在验证的网页任务</b><span>点击“开始网页验证 · 1题”，系统会从固定50问中领取下一题。完成外部AI网页提问后，再把真实回答和页面地址保存为 Receipt。</span><button type="button">开始第1题</button>';
    hint.querySelector('button')?.addEventListener('click', () => byId('geo-browser-one')?.click());
    workbench.appendChild(hint);
  }

  function updateWorkbench() {
    const workbench = document.querySelector('#geo-growth-pane .geo-browser-workbench');
    if (!workbench) return;
    decorateWorkbenchFields(workbench);
    ensureWorkbenchIdleHint(workbench);
    const taskId = byId('geo-browser-task-id')?.value?.trim();
    const badge = byId('geo-browser-task-state')?.textContent || '';
    const active = Boolean(taskId) || badge.includes('等待网页回答');
    workbench.classList.toggle('is-idle', !active);
    workbench.classList.toggle('is-active', active);
    const one = byId('geo-browser-one');
    const ten = byId('geo-browser-ten');
    if (one) one.textContent = active ? '继续当前网页验证' : '开始网页验证 · 1题';
    if (ten) ten.disabled = active;
  }

  function focusWorkbench() {
    document.querySelector('#geo-growth-pane .geo-browser-workbench')?.scrollIntoView({behavior: 'smooth', block: 'start'});
  }

  function updateLegacyQueueNotice() {
    const list = byId('geo-task-list');
    if (!list) return;
    let note = byId('geo-legacy-queue-note');
    const hasLegacyApiQueue = list.innerText.includes('openai_web_search') && list.innerText.includes('排队');
    if (!hasLegacyApiQueue) {
      note?.remove();
      return;
    }
    if (!note) {
      note = document.createElement('div');
      note.id = 'geo-legacy-queue-note';
      note.className = 'geo-legacy-queue-notice';
      note.textContent = '检测到升级前遗留的 API 排队任务。开始网页验证后会自动转换为网页验证任务，不会重复建题，也不需要配置 API。';
      list.parentNode?.insertBefore(note, list);
    }
  }

  async function refreshGeo() {
    if (typeof window.searchGrowthActivate === 'function') await window.searchGrowthActivate();
    updateProgress();
    updateWorkbench();
    updateLegacyQueueNotice();
  }

  async function withBusy(button, busyText, fn) {
    if (actionBusy) {
      feedback('已有 GEO 操作正在执行，请等待当前操作完成。', 'warning');
      return;
    }
    actionBusy = true;
    const original = button?.textContent || '';
    if (button) {
      button.disabled = true;
      button.textContent = busyText;
    }
    try {
      await fn();
    } catch (error) {
      feedback(error.message || String(error), 'error');
    } finally {
      actionBusy = false;
      if (button) {
        button.disabled = false;
        button.textContent = original;
      }
      updateWorkbench();
    }
  }

  async function browserStart(button, limit) {
    const currentTask = byId('geo-browser-task-id')?.value?.trim();
    if (currentTask) {
      feedback(`当前已有网页验证任务 ${currentTask}，请先完成并保存 Receipt，避免重复领取任务。`, 'info');
      focusWorkbench();
      return;
    }
    await withBusy(button, limit === 1 ? '正在领取第1题…' : '正在准备10题…', async () => {
      await post('/api/r8-19/geo/bootstrap', {});
      const platform = byId('geo-browser-platform')?.value || 'chatgpt_web';
      const reply = await post('/api/r8-19/geo/browser/prepare', {limit, platform});
      const task = reply.result?.claim?.task || {};
      await refreshGeo();
      if (!task.task_id) throw new Error('没有取得可执行的网页验证任务，请刷新后重试。');
      feedback(limit === 1
        ? `已领取第1题：${task.question_id || task.task_id}。请到真实外部AI网页提问，再保存回答。`
        : `已准备本轮网页验证队列，并激活第1题：${task.question_id || task.task_id}。先完成当前题，再继续下一题。`, 'success');
      focusWorkbench();
    });
  }

  async function localPrecheck(button, limit) {
    await withBusy(button, `本地预检 ${limit} 题中…`, async () => {
      const reply = await post('/api/r8-19/geo/local-precheck/run', {limit});
      await refreshGeo();
      feedback(`本地预检完成 ${Number(reply.result?.completed || 0)} 题。结果固定为 C 级辅助，不计正式 GEO。`, 'success');
    });
  }

  async function submitReceipt(button) {
    await withBusy(button, '正在保存 Receipt…', async () => {
      const taskId = byId('geo-browser-task-id')?.value?.trim();
      const sessionUrl = byId('geo-browser-url')?.value?.trim();
      const rawAnswer = byId('geo-browser-answer')?.value?.trim();
      if (!taskId) throw new Error('当前没有网页验证任务。请先点击“开始网页验证 · 1题”。');
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
      byId('geo-browser-task-id').value = '';
      byId('geo-browser-question').value = '';
      byId('geo-browser-url').value = '';
      byId('geo-browser-answer').value = '';
      byId('geo-browser-citations').value = '';
      await refreshGeo();
      feedback(`已保存 ${reply.result?.evidence_level || 'A'} 级 GEO Evidence / Receipt。正式基线已更新。`, 'success');
    });
  }

  async function bootstrap(button) {
    await withBusy(button, '正在核验50问…', async () => {
      await post('/api/r8-19/geo/bootstrap', {});
      await refreshGeo();
      feedback('固定50问已核验：30自然发现 + 10商业推荐 + 10品牌认知。', 'success');
    });
  }

  function installInteractionRepair() {
    if (document.documentElement.dataset.kzGeoInteractionRepair === '1') return;
    document.documentElement.dataset.kzGeoInteractionRepair = '1';
    document.addEventListener('click', event => {
      const button = event.target.closest?.('#geo-browser-one,#geo-browser-ten,#geo-local-one,#geo-local-ten,#geo-browser-submit,#geo-bootstrap,#geo-refresh');
      if (!button || !button.closest('#geo-growth-pane')) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (button.id === 'geo-browser-one') browserStart(button, 1);
      else if (button.id === 'geo-browser-ten') browserStart(button, 10);
      else if (button.id === 'geo-local-one') localPrecheck(button, 1);
      else if (button.id === 'geo-local-ten') localPrecheck(button, 10);
      else if (button.id === 'geo-browser-submit') submitReceipt(button);
      else if (button.id === 'geo-bootstrap') bootstrap(button);
      else if (button.id === 'geo-refresh') withBusy(button, '刷新中…', async () => { await refreshGeo(); feedback('GEO 状态已刷新。', 'success'); });
    }, true);
  }

  function polishGeo() {
    const pane = byId('geo-growth-pane');
    if (!pane) return;
    pane.classList.add('geo-polished');
    decorateModes();
    makeCommandDeck();
    makeProgress();
    updateProgress();
    updateWorkbench();
    updateLegacyQueueNotice();
    installInteractionRepair();

    const tested = byId('geo-tested');
    if (tested && !tested.__kzPolishObserver && window.MutationObserver) {
      const observer = new MutationObserver(updateProgress);
      observer.observe(tested, {childList: true, subtree: true, characterData: true});
      tested.__kzPolishObserver = observer;
    }
    const taskState = byId('geo-browser-task-state');
    if (taskState && !taskState.__kzPolishObserver && window.MutationObserver) {
      const observer = new MutationObserver(() => setTimeout(updateWorkbench, 0));
      observer.observe(taskState, {childList: true, subtree: true, characterData: true});
      taskState.__kzPolishObserver = observer;
    }
    const taskList = byId('geo-task-list');
    if (taskList && !taskList.__kzPolishObserver && window.MutationObserver) {
      const observer = new MutationObserver(updateLegacyQueueNotice);
      observer.observe(taskList, {childList: true, subtree: true, characterData: true});
      taskList.__kzPolishObserver = observer;
    }
  }

  function install() {
    polishSeo();
    polishGeo();
    if (!byId('geo-growth-pane')) setTimeout(install, 120);
  }

  install();
  window.addEventListener('load', install);
  window.addEventListener('kz:app-ready', install);
  window.addEventListener('r810:workbench-ready', install);
})();

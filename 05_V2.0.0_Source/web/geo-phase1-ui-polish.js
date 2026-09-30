(() => {
  'use strict';
  if (window.__KZ_R819_GEO_UI_POLISH__) return;
  window.__KZ_R819_GEO_UI_POLISH__ = true;

  const byId = id => document.getElementById(id);

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

  function makeCommandDeck() {
    const actionbar = document.querySelector('#geo-growth-pane .geo-actionbar');
    if (!actionbar || document.querySelector('.geo-command-deck')) return;

    const deck = document.createElement('div');
    deck.className = 'geo-command-deck';
    deck.innerHTML = `
      <div class="geo-command-main">
        <div class="geo-command-copy">
          <span>今日建议</span>
          <strong>先做 1 题网页真实验证</strong>
          <small>确认真实外部回答能生成 A 级 Receipt 后，再扩大到 10 题；无需 API。</small>
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
      browserTen.textContent = '建立10题网页队列';
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
    ensureWorkbenchIdleHint(workbench);
    const taskId = byId('geo-browser-task-id')?.value?.trim();
    const badge = byId('geo-browser-task-state')?.textContent || '';
    const active = Boolean(taskId) || badge.includes('等待网页回答');
    workbench.classList.toggle('is-idle', !active);
    workbench.classList.toggle('is-active', active);
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
      note.className = 'geo-legacy-queue-note';
      note.textContent = '检测到升级前遗留的 API 排队任务。点击“开始网页验证”后会自动转换为网页验证任务，不会重复建题，也不需要配置 API。';
      list.parentNode?.insertBefore(note, list);
    }
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

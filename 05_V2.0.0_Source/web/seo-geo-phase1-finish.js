(() => {
  'use strict';
  if (window.__KZ_SEO_GEO_PHASE1_FINISH__) return;
  window.__KZ_SEO_GEO_PHASE1_FINISH__ = true;

  const byId = id => document.getElementById(id);
  let passes = 0;
  let timer = null;
  let heightTimer = null;
  let lastHeight = 0;

  function isEmbedded() {
    return window.self !== window.top && Boolean(window.frameElement);
  }

  function measuredDocumentHeight() {
    const body = document.body;
    const root = document.documentElement;
    const candidates = [
      body?.scrollHeight || 0,
      root?.scrollHeight || 0,
      document.querySelector('.wrap')?.scrollHeight || 0,
      document.querySelector('#search')?.scrollHeight || 0,
      document.querySelector('.geo-direct-main')?.scrollHeight || 0,
    ];
    document.querySelectorAll('body > *, .wrap > *, .geo-direct-main > *').forEach(node => {
      const rect = node.getBoundingClientRect?.();
      if (rect) candidates.push(Math.ceil(rect.bottom + (window.scrollY || 0)));
    });
    return Math.min(30000, Math.max(720, ...candidates) + 28);
  }

  function repairEmbeddedHeight() {
    if (!isEmbedded()) return;
    const frame = window.frameElement;
    const height = measuredDocumentHeight();
    const current = parseInt(frame.style.height || '0', 10) || frame.getBoundingClientRect().height || 0;
    if (Math.abs(current - height) > 6) frame.style.height = `${height}px`;
    frame.style.maxHeight = 'none';
    frame.style.minHeight = '0';
    frame.style.overflow = 'hidden';
    frame.setAttribute('scrolling', 'no');
    lastHeight = height;
    document.documentElement.dataset.kzEmbeddedHeight = String(height);
  }

  function scheduleHeightRepair() {
    if (!isEmbedded()) return;
    clearTimeout(heightTimer);
    heightTimer = setTimeout(repairEmbeddedHeight, 60);
    [0, 120, 320, 700, 1400, 2600, 4800, 8000, 12000].forEach(delay => setTimeout(repairEmbeddedHeight, delay));
  }

  function polishSeoTitle() {
    if (!document.documentElement.classList.contains('kz-growth-embedded')) return;
    const heading = document.querySelector('.head h1');
    if (heading && heading.textContent.trim() === 'SEO/GEO增长中心') heading.textContent = 'SEO增长中心';
    const eyebrow = document.querySelector('.head .muted');
    if (eyebrow && /SEO\/GEO增长/.test(eyebrow.textContent || '')) eyebrow.textContent = '卡嘴子 AI · SEO增长';
  }

  function polishTaskId() {
    const input = byId('geo-browser-task-id');
    const label = input?.closest('label');
    if (!input || !label || label.dataset.kzTaskLabelReady === '1') return;
    label.dataset.kzTaskLabelReady = '1';
    const textNode = [...label.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
    if (textNode) textNode.textContent = '任务编号';
    input.title = '用于审计和追溯，不需要手动修改';
  }

  function polishPrimaryAction() {
    const button = byId('geo-browser-one');
    if (!button) return;
    const active = Boolean(byId('geo-browser-task-id')?.value?.trim());
    const label = active ? '继续当前验证' : '开始第1题验证';
    button.setAttribute('aria-label', label);
    button.title = active ? '复制当前问题并继续真实外部AI验证' : '领取固定50问中的第1个待验证问题';
  }

  function explainPausedTasks() {
    document.querySelectorAll('#geo-task-list .geo-task').forEach(task => {
      const badge = task.querySelector('.geo-badge');
      if (!badge || badge.textContent.trim() !== '暂停' || task.querySelector('.kz-pause-reason')) return;
      const body = task.querySelector('div');
      if (!body) return;
      const reason = document.createElement('small');
      reason.className = 'kz-pause-reason';
      reason.textContent = '暂停原因：历史重复运行任务已自动整理，不影响当前验证。';
      body.appendChild(reason);
    });
  }

  function polishWorkbenchHeading() {
    const panel = document.querySelector('#geo-growth-pane .geo-browser-workbench');
    const eyebrow = panel?.querySelector('.panel-head p');
    const title = panel?.querySelector('.panel-head h3');
    if (eyebrow && eyebrow.textContent.trim() === '网页验证工作台') eyebrow.textContent = '当前验证任务';
    if (title && /Evidence\s*\/\s*Receipt/.test(title.textContent || '')) title.textContent = '真实外部 AI 网页验证';
  }

  function sync() {
    polishSeoTitle();
    polishTaskId();
    polishPrimaryAction();
    explainPausedTasks();
    polishWorkbenchHeading();
    passes += 1;
    repairEmbeddedHeight();
  }

  function schedule(delay = 80) {
    clearTimeout(timer);
    timer = setTimeout(sync, delay);
  }

  window.__KZ_GROWTH_RESIZE__ = repairEmbeddedHeight;
  window.__KZ_GROWTH_HEIGHT_REPAIR__ = {measure: measuredDocumentHeight, repair: repairEmbeddedHeight, get lastHeight(){ return lastHeight; }};

  [0, 160, 500, 1200, 2600, 4800].forEach(delay => setTimeout(sync, delay));
  scheduleHeightRepair();
  const bounded = setInterval(() => {
    sync();
    if (passes >= 14) clearInterval(bounded);
  }, 1800);

  document.addEventListener('input', event => {
    if (event.target?.closest?.('#geo-growth-pane')) schedule(60);
  });
  document.addEventListener('click', event => {
    if (event.target?.closest?.('#geo-growth-pane,.tabs')) {
      schedule(120);
      scheduleHeightRepair();
    }
  });
  window.addEventListener('operational:search-updated', () => {
    schedule(80);
    scheduleHeightRepair();
  });
  window.addEventListener('load', scheduleHeightRepair, {once:true});
  window.addEventListener('focus', () => {
    schedule(100);
    scheduleHeightRepair();
  });
  window.addEventListener('resize', () => {
    clearTimeout(heightTimer);
    heightTimer = setTimeout(repairEmbeddedHeight, 140);
  });
})();

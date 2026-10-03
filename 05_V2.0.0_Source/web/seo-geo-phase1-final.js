(() => {
  'use strict';
  if (window.__KZ_SEO_GEO_PHASE1_FINAL__) return;
  window.__KZ_SEO_GEO_PHASE1_FINAL__ = true;

  const byId = id => document.getElementById(id);
  let syncTimer = null;
  let repairAttempted = false;
  let resizePasses = 0;

  function numberFrom(node, fallback = 0) {
    const match = String(node?.textContent || '').replace(/,/g, '').match(/\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : fallback;
  }

  function scheduleSync(delay = 80) {
    if (syncTimer) clearTimeout(syncTimer);
    syncTimer = setTimeout(() => { syncTimer = null; syncAll(); }, delay);
  }

  function installEmbeddedSingleScroll() {
    if (window.self === window.top || !window.frameElement) return;
    document.documentElement.classList.add('kz-growth-embedded');
    const frame = window.frameElement;
    frame.setAttribute('scrolling', 'no');
    frame.style.overflow = 'hidden';
    frame.style.maxHeight = 'none';
    frame.style.minHeight = '0';
    const resize = () => {
      const body = document.body;
      const root = document.documentElement;
      const height = Math.min(14000, Math.max(720, body?.scrollHeight || 0, root?.scrollHeight || 0));
      const current = parseInt(frame.style.height || '0', 10) || 0;
      if (Math.abs(current - height) > 8) frame.style.height = `${height}px`;
      resizePasses += 1;
    };
    [0, 120, 360, 800, 1600, 3200].forEach(delay => setTimeout(resize, delay));
    window.addEventListener('focus', () => setTimeout(resize, 80));
    window.addEventListener('resize', () => setTimeout(resize, 120));
    window.__KZ_GROWTH_RESIZE__ = resize;
  }

  function makeProgressShell(kind) {
    const node = document.createElement('section');
    node.className = `kz-growth-progress ${kind === 'seo' ? 'kz-seo-progress' : 'kz-geo-progress'}`;
    node.dataset.progressKind = kind;
    node.innerHTML = `
      <div class="kz-growth-progress-head">
        <div><span class="kz-growth-progress-kicker">${kind === 'seo' ? 'SEO 今日运行进度' : 'GEO 今日验证进度'}</span><h3 class="kz-growth-progress-title">正在读取真实执行状态…</h3></div>
        <span class="kz-growth-progress-status">读取中</span>
      </div>
      <div class="kz-growth-progress-main"><div class="kz-growth-progress-track"><i></i></div><b class="kz-growth-progress-value">--</b></div>
      <div class="kz-growth-progress-detail"><span class="kz-current">当前：读取中</span><span class="kz-next">下一步：读取中</span></div>
      <div class="kz-growth-steps"></div>`;
    return node;
  }

  function updateProgressShell(shell, {title, status, done, total, current, next, steps}) {
    if (!shell) return;
    shell.querySelector('.kz-growth-progress-title').textContent = title;
    shell.querySelector('.kz-growth-progress-status').textContent = status;
    const safeTotal = Math.max(1, Number(total || 1));
    const safeDone = Math.max(0, Math.min(safeTotal, Number(done || 0)));
    shell.querySelector('.kz-growth-progress-track i').style.width = `${Math.round(safeDone / safeTotal * 100)}%`;
    shell.querySelector('.kz-growth-progress-value').textContent = `${safeDone} / ${safeTotal}`;
    shell.querySelector('.kz-current').innerHTML = `<b>当前：</b>${current}`;
    shell.querySelector('.kz-next').innerHTML = `<b>下一步：</b>${next}`;
    const stepBox = shell.querySelector('.kz-growth-steps');
    stepBox.innerHTML = (steps || []).map((step, index) => `<div class="kz-growth-step ${step.state || 'waiting'}"><b>${String(index + 1).padStart(2, '0')} ${step.label}</b><span>${step.note || ''}</span></div>`).join('');
  }

  function ensureSeoProgress() {
    if (!document.querySelector('.hero') || document.querySelector('.kz-seo-progress')) return;
    const shell = makeProgressShell('seo');
    document.querySelector('.hero')?.insertAdjacentElement('afterend', shell);
  }

  function updateSeoProgress() {
    const shell = document.querySelector('.kz-seo-progress');
    if (!shell) return;
    const steps = [...document.querySelectorAll('.pipeline .step')];
    const total = steps.length || 7;
    const doneCount = steps.filter(step => step.classList.contains('done')).length;
    const blocked = steps.find(step => step.classList.contains('blocked'));
    const currentStep = blocked || steps.find(step => !step.classList.contains('done'));
    const currentTitle = currentStep?.querySelector('b')?.textContent?.trim() || (doneCount >= total ? '今日SEO流水线已完成' : '等待真实执行状态');
    const currentNote = currentStep?.querySelector('span')?.textContent?.trim() || '';
    const stepModels = (steps.length ? steps : Array.from({length: 7}, (_, i) => ({querySelector:()=>null,classList:{contains:()=>false}}))).map((step, index) => {
      const label = step.querySelector?.('b')?.textContent?.replace(/^\d+\s*/, '').trim() || ['需求扫描','关键词评分','内容生成','技术质检','公开上线','搜索提交','结果验证'][index] || `步骤${index + 1}`;
      const isDone = step.classList?.contains?.('done');
      const isBlocked = step.classList?.contains?.('blocked');
      return {label, state:isDone?'done':isBlocked?'active':(index===doneCount?'active':'waiting'), note:isDone?'已完成':isBlocked?'待真实条件':'等待'};
    });
    const status = blocked ? '等待真实条件' : doneCount >= total ? '今日完成' : '自动运行中';
    updateProgressShell(shell, {
      title:`今日 SEO 流水线 ${doneCount} / ${total}`,
      status,
      done:doneCount,
      total,
      current:`${currentTitle}${currentNote ? ` · ${currentNote}` : ''}`,
      next: blocked ? '等待真实抓取/收录等外部证据后继续' : (doneCount >= total ? '等待下一轮 ChatGPT SEO 计划' : '完成当前步骤后自动进入下一步'),
      steps:stepModels,
    });
  }

  function ensureGeoProgress() {
    const control = document.querySelector('#geo-growth-pane .geo-control');
    if (!control || document.querySelector('.kz-geo-progress')) return;
    const shell = makeProgressShell('geo');
    control.insertAdjacentElement('afterend', shell);
  }

  function geoTaskStage() {
    const taskId = byId('geo-browser-task-id')?.value?.trim() || '';
    const question = byId('geo-browser-question')?.value?.trim() || '';
    const url = byId('geo-browser-url')?.value?.trim() || '';
    const answer = byId('geo-browser-answer')?.value?.trim() || '';
    const tested = numberFrom(byId('geo-tested'));
    if (!taskId) return {index:0,current: tested ? '等待领取下一题真实网页验证' : '等待领取第1题真实网页验证',next:'领取问题后复制并打开外部AI'};
    if (!question) return {index:0,current:'正在准备固定50问中的当前问题',next:'准备完成后打开外部AI'};
    if (!url && !answer) return {index:1,current:'当前题已领取，等待到真实外部AI网页提问',next:'获取完整回答并复制会话地址'};
    if (!answer) return {index:2,current:'已记录外部AI会话，等待完整原始回答',next:'粘贴完整回答'};
    return {index:3,current:'外部AI回答已回填，等待保存正式 Evidence / Receipt',next:'保存证据后由 ChatGPT 判断下一题'};
  }

  function updateGeoProgress() {
    const shell = document.querySelector('.kz-geo-progress');
    if (!shell) return;
    const testedText = String(byId('geo-tested')?.textContent || '0 / 50');
    const m = testedText.match(/(\d+)\s*\/\s*(\d+)/);
    const tested = Number(m?.[1] || 0);
    const total = Number(m?.[2] || 50);
    const queued = numberFrom(byId('geo-queued'));
    const running = numberFrom(byId('geo-running'));
    const stage = geoTaskStage();
    const steps = ['领取问题','打开外部AI','获取回答','保存证据','ChatGPT判断'].map((label, index) => ({
      label,
      state:index < stage.index ? 'done' : index === stage.index ? 'active' : 'waiting',
      note:index < stage.index ? '已完成' : index === stage.index ? '正在进行' : '等待',
    }));
    updateProgressShell(shell, {
      title:`第一轮真实基线 ${tested} / ${total}`,
      status: running > 0 ? '正在验证' : queued > 0 ? '已排队' : tested >= total ? '本轮完成' : '等待下一步',
      done:tested,
      total,
      current:stage.current,
      next:stage.next,
      steps,
    });
  }

  function humaniseGeoLabels() {
    const cards = [...document.querySelectorAll('#geo-growth-pane .geo-kpis article')];
    const labels = ['已完成验证','待验证','当前任务','已获得证据','需重试','GEO待授权'];
    cards.forEach((card, index) => { const span = card.querySelector('span'); if (span && labels[index] && span.textContent !== labels[index]) span.textContent = labels[index]; });
    const submit = byId('geo-browser-submit');
    if (submit && submit.textContent !== '保存本次验证') submit.textContent = '保存本次验证';
    const one = byId('geo-browser-one');
    if (one) one.textContent = byId('geo-browser-task-id')?.value?.trim() ? '继续当前验证' : '开始第1题验证';
    const ten = byId('geo-browser-ten');
    const advanced = document.querySelector('#geo-growth-pane .geo-command-tools details:last-child .geo-command-actions');
    if (ten && advanced && ten.parentElement !== advanced) advanced.prepend(ten);
    const repair = document.querySelector('[data-geo-field-action="repair"]');
    if (repair) repair.hidden = true;
  }

  function ensureGeoHumanFlow() {
    const workbench = document.querySelector('#geo-growth-pane .geo-browser-workbench');
    if (!workbench || workbench.querySelector('.geo-human-flow')) return;
    const flow = document.createElement('div');
    flow.className = 'geo-human-flow';
    flow.innerHTML = `
      <div class="geo-human-flow-step"><b>① 当前问题</b><span>领取固定50问中的一题，并复制到外部AI。</span></div>
      <div class="geo-human-flow-step"><b>② 回填真实结果</b><span>保存真实会话URL和完整原始回答。</span></div>
      <div class="geo-human-flow-step"><b>③ 保存证据</b><span>生成可追溯 Evidence / Receipt。</span></div>`;
    const head = workbench.querySelector('.panel-head');
    head?.insertAdjacentElement('afterend', flow);

    const citation = byId('geo-browser-citations')?.closest('label');
    if (citation && !citation.closest('.geo-evidence-advanced')) {
      const details = document.createElement('details');
      details.className = 'geo-evidence-advanced';
      details.innerHTML = '<summary>补充证据字段（引用URL，可选）</summary><div class="geo-browser-citation-wrap"></div>';
      citation.parentNode?.insertBefore(details, citation);
      details.querySelector('.geo-browser-citation-wrap')?.appendChild(citation);
    }
  }

  function updateGeoHumanFlow() {
    const workbench = document.querySelector('#geo-growth-pane .geo-browser-workbench');
    const flow = workbench?.querySelector('.geo-human-flow');
    if (!flow) return;
    const task = Boolean(byId('geo-browser-task-id')?.value?.trim());
    const answer = Boolean(byId('geo-browser-answer')?.value?.trim());
    const url = Boolean(byId('geo-browser-url')?.value?.trim());
    const steps = [...flow.children];
    steps.forEach(step => step.classList.remove('done','active'));
    if (!task) steps[0]?.classList.add('active');
    else if (!answer || !url) { steps[0]?.classList.add('done'); steps[1]?.classList.add('active'); }
    else { steps[0]?.classList.add('done'); steps[1]?.classList.add('done'); steps[2]?.classList.add('active'); }
  }

  async function repairDuplicateRunningOnce() {
    if (repairAttempted || !document.querySelector('#geo-growth-pane')) return;
    repairAttempted = true;
    try {
      const response = await fetch('/api/r8-19/geo/queue', {cache:'no-store'});
      if (!response.ok) return;
      const data = await response.json();
      const running = (data.tasks || []).filter(task => task.state === 'running' && task.test_method === 'browser');
      if (running.length <= 1) return;
      const current = byId('geo-browser-task-id')?.value?.trim();
      const keep = running.find(task => task.task_id === current) || running[0];
      for (const task of running) {
        if (task.task_id === keep.task_id) continue;
        await fetch('/api/r8-19/geo/pause', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:task.task_id})});
      }
      if (typeof window.searchGrowthActivate === 'function') await window.searchGrowthActivate();
      window.notify?.(`已自动整理重复运行任务：仅保留当前1题，其余 ${running.length - 1} 题已暂停。`);
    } catch (error) {
      console.warn('GEO duplicate-running auto repair deferred', error);
    }
  }

  function translateIntentLabels() {
    const map = {commercial_compare:'商业比较',commercial_recommend:'商业推荐',local_discovery:'本地发现',urgent_service:'紧急服务',brand_awareness:'品牌认知',platform_discovery:'平台发现'};
    document.querySelectorAll('#geo-question-rows td').forEach(cell => { const text = cell.textContent.trim(); if (map[text]) cell.textContent = map[text]; });
  }

  function syncAll() {
    ensureSeoProgress();
    updateSeoProgress();
    ensureGeoProgress();
    humaniseGeoLabels();
    ensureGeoHumanFlow();
    updateGeoHumanFlow();
    updateGeoProgress();
    translateIntentLabels();
    window.__KZ_GROWTH_RESIZE__?.();
  }

  installEmbeddedSingleScroll();
  [0, 160, 500, 1200, 2600].forEach(delay => setTimeout(syncAll, delay));
  setTimeout(repairDuplicateRunningOnce, 1400);
  const bounded = setInterval(() => {
    syncAll();
    if (resizePasses > 18) clearInterval(bounded);
  }, 1800);
  document.addEventListener('input', event => {
    if (event.target?.closest?.('#geo-growth-pane')) scheduleSync(80);
  });
  document.addEventListener('click', event => {
    if (event.target?.closest?.('[data-growth-tab],#geo-browser-one,#geo-browser-submit,#geo-refresh')) scheduleSync(180);
  });
  window.addEventListener('focus', () => scheduleSync(100));
})();

(() => {
  'use strict';
  if (window.__KZ_CONTENT_STUDIO_EASY_FRONT__) return;
  window.__KZ_CONTENT_STUDIO_EASY_FRONT__ = true;

  const byId = id => document.getElementById(id);
  let attempts = 0;
  let retryTimer = null;

  function ensureStyle() {
    if (byId('kz-easy-front-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-easy-front-style';
    style.textContent = `
      body.kz-simple-mode .kz-simple-hero p{max-width:760px}
      body.kz-simple-mode .kz-simple-flow span{font-size:12px}
      .kz-easy-detect{display:flex;align-items:center;gap:8px;margin-top:8px;padding:8px 10px;border-radius:6px;background:#f7faff;border:1px solid #dce7f4;color:#53677e;font-size:12px}
      .kz-easy-detect b{color:#17324f}.kz-easy-detect[data-tone="ready"]{background:#eefaf4;border-color:#c8e9d7;color:#287553}.kz-easy-detect[data-tone="warn"]{background:#fff8ea;border-color:#f1d7a7;color:#8b641d}
      body.kz-simple-mode label:has(#kz-simple-ratio),body.kz-simple-mode label:has(#kz-simple-version-count){display:none!important}
      body.kz-simple-mode .kz-simple-note{background:#f7faff;border-color:#dce7f4;color:#53677e}
      body.kz-simple-mode #kz-simple-request{min-height:72px}
      .kz-easy-defaults{margin-top:10px;font-size:11px;color:#7a8ba0}.kz-easy-defaults b{color:#315476}
      .kz-easy-options-title{grid-column:1/-1;margin:2px 0 0;padding:10px 12px;border-radius:6px;background:#f7faff;border:1px solid #dce7f4;color:#315476;font-size:12px;font-weight:700}
      body.kz-simple-mode .kz-simple-actions{align-items:center}
      body.kz-simple-mode .kz-simple-actions .kz-simple-primary{min-width:240px;height:46px;font-size:15px}
      .kz-easy-action-hint{font-size:12px;color:#6d7f96}
      .kz-easy-queue-warning{margin-top:8px;padding:8px 10px;border:1px solid #f1d7a7;border-radius:6px;background:#fff8ea;color:#8b641d;font-size:12px;line-height:1.55}
      @media(max-width:760px){body.kz-simple-mode .kz-simple-flow{display:grid;grid-template-columns:1fr}body.kz-simple-mode .kz-simple-flow i{display:none}.kz-easy-action-hint{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function syncHostHeight() {
    const root = byId('kz-simple-root');
    if (!root || !document.body.classList.contains('kz-simple-mode')) return;
    const shell = document.querySelector('.studio-shell');
    const height = Math.max(760, (shell?.offsetHeight || 0) + root.scrollHeight + 36);
    try { parent.postMessage({type:'kz-content-studio-height',height}, location.origin); } catch (_) {}
  }

  function setLabel(id, text) {
    const control = byId(id);
    const label = control?.closest('label');
    if (!label) return;
    const firstText = [...label.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.nodeValue.trim());
    if (firstText && firstText.nodeValue !== text) firstText.nodeValue = text;
  }

  function detectInput() {
    const input = byId('kz-simple-source');
    const box = byId('kz-easy-detect');
    if (!input || !box) return;
    const raw = input.value.trim();
    const hasUrl = /https?:\/\/\S+/i.test(raw);
    const withoutUrl = raw.replace(/https?:\/\/\S+/ig, ' ').replace(/\s+/g, ' ').trim();
    let text = '等待输入：一句话 / 文案 / 参考链接都可以。';
    let tone = '';
    if (raw) {
      if (hasUrl && withoutUrl.length > 8) { text = '已识别：参考链接 + 分享文案。系统会先清洗无用信息，再理解内容。'; tone = 'ready'; }
      else if (hasUrl) { text = '已识别：参考链接。若平台暂时取不到文字，系统会提示补充分享文案，不会猜内容。'; tone = 'warn'; }
      else if (raw.length >= 80) { text = '已识别：完整文案。系统会直接理解文案并制作你的视频版本。'; tone = 'ready'; }
      else { text = '已识别：一句话想法。系统会自动扩写成完整视频方案。'; tone = 'ready'; }
    }
    box.dataset.tone = tone;
    const next = `<b>输入识别</b><span>${text}</span>`;
    if (box.innerHTML !== next) box.innerHTML = next;
    syncHostHeight();
  }

  function relabelProgress() {
    const copy = {
      reference:['理解你的内容','识别主题、开头和重点'],
      creative:['改成我们的版本','重新组织文案和表达'],
      director:['准备人物和场景','自动安排画面和说话方式'],
      production:['正在制作视频','后台自动完成制作'],
      candidate:['准备多个结果','生成可供选择的版本'],
      candidates:['准备多个结果','生成可供选择的版本'],
      qc:['检查视频质量','自动检查明显问题']
    };
    document.querySelectorAll('[data-simple-stage]').forEach(node => {
      const pair = copy[node.dataset.simpleStage];
      if (!pair) return;
      const b = node.querySelector('b');
      const span = node.querySelector('span');
      if (b && b.textContent !== pair[0]) b.textContent = pair[0];
      if (span && span.textContent !== pair[1]) span.textContent = pair[1];
    });
  }

  function replaceResultText(result) {
    const replacements = [
      ['导演分镜','视频结构'],
      ['生产项目','制作任务'],
      ['候选生成','视频制作'],
      ['AI 导演','自动编排']
    ];
    const walker = document.createTreeWalker(result, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node;
    while ((node = walker.nextNode())) nodes.push(node);
    nodes.forEach(textNode => {
      let value = textNode.nodeValue || '';
      replacements.forEach(([from,to]) => { value = value.replaceAll(from,to); });
      if (value !== textNode.nodeValue) textNode.nodeValue = value;
    });
  }

  function markQueueMismatch(result) {
    const text = result.textContent || '';
    const match = text.match(/共\s*\d+\s*个方向、\s*(\d+)\s*个分镜，已排入\s*(\d+)\s*个镜头候选任务/);
    const existing = result.querySelector('#kz-easy-queue-warning');
    if (!match) {
      existing?.remove();
      return;
    }
    const total = Number(match[1]);
    const queued = Number(match[2]);
    if (!Number.isFinite(total) || !Number.isFinite(queued) || queued >= total) {
      existing?.remove();
      return;
    }
    result.classList.remove('kz-simple-success');
    result.classList.add('kz-simple-error');
    const warning = existing || document.createElement('div');
    warning.id = 'kz-easy-queue-warning';
    warning.className = 'kz-easy-queue-warning';
    warning.textContent = `有 ${total - queued} 个镜头没有成功排入候选任务；请检查本地内容中心状态后再继续。`;
    if (!existing) result.appendChild(warning);
  }

  function simplifyResult() {
    const result = byId('kz-simple-result');
    if (!result) return;
    result.querySelectorAll('button').forEach(button => {
      if (/生产|工作台/.test(button.textContent)) button.textContent = '查看制作进度';
    });
    replaceResultText(result);
    markQueueMismatch(result);
    syncHostHeight();
  }

  function announce() {
    try {
      parent.postMessage({type:'kz-content-studio-route-changed',route:'overview',title:'一键生成视频',subtitle:'一句话、文案或参考链接；选好人物、地点和声音，其余交给后台'}, location.origin);
    } catch (_) {}
  }

  function install() {
    const root = byId('kz-simple-root');
    const source = byId('kz-simple-source');
    if (!root || !source) {
      attempts += 1;
      if (attempts < 30 && !retryTimer) retryTimer = setTimeout(() => { retryTimer = null; install(); }, 150);
      return;
    }
    attempts = 0;
    ensureStyle();

    const hero = root.querySelector('.kz-simple-hero');
    const heroSmall = hero?.querySelector('small');
    const heroTitle = hero?.querySelector('h2');
    const heroText = hero?.querySelector('p');
    if (heroSmall) heroSmall.textContent = '简单模式 · 你只负责告诉系统想要什么';
    if (heroTitle) heroTitle.textContent = '告诉 AI 你想做什么，选好人、地点和声音，然后生成视频';
    if (heroText) heroText.textContent = '一句话、完整文案、参考视频都可以。人物、场景、声音和视频方向由你选择；复杂制作过程全部在后台完成。';

    const flow = root.querySelector('.kz-simple-flow');
    const flowHtml = '<span>1 告诉 AI 你想做什么</span><i>→</i><span>2 选择人物 / 地点 / 声音</span><i>→</i><span>3 开始生成视频</span><i>→</i><span>4 选择喜欢的结果</span>';
    if (flow && flow.innerHTML !== flowHtml) flow.innerHTML = flowHtml;

    const card = source.closest('.kz-simple-card');
    const heading = card?.querySelector('h3');
    const intro = card?.querySelector('h3 + p');
    if (heading) heading.textContent = '告诉 AI 你想做什么';
    if (intro) intro.textContent = '可以只写一句话，也可以粘贴完整文案或参考视频分享内容。';

    setLabel('kz-simple-source','一句话 / 文案 / 参考链接');
    source.placeholder = '例如：做一条30秒“涟水家庭电路老跳闸”的维修科普视频；\n也可以直接粘贴完整文案；\n或者粘贴抖音、视频号、小红书、B站、快手的分享内容和链接。';
    setLabel('kz-simple-request','我想怎么改（可不填）');
    const request = byId('kz-simple-request');
    if (request) request.placeholder = '例如：改成涟水本地真实维修案例；王师傅出镜；说话自然一点；结尾引导进入卡嘴子咨询。留空则由系统自动决定。';

    setLabel('kz-simple-character','人物');
    setLabel('kz-simple-scene','地点 / 场景');
    setLabel('kz-simple-voice','声音');
    setLabel('kz-simple-direction','视频方向');
    setLabel('kz-simple-duration','视频时长');

    const ratio = byId('kz-simple-ratio'); if (ratio) ratio.value = '9:16';
    const count = byId('kz-simple-version-count'); if (count) count.value = '3';
    const start = byId('kz-simple-start'); if (start && !start.disabled) start.textContent = '开始生成视频';
    const assets = byId('kz-simple-assets'); if (assets) assets.textContent = '管理常用人物 / 场景 / 声音';

    const note = root.querySelector('.kz-simple-note');
    if (note) note.textContent = '人物、地点、声音都可以选“自动”。不想设置时直接生成，系统会按内容推荐。参考链接如果暂时无法读取文字，只需补充平台分享文案即可。';

    if (!byId('kz-easy-detect')) {
      const detect = document.createElement('div');
      detect.id = 'kz-easy-detect';
      detect.className = 'kz-easy-detect';
      source.insertAdjacentElement('afterend', detect);
    }
    if (!source.dataset.kzEasyInputBound) {
      source.dataset.kzEasyInputBound = '1';
      source.addEventListener('input', detectInput);
    }
    detectInput();
    relabelProgress();

    const grid = root.querySelector('.kz-simple-grid');
    if (grid && !byId('kz-easy-options-title')) {
      const title = document.createElement('div');
      title.id = 'kz-easy-options-title';
      title.className = 'kz-easy-options-title';
      title.textContent = '第 2 步：选择人物、地点、声音、视频方向和时长；都可以使用“自动”。';
      grid.insertAdjacentElement('afterbegin', title);
    }

    const actions = root.querySelector('.kz-simple-actions');
    if (actions && !byId('kz-easy-action-hint')) {
      const hint = document.createElement('span');
      hint.id = 'kz-easy-action-hint';
      hint.className = 'kz-easy-action-hint';
      hint.textContent = '设置完成后，点击左侧“开始生成视频”。';
      actions.appendChild(hint);
    }

    const result = byId('kz-simple-result');
    if (result && !result.dataset.kzEasyObserved) {
      result.dataset.kzEasyObserved = '1';
      let mutating = false;
      new MutationObserver(() => {
        if (mutating) return;
        mutating = true;
        try { simplifyResult(); } finally { mutating = false; }
      }).observe(result,{childList:true,subtree:true,characterData:true});
      simplifyResult();
    }

    if (!byId('kz-easy-defaults')) {
      const defaults = document.createElement('div');
      defaults.id = 'kz-easy-defaults';
      defaults.className = 'kz-easy-defaults';
      defaults.innerHTML = '<b>默认：</b>竖屏短视频 · 自动生成 3 个方向供选择。需要精细控制时再进入“专业模式”。';
      root.querySelector('.kz-simple-actions')?.insertAdjacentElement('afterend', defaults);
    }

    announce();
    syncHostHeight();
    setTimeout(syncHostHeight, 120);
    setTimeout(syncHostHeight, 500);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(install, 120), {once:true});
  else setTimeout(install, 120);
  window.addEventListener('kz:easy-front-refresh', install);
})();
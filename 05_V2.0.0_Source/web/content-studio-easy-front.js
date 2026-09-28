(() => {
  'use strict';
  if (window.__KZ_CONTENT_STUDIO_EASY_FRONT__) return;
  window.__KZ_CONTENT_STUDIO_EASY_FRONT__ = true;

  const byId = id => document.getElementById(id);
  let installTimer = null;

  function ensureStyle() {
    if (byId('kz-easy-front-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-easy-front-style';
    style.textContent = `
      body.kz-simple-mode .kz-simple-hero p{max-width:760px}
      body.kz-simple-mode .kz-simple-flow span{font-size:12px}
      .kz-easy-detect{display:flex;align-items:center;gap:8px;margin-top:8px;padding:8px 10px;border-radius:6px;background:#f7faff;border:1px solid #dce7f4;color:#53677e;font-size:12px}
      .kz-easy-detect b{color:#17324f}
      .kz-easy-detect[data-tone="ready"]{background:#eefaf4;border-color:#c8e9d7;color:#287553}
      .kz-easy-detect[data-tone="warn"]{background:#fff8ea;border-color:#f1d7a7;color:#8b641d}
      body.kz-simple-mode label:has(#kz-simple-ratio),body.kz-simple-mode label:has(#kz-simple-version-count){display:none!important}
      body.kz-simple-mode .kz-simple-note{background:#f7faff;border-color:#dce7f4;color:#53677e}
      .kz-easy-defaults{margin-top:10px;font-size:11px;color:#7a8ba0}
      .kz-easy-defaults b{color:#315476}
      @media(max-width:760px){body.kz-simple-mode .kz-simple-flow{display:grid;grid-template-columns:1fr}body.kz-simple-mode .kz-simple-flow i{display:none}}
    `;
    document.head.appendChild(style);
  }

  function setLabel(id, text) {
    const control = byId(id);
    const label = control?.closest('label');
    if (!label) return;
    const firstText = [...label.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.nodeValue.trim());
    if (firstText) firstText.nodeValue = text;
  }

  function detectInput() {
    const input = byId('kz-simple-source');
    const box = byId('kz-easy-detect');
    if (!input || !box) return;
    const raw = input.value.trim();
    const hasUrl = /https?:\/\/\S+/i.test(raw);
    const withoutUrl = raw.replace(/https?:\/\/\S+/ig, ' ').replace(/\s+/g, ' ').trim();
    let text = '可输入一句话、完整文案，或粘贴参考视频链接。';
    let tone = '';
    if (!raw) {
      text = '等待输入：一句话 / 文案 / 参考链接都可以。';
    } else if (hasUrl && withoutUrl.length > 8) {
      text = '已识别：参考链接 + 分享文案。系统会先清洗无用信息，再理解内容。';
      tone = 'ready';
    } else if (hasUrl) {
      text = '已识别：参考链接。若平台暂时取不到文字，系统会提示补充分享文案，不会猜内容。';
      tone = 'warn';
    } else if (raw.length >= 80) {
      text = '已识别：完整文案。系统会直接理解文案并制作你的视频版本。';
      tone = 'ready';
    } else {
      text = '已识别：一句话想法。系统会自动扩写成完整视频方案。';
      tone = 'ready';
    }
    box.dataset.tone = tone;
    box.innerHTML = `<b>输入识别</b><span>${text}</span>`;
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
      if (b) b.textContent = pair[0];
      if (span) span.textContent = pair[1];
    });
  }

  function simplifyResult() {
    const result = byId('kz-simple-result');
    if (!result) return;
    result.querySelectorAll('button').forEach(button => {
      if (/生产|工作台/.test(button.textContent)) button.textContent = '查看制作进度';
    });
    [...result.childNodes].forEach(() => {});
    if (result.innerHTML) {
      result.innerHTML = result.innerHTML
        .replaceAll('导演分镜','视频结构')
        .replaceAll('生产项目','制作任务')
        .replaceAll('候选生成','视频制作')
        .replaceAll('AI 导演','自动编排');
    }
  }

  function announce() {
    try {
      parent.postMessage({
        type:'kz-content-studio-route-changed',
        route:'overview',
        title:'一键生成视频',
        subtitle:'一句话、文案或参考链接；选好人物、地点和声音，其余交给后台'
      }, location.origin);
    } catch (_) {}
  }

  function install() {
    const root = byId('kz-simple-root');
    const source = byId('kz-simple-source');
    if (!root || !source) {
      if (!installTimer) installTimer = setTimeout(() => { installTimer = null; install(); }, 120);
      return;
    }
    ensureStyle();

    const hero = root.querySelector('.kz-simple-hero');
    const heroSmall = hero?.querySelector('small');
    const heroTitle = hero?.querySelector('h2');
    const heroText = hero?.querySelector('p');
    if (heroSmall) heroSmall.textContent = '简单模式 · 你只负责告诉系统想要什么';
    if (heroTitle) heroTitle.textContent = '告诉 AI 你想做什么，选好人、地点和声音，然后生成视频';
    if (heroText) heroText.textContent = '一句话、完整文案、参考视频都可以。人物、场景、声音和视频方向由你选择；复杂制作过程全部在后台完成。';

    const flow = root.querySelector('.kz-simple-flow');
    if (flow) flow.innerHTML = '<span>1 告诉 AI 你想做什么</span><i>→</i><span>2 选择人物 / 地点 / 声音</span><i>→</i><span>3 开始生成视频</span><i>→</i><span>4 选择喜欢的结果</span>';

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

    const ratio = byId('kz-simple-ratio');
    if (ratio) ratio.value = '9:16';
    const count = byId('kz-simple-version-count');
    if (count) count.value = '3';

    const start = byId('kz-simple-start');
    if (start && !start.disabled) start.textContent = '开始生成视频';
    const assets = byId('kz-simple-assets');
    if (assets) assets.textContent = '管理常用人物 / 场景 / 声音';

    const note = root.querySelector('.kz-simple-note');
    if (note) note.textContent = '人物、地点、声音都可以选“自动”。不想设置时直接生成，系统会按内容推荐。参考链接如果暂时无法读取文字，只需补充平台分享文案即可。';

    if (!byId('kz-easy-detect')) {
      const detect = document.createElement('div');
      detect.id = 'kz-easy-detect';
      detect.className = 'kz-easy-detect';
      source.insertAdjacentElement('afterend', detect);
      source.addEventListener('input', detectInput);
    }
    detectInput();
    relabelProgress();

    const result = byId('kz-simple-result');
    if (result && !result.dataset.kzEasyObserved) {
      result.dataset.kzEasyObserved = '1';
      new MutationObserver(() => simplifyResult()).observe(result,{childList:true,subtree:true,characterData:true});
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
  }

  const observer = new MutationObserver(() => {
    if (document.body.classList.contains('kz-simple-mode')) install();
  });
  if (document.body) observer.observe(document.body,{childList:true,subtree:true});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',()=>setTimeout(install,120),{once:true});
  else setTimeout(install,120);
  window.addEventListener('kz:easy-front-refresh', install);
})();
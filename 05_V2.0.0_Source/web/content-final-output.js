(() => {
  'use strict';
  if (window.__KZ_FINAL_OUTPUT_71__) return;
  window.__KZ_FINAL_OUTPUT_71__ = true;

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const json = (url, options={}) => fetch(url, options).then(async response => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.detail || data.message || `HTTP ${response.status}`);
    return data;
  });
  let timer = null;
  let lastError = '';

  function installStyle() {
    if (document.getElementById('kz-final-output-71-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-final-output-71-style';
    style.textContent = `
      .kz-final71{margin-top:12px;border:1px solid #cfdced;border-radius:8px;background:#fff;padding:14px;display:grid;gap:11px}
      .kz-final71-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
      .kz-final71-head h4{margin:0 0 4px;color:#17324f;font-size:14px}.kz-final71-head p{margin:0;color:#708299;font-size:11px;line-height:1.55}
      .kz-final71-badge{font-size:10px;border-radius:999px;padding:5px 8px;background:#edf2f7;color:#65778d;white-space:nowrap}
      .kz-final71-badge.running{background:#e8f1ff;color:#1768e5}.kz-final71-badge.done{background:#e8f7f0;color:#16875c}.kz-final71-badge.bad{background:#fff0f0;color:#b33d3d}
      .kz-final71-counts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
      .kz-final71-count{border:1px solid #e2e9f2;background:#f8fbff;border-radius:6px;padding:9px}.kz-final71-count small{display:block;color:#8090a4;font-size:10px;margin-bottom:3px}.kz-final71-count b{color:#17324f;font-size:13px}
      .kz-final71-progress{border:1px solid #e2e9f2;border-radius:6px;padding:10px;background:#fbfdff}.kz-final71-progress-top{display:flex;justify-content:space-between;gap:10px;font-size:11px;color:#53677e;margin-bottom:7px}.kz-final71-track{height:8px;border-radius:999px;background:#eaf0f7;overflow:hidden}.kz-final71-track i{display:block;height:100%;background:#1768e5;border-radius:999px;transition:width .25s ease}
      .kz-final71-video{border:1px solid #dbe5f0;border-radius:7px;padding:10px;background:#f8fbff}.kz-final71-video video{display:block;width:100%;max-height:560px;background:#0d1828;border-radius:6px}
      .kz-final71-meta{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px;font-size:10px;color:#667a91}.kz-final71-meta span{background:#edf3fb;border-radius:4px;padding:4px 7px}
      .kz-final71-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.kz-final71-actions a,.kz-final71-actions button{height:32px;border:1px solid #b9cbe0;border-radius:5px;background:#fff;color:#24496f;padding:0 11px;font-size:11px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center}
      .kz-final71-actions a.primary{background:#1768e5;border-color:#1768e5;color:#fff;font-weight:700}
      .kz-final71-path{margin-top:8px;font-size:10px;color:#7a8ba0;word-break:break-all}
      .kz-final71-error{border:1px solid #efc0c0;border-radius:6px;background:#fff0f0;color:#a83b3b;padding:9px;font-size:11px;line-height:1.55}
      .kz-final71-note{font-size:10px;color:#72849a;line-height:1.55}
      @media(max-width:900px){.kz-final71-counts{grid-template-columns:1fr}.kz-final71-head{flex-direction:column}}
    `;
    document.head.appendChild(style);
  }

  function ensurePanel() {
    const monitor = document.getElementById('kz-production-monitor');
    if (!monitor) return null;
    let panel = document.getElementById('kz-final-output-71');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'kz-final-output-71';
      panel.className = 'kz-final71';
      monitor.insertAdjacentElement('afterend', panel);
    }
    return panel;
  }

  function taskCounts(production={}) {
    const outputs = production.outputs || [];
    const totalShots = Number(production.total_shots || 0);
    const confirmed = Number(production.confirmed_shots || 0);
    const planned = Number(production.planned_candidates || 0);
    const generated = outputs.filter(x => String(x.kind || '') === '镜头候选视频').length;
    const unused = Math.max(0, planned - generated);
    return {totalShots, confirmed, planned, generated, unused};
  }

  function badge(executor={}) {
    const status = String(executor.status || 'idle');
    if (status === 'completed') return ['done','最终成片已完成'];
    if (status === 'error') return ['bad','最终成片异常'];
    if (['running','queued'].includes(status)) return ['running','正在自动成片'];
    return ['','等待最终成片'];
  }

  function render(production, executor) {
    installStyle();
    const panel = ensurePanel();
    if (!panel) return;
    const counts = taskCounts(production);
    const [badgeClass,badgeText] = badge(executor);
    const progress = Math.max(0, Math.min(100, Number(executor.progress || 0)));
    const output = executor.output || (production.outputs || []).find(x => String(x.kind || '') === '最终成片');
    const optional = counts.confirmed >= counts.totalShots && counts.totalShots > 0 && counts.unused > 0;
    const tts = output?.tts || {};
    const mux = tts.mux || {};
    const voiceText = mux.status === 'ready' ? '配音已封装' : (tts.status === 'ready' ? '配音已生成' : '配音未启用/不可用');
    const subtitleText = output?.subtitle?.status === 'burned' ? '字幕已烧录' : (output?.subtitle_path ? 'SRT字幕已生成' : '字幕处理中');

    panel.innerHTML = `
      <div class="kz-final71-head"><div><h4>#71 最终成片中心</h4><p>正式镜头与“候选素材”分开统计。候选没有全部补齐时，只要每个正式镜头已有一个可用选择，就允许直接进入成片。</p></div><span class="kz-final71-badge ${badgeClass}">${esc(badgeText)}</span></div>
      <div class="kz-final71-counts">
        <div class="kz-final71-count"><small>正式镜头</small><b>${counts.confirmed}/${counts.totalShots} 已确认</b></div>
        <div class="kz-final71-count"><small>候选素材</small><b>${counts.generated}/${counts.planned} 已生成</b></div>
        <div class="kz-final71-count"><small>未生成候选</small><b>${counts.unused}${optional?' · 可跳过':''}</b></div>
      </div>
      ${optional?'<div class="kz-final71-note">当前缺少的是备用候选，不是正式镜头。6/6 这类正式镜头全部确认后，缺少的备用候选不会阻塞最终成片。</div>':''}
      ${executor.status === 'error' ? `<div class="kz-final71-error">本轮没有生成最终成片：${esc(executor.last_error || executor.message || '未知异常')}<br>已生成的镜头候选不会删除，也不会从头重跑。</div>` : `
      <div class="kz-final71-progress"><div class="kz-final71-progress-top"><span>${esc(executor.stage || '等待成片任务')}</span><b>${progress}%</b></div><div class="kz-final71-track"><i style="width:${progress}%"></i></div><div class="kz-final71-note" style="margin-top:7px">${esc(executor.message || '')}</div></div>`}
      ${output ? `<div class="kz-final71-video"><video controls preload="metadata" src="${esc(output.url || output.file_url || '')}"></video><div class="kz-final71-meta"><span>${esc(output.resolution || '1080P')}</span><span>${esc(output.fps || 30)}fps</span><span>${esc(subtitleText)}</span><span>${esc(voiceText)}</span><span>FFmpeg技术质检 ${output.technical_qc?.passed?'已通过':'待确认'}</span></div><div class="kz-final71-actions"><a class="primary" href="${esc(output.download_url || `/api/final-output/download?id=${encodeURIComponent(output.id || '')}`)}">保存最终视频</a><button type="button" id="kz-final71-open-folder">打开文件位置</button></div><div class="kz-final71-path">${esc(output.file_path || '')}</div></div>` : ''}
    `;

    const open = document.getElementById('kz-final71-open-folder');
    if (open && output?.id) {
      open.addEventListener('click', async () => {
        open.disabled = true;
        open.textContent = '正在打开…';
        try {
          await json('/api/final-output/open-folder', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({id:output.id})
          });
          open.textContent = '已打开文件位置';
        } catch (error) {
          open.disabled = false;
          open.textContent = '打开文件位置';
          alert(`打开失败：${error.message}`);
        }
      }, {once:true});
    }
  }

  async function refresh() {
    const panel = ensurePanel();
    if (!panel) return;
    try {
      const [monitor, finalState] = await Promise.all([
        json('/api/production-monitor'),
        json('/api/final-render/status')
      ]);
      lastError = '';
      render(monitor.production || {}, finalState.executor || {});
    } catch (error) {
      if (String(error.message || '') !== lastError) lastError = String(error.message || '');
      installStyle();
      const target = ensurePanel();
      if (target) target.innerHTML = `<div class="kz-final71-error">#71 状态暂时不可读取：${esc(lastError)}</div>`;
    }
  }

  function install() {
    installStyle();
    if (!ensurePanel()) {
      setTimeout(install, 250);
      return;
    }
    refresh();
    clearInterval(timer);
    timer = setInterval(refresh, 3500);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true});
  else install();
})();
(() => {
  'use strict';
  if (window.__KZ_CONTENT_STUDIO_V111__) return;
  window.__KZ_CONTENT_STUDIO_V111__ = true;

  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api = async url => {
    const response = await fetch(url, {cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.error || data.message || `HTTP ${response.status}`);
    return data;
  };

  const CSS = `
    :root{--v111-blue:#1768e5;--v111-navy:#0d2e57;--v111-green:#16875c;--v111-amber:#9a671c;--v111-red:#c53b3b;--v111-border:#dfe7f1;--v111-muted:#71839a}
    #studio-root{font-size:13px;color:#17243b}
    #studio-root .studio-shell{padding-bottom:12px}
    #studio-root .studio-nav{min-height:52px;border-radius:0 0 6px 6px;padding:8px 16px;box-shadow:0 2px 8px rgba(14,46,87,.08)}
    #studio-root .studio-brand{min-width:210px}
    #studio-root .studio-tab,#studio-root .studio-primary,#studio-root .studio-secondary,#studio-root input,#studio-root select{height:36px}
    #studio-root .studio-tab,#studio-root .studio-primary,#studio-root .studio-secondary{border-radius:4px}
    #studio-root .studio-page{padding:0 16px 16px}
    #studio-root .studio-page-head{padding:12px 16px;margin-bottom:16px;border-radius:7px;box-shadow:0 1px 2px rgba(20,48,82,.025)}
    #studio-root .studio-page-head h2{font-size:18px;line-height:1.35;margin-top:2px}
    #studio-root .studio-page-head p{font-size:12px;line-height:1.5;margin-top:3px}
    #studio-root .studio-grid{gap:16px;margin-bottom:16px}
    #studio-root .studio-card,#studio-root .studio-section{padding:12px 16px;border-radius:7px;box-shadow:0 1px 2px rgba(20,48,82,.025)}
    #studio-root .studio-card strong{font-size:22px;line-height:1.15;margin:5px 0 2px;font-variant-numeric:tabular-nums}
    #studio-root .studio-card small,#studio-root .studio-card span{font-size:12px}
    #studio-root .studio-main-grid{gap:16px}
    #studio-root .studio-section h3{font-size:14px;margin-bottom:8px}
    #studio-root .studio-list{gap:0}
    #studio-root .studio-row{min-height:42px;grid-template-columns:120px minmax(0,1fr) auto;gap:12px;padding:7px 0}
    #studio-root .studio-row b{font-size:13px}.studio-row span{line-height:1.45}
    #studio-root .studio-status{min-height:24px;border-radius:4px;font-weight:700;font-style:normal;white-space:nowrap}
    #studio-root .studio-status.blue{background:#e8f1ff;color:var(--v111-blue)}
    #studio-root .studio-status.green{background:#e8f7f0;color:var(--v111-green)}
    #studio-root .studio-status.amber{background:#fff4df;color:var(--v111-amber)}
    #studio-root .studio-status.red{background:#ffebeb;color:var(--v111-red)}
    #studio-root .studio-form{gap:10px 16px}
    #studio-root .studio-form label{font-size:12px}
    #studio-root .studio-form input,#studio-root .studio-form select,#studio-root .studio-form textarea{border-radius:4px;font-size:13px}
    #studio-root .studio-form textarea{min-height:88px;padding:8px 10px;line-height:1.55}
    #studio-root .studio-actions{gap:8px;margin-top:12px}
    #studio-root .studio-empty{padding:16px;min-height:0;border-radius:6px;line-height:1.55}
    #studio-root .studio-note{padding:9px 12px;border-radius:6px;line-height:1.55}
    #studio-root button:focus-visible,#studio-root input:focus,#studio-root select:focus,#studio-root textarea:focus{outline:none;box-shadow:0 0 0 3px rgba(23,104,229,.10);border-color:#75a1e8}
    #studio-root .studio-primary{box-shadow:none}
    #studio-root .studio-secondary{background:#fff}
    #studio-root [data-danger],#studio-root .danger{color:#b4233e!important;border-color:#e6b9c0!important;background:#fff!important}
    #studio-root .v111-state-list{display:grid;gap:0;border:1px solid #e5ebf3;border-radius:6px;background:#fff}
    #studio-root .v111-state-row{display:grid;grid-template-columns:minmax(180px,1.2fr) minmax(180px,.8fr) 150px 96px;gap:12px;align-items:center;min-height:44px;padding:7px 10px;border-top:1px solid #edf1f6}
    #studio-root .v111-state-row:first-child{border-top:0}
    #studio-root .v111-state-row b{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    #studio-root .v111-state-row span{font-size:12px;color:#6f8198;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    #studio-root .v111-state-row time{text-align:right;font-size:11px;color:#8c99aa;font-variant-numeric:tabular-nums;white-space:nowrap}
    #studio-root .v111-state-row a{justify-self:end;text-decoration:none}
    #studio-root .v111-state-row .studio-status{justify-self:end}
    #studio-root .v111-empty{padding:14px;border:1px dashed #cedaea;border-radius:6px;background:#fbfdff;color:#71839a;text-align:center;font-size:12px}
    #studio-root .v111-subtle{color:#8796a8;font-size:11px}
    #studio-root .v111-metric-ok{color:var(--v111-green)!important}
    #studio-root .v111-metric-warn{color:var(--v111-amber)!important}
    #studio-root .reference-page{padding:0 16px 16px!important}
    #studio-root .reference-page-head{padding:12px 16px;margin-bottom:16px;border-radius:7px;box-shadow:0 1px 2px rgba(20,48,82,.025)}
    #studio-root .reference-page-head h2{font-size:18px}
    #studio-root .reference-kpis{gap:16px;margin-bottom:16px}
    #studio-root .reference-kpis article{padding:11px 14px;border-radius:7px;box-shadow:0 1px 2px rgba(20,48,82,.025)}
    #studio-root .reference-import-card{padding:12px 16px;margin-bottom:16px;border-radius:7px;box-shadow:0 1px 2px rgba(20,48,82,.025)}
    #studio-root .reference-import-grid textarea{min-height:88px}
    #studio-root .reference-workspace{gap:16px}
    #studio-root .reference-library,#studio-root .reference-analysis,#studio-root .reference-director{padding:12px 14px;border-radius:7px;box-shadow:0 1px 2px rgba(20,48,82,.025)}
    #studio-root .reference-list{gap:0;border:1px solid #e5ebf3;border-radius:6px;overflow:hidden}
    #studio-root .reference-list-item{border:0;border-top:1px solid #edf1f6;border-radius:0;padding:8px 10px}
    #studio-root .reference-list-item:first-child{border-top:0}
    #studio-root .reference-analysis-block{padding:10px;border-radius:6px}
    #studio-root .reference-empty.hero{min-height:180px}
    #studio-root .apc-topbar{padding:12px 16px;margin-bottom:16px;border-radius:7px;box-shadow:0 1px 2px rgba(20,48,82,.025)}
    #studio-root .apc-topbar h2{font-size:20px}
    #studio-root .apc-status{margin-bottom:16px;border-radius:6px;box-shadow:none}
    #studio-root .apc-assets,#studio-root .apc-canvas,#studio-root .apc-control,#studio-root .apc-bottom{border-radius:7px;box-shadow:0 1px 2px rgba(20,48,82,.025)}
    #studio-root .apc-grid{gap:16px}
    #studio-root .apc-bottom{margin-top:16px}
    #studio-root .kz-simple{padding:0 16px 16px}
    #studio-root .kz-simple-hero,#studio-root .kz-simple-flow,#studio-root .kz-simple-card,#studio-root .kz-v101-card{border-radius:7px;box-shadow:0 1px 2px rgba(20,48,82,.025)}
    #studio-root .kz-simple-hero{padding:12px 16px;margin-bottom:16px}
    #studio-root .kz-simple-hero h2{font-size:18px}
    #studio-root .kz-simple-flow{margin-bottom:16px;padding:8px 12px}
    #studio-root .kz-simple-main{gap:16px}
    #studio-root .kz-simple-card{padding:14px 16px}
    #studio-root .kz-simple-card textarea{min-height:88px}
    #studio-root .kz-v101-grid{gap:12px}
    #studio-root .kz-v101-box{border-radius:6px;padding:10px 12px}
    @media(max-width:1100px){#studio-root .v111-state-row{grid-template-columns:1fr auto}#studio-root .v111-state-row span{grid-column:1/-1}#studio-root .v111-state-row time{grid-column:1}#studio-root .v111-state-row a,#studio-root .v111-state-row .studio-status{grid-column:2;grid-row:1}}
    @media(max-width:760px){#studio-root .studio-page,#studio-root .reference-page,#studio-root .kz-simple{padding-left:12px!important;padding-right:12px!important}#studio-root .studio-grid{gap:10px}.studio-page-head{align-items:flex-start;flex-direction:column}.v111-state-row{grid-template-columns:1fr!important}.v111-state-row>*{grid-column:1!important;grid-row:auto!important;justify-self:start!important}.v111-state-row time{text-align:left!important}}
  `;

  function installStyle(){
    if (byId('kz-content-v111-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-content-v111-style';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function fmtTime(value){
    if (!value) return '—';
    try {
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return String(value).slice(0,19);
      return new Intl.DateTimeFormat('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(d);
    } catch (_) { return String(value).slice(0,19); }
  }

  function finalOutputs(center){
    return (center?.outputs || []).filter(item => {
      const kind = String(item?.kind || item?.type || '');
      return /最终成片|完整成片/.test(kind) && !/候选/.test(kind);
    }).sort((a,b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  }

  function projectName(center, projectId){
    const project = (center?.projects || []).find(x => String(x.id || '') === String(projectId || ''));
    return project?.name || projectId || '未命名项目';
  }

  async function refreshAssets(){
    const root = byId('assets');
    if (!root) return;
    const cards = [...root.querySelectorAll('.studio-card')];
    if (cards.length < 4) return;
    try {
      const [center, series] = await Promise.all([
        api('/api/ai-content-center'),
        api('/api/series-asset-center').catch(() => ({items:[],counts:{}})),
      ]);
      const items = series.items || [];
      const counts = series.counts || {};
      const centerAssets = center.assets || [];
      const seriesBacked = new Set(items.map(x => String(x.id || '')).filter(Boolean));
      const realBrand = centerAssets.filter(asset => {
        if (seriesBacked.has(String(asset.series_asset_id || ''))) return false;
        const type = String(asset.asset_type || asset.type || asset.kind || '');
        return !/人物|数字人|场景|物品|声音/.test(type) || /真实|品牌|图片|视频|素材/.test(type);
      }).length;
      const values = [Number(counts.character || 0), Number(counts.scene || 0), Number(counts.voice || 0), realBrand];
      cards.slice(0,4).forEach((card,index) => {
        const strong = card.querySelector('strong');
        const hint = card.querySelector('span');
        if (strong) strong.textContent = String(values[index]);
        if (hint && values[index] > 0 && /等待登记/.test(hint.textContent || '')) hint.textContent = '已登记';
      });
    } catch (_) {
      // Keep the original truthful zero/empty state when the local API is unavailable.
    }
  }

  function qcFacts(output){
    const director = output?.director_qc || output?.quality_qc || {};
    const technical = output?.technical_qc || output?.qc || {};
    const continuity = output?.continuity_qc || {};
    return {
      subtitle: output?.public_narration_hygiene === true && director?.passed === true,
      technical: technical?.passed === true,
      continuity: continuity?.passed === true || output?.continuity_qc_passed === true,
    };
  }

  function setQcBadge(node, mode, text){
    if (!node) return;
    node.classList.remove('blue','green','amber','red');
    node.classList.add(mode);
    node.textContent = text;
  }

  async function refreshQc(){
    const root = byId('qc');
    if (!root) return;
    try {
      const center = await api('/api/ai-content-center');
      const finals = finalOutputs(center);
      const badges = [...root.querySelectorAll('.studio-list .studio-status')];
      if (!finals.length) return;
      const latest = finals[0];
      const facts = qcFacts(latest);
      setQcBadge(badges[0], facts.continuity ? 'green' : 'amber', facts.continuity ? '规则通过' : '待人工');
      setQcBadge(badges[1], facts.subtitle ? 'green' : 'amber', facts.subtitle ? '规则通过' : '待人工');
      setQcBadge(badges[2], 'amber', '待人工');
      setQcBadge(badges[3], 'amber', '待人工');
      const empty = root.querySelector('.studio-empty');
      if (!empty) return;
      empty.className = 'v111-state-list';
      empty.innerHTML = finals.slice(0,8).map(output => {
        const f = qcFacts(output);
        const passed = f.technical && f.subtitle;
        return `<div class="v111-state-row"><b>${esc(projectName(center,output.project_id))}</b><span>${esc(output.kind || '最终成片')} · ${esc(output.source || '本地成片')}</span><time>${esc(fmtTime(output.created_at))}</time><em class="studio-status ${passed?'green':'amber'}">${passed?'技术/结构通过':'待人工复核'}</em></div>`;
      }).join('');
    } catch (_) {}
  }

  async function refreshLibrary(){
    const root = byId('library');
    if (!root) return;
    const empty = root.querySelector('.studio-empty');
    if (!empty) return;
    try {
      const center = await api('/api/ai-content-center');
      const finals = finalOutputs(center);
      if (!finals.length) return;
      empty.className = 'v111-state-list';
      empty.innerHTML = finals.slice(0,20).map(output => {
        const url = output.file_url || output.url || '';
        const status = String(output.status || '成片已完成');
        return `<div class="v111-state-row"><b>${esc(projectName(center,output.project_id))}</b><span>${esc(output.kind || '最终成片')} · ${esc(status)}</span><time>${esc(fmtTime(output.created_at))}</time>${url?`<a class="studio-secondary" href="${esc(url)}" target="_blank" rel="noopener">查看成片</a>`:`<em class="studio-status green">${esc(status)}</em>`}</div>`;
      }).join('');
    } catch (_) {}
  }

  async function refreshOverviewCards(){
    const root = byId('overview');
    if (!root) return;
    try {
      const center = await api('/api/ai-content-center');
      const projects = center.projects || [];
      const tasks = center.tasks || [];
      const pending = tasks.filter(task => !/已完成|完成|已取消|取消/.test(String(task.status || ''))).length;
      const p = byId('ov-projects'), t = byId('ov-tasks'), pd = byId('ov-pending');
      if (p) p.textContent = String(projects.length);
      if (t) t.textContent = String(tasks.length);
      if (pd) pd.textContent = String(pending);
    } catch (_) {}
  }

  async function refreshActive(){
    const active = document.querySelector('.studio-tab.active')?.dataset?.route || document.querySelector('#studio-pages>.page.active')?.id || '';
    if (active === 'assets') return refreshAssets();
    if (active === 'qc') return refreshQc();
    if (active === 'library') return refreshLibrary();
    if (active === 'overview') return refreshOverviewCards();
  }

  function compactStaticLayout(){
    document.querySelectorAll('#studio-root time,.apc-audit span,.reference-list-item small').forEach(node => { node.style.fontVariantNumeric = 'tabular-nums'; });
  }

  function install(){
    if (!byId('studio-root')) return;
    installStyle();
    compactStaticLayout();
    document.addEventListener('click', event => {
      if (event.target.closest?.('.studio-tab,[data-go]')) setTimeout(refreshActive,180);
    }, true);
    refreshActive();
    window.setInterval(() => {
      if (document.visibilityState === 'visible') refreshActive();
    }, 10000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(install,80), {once:true});
  else setTimeout(install,80);
})();

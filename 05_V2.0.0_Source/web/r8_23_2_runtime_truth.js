(() => {
  'use strict';
  if (window.__KZ_R8232_RUNTIME_TRUTH_UI_LOADED__) return;
  window.__KZ_R8232_RUNTIME_TRUTH_UI_LOADED__ = true;

  const API = '/api/r8-23-2/runtime-truth';
  const labels = {
    waiting_external_validation: '待外部验证',
    ready_for_content_route: '内容通道已就绪',
    registered_manual_or_browser_route: '已登记 · 需浏览器/人工',
    ready_owned_route: '自有通道已就绪',
    graded_authorization: '分级授权',
    not_configured: '未配置',
    configured: '已配置 · 待验证',
    ready: '已就绪',
    policy_ready: '策略已就绪',
    waiting_connector: '等待连接器',
  };

  const style = document.createElement('style');
  style.textContent = `
    #kz-runtime-truth-strip{margin:0 0 12px;padding:9px 14px;min-height:42px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;background:#fff;border:1px solid #e5e7eb;border-radius:8px;box-shadow:0 1px 2px rgba(15,23,42,.04);font:13px/1.4 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#334155}
    #kz-runtime-truth-strip b{color:#0f172a;font-weight:650}#kz-runtime-truth-strip .kz-sep{width:1px;height:18px;background:#e2e8f0}
    .kz-state{display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;font-weight:650}.kz-ready{background:#ecfdf5;color:#047857}.kz-degraded{background:#fffbeb;color:#b45309}.kz-blocked{background:#fef2f2;color:#b91c1c}.kz-running{background:#eff6ff;color:#1d4ed8}.kz-muted{background:#f1f5f9;color:#64748b}
    #kz-owner-truth-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0 0 14px}#kz-owner-truth-summary>div{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:12px 14px;min-height:70px}#kz-owner-truth-summary small{display:block;color:#64748b;margin-bottom:6px}#kz-owner-truth-summary strong{font-size:20px;color:#0f172a}#kz-owner-truth-summary span{display:block;margin-top:4px;color:#64748b;font-size:12px}
    .kz-legacy-technical{opacity:.96}.kz-legacy-technical>summary{cursor:pointer;font-weight:650;color:#475569}
    .kz-secret-config-note{display:block;margin:8px 0;padding:8px 10px;border-radius:6px;background:#f8fafc;color:#64748b;font-size:12px}
    @media(max-width:900px){#kz-owner-truth-summary{grid-template-columns:repeat(2,minmax(0,1fr))}#kz-runtime-truth-strip{gap:8px}.kz-sep{display:none!important}}
  `;
  document.head.appendChild(style);

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  function mainContainer(){ return document.querySelector('main') || document.body; }

  function ensureStrip(){
    let el = document.getElementById('kz-runtime-truth-strip');
    if(el) return el;
    el = document.createElement('div'); el.id='kz-runtime-truth-strip'; el.setAttribute('aria-live','polite');
    const main=mainContainer(), header=main.querySelector('header');
    if(header && header.nextSibling) main.insertBefore(el, header.nextSibling); else main.prepend(el);
    return el;
  }

  function queueCounts(items){
    const rows=Object.values(items||{}); const c={queued:0,running:0,ready:0,scheduled:0,failed:0};
    rows.forEach(r=>{ const s=String(r.state||''); if(s==='queued')c.queued++; if(s==='running')c.running++; if(s==='failed')c.failed++; if(r.wait_reason_code==='ready'||r.wait_reason_code==='retry_ready')c.ready++; if(r.wait_reason_code==='scheduled_time')c.scheduled++; });
    return c;
  }

  function renderStrip(data){
    const el=ensureStrip(), ctl=data.control||{}, rd=data.readiness||{}, q=queueCounts((data.queue||{}).items), dp=(data.decision_pack||{}).pack||{};
    const state=String(rd.state||'BLOCKED').toUpperCase(); const cls=state==='READY'?'kz-ready':state==='DEGRADED'?'kz-degraded':'kz-blocked';
    el.innerHTML=`<span class="kz-state ${cls}">${esc(state)}</span><span><b>当前 Command</b> ${esc(ctl.command_id||'未建立')}</span><span class="kz-sep"></span><span><b>Mission</b> ${esc(ctl.mission_id||'—')}</span><span class="kz-sep"></span><span><b>执行</b> ${q.running}</span><span><b>可领取</b> ${q.ready}</span><span><b>计划等待</b> ${q.scheduled}</span><span class="kz-sep"></span><span><b>控制租约</b> ${esc((data.decision_pack||{}).state||'missing')}${dp.expires_at?` · 至 ${esc(String(dp.expires_at).replace('T',' ').slice(0,16))}`:''}</span>`;
  }

  function renderOwnerSummary(data){
    const dashboard=document.getElementById('dashboard'); if(!dashboard) return;
    let box=document.getElementById('kz-owner-truth-summary'); if(!box){ box=document.createElement('div'); box.id='kz-owner-truth-summary'; dashboard.prepend(box); }
    const q=queueCounts((data.queue||{}).items), pending=data.pending||{}, ctl=data.control||{};
    const sys=(pending.system_owned||[]).length, human=(pending.human||[]).length;
    box.innerHTML=`<div><small>当前控制链</small><strong>${ctl.consistent?'一致':'需修复'}</strong><span>${esc(ctl.plan_id||'等待 Controller Plan')}</span></div><div><small>AI员工任务</small><strong>${q.running} 执行 / ${q.ready} 可领取</strong><span>${q.scheduled} 项正常等待计划时间</span></div><div><small>真正需要老板</small><strong>${human}</strong><span>${sys} 项已由系统自动接管，不推给老板</span></div><div><small>结果真值</small><strong>Receipt / Evidence</strong><span>本地完成不等于外部成功</span></div>`;
  }

  function translateRawStates(root=document.body){
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT); let n; const targets=[];
    while((n=walker.nextNode())){ if(n.nodeValue && Object.keys(labels).some(k=>n.nodeValue.includes(k))) targets.push(n); if(targets.length>400)break; }
    targets.forEach(node=>{ let t=node.nodeValue; Object.entries(labels).forEach(([k,v])=>{t=t.split(k).join(v)}); node.nodeValue=t; });
  }

  function compactLegacy(){
    document.querySelectorAll('h1,h2,h3,h4,p,b,strong').forEach(h=>{
      const txt=(h.textContent||'').trim().toUpperCase();
      if(txt.includes('MISSION CONTROL LEDGER') || txt.includes('R8-22 · 7×24 AUTONOMOUS CONVERGENCE')){
        const card=h.closest('article,.panel,.card,section,div'); if(!card || card.dataset.kzWrapped)return;
        card.dataset.kzWrapped='1'; card.classList.add('kz-legacy-technical');
        if(!card.querySelector(':scope > .kz-secret-config-note')){
          const note=document.createElement('span'); note.className='kz-secret-config-note'; note.textContent='历史/技术审计信息；当前真值以顶部 Command · Mission · Controller Plan 为准。'; card.prepend(note);
        }
      }
    });
  }

  async function refresh(){
    try{
      const res=await fetch(API,{cache:'no-store'}); if(!res.ok) throw new Error(String(res.status)); const data=await res.json();
      renderStrip(data); renderOwnerSummary(data); translateRawStates(); compactLegacy();
      window.__KZ_RUNTIME_TRUTH__=data;
    }catch(err){
      const el=ensureStrip(); el.innerHTML='<span class="kz-state kz-degraded">运行真值接口暂不可用</span><span>核心页面仍可使用；系统将在下一次轮询自动恢复。</span>';
    }
  }

  const observer=new MutationObserver(()=>{ translateRawStates(); compactLegacy(); });
  observer.observe(document.documentElement,{subtree:true,childList:true});
  const start=()=>{refresh(); setInterval(refresh,15000);};
  if(document.readyState==='loading') window.addEventListener('DOMContentLoaded',start,{once:true}); else start();
})();

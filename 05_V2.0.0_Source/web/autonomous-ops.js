(() => {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const mode = location.pathname.includes('operational') ? 'execution' : 'boss';
  const embedded = window.self !== window.top;
  let last = null;
  let lastGateway = null;
  let detailOpen = false;

  function installShellStyle(){
    if(document.getElementById('kz-v374-shell-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-v374-shell-style';
    style.textContent = `
      html.kz-embedded-r8 .sidebar{display:none!important}
      html.kz-embedded-r8 .app-shell{grid-template-columns:minmax(0,1fr)!important}
      html.kz-embedded-r8 #mission-command-strip{display:none!important}
      html.kz-embedded-r8 header{height:60px!important}
      .mission-ai-gateway{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:7px 10px;border:1px solid #dce5f0;background:#fff;color:#29415f;font-size:12px}
      .mission-ai-gateway.ready{background:#e8f7ef;color:#147451;border-color:#ccebdc}
      .mission-ai-gateway.warn{background:#fff2df;color:#9a5a13;border-color:#f4d6aa;cursor:pointer}
      .kz-ai-modal-backdrop{position:fixed;inset:0;background:rgba(8,20,38,.48);z-index:99999;display:grid;place-items:center;padding:24px}
      .kz-ai-modal{width:min(520px,100%);background:#fff;border-radius:16px;box-shadow:0 24px 70px rgba(0,0,0,.22);padding:22px}
      .kz-ai-modal h3{margin:0 0 6px;font-size:20px}.kz-ai-modal p{margin:0 0 16px;color:#65738a;line-height:1.7}
      .kz-ai-modal label{display:grid;gap:6px;margin:12px 0;color:#526178;font-size:13px}.kz-ai-modal input{width:100%;border:1px solid #dce5f0;border-radius:9px;padding:10px;font:inherit}
      .kz-ai-modal-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}.kz-ai-modal button{border:1px solid #dce5f0;background:#fff;border-radius:9px;padding:9px 13px;cursor:pointer}.kz-ai-modal button.primary{background:#2865df;color:#fff;border-color:#2865df}
      .kz-ai-modal .note{font-size:12px;background:#eef4ff;color:#3d5c8d;padding:10px;border-radius:9px;margin-top:12px}.kz-ai-modal .error{font-size:12px;background:#fff0f0;color:#b94242;padding:10px;border-radius:9px;margin-top:12px}
    `;
    document.head.appendChild(style);
    if(embedded) document.documentElement.classList.add('kz-embedded-r8');
  }

  async function request(path, options={}){
    const response = await fetch(path, {cache:'no-store', ...options});
    const data = await response.json().catch(() => ({}));
    if(!response.ok) throw new Error(data.error || data.message || `HTTP ${response.status}`);
    return data;
  }

  function userTone(state){
    if(state === '异常') return 'danger';
    if(state === '等待你处理') return 'human';
    if(state === '已完成') return 'done';
    return 'running';
  }

  function stageCopy(mission){
    if(!mission) return '等待经营任务';
    const stage = mission.stage || '自动处理中';
    const auto = mission.auto_action || '';
    const bottleneck = mission.bottleneck || '';
    if(mission.user_state === '等待你处理') return bottleneck || '当前需要老板完成关键确认';
    if(mission.user_state === '异常') return bottleneck || '自动恢复达到上限，需要检查';
    return auto || bottleneck || `系统正在推进：${stage}`;
  }

  function timelineHtml(items){
    if(!Array.isArray(items) || !items.length) return '<div class="mission-empty">当前还没有流水线事件。系统产生真实状态变化后会自动记录。</div>';
    return `<div class="mission-timeline">${items.slice(0,8).map(item => `<div class="mission-event"><span>${esc((item.at||'').replace('T',' ').slice(5,16))}</span><div><b>${esc(item.message || item.kind || '状态更新')}</b><small>${esc(item.kind || '')}</small></div></div>`).join('')}</div>`;
  }

  function goalText(data, mission){
    return data?.owner_goal?.objective || mission?.goal || mission?.title || '等待老板经营目标或R7真实机会';
  }

  function ensureHost(){
    let panel = document.getElementById('mission-command-strip');
    if(panel) return panel;
    panel = document.createElement('section');
    panel.id = 'mission-command-strip';
    panel.className = 'mission-command-strip';
    const main = document.querySelector('main');
    if(main) main.prepend(panel);
    else document.body.prepend(panel);
    return panel;
  }

  function gatewayBadge(gateway){
    if(!gateway) return '<span class="mission-ai-gateway warn" data-ai-gateway-config>AI大脑：检查中</span>';
    if(gateway.configured && gateway.status === 'ready') return `<span class="mission-ai-gateway ready">AI大脑：${esc(gateway.model || '已连接')}</span>`;
    if(gateway.configured) return `<button type="button" class="mission-ai-gateway warn" data-ai-gateway-config>AI大脑：${esc(gateway.status_label || '待验证')}</button>`;
    return '<button type="button" class="mission-ai-gateway warn" data-ai-gateway-config>AI大脑：一次配置</button>';
  }

  function render(data, gateway=lastGateway){
    last = data;
    lastGateway = gateway || lastGateway;
    const panel = ensureHost();
    const mission = data?.active_mission || null;
    const world = data?.world_state || {};
    const state = mission?.user_state || '自动处理中';
    const humanCount = Number(world.waiting_owner_review || 0) + Number(world.accounts_needing_human || 0) + Number(world.attention_missions || 0);
    const r7Headline = world?.r7_manager?.headline || 'R7 正在等待可核验经营数据';
    const missionLabel = mission?.mission_id || '尚未建立 Mission';
    const context = mission ? `${mission.region || '区域待定'} · ${mission.service || '业务待定'}` : 'R7 与 R8 将共享同一经营任务';
    const bossActive = mode === 'boss' ? 'active' : '';
    const execActive = mode === 'execution' ? 'active' : '';

    panel.innerHTML = `
      <div class="mission-bar">
        <div class="mission-identity">
          <span class="mission-eyebrow">卡嘴子自治运营主线 · V2.2.2</span>
          <div class="mission-title-row"><strong>${esc(missionLabel)}</strong><span>${esc(context)}</span></div>
          <p><b>老板目标：</b>${esc(goalText(data, mission))}</p>
        </div>
        <div class="mission-now">
          <span class="mission-state ${userTone(state)}">${esc(state)}</span>
          <b>${esc(mission?.stage || '等待R7机会')}</b>
          <small>${esc(stageCopy(mission))}</small>
        </div>
        <div class="mission-actions">
          ${gatewayBadge(lastGateway)}
          <a class="${bossActive}" href="/">老板总控</a>
          <a class="${execActive}" href="/operational.html">执行中心</a>
          <button type="button" data-mission-toggle>${detailOpen ? '收起流水线' : '查看流水线'}</button>
          <span class="mission-human ${humanCount ? 'has' : ''}">待我处理 ${humanCount}</span>
        </div>
      </div>
      <div class="mission-detail" ${detailOpen ? '' : 'hidden'}>
        <div class="mission-detail-grid">
          <article><span>ChatGPT / R7 AI决策</span><b>${esc(r7Headline)}</b><small>R7输出自动进入同一 Mission；AI Gateway直连时不再依赖人工搬运文件。</small></article>
          <article><span>R8 自动执行</span><b>${esc(mission?.video_status || mission?.stage || '等待任务')}</b><small>${esc(stageCopy(mission))}</small></article>
          <article><span>真实结果</span><b>${Number(mission?.verified_publications || 0)} 个已验证发布</b><small>只有真实平台回执才计入完成；咨询和订单继续回流复盘。</small></article>
        </div>
        <div class="mission-detail-bottom">
          <div class="mission-goal-editor">
            <label for="mission-owner-goal">老板经营目标</label>
            <div><input id="mission-owner-goal" maxlength="300" value="${esc(data?.owner_goal?.objective || '')}" placeholder="例如：提高涟水县真实维修咨询与订单"><button type="button" data-save-owner-goal>保存目标</button></div>
            <small>只设置经营目标和边界；选题、脚本、生产、调度与复盘由 ChatGPT + R7/R8 自动推进。</small>
          </div>
          <div class="mission-history"><div class="mission-history-head"><b>当前 Mission 时间线</b><span>真实状态变化自动记录</span></div>${timelineHtml(data?.timeline || [])}</div>
        </div>
      </div>`;
  }

  function openGatewayModal(){
    document.querySelector('.kz-ai-modal-backdrop')?.remove();
    const gateway = lastGateway || {};
    const root = document.createElement('div');
    root.className = 'kz-ai-modal-backdrop';
    root.innerHTML = `<div class="kz-ai-modal" role="dialog" aria-modal="true">
      <h3>连接 ChatGPT AI 大脑</h3>
      <p>只需首次配置一次。密钥仅发送到本机 127.0.0.1，并使用 Windows DPAPI 加密保存在当前 Windows 用户下；网页不会读取回密钥。</p>
      <label>OpenAI API Key<input type="password" autocomplete="off" data-ai-key placeholder="sk-..."></label>
      <label>模型<input data-ai-model value="${esc(gateway.model || 'gpt-5.6')}"></label>
      <div class="note">配置成功后，当前卡住的 ChatGPT 策划/QC 会自动恢复；文件同步桥保留为备用通道。最终成片仍必须老板审核后才能发布。</div>
      <div data-ai-error hidden></div>
      <div class="kz-ai-modal-actions"><button type="button" data-ai-cancel>取消</button><button type="button" class="primary" data-ai-save>保存并立即验证</button></div>
    </div>`;
    document.body.appendChild(root);
    root.querySelector('[data-ai-key]')?.focus();
  }

  async function refresh(){
    try{
      const [ops, gateway] = await Promise.all([
        request('/api/autonomous-ops'),
        request('/api/ai-gateway/status').catch(() => null)
      ]);
      render(ops, gateway);
      document.querySelectorAll('.side-footer b').forEach(node => { node.textContent = 'V2.2.2 自治运营核心'; });
    }catch(error){
      const panel = ensureHost();
      panel.innerHTML = `<div class="mission-bar mission-error"><div><b>自治运营主线暂时不可读取</b><span>${esc(error.message)}</span></div><button type="button" data-mission-retry>重新检查</button></div>`;
    }
  }

  document.addEventListener('click', async event => {
    if(event.target.closest('[data-mission-toggle]')){
      detailOpen = !detailOpen;
      if(last) render(last); else refresh();
      return;
    }
    if(event.target.closest('[data-mission-retry]')){ refresh(); return; }
    if(event.target.closest('[data-ai-gateway-config]')){ openGatewayModal(); return; }
    if(event.target.closest('[data-ai-cancel]')){ event.target.closest('.kz-ai-modal-backdrop')?.remove(); return; }
    const aiSave = event.target.closest('[data-ai-save]');
    if(aiSave){
      const modal = aiSave.closest('.kz-ai-modal');
      const key = String(modal?.querySelector('[data-ai-key]')?.value || '').trim();
      const model = String(modal?.querySelector('[data-ai-model]')?.value || 'gpt-5.6').trim();
      const errorBox = modal?.querySelector('[data-ai-error]');
      if(!key){ modal?.querySelector('[data-ai-key]')?.focus(); return; }
      aiSave.disabled = true; aiSave.textContent = '正在连接…';
      try{
        await request('/api/ai-gateway/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({api_key:key, model})});
        await request('/api/ai-gateway/test', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
        modal?.closest('.kz-ai-modal-backdrop')?.remove();
        await refresh();
      }catch(error){
        if(errorBox){ errorBox.hidden = false; errorBox.className = 'error'; errorBox.textContent = `连接失败：${error.message}`; }
        aiSave.disabled = false; aiSave.textContent = '保存并立即验证';
      }
      return;
    }
    const save = event.target.closest('[data-save-owner-goal]');
    if(save){
      const input = document.getElementById('mission-owner-goal');
      const objective = String(input?.value || '').trim();
      if(!objective){ input?.focus(); return; }
      save.disabled = true; save.textContent = '保存中…';
      try{
        await request('/api/autonomous-ops/goal', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({objective, metric:'真实咨询/订单'})});
        await refresh();
      }catch(error){
        save.disabled = false; save.textContent = '保存目标';
        alert(`经营目标保存失败：${error.message}`);
      }
    }
  }, true);

  installShellStyle();
  window.kazuizhiAutonomousRefresh = refresh;
  window.addEventListener('operational:refreshed', () => setTimeout(refresh, 60));
  window.addEventListener('focus', () => refresh());
  refresh();
  setInterval(refresh, 30000);
})();

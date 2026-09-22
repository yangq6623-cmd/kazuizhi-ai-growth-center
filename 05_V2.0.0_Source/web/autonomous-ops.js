(() => {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const mode = location.pathname.includes('operational') ? 'execution' : 'boss';
  let last = null;
  let detailOpen = false;

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

  function render(data){
    last = data;
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
          <span class="mission-eyebrow">卡嘴子自治运营主线</span>
          <div class="mission-title-row"><strong>${esc(missionLabel)}</strong><span>${esc(context)}</span></div>
          <p><b>老板目标：</b>${esc(goalText(data, mission))}</p>
        </div>
        <div class="mission-now">
          <span class="mission-state ${userTone(state)}">${esc(state)}</span>
          <b>${esc(mission?.stage || '等待R7机会')}</b>
          <small>${esc(stageCopy(mission))}</small>
        </div>
        <div class="mission-actions">
          <a class="${bossActive}" href="/">老板总控</a>
          <a class="${execActive}" href="/operational.html">执行中心</a>
          <button type="button" data-mission-toggle>${detailOpen ? '收起流水线' : '查看流水线'}</button>
          <span class="mission-human ${humanCount ? 'has' : ''}">待我处理 ${humanCount}</span>
        </div>
      </div>
      <div class="mission-detail" ${detailOpen ? '' : 'hidden'}>
        <div class="mission-detail-grid">
          <article><span>ChatGPT / R7 AI决策</span><b>${esc(r7Headline)}</b><small>R7输出自动进入同一 Mission 上下文，不需要在 R8 重新填一次。</small></article>
          <article><span>R8 自动执行</span><b>${esc(mission?.video_status || mission?.stage || '等待任务')}</b><small>${esc(stageCopy(mission))}</small></article>
          <article><span>真实结果</span><b>${Number(mission?.verified_publications || 0)} 个已验证发布</b><small>只有真实平台回执才计入完成；后续咨询和订单继续回流复盘。</small></article>
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

  async function refresh(){
    try{
      render(await request('/api/autonomous-ops'));
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

  window.kazuizhiAutonomousRefresh = refresh;
  window.addEventListener('operational:refreshed', () => setTimeout(refresh, 60));
  window.addEventListener('focus', () => refresh());
  refresh();
  setInterval(refresh, 30000);
})();

(() => {
  'use strict';

  async function readJson(path) {
    try {
      const response = await fetch(path, {cache:'no-store', credentials:'same-origin'});
      if (!response.ok) return null;
      return await response.json();
    } catch (_) {
      return null;
    }
  }

  function ensureSummary() {
    const card = document.querySelector('.r810-connector-card');
    if (!card || document.getElementById('kz-async-control-summary')) return;
    const box = document.createElement('div');
    box.id = 'kz-async-control-summary';
    box.className = 'r810-async-control-summary';
    box.innerHTML = `
      <div><small>日常主控</small><b>异步控制总线</b><span id="kz-bus-state">检查中</span></div>
      <div><small>本地自治</small><b>Mission 持续执行</b><span id="kz-autonomy-state">检查中</span></div>
      <div><small>工程通道</small><b>Work / Codex</b><span>仅检查、修复、升级</span></div>
    `;
    card.appendChild(box);
  }

  function patchMissionPill(bus, connector) {
    const pill = document.getElementById('r810-ai-state');
    if (!pill) return;
    const realtime = Boolean(connector?.verified);
    const autonomy = String(bus?.local_autonomy || 'RUNNING').toUpperCase() === 'RUNNING';
    pill.textContent = autonomy
      ? `AI自治：正常 · 实时ChatGPT：${realtime ? '已连接' : '离线'}`
      : `AI自治：需处理 · 实时ChatGPT：${realtime ? '已连接' : '离线'}`;
    pill.className = `r810-state-pill ${autonomy ? 'ok' : 'attention'}`;
  }

  function patchOwnerCommand(bus, connector) {
    const note = document.getElementById('r810-command-note');
    const button = document.getElementById('r810-send-command');
    const realtime = Boolean(connector?.verified);
    if (note) {
      if (realtime) {
        note.textContent = '实时 Site Tools 已连接，可在当前工作台直接下达目标；日常仍建议由普通 ChatGPT 形成 Decision Pack。';
      } else if (bus?.configured) {
        note.textContent = '普通 ChatGPT 为日常总脑；Decision Pack 通过私有异步控制总线下发。本地已批准 Mission 不因实时 ChatGPT 离线而停工。';
      } else {
        note.textContent = '本地自治可继续运行；日常主控建议配置独立私有 GitHub 控制总线。Site Tools 只作为实时辅助。';
      }
    }
    if (button && !realtime) {
      button.title = '当前没有实时 Site Tools 连接。请在普通 ChatGPT 中形成 Decision Pack，或稍后使用实时辅助通道。';
    }
  }

  function apply(bus, connector) {
    ensureSummary();
    const busState = document.getElementById('kz-bus-state');
    const autonomyState = document.getElementById('kz-autonomy-state');
    const copy = document.getElementById('r810-connector-copy');

    if (busState) {
      if (bus?.configured && !bus?.last_error) {
        busState.textContent = bus.last_sync_at ? '已配置 · 已同步' : '已配置 · 等待首次同步';
        busState.className = 'ok';
      } else if (bus?.configured && bus?.last_error) {
        busState.textContent = '已配置 · 同步异常';
        busState.className = 'attention';
      } else {
        busState.textContent = '待配置独立私有仓库';
        busState.className = 'waiting';
      }
    }
    if (autonomyState) {
      const running = String(bus?.local_autonomy || 'RUNNING').toUpperCase() === 'RUNNING';
      autonomyState.textContent = running ? '正常运行' : '需要处理';
      autonomyState.className = running ? 'ok' : 'attention';
    }

    if (copy) {
      if (bus?.configured) {
        copy.textContent = '日常主控采用“普通 ChatGPT → 私有异步控制总线 → 本机 Mission → Receipt 回流”。Site Tools 仅作为同机实时辅助；Work/Codex 仅用于软件检查、修复和升级。';
      } else {
        copy.textContent = '本地自治已与实时 ChatGPT 解耦：已批准 Mission 可继续运行。异步控制总线代码已就绪，激活时必须使用独立 PRIVATE GitHub 仓库；当前公共源码仓库禁止作为运营控制总线。';
      }
    }

    patchMissionPill(bus, connector);
    patchOwnerCommand(bus, connector);
  }

  async function refresh() {
    const [bus, connector] = await Promise.all([
      readJson('/api/async-control-bus/status'),
      readJson('/api/chatgpt-control/status'),
    ]);
    apply(bus, connector);
  }

  const style = document.createElement('style');
  style.textContent = `
    .r810-async-control-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px;width:100%}
    .r810-async-control-summary>div{border:1px solid rgba(148,163,184,.22);border-radius:10px;padding:10px 12px;display:grid;gap:3px;background:rgba(15,23,42,.03)}
    .r810-async-control-summary small{font-size:11px;color:#64748b}.r810-async-control-summary b{font-size:14px}.r810-async-control-summary span{font-size:12px;color:#64748b}
    .r810-async-control-summary span.ok{color:#15803d}.r810-async-control-summary span.waiting{color:#b45309}.r810-async-control-summary span.attention{color:#b45309}
    @media(max-width:860px){.r810-async-control-summary{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const start = () => {
    refresh();
    setInterval(refresh, 15000);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(start, 500));
  else setTimeout(start, 500);
})();

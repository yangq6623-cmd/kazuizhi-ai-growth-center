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

  function busState(bus) {
    if (bus?.configured && !bus?.last_error) {
      return {
        text: bus.last_sync_at ? '已配置 · 已同步' : '已配置 · 等待首次同步',
        tone: 'ok',
        short: bus.last_sync_at ? '已同步' : '已配置',
      };
    }
    if (bus?.configured && bus?.last_error) {
      return {text:'已配置 · 同步异常', tone:'attention', short:'同步异常'};
    }
    return {text:'待配置独立私有仓库', tone:'waiting', short:'待配置'};
  }

  function autonomyRunning(bus) {
    return String(bus?.local_autonomy || 'RUNNING').toUpperCase() === 'RUNNING';
  }

  function ensureSummary() {
    const card = document.querySelector('.r810-connector-card');
    if (!card || document.getElementById('kz-async-control-summary')) return;
    const box = document.createElement('div');
    box.id = 'kz-async-control-summary';
    box.className = 'r810-async-control-summary';
    box.innerHTML = `
      <div><small>日常主控</small><b>私有异步控制总线</b><span id="kz-bus-state">检查中</span></div>
      <div><small>本地自治</small><b>Mission 持续执行</b><span id="kz-autonomy-state">检查中</span></div>
      <div><small>实时辅助</small><b>实时 ChatGPT 通道（可选）</b><span id="kz-realtime-state">检查中</span></div>
      <div><small>工程通道</small><b>Work / Codex</b><span>仅检查、修复、升级</span></div>
    `;
    card.appendChild(box);
  }

  function patchMissionPill(bus, connector) {
    const pill = document.getElementById('r810-ai-state');
    if (!pill) return;
    const realtime = Boolean(connector?.verified);
    const autonomy = autonomyRunning(bus);
    const busInfo = busState(bus);
    pill.textContent = autonomy
      ? `自治：正常 · 异步主控：${busInfo.short} · 实时通道：${realtime ? '已连接' : '可选'}`
      : `自治：需处理 · 异步主控：${busInfo.short} · 实时通道：${realtime ? '已连接' : '可选'}`;
    pill.className = `r810-state-pill ${autonomy ? 'ok' : 'attention'}`;
  }

  function patchOwnerSummary(bus, connector) {
    const summary = document.getElementById('r810-owner-connection-summary');
    const first = summary?.querySelector(':scope > div:first-child');
    const label = first?.querySelector('small');
    const value = document.getElementById('r810-owner-chatgpt') || first?.querySelector('b');
    const note = first?.querySelector('span');
    const info = busState(bus);
    if (label) label.textContent = '日常 AI 主控';
    if (value) value.textContent = info.text;
    if (note) {
      note.textContent = bus?.configured
        ? '普通 ChatGPT Decision Pack → PRIVATE GitHub 控制总线 → 本机 Mission → Receipt 回流'
        : '本地自治仍可运行；配置独立 PRIVATE GitHub 控制总线后，普通 ChatGPT 可作为日常总脑异步下发决策';
    }

    const card = document.getElementById('r810-connector-card');
    const heading = card?.querySelector('h3');
    const eyebrow = card?.querySelector('small');
    if (eyebrow) eyebrow.textContent = 'AI CONTROL CHANNELS';
    if (heading) heading.textContent = '日常异步主控 + 实时辅助通道';

    const status = document.getElementById('r810-connector-status');
    const statusLabel = status?.parentElement?.querySelector('small');
    if (statusLabel) statusLabel.textContent = '实时 ChatGPT（可选）';
    if (status) status.textContent = connector?.verified ? '已验证连接' : '未连接 · 不影响自治';
  }

  function patchOwnerCommand(bus, connector) {
    const note = document.getElementById('r810-command-note');
    const button = document.getElementById('r810-send-command');
    const label = document.querySelector('label[for="r810-owner-command"]');
    const realtime = Boolean(connector?.verified);
    if (label) label.textContent = '实时辅助指令（可选）';
    if (button) button.textContent = '实时下达目标';
    if (note) {
      if (realtime) {
        note.textContent = '实时 ChatGPT 通道已验证，可在当前工作台直接下达目标；日常主控仍可通过 Decision Pack 异步执行。';
      } else if (bus?.configured) {
        note.textContent = '日常主控正常：普通 ChatGPT 的 Decision Pack 通过私有异步控制总线下发；实时通道未连接不影响已批准 Mission 自动运行。';
      } else {
        note.textContent = '本地自治可继续运行。建议配置独立 PRIVATE GitHub 控制总线作为日常主控；实时 ChatGPT 通道只是可选辅助。';
      }
    }
    if (button && !realtime) {
      button.title = '这是实时辅助按钮，只有实时 ChatGPT 往返验证通过后才启用；日常异步控制总线和本地自治不受影响。';
    }
  }

  function apply(bus, connector) {
    ensureSummary();
    const info = busState(bus);
    const busStateNode = document.getElementById('kz-bus-state');
    const autonomyState = document.getElementById('kz-autonomy-state');
    const realtimeState = document.getElementById('kz-realtime-state');
    const copy = document.getElementById('r810-connector-copy');
    const warning = document.querySelector('#r810-connector-card .r810-connection-warning');

    if (busStateNode) {
      busStateNode.textContent = info.text;
      busStateNode.className = info.tone;
    }
    if (autonomyState) {
      const running = autonomyRunning(bus);
      autonomyState.textContent = running ? '正常运行' : '需要处理';
      autonomyState.className = running ? 'ok' : 'attention';
    }
    if (realtimeState) {
      realtimeState.textContent = connector?.verified ? '已验证连接' : '未连接 · 不影响日常自治';
      realtimeState.className = connector?.verified ? 'ok' : 'waiting';
    }

    if (copy) {
      if (bus?.configured) {
        copy.textContent = '日常主控采用“普通 ChatGPT → 私有异步控制总线 → 本机 Mission → Receipt 回流”。实时 ChatGPT 通道只用于同机即时指令；Work/Codex 只用于软件检查、修复和升级。';
      } else {
        copy.textContent = '本地自治已经与实时 ChatGPT 解耦：已批准 Mission 可继续运行。异步控制总线代码已就绪，激活时必须使用独立 PRIVATE GitHub 仓库；实时 ChatGPT 通道保持可选。';
      }
    }
    if (warning) {
      warning.textContent = '真实状态分开计算：异步总线只证明 Decision Pack/Receipt 链路；实时通道只有完成真实往返验证才显示“已连接”。两者都不会伪造发布、咨询或订单结果。';
    }

    patchMissionPill(bus, connector);
    patchOwnerSummary(bus, connector);
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
    .r810-async-control-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px;width:100%}
    .r810-async-control-summary>div{border:1px solid rgba(148,163,184,.22);border-radius:10px;padding:10px 12px;display:grid;gap:3px;background:rgba(15,23,42,.03)}
    .r810-async-control-summary small{font-size:11px;color:#64748b}.r810-async-control-summary b{font-size:14px}.r810-async-control-summary span{font-size:12px;color:#64748b}
    .r810-async-control-summary span.ok{color:#15803d}.r810-async-control-summary span.waiting{color:#b45309}.r810-async-control-summary span.attention{color:#b45309}
    @media(max-width:1060px){.r810-async-control-summary{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media(max-width:680px){.r810-async-control-summary{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const start = () => {
    refresh();
    setInterval(refresh, 15000);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(start, 0));
  else setTimeout(start, 0);
})();

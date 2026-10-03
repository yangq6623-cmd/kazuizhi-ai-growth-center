(() => {
  'use strict';
  if (window.__KZ_R8234_RECOVERY__) return;
  window.__KZ_R8234_RECOVERY__ = true;

  const VERSION = 'R8-23.4 Runtime & Route Recovery';
  const REQUEST_TIMEOUT_MS = 4500;
  const REFRESH_MS = 15000;
  const inflight = new Map();
  let lastCandidate = null;
  let refreshTimer = null;

  const $ = (sel, root=document) => root.querySelector(sel);
  const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[ch]);

  async function fetchJson(url, {timeout=REQUEST_TIMEOUT_MS, dedupe=true}={}) {
    if (dedupe && inflight.has(url)) return inflight.get(url);
    const task = (async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      try {
        const response = await fetch(url, {cache:'no-store', signal:controller.signal});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || data.message || `${url} HTTP ${response.status}`);
        return data;
      } finally {
        clearTimeout(timer);
      }
    })();
    if (dedupe) inflight.set(url, task);
    try { return await task; }
    finally { if (inflight.get(url) === task) inflight.delete(url); }
  }

  function clearLegacyBuildQuery() {
    try {
      const url = new URL(location.href);
      if (!url.searchParams.has('build')) return;
      url.searchParams.delete('build');
      history.replaceState(null, '', url.pathname + (url.search || '') + url.hash);
    } catch (_) {}
  }

  function buildInfo() {
    const info = window.KZ_BUILD_INFO || {};
    return {
      run: String(info.runNumber || '').replace(/^__.*__$/, ''),
      commit: String(info.commit || '').replace(/^__.*__$/, ''),
    };
  }

  function normalizeVersionCopy() {
    const info = buildInfo();
    const baseline = $('.baseline');
    if (baseline && baseline.dataset.kzR8234Version !== `${info.run}|${info.commit}`) {
      baseline.dataset.kzR8234Version = `${info.run}|${info.commit}`;
      baseline.innerHTML = `<b>R8-23.4 Candidate${info.run ? ` · #${esc(info.run)}` : ''}</b><br><span>运行恢复 · 路由收口 · 真实回执</span>${info.commit ? `<code>${esc(info.commit.slice(0,8))}</code>` : ''}`;
    }
    if (document.title !== '卡嘴子 AI 自治运营 · R8-23.4') document.title = '卡嘴子 AI 自治运营 · R8-23.4';
    $$('body *').forEach(node => {
      if (node.children.length) return;
      const text = node.textContent || '';
      let next = text;
      if (text === '员工汇报，R7 汇总，ChatGPT 做战略判断') next = 'AI员工汇报 → 运营经理汇总 → ChatGPT战略复盘';
      else if (/R7\s*经理报告/.test(text)) next = text.replace(/R7\s*经理报告/g, '运营经理报告');
      else if (/R7\s*经理/.test(text)) next = text.replace(/R7\s*经理/g, '运营经理');
      else if (/R7\s*汇总/.test(text)) next = text.replace(/R7\s*汇总/g, '运营经理汇总');
      if (next !== text) node.textContent = next;
    });
  }

  function ensureContentRoute() {
    const nav = $('aside nav');
    if (!nav) return null;
    const button = $('button.nav[data-page="promotion"]', nav);
    if (!button) return null;
    button.dataset.title = '内容生产与发布';
    button.dataset.subtitle = 'SEO/GEO、广告、短视频等内容生产、质检与发布准备';
    button.dataset.kzRouteRole = 'content-production';
    if (!/内容生产与发布/.test(button.textContent || '')) {
      const icon = button.querySelector('span');
      button.innerHTML = `${icon ? icon.outerHTML : '<span>创</span>'}内容生产与发布`;
    }
    return button;
  }

  function ensureSeoGeoRoute() {
    const primary = $('.r810-primary-nav');
    if (primary && !primary.querySelector('[data-target="r813-seo-geo"]') && window.KZR813SeoGeoBridge) {
      const button = document.createElement('button');
      button.className = 'r810-nav-button';
      button.dataset.target = 'r813-seo-geo';
      button.innerHTML = '<span class="r810-icon">搜</span><span>SEO/GEO增长</span>';
      const evolution = primary.querySelector('[data-target="r810-evolution"]');
      if (evolution) primary.insertBefore(button, evolution); else primary.appendChild(button);
      button.addEventListener('click', event => {
        event.preventDefault(); event.stopImmediatePropagation();
        window.KZR813SeoGeoBridge?.open?.();
      }, {capture:true});
    }

    const legacy = $('aside nav');
    if (!legacy) return;
    let seo = legacy.querySelector('button.nav[data-page="r813-seo-geo"]');
    if (!seo) {
      seo = document.createElement('button');
      seo.className = 'nav kz-r8234-seo-geo-nav';
      seo.dataset.page = 'r813-seo-geo';
      seo.dataset.title = 'SEO/GEO增长';
      seo.dataset.subtitle = '关键词、技术SEO、搜索收录、GEO正式Evidence';
      seo.innerHTML = '<span>搜</span>SEO/GEO增长';
      const content = legacy.querySelector('button.nav[data-page="promotion"]');
      if (content?.nextSibling) legacy.insertBefore(seo, content.nextSibling); else legacy.appendChild(seo);
      seo.addEventListener('click', event => {
        event.preventDefault(); event.stopImmediatePropagation();
        window.KZR813SeoGeoBridge?.open?.();
      }, {capture:true});
    }
    seo.hidden = false;
    seo.dataset.kzRouteRole = 'seo-geo';

    const groups = [
      $$('button.nav[data-page="r813-seo-geo"]'),
      $$('.r810-primary-nav .r810-nav-button[data-target="r813-seo-geo"]'),
    ];
    groups.forEach(group => group.slice(1).forEach(button => button.remove()));
  }

  function routeContract() {
    ensureContentRoute();
    ensureSeoGeoRoute();
    $$('button.nav[data-page="promotion"]').forEach(el => {
      if (/SEO\/GEO增长/.test(el.textContent || '')) {
        el.dataset.kzRouteRole = '';
        ensureContentRoute();
      }
    });
  }

  function ensureRuntimeBanner() {
    let banner = $('#kz-r8234-runtime-banner');
    if (banner) return banner;
    const main = $('main');
    if (!main) return null;
    banner = document.createElement('div');
    banner.id = 'kz-r8234-runtime-banner';
    banner.style.cssText = 'margin:10px 18px 0;padding:9px 13px;border:1px solid #dce5f3;border-radius:10px;background:#fff;color:#52647e;font-size:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap';
    const header = main.querySelector('header');
    if (header?.nextSibling) main.insertBefore(banner, header.nextSibling); else main.prepend(banner);
    return banner;
  }

  function showRuntimeState({ping, version, health, readiness, error}={}) {
    const banner = ensureRuntimeBanner();
    if (!banner) return;
    const state = readiness?.state || health?.readiness || (error ? 'DEGRADED' : 'CHECKING');
    const color = state === 'READY' ? '#14805c' : state === 'BLOCKED' ? '#b63434' : state === 'DEGRADED' ? '#a36812' : '#52647e';
    const blockers = (readiness?.blockers || health?.blockers || []).map(x => x?.label || x?.code || x).filter(Boolean);
    const html = `<b>R8-23.4 运行状态</b><span style="color:${color};font-weight:700">${esc(state)}</span>` +
      `<span>本地服务 ${ping?.alive ? '在线' : error ? '检查超时' : '检查中'}</span>` +
      `<span>版本 ${esc(version?.phase || '后台核验中')}</span>` +
      (blockers.length ? `<span style="color:#b63434">阻塞：${blockers.map(esc).join('；')}</span>` : '') +
      (error ? `<span style="color:#a36812">后台检查可重试，不阻断界面查看</span>` : '');
    if (banner.innerHTML !== html) banner.innerHTML = html;
  }

  function candidateStrip(snapshot) {
    if (!snapshot) return;
    lastCandidate = snapshot;
    const truth = snapshot.truth || {};
    const queue = snapshot.queue || {};
    const readiness = snapshot.readiness || {};
    const dashboard = $('#dashboard');
    if (!dashboard) return;
    let strip = $('#kz-r8234-truth-strip');
    if (!strip) {
      strip = document.createElement('section');
      strip.id = 'kz-r8234-truth-strip';
      strip.style.cssText = 'margin:10px 0 14px;padding:10px 14px;border:1px solid #dce5f3;border-radius:12px;background:#fff;font-size:12px';
      dashboard.prepend(strip);
    }
    const html = `<b>R8-23.4 · 单一运行真值</b>　<span>自治 ${esc(readiness.state || 'UNKNOWN')}</span>　` +
      `<span>Command ${esc(truth.active_command_id || '—')}</span>　` +
      (truth.pending_command_id ? `<span style="color:#a36812">待确认 ${esc(truth.pending_command_id)}</span>　` : '') +
      `<span>Mission ${esc(truth.mission_id || '—')}</span>　` +
      `<span>队列 ${Number(queue.waiting || 0)}等待 / ${Number(queue.running || 0)}运行 / ${Number(queue.timed_out || 0)}超时</span>`;
    if (strip.innerHTML !== html) strip.innerHTML = html;
    $('#kz-r8-23-2-pilot')?.setAttribute('hidden','hidden');
    $('#kz-r8-23-3-candidate-strip')?.setAttribute('hidden','hidden');
  }

  function reconcileDecisionStats() {
    if (!Array.isArray(window.r7Jobs) || !window.r7Jobs.length) return;
    const assigned = typeof window.r7TodayAssigned === 'function' ? window.r7Jobs.filter(window.r7TodayAssigned) : [];
    if (!assigned.length) return;
    const completed = assigned.filter(job => job?.state === 'completed');
    const queued = assigned.filter(job => ['queued','awaiting_approval','human_required'].includes(job?.state));
    const failed = assigned.filter(job => job?.state === 'failed');
    const rate = Math.round(completed.length * 100 / assigned.length);
    const map = {'decision-planned':assigned.length,'decision-completed':completed.length,'decision-queued':queued.length,'decision-failed':failed.length,'decision-rate':`${rate}%`};
    Object.entries(map).forEach(([id,value]) => { const el=document.getElementById(id); if (el && el.textContent !== String(value)) el.textContent=String(value); });
    const headline = $('#decision-headline');
    const copy = `8 个 AI 员工今日执行 ${assigned.length} 项，已完成 ${completed.length} 项，执行完成度 ${rate}%`;
    if (headline && headline.textContent !== copy) headline.textContent = copy;
  }

  function normalizeOwnerSemantics() {
    const social = $$('.page').find(page => /社媒中心/.test(page.querySelector('h1,h2')?.textContent || ''));
    if (social && /真实手机\s*0/.test(social.textContent || '') && !social.querySelector('[data-kz-social-unconfigured]')) {
      const note = document.createElement('div');
      note.dataset.kzSocialUnconfigured = '1';
      note.style.cssText = 'margin:10px 0;padding:10px 12px;border-radius:9px;background:#f6f8fc;color:#66758a;font-size:12px';
      note.textContent = '社媒真机/账号尚未接入：属于未启用，不计为失败；只有 Mission 明确要求社媒发布时才进入人工授权。官网 SEO/GEO 不受阻断。';
      social.querySelector('article,section,.wide')?.appendChild(note);
    }
  }

  function settleDiagnostics() {
    const button = $('#run-diagnostics');
    if (!button || button.dataset.kzR8234Bound === '1') return;
    button.dataset.kzR8234Bound = '1';
    button.addEventListener('click', () => {
      const started = Date.now();
      const timer = setInterval(() => {
        const busy = button.disabled || /体检中|检查中/.test(button.textContent || '');
        if (!busy) { clearInterval(timer); return; }
        if (Date.now() - started >= 8000) {
          clearInterval(timer);
          button.disabled = false;
          button.textContent = '重新体检';
          const summary = $('#diagnostic-summary');
          if (summary && /体检中|检查中|正在/.test(summary.textContent || '')) summary.textContent = '体检请求超过8秒，已结束等待；可重新体检。界面不会无限转圈。';
        }
      }, 300);
    }, {capture:true});
  }

  function clearStaleLoadingCopy() {
    if (!lastCandidate) return;
    $$('body *').forEach(node => {
      if (node.children.length) return;
      const text = (node.textContent || '').trim();
      if (text === '正在检查服务...' || text === '正在检查服务…') node.textContent = '本地服务已响应；详细连接状态按各卡片实测结果显示。';
    });
  }

  async function backgroundChecks() {
    const results = await Promise.allSettled([
      fetchJson('/api/ping', {timeout:2000}),
      fetchJson('/api/version', {timeout:2500}),
      fetchJson('/api/health', {timeout:4500}),
      fetchJson('/api/readiness', {timeout:4500}),
    ]);
    const value = i => results[i].status === 'fulfilled' ? results[i].value : null;
    const rejected = results.find(item => item.status === 'rejected');
    showRuntimeState({ping:value(0),version:value(1),health:value(2),readiness:value(3),error:rejected?.reason});
  }

  async function refreshCandidate() {
    try {
      const snapshot = await fetchJson('/api/r8-23-3/candidate');
      candidateStrip(snapshot);
      clearStaleLoadingCopy();
    } catch (error) {
      console.warn('R8-23.4 candidate snapshot deferred', error);
    }
  }

  function applyUiContract() {
    normalizeVersionCopy();
    routeContract();
    reconcileDecisionStats();
    normalizeOwnerSemantics();
    settleDiagnostics();
    clearStaleLoadingCopy();
  }

  function scheduleRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
      Promise.allSettled([refreshCandidate(), backgroundChecks()]).finally(applyUiContract);
    }, REFRESH_MS);
  }

  function start() {
    clearLegacyBuildQuery();
    document.documentElement.dataset.kzR8234Ui = 'ready';
    applyUiContract();
    Promise.allSettled([backgroundChecks(), refreshCandidate()]).finally(applyUiContract);
    // Late R8 modules are finite; re-apply only at bounded checkpoints instead of observing every DOM mutation.
    [250, 900, 1800, 3500, 6000].forEach(ms => setTimeout(applyUiContract, ms));
    scheduleRefresh();
    window.addEventListener('kz:app-ready', applyUiContract);
    window.addEventListener('r810:workbench-ready', applyUiContract);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();

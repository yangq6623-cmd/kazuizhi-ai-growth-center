(() => {
  'use strict';

  if (window.__KZ_R815_UI_TRUTH_PATCH__) return;
  window.__KZ_R815_UI_TRUTH_PATCH__ = true;

  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  function buildValue(value, fallback = '') {
    const text = String(value || '').trim();
    return !text || /^__.+__$/.test(text) ? fallback : text;
  }

  function releaseInfo() {
    const build = window.KZ_BUILD_INFO || {};
    return {
      phase: buildValue(build.phase, 'R8-15'),
      run: buildValue(build.runNumber),
      commit: buildValue(build.commit),
      version: buildValue(build.displayVersion, 'V2.2.2 Autonomous Mission Core'),
    };
  }

  async function api(path) {
    try {
      const response = await fetch(path, {cache:'no-store'});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      return payload.data || payload;
    } catch (error) {
      return {__error:true, message:String(error?.message || error)};
    }
  }

  function contentHumanItems(factory) {
    return (factory?.action_center?.human_items || []).map(item => ({
      source: 'mission',
      id: String(item.id || ''),
      title: item.title || '需要处理',
      detail: item.detail || '请打开对应执行环节查看。',
      action: item.action || '去处理',
      page: item.page || 'dashboard',
    }));
  }

  function seoHumanItems(seo) {
    return (seo?.human_items || []).map(item => ({
      source: 'seo',
      id: String(item.key || ''),
      title: item.title || 'SEO/GEO 需要授权或配置',
      detail: [item.reason, item.action ? `下一步：${item.action}` : ''].filter(Boolean).join(' '),
      action: '去 SEO/GEO 处理',
      page: 'r813-seo-geo',
    }));
  }

  function combinedAttention(factory, seo) {
    const items = [...contentHumanItems(factory), ...seoHumanItems(seo)];
    const seen = new Set();
    return items.filter(item => {
      const key = `${item.source}:${item.id || item.title}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function renderGlobalAttention(factory, seo) {
    const items = combinedAttention(factory, seo);
    const videos = factory?.videos || [];
    const review = videos.filter(item => item.status === '等待人工审核').length;
    const hard = videos.filter(item => item.status === '异常待处理' && Number(item.retry_count || 0) >= 3).length;
    const auth = items.filter(item => item.source === 'seo' || /账号|登录|授权|验证|公网|连接器/.test(`${item.id} ${item.title} ${item.detail}`)).length;

    const humanState = $('r810-human-state');
    if (humanState) {
      humanState.textContent = `待我处理：${items.length}`;
      humanState.className = `r810-state-pill ${items.length ? 'attention' : 'ok'}`;
      humanState.title = items.length ? '已汇总 Mission、账号验证、SEO/GEO 公网部署与搜索平台授权事项。' : '当前没有必须由老板处理的事项。';
    }
    const badge = $('r810-attention-badge');
    if (badge) {
      badge.textContent = String(items.length);
      badge.hidden = !items.length;
    }
    if ($('r810-human-total')) $('r810-human-total').textContent = String(items.length);
    if ($('r810-video-review')) $('r810-video-review').textContent = String(review);
    if ($('r810-login-human')) $('r810-login-human').textContent = String(auth);
    if ($('r810-hard-errors')) $('r810-hard-errors').textContent = String(hard);

    const loginCard = $('r810-login-human')?.closest('.r810-kpi');
    const loginLabel = loginCard?.querySelector('small');
    const loginNote = loginCard?.querySelector('span');
    if (loginLabel) loginLabel.textContent = '账号 / 授权 / 公网';
    if (loginNote) loginNote.textContent = '登录、站点验证、部署连接器';

    const list = $('r810-attention-list');
    const attentionPage = $('r810-attention');
    if (!list || !attentionPage?.classList.contains('active')) return;
    if (!items.length) {
      list.innerHTML = '<div class="r810-empty">当前没有必须由你处理的事项。系统可以继续自动执行已批准 Mission。</div>';
      return;
    }
    list.innerHTML = items.map((item, index) => `
      <div class="r810-attention-item">
        <div class="r810-attention-icon">${index + 1}</div>
        <div><b>${esc(item.title)}</b><span>${esc(item.detail)}</span></div>
        <button class="r810-action primary" data-r815-attention-page="${esc(item.page)}">${esc(item.action)}</button>
      </div>`).join('');
    list.querySelectorAll('[data-r815-attention-page]').forEach(button => button.addEventListener('click', () => {
      const page = button.dataset.r815AttentionPage;
      if (page === 'r813-seo-geo') {
        document.querySelector('.r810-nav-button[data-target="r813-seo-geo"]')?.click();
        return;
      }
      if (typeof window.openPage === 'function') window.openPage(page);
      else document.querySelector(`.r810-nav-button[data-target="${CSS.escape(page)}"]`)?.click();
    }));
  }

  function patchLegacyReleaseCopy() {
    const info = releaseInfo();
    const runLabel = info.run ? `#${info.run}` : '本地源码';
    document.title = `卡嘴子 AI 自治运营工作台 · ${info.phase}${info.run ? ` · #${info.run}` : ''}`;

    const baseline = document.querySelector('.baseline');
    if (baseline) {
      const title = baseline.querySelector('b');
      const subtitle = baseline.querySelector('span');
      const code = baseline.querySelector('code');
      if (title) title.textContent = `${info.phase} · ${runLabel}`;
      if (subtitle) subtitle.textContent = '自治运营 · 真实执行 · 真实回执';
      if (code) code.textContent = `${info.version}${info.commit ? ` · ${info.commit}` : ''}`;
    }

    const evolution = $('r810-evolution');
    evolution?.querySelectorAll('.r810-status-card').forEach(card => {
      const label = card.querySelector('small')?.textContent?.trim();
      const title = card.querySelector('b');
      const note = card.querySelector('span');
      if (label === '正式生产版本') {
        if (title) title.textContent = `当前安装构建 ${runLabel}`;
        if (note) note.textContent = '覆盖升级保留数据；回滚以真实安装备份为准，不再用旧构建号判断当前版本。';
      }
      if (label === '当前开发阶段') {
        if (title) title.textContent = `${info.phase} · ${runLabel}`;
        if (note) note.textContent = `当前可追溯标识：GitHub Run${info.commit ? ` · Commit ${info.commit}` : ''}`;
      }
    });
    const devButton = $('r810-dev-mission-disabled');
    if (devButton?.title?.includes('#398')) devButton.title = '自动创建 DEV-MISSION 的后端写入接口未开放时保持禁用；不得用旧构建号作为能力判断依据。';

    document.querySelectorAll('.r810-data-missing').forEach(node => {
      if (node.textContent.includes('#398 不用虚构分数')) {
        node.textContent = node.textContent.replace('#398 不用虚构分数', '当前版本不会用虚构分数');
      }
    });
  }

  function patchSeoFrameTruth() {
    const frame = $('r813-seo-geo-frame');
    let doc;
    try { doc = frame?.contentDocument; } catch { return; }
    if (!doc) return;
    doc.querySelectorAll('.health-item').forEach(item => {
      const name = item.querySelector('b')?.textContent?.trim() || '';
      const sub = item.querySelector('.sub');
      const badge = item.querySelector('.tag');
      if (!sub || !badge) return;
      const positive = /正常|已有|通过|200/.test(badge.textContent || '');
      if (['robots.txt','sitemap.xml','canonical / Schema'].includes(name)) {
        sub.textContent = positive ? '本地生成/配置证据已存在；不等于公网已发布' : '待本地生成或配置';
        badge.textContent = positive ? '本地已就绪' : '待配置';
        badge.className = `tag ${positive ? 'wait' : 'warn'}`;
      } else if (name === '公网技术审计') {
        sub.textContent = positive ? '已取得真实公网技术审计证据' : '待真实公网 URL 上线后验证';
        badge.textContent = positive ? '公网已审计' : '待公网验证';
        badge.className = `tag ${positive ? 'ok' : 'warn'}`;
      } else if (name === '移动端/速度') {
        sub.textContent = positive ? '真实公网首页已返回 HTTP 200，可继续测速' : '待真实公网 URL 后验证';
        badge.textContent = positive ? '公网可访问' : '待公网验证';
        badge.className = `tag ${positive ? 'ok' : 'warn'}`;
      } else if (name === '内链结构') {
        sub.textContent = '待页面真实公开后做可抓取内链验证';
        badge.textContent = '待公网验证';
        badge.className = 'tag warn';
      }
    });

    const humanCount = doc.getElementById('r814-human-count');
    const humanCard = humanCount?.closest('.r814-stat');
    const humanLabel = humanCard?.querySelector('span');
    if (humanLabel) humanLabel.textContent = 'SEO/GEO 待我处理';
  }

  async function refreshTruth() {
    const [factory, seo] = await Promise.all([
      api('/api/content-factory'),
      api('/api/r8-14/seo-geo/autonomy'),
    ]);
    patchLegacyReleaseCopy();
    patchSeoFrameTruth();
    if (!factory.__error || !seo.__error) renderGlobalAttention(factory.__error ? {} : factory, seo.__error ? {} : seo);
  }

  function scheduleRefresh(delay = 80) {
    clearTimeout(scheduleRefresh._timer);
    scheduleRefresh._timer = setTimeout(() => refreshTruth().catch(() => {}), delay);
  }

  document.addEventListener('click', event => {
    const target = event.target.closest?.('.r810-nav-button,[data-target],[data-to],button');
    if (target) scheduleRefresh(180);
  }, true);
  window.addEventListener('focus', () => scheduleRefresh(20));
  document.addEventListener('visibilitychange', () => { if (!document.hidden) scheduleRefresh(20); });
  document.addEventListener('r810:workbench-ready', () => scheduleRefresh(20));
  document.addEventListener('kz:app-ready', () => scheduleRefresh(20));
  const seoFrame = $('r813-seo-geo-frame');
  seoFrame?.addEventListener('load', () => scheduleRefresh(250));
  setInterval(() => refreshTruth().catch(() => {}), 15000);
  scheduleRefresh(0);
})();

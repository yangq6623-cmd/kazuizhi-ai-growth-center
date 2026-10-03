(() => {
  "use strict";

  const CANDIDATE = "R8-23.3 Candidate";
  const BOOT_MAX_WAIT_MS = 3000;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  let lastSnapshot = null;
  let scheduled = false;
  let bootReleased = false;

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[ch]);
  }

  async function json(url) {
    const response = await fetch(url, {cache: "no-store"});
    if (!response.ok) throw new Error(`${url} HTTP ${response.status}`);
    return response.json();
  }

  function buildInfo() {
    const info = window.KZ_BUILD_INFO || {};
    return {
      run: String(info.runNumber || "").replace(/^__.*__$/, ""),
      commit: String(info.commit || "").replace(/^__.*__$/, ""),
    };
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, "").replace(/[0-9]+$/g, "").trim();
  }

  function ensureSeoGeoNavigation() {
    const nav = $("aside nav");
    if (!nav) return;
    const canonical = $("button.nav[data-page='promotion']", nav);
    if (!canonical) return;
    canonical.dataset.title = "SEO/GEO增长";
    canonical.dataset.subtitle = "关键词、技术SEO、搜索收录、GEO问题池与正式Evidence";
    canonical.dataset.kzSeoGeoCanonical = "1";
    if (!/SEO\/GEO增长/.test(canonical.textContent || "")) {
      const icon = canonical.querySelector("span");
      canonical.innerHTML = `${icon ? icon.outerHTML : "<span>搜</span>"}SEO/GEO增长`;
    }
  }

  function dedupeNavigation() {
    ensureSeoGeoNavigation();
    const buttons = $$("aside nav button, aside .nav");
    const seen = new Map();
    for (const button of buttons) {
      const raw = normalizeText(button.textContent);
      let key = button.dataset && button.dataset.page ? `page:${button.dataset.page}` : `text:${raw}`;
      if ((button.dataset && button.dataset.page === "promotion") || /SEO\/GEO增长/i.test(raw)) key = "owner:seo-geo-growth";
      if (!seen.has(key)) {
        seen.set(key, button);
        continue;
      }
      const kept = seen.get(key);
      const buttonCanonical = button.dataset && button.dataset.kzSeoGeoCanonical === "1";
      const keptCanonical = kept.dataset && kept.dataset.kzSeoGeoCanonical === "1";
      if (buttonCanonical && !keptCanonical) {
        kept.remove();
        seen.set(key, button);
      } else if (button.classList.contains("active") && !kept.classList.contains("active") && !keptCanonical) {
        kept.remove();
        seen.set(key, button);
      } else {
        button.remove();
      }
    }
  }

  function normalizeVersionLabels() {
    const info = buildInfo();
    const run = info.run ? `#${esc(info.run)}` : "Candidate";
    const commit = info.commit ? esc(info.commit.slice(0, 8)) : "";
    const baseline = $(".baseline");
    if (baseline) {
      baseline.innerHTML = `<b>${CANDIDATE} · ${run}</b><br><span>自治执行 · 真实回执 · UI收口</span>${commit ? `<code>${commit}</code>` : ""}`;
    }
    document.title = `卡嘴子 AI 自治运营 · ${CANDIDATE}`;
    $$("body *").forEach((node) => {
      if (node.children.length) return;
      const text = node.textContent || "";
      if (/R8-23\s*·\s*#/.test(text)) node.textContent = text.replace(/R8-23\s*·\s*#/, "R8-23.3 Candidate · #");
      if (/R8-23\.2 Pilot\s*·\s*运行真值/.test(text)) node.textContent = text.replace("R8-23.2 Pilot · 运行真值", "R8-23.3 Candidate · 运行真值");
    });
  }

  const STATE_LABELS = {
    waiting_external_validation: "等待外部验证",
    ready_for_content_route: "已可生成内容，待真实回执",
    registered_manual_or_browser_route: "已登记，需人工/浏览器授权",
    ready_owned_route: "自有渠道可执行",
    configured: "已配置",
    routable: "可路由",
  };

  function translateConnectorStates(root = document) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      let text = node.nodeValue || "";
      let next = text;
      Object.entries(STATE_LABELS).forEach(([raw, label]) => {
        next = next.replace(new RegExp(`\\b${raw}\\b`, "g"), label);
      });
      if (next !== text) node.nodeValue = next;
    }
  }

  function unifiedAttention(snapshot) {
    const attention = snapshot && snapshot.attention || {};
    const count = Number(attention.owner_badge_count || 0);
    $$("aside .nav, aside nav button").forEach((el) => {
      if (!/待我处理/.test(el.textContent || "")) return;
      const badge = el.querySelector(".badge,.count,.nav-count") || Array.from(el.children).find((x) => /^\d+$/.test((x.textContent || "").trim()));
      if (badge) {
        badge.textContent = String(count);
        badge.hidden = count === 0;
      }
    });
    $$("body *").forEach((el) => {
      if (el.children.length) return;
      const text = el.textContent || "";
      if (/待我处理\s*[:：]\s*\d+/.test(text)) el.textContent = text.replace(/待我处理\s*[:：]\s*\d+/, `待我处理：${count}`);
    });
  }

  function ensureCandidateStrip(snapshot) {
    const dashboard = $("#dashboard") || $(".page.active");
    if (!dashboard || !snapshot) return;
    let strip = $("#kz-r8-23-3-candidate-strip");
    if (!strip) {
      strip = document.createElement("section");
      strip.id = "kz-r8-23-3-candidate-strip";
      strip.style.cssText = "margin:10px 0 14px;padding:10px 14px;border:1px solid #dce5f3;border-radius:12px;background:#fff;box-shadow:0 5px 18px rgba(25,50,90,.05);font-size:12px";
      dashboard.prepend(strip);
    }
    const readiness = snapshot.readiness || {};
    const truth = snapshot.truth || {};
    const queue = snapshot.queue || {};
    const lease = snapshot.control_lease || {};
    const state = readiness.state || "UNKNOWN";
    const tone = state === "READY" ? "#14805c" : state === "DEGRADED" ? "#a36812" : "#b63434";
    const blockers = (readiness.blockers || []).map((x) => x.label || x.code || x).filter(Boolean);
    strip.innerHTML = `
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <b>${CANDIDATE} · 运行真值</b>
        <span style="color:${tone};font-weight:700">自治准备度 ${esc(state)}</span>
        <span>当前Command ${esc(truth.active_command_id || "—")}</span>
        ${truth.pending_command_id ? `<span style="color:#a36812">待确认Command ${esc(truth.pending_command_id)}</span>` : ""}
        <span>Mission ${esc(truth.mission_id || "—")}</span>
        <span>当前队列 ${Number(queue.waiting || 0)}等待 / ${Number(queue.running || 0)}运行 / ${Number(queue.timed_out || 0)}超时</span>
        <span>控制租约 ${lease.valid ? `有效 · 剩余${Number(lease.remaining_minutes || 0)}分钟` : "无效"}</span>
      </div>
      ${blockers.length ? `<div style="margin-top:7px;color:#b63434">阻塞原因：${blockers.map(esc).join("；")}</div>` : `<div style="margin-top:7px;color:#62728d">核心控制链无阻塞；可选外部渠道不会阻断官网SEO/GEO。</div>`}
    `;
  }

  function foldLegacyLedger() {
    const dashboard = $("#dashboard");
    if (!dashboard) return;
    if ($("#kz-r8233-legacy-audit", dashboard)) return;
    const ledger = $$("article", dashboard).find((el) => /MISSION CONTROL LEDGER/i.test(el.textContent || ""));
    if (!ledger) return;
    const details = document.createElement("details");
    details.id = "kz-r8233-legacy-audit";
    details.style.cssText = "margin:10px 0;border:1px solid #e1e7f0;border-radius:10px;background:#fff;padding:8px 12px";
    const summary = document.createElement("summary");
    summary.textContent = "高级审计：Command / Mission / Receipt（历史账本）";
    summary.style.cssText = "cursor:pointer;font-weight:700;font-size:12px;color:#52647e";
    ledger.parentNode.insertBefore(details, ledger);
    details.appendChild(summary);
    details.appendChild(ledger);
  }

  function foldGeoAdvanced() {
    const page = $("#r8-13-seo-geo-page") || $("#promotion") || $$(".page").find((el) => /SEO\/GEO增长中心|GEO增长/.test((el.querySelector("h1,h2") || {}).textContent || ""));
    if (!page || $("#kz-r8233-geo-advanced", page)) return;
    const cards = $$("article,section", page).filter((el) => {
      if (el.closest("#kz-r8233-geo-advanced")) return false;
      const title = (el.querySelector("h2,h3,h4,label") || {}).textContent || "";
      return /Phase\s*[123]|FIXED.?50|Evidence\s*\/\s*Receipt|Provider|Route Matrix|路由矩阵|趋势|Governance|治理|Cloud Scan|浏览器验证|人工授权/i.test(title);
    });
    if (!cards.length) return;
    const details = document.createElement("details");
    details.id = "kz-r8233-geo-advanced";
    details.style.cssText = "margin:16px 0;border:1px solid #dfe7f2;border-radius:12px;background:#fff;padding:10px 14px";
    const summary = document.createElement("summary");
    summary.textContent = `高级 GEO 诊断（Phase / Evidence / Provider / Router · ${cards.length}项）`;
    summary.style.cssText = "cursor:pointer;font-weight:700;color:#52647e";
    const anchor = cards[0];
    anchor.parentNode.insertBefore(details, anchor);
    details.appendChild(summary);
    cards.forEach((card) => details.appendChild(card));
  }

  function labelTechnicalProgress() {
    $$("article,section,div").forEach((el) => {
      if (el.dataset && el.dataset.kzR8233Labeled) return;
      const text = el.textContent || "";
      if (/搜索增长/.test(text) && /\d+\s*\/\s*\d+/.test(text) && text.length < 500) {
        const heading = el.querySelector("h3,h4,strong,label");
        if (heading && !/技术进度/.test(heading.textContent || "")) heading.textContent += " · 技术进度";
        if (el.dataset) el.dataset.kzR8233Labeled = "1";
      }
    });
  }

  function cleanPilotStrip() {
    const old = $("#kz-r8-23-2-pilot");
    if (old) old.hidden = true;
  }

  function releaseBoot() {
    if (bootReleased) return;
    bootReleased = true;
    document.documentElement.classList.remove("kz-r8233-booting");
    document.documentElement.classList.add("kz-r8233-ready");
    const boot = $("#kz-r8233-boot");
    if (boot) boot.remove();
    document.querySelectorAll(".layout").forEach((el) => { el.style.visibility = ""; });
  }

  function showBootError(error) {
    const boot = $("#kz-r8233-boot");
    if (!boot) return;
    const status = $("[data-kz-boot-status]", boot);
    if (status) status.innerHTML = `启动检查未完成：${esc(error && error.message || error)}<br><button data-kz-retry style="margin-top:12px;padding:8px 14px;border:0;border-radius:8px;background:#2764e7;color:white;cursor:pointer">重新检查</button>`;
    const retry = $("[data-kz-retry]", boot);
    if (retry) retry.onclick = () => bootHandshake();
  }

  function applyConvergence(snapshot) {
    lastSnapshot = snapshot || lastSnapshot;
    ensureSeoGeoNavigation();
    dedupeNavigation();
    normalizeVersionLabels();
    translateConnectorStates(document);
    if (lastSnapshot) {
      unifiedAttention(lastSnapshot);
      ensureCandidateStrip(lastSnapshot);
    }
    foldLegacyLedger();
    foldGeoAdvanced();
    labelTechnicalProgress();
    cleanPilotStrip();
  }

  function scheduleConvergence() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(() => {
      scheduled = false;
      applyConvergence(lastSnapshot);
    }, 100);
  }

  async function refresh() {
    try {
      const snapshot = await json("/api/r8-23-3/candidate");
      applyConvergence(snapshot);
      return snapshot;
    } catch (error) {
      console.warn("R8-23.3 candidate refresh deferred", error);
      return null;
    }
  }

  async function backgroundRuntimeSync() {
    const results = await Promise.allSettled([
      json("/api/health"),
      json("/api/r8-23-3/candidate")
    ]);
    const health = results[0].status === "fulfilled" ? results[0].value : null;
    const snapshot = results[1].status === "fulfilled" ? results[1].value : null;
    if (health && !health.alive) console.warn("R8-23.3 runtime health is not alive", health);
    if (snapshot) applyConvergence(snapshot);
  }

  async function bootHandshake() {
    try {
      const versionPromise = json("/api/version");
      const timeoutPromise = new Promise((_, reject) => setTimeout(() => reject(new Error("版本握手超过3秒，请重新检查本地服务")), BOOT_MAX_WAIT_MS));
      const version = await Promise.race([versionPromise, timeoutPromise]);
      if (!String(version.phase || "").startsWith("R8-23.3")) throw new Error(`前后端版本未收口：${version.phase || "unknown"}`);
      applyConvergence(null);
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      releaseBoot();
      backgroundRuntimeSync();
    } catch (error) {
      showBootError(error);
    }
  }

  function start() {
    const observer = new MutationObserver(scheduleConvergence);
    observer.observe(document.documentElement, {childList: true, subtree: true});
    bootHandshake();
    setInterval(refresh, 15000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, {once: true});
  else start();
})();

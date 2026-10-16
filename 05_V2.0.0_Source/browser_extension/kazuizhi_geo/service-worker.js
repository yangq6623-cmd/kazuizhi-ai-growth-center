const API = "http://127.0.0.1:8876/api/r8-27/geo-browser-agent";
const ALARM = "kazuizhi-geo-cycle";
const PLATFORMS = {
  doubao_web: {url: "https://www.doubao.com/chat/", hosts: ["www.doubao.com"]},
  douyin_search_web: {url: "https://www.douyin.com/search/", hosts: ["www.douyin.com"], search: true},
  deepseek_web: {url: "https://chat.deepseek.com/", hosts: ["chat.deepseek.com"]},
  qwen_web: {url: "https://www.qianwen.com/", hosts: ["chat.qwen.ai", "tongyi.aliyun.com", "www.tongyi.com", "www.qianwen.com"]},
  so360_ai_search: {url: "https://n.cn/", hosts: ["n.cn", "so.com"]}
};
let running = false;
let runningSince = 0;
let currentStage = "空闲";
function stage(name) { currentStage = name; }

async function stored() {
  return chrome.storage.local.get(["agentId", "token", "sessions", "lastVerified", "lastRetryAt", "lastCycle", "lastError", "lastOutcome"]);
}

async function call(path, payload) {
  const response = await fetch(`${API}/${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Kazuizhi-Agent": "r8-28-extension"},
    body: JSON.stringify(payload || {}),
    signal: AbortSignal.timeout(15000)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
  return data.result || data;
}

async function readJson(url) {
  const response = await fetch(url, {headers: {"X-Kazuizhi-Agent": "r8-28-extension"}, signal: AbortSignal.timeout(15000)});
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
  return data.result || data;
}

async function ensureAlarm() {
  await chrome.alarms.create(ALARM, {periodInMinutes: 3});
}

function tabMatches(tab, hosts) {
  try { return hosts.some(host => new URL(tab.url || "").hostname.endsWith(host)); }
  catch (_) { return false; }
}

async function waitLoaded(tabId, timeoutMs = 45000) {
  // AI sites often keep network requests open after their UI is usable.
  // Accept a real interactive/complete DOM, not just tab.status=complete.
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const current = await chrome.tabs.get(tabId).catch(() => null);
    if (!current) throw new Error("tab_closed_during_load");
    if (current.status === "complete") return current;
    try {
      const inspected = await chrome.scripting.executeScript({
        target: {tabId},
        func: () => Boolean(document.body) && document.readyState !== "loading"
      });
      if (inspected?.[0]?.result === true) return current;
    } catch (_) {
      // A navigation can briefly make injection unavailable; keep waiting.
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  throw new Error("page_load_timeout");
}

async function platformTab(platform, question, activate = false, loadTimeoutMs = 45000) {
  const spec = PLATFORMS[platform];
  if (!spec) throw new Error(`unsupported_platform:${platform}`);
  const tabs = await chrome.tabs.query({});
  let matching = tabs.filter(item => tabMatches(item, spec.hosts));
  if (platform === "so360_ai_search") {
    // Prefer Nano's usable home/chat composer over stale blank conversation tabs.
    matching = matching.sort((a, b) => {
      const stale = item => {
        try { return /^\/(?:agentchat|aichat)\//.test(new URL(item.url || "").pathname) ? 1 : 0; }
        catch (_) { return 1; }
      };
      return stale(a) - stale(b) || Number(b.active) - Number(a.active) || Number(b.lastAccessed || 0) - Number(a.lastAccessed || 0);
    });
  } else {
    matching = matching.sort((a, b) => Number(b.active) - Number(a.active) || Number(b.lastAccessed || 0) - Number(a.lastAccessed || 0));
  }
  let tab = matching[0];
  let created = false;
  let url = spec.url;
  if (spec.search && question) url = `${spec.url}${encodeURIComponent(question)}?type=general`;
  if (platform === "deepseek_web" && question) { tab = await chrome.tabs.create({url: spec.url, active: activate}); created = true; }
  else if (!tab) { tab = await chrome.tabs.create({url, active: activate}); created = true; }
  else if (platform === "so360_ai_search" && (() => { try { return /^\/(?:agentchat|aichat)\//.test(new URL(tab.url || "").pathname); } catch (_) { return true; } })()) {
    tab = await chrome.tabs.update(tab.id, {url: spec.url, active: activate});
  }
  else if (activate) tab = await chrome.tabs.update(tab.id, {active: true});
  else if (spec.search && question) tab = await chrome.tabs.update(tab.id, {url, active: activate});
  else if (question && (platform === "qwen_web" || platform === "deepseek_web" || platform === "so360_ai_search")) {
    await chrome.tabs.reload(tab.id);
    await new Promise(resolve => setTimeout(resolve, 750));
  }
  await waitLoaded(tab.id, loadTimeoutMs);
  return {tab: await chrome.tabs.get(tab.id), created};
}

async function ask(tabId, message, timeoutMs = 150000) {
  const send = async () => {
    try {
      return await chrome.tabs.sendMessage(tabId, message);
    } catch (error) {
      const reason = String(error?.message || error);
      // Inject only when no content listener exists. Never reinject after
      // arbitrary execution, navigation or permission failures.
      if (!/Receiving end does not exist|Could not establish connection/i.test(reason)) throw error;
      await chrome.scripting.executeScript({target: {tabId}, files: ["content-agent.js"]});
      return await chrome.tabs.sendMessage(tabId, message);
    }
  };
  let timer;
  try {
    const reply = await Promise.race([
      send(),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("agent_response_timeout")), timeoutMs);
      })
    ]);
    if (!reply) throw new Error("empty_agent_response");
    return reply;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

async function executeDeepSeek(tabId, platform, question) {
  const started = await ask(tabId, {type: "kz-start", platform, question}, 30000);
  if (!started?.ok) return started;
  // DeepSeek web search / reasoning can legitimately take longer than the
  // generic 150-second message timeout. Poll the page for up to five minutes
  // while still requiring a complete, stable external answer.
  const deadline = Date.now() + 300000;
  while (Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, 1000));
    try {
      const result = await ask(tabId, {type: "kz-capture", platform, question}, 10000);
      if (result?.ok || result?.state === "captcha" || result?.state === "auth_required") return result;
    } catch (_) {
      // The page may be navigating between the start and capture phases.
    }
  }
  throw new Error("agent_response_timeout");
}

async function probe(platform, activate = false) {
  const opened = await platformTab(platform, "", activate, 12000);
  try {
    let result = null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      result = await ask(opened.tab.id, {type: "kz-probe", platform}, 8000);
      if (result?.state === "ready" || result?.state === "captcha" || result?.state === "auth_required") break;
      if (attempt < 1) await new Promise(resolve => setTimeout(resolve, 1000));
    }
    if (opened.created && result.state === "ready") await chrome.tabs.remove(opened.tab.id).catch(() => {});
    const normalized = result.state === "captcha" ? "captcha_required" : result.state === "auth_required" || result.state === "error" ? "authorization_required" : result.state;
    return {platform, state: normalized || "authorization_required", session_url: result.url || opened.tab.url, reason: normalized === "authorization_required" ? `page=${result.url || opened.tab.url}; marker=${Boolean(result.nano_marker)}; input=${Boolean(result.input_found)}` : "", verified_at: new Date().toISOString()};
  } catch (error) {
    if (opened.created) await chrome.tabs.remove(opened.tab.id).catch(() => {});
    return {platform, state: "authorization_required", reason: String(error.message || error), verified_at: new Date().toISOString()};
  }
}

async function verifyAll(activate = false) {
  const sessions = [];
  for (const platform of Object.keys(PLATFORMS)) {
    stage("检查登录：" + platform);
    sessions.push(await probe(platform, activate));
  }
  const stamped = new Date().toISOString();
  await chrome.storage.local.set({sessions, lastVerified: stamped, lastRetryAt: stamped});
  return sessions;
}

async function identity(sessions) {
  let state = await stored();
  if (state.agentId && state.token) return state;
  const seed = crypto.randomUUID();
  const registered = await call("register", {
    agent_id: `kz-r8-28-${seed}`,
    browser: "chrome",
    profile: "current-user",
    version: chrome.runtime.getManifest().version,
    owner_confirmed: true,
    sessions
  });
  const agentId = registered.status?.agent_id || `kz-r8-28-${seed}`;
  const token = registered.agent_token;
  if (!token) throw new Error("agent_registration_token_missing");
  await chrome.storage.local.set({agentId, token});
  return {...state, agentId, token};
}

async function executeTask(task, auth) {
  const platform = String(task.platform || "");
  const question = String(task.question_text || task.question || task.prompt || "").trim();
  if (!PLATFORMS[platform] || !question) throw new Error("task_contract_invalid");
  const opened = await platformTab(platform, question, false);
  try {
    const result = ["deepseek_web", "so360_ai_search"].includes(platform)
      ? await executeDeepSeek(opened.tab.id, platform, question)
      : await ask(opened.tab.id, {type: "kz-execute", platform, question}, 150000);
    if (result.state === "auth_required" || result.state === "captcha") {
      await chrome.tabs.update(opened.tab.id, {active: true}).catch(() => {});
      await call("block", {...auth, task_id: task.task_id, platform, kind: result.state === "captcha" ? "captcha" : "authorization", reason: result.state, session_url: result.url || opened.tab.url});
      return {blocked: true, reason: result.state};
    }
    if (!result.ok || !result.raw_answer || String(result.raw_answer).trim().length < 20) throw new Error(result.error || "real_answer_not_captured");
    const sessionUrl = String(result.url || opened.tab.url || "");
    if (!sessionUrl.startsWith("https://")) throw new Error("external_https_session_required");
    await call("receipt", {
      ...auth,
      task_id: task.task_id,
      platform,
      session_url: sessionUrl,
      raw_answer: String(result.raw_answer).trim(),
      citation_urls: Array.isArray(result.citation_urls) ? result.citation_urls : [],
      tested_at: new Date().toISOString(),
      evidence_source: "r8_28_chrome_extension"
    });
    if (opened.created) await chrome.tabs.remove(opened.tab.id).catch(() => {});
    return {completed: true};
  } catch (error) {
    await call("block", {...auth, task_id: task.task_id, platform, kind: "execution_error", reason: `capture_failed:${String(error.message || error)}`}).catch(() => {});
    if (opened.created) await chrome.tabs.remove(opened.tab.id).catch(() => {});
    throw error;
  }
}

async function recoverCurrentPlatform() {
  const state = await stored();
  if (!state.agentId || !state.token) throw new Error("agent_not_registered");
  const queue = await readJson("http://127.0.0.1:8876/api/r8-19/geo/queue");
  const supported = ["deepseek_web", "qwen_web"];
  const tabs = (await chrome.tabs.query({currentWindow: true}))
    .filter(tab => supported.some(platform => tabMatches(tab, PLATFORMS[platform].hosts)))
    .sort((a, b) => Number(b.active) - Number(a.active) || Number(b.lastAccessed || 0) - Number(a.lastAccessed || 0));
  const tab = tabs[0];
  if (!tab) throw new Error("open_supported_conversation_required");
  const platform = supported.find(name => tabMatches(tab, PLATFORMS[name].hosts));
  if (!platform) throw new Error("unsupported_current_platform");
  const candidates = (queue.tasks || []).filter(item => item.expected_platform === platform && item.question_text);
  const identified = await ask(tab.id, {type: "kz-identify-current-question", items: candidates.map(item => ({task_id: item.task_id, question_id: item.question_id, question_text: item.question_text}))}, 10000);
  if (!identified?.ok) throw new Error(identified?.error || "current_question_not_matched");
  const taskId = String(identified.task_id || "").trim();
  const task = candidates.find(item => item.task_id === taskId);
  if (!task) throw new Error("matched_geo_task_not_found");
  if (task.state === "succeeded" && task.evidence_id) {
    await chrome.storage.local.set({lastCycle: new Date().toISOString(), lastError: "", lastOutcome: {recovered: true, already_recovered: true, task_id: taskId}});
    return {ok: true, already_recovered: true, task_id: taskId, question_id: task.question_id, evidence_id: task.evidence_id};
  }
  const result = await ask(tab.id, {type: "kz-extract-current", platform, question: String(task.question_text || "")}, 30000);
  if (!result?.ok || !result.raw_answer) throw new Error(result?.error || result?.state || "current_answer_not_captured");
  const receipt = await call("receipt", {
    agent_id: state.agentId,
    agent_token: state.token,
    task_id: taskId,
    platform,
    session_url: String(result.url || tab.url || ""),
    raw_answer: String(result.raw_answer).trim(),
    citation_urls: Array.isArray(result.citation_urls) ? result.citation_urls : [],
    tested_at: new Date().toISOString(),
    evidence_source: "r8_28_chrome_extension_current_page_recovery"
  });
  await chrome.storage.local.set({lastCycle: new Date().toISOString(), lastError: "", lastOutcome: {recovered: true, task_id: taskId}});
  return {ok: true, task_id: taskId, question_id: task.question_id, receipt};
}

async function cycle(options = {}) {
  if (running) return {skipped: "cycle_already_running", stage: currentStage, elapsed_seconds: Math.round((Date.now() - runningSince) / 1000)};
  running = true;
  runningSince = Date.now();
  stage("准备本轮任务");
  try {
    let state = await stored();
    let sessions = Array.isArray(state.sessions) ? state.sessions : [];
    const lastVerified = Date.parse(state.lastVerified || 0) || 0;
    const lastRetryAt = Date.parse(state.lastRetryAt || 0) || 0;
    if (options.verify || sessions.length !== 5 || Date.now() - lastVerified > 6 * 60 * 60 * 1000) {
      sessions = await verifyAll(Boolean(options.activate));
    } else if (sessions.some(item => item.state !== "ready") && Date.now() - lastRetryAt > 10 * 60 * 1000) {
      stage("重检需要授权的平台");
      sessions = await Promise.all(sessions.map(async item => item.state === "ready" ? item : await probe(item.platform, false)));
      await chrome.storage.local.set({sessions, lastRetryAt: new Date().toISOString()});
    }
    stage("注册及同步浏览器心跳");
    state = await identity(sessions);
    const auth = {agent_id: state.agentId, agent_token: state.token};
    await call("heartbeat", {...auth, sessions, version: chrome.runtime.getManifest().version});
    let outcome = {idle: true};
    const ready = sessions.filter(item => item.state === "ready").map(item => item.platform);
    for (const platform of ready) {
      stage("检查队列：" + platform);
      const claimed = await call("claim", {...auth, platform});
      const claimedTask = claimed.claim?.task || claimed.task || claimed.claimed_task || (claimed.task_id ? claimed : null);
      if (claimedTask?.task_id) {
        const task = {...claimedTask, platform: claimed.contract?.platform || claimedTask.expected_platform, question_text: claimed.contract?.question_text || claimedTask.question_text};
        stage("采集正式回答：" + platform);
        outcome = await executeTask(task, auth); break;
      }
    }
    await chrome.storage.local.set({lastCycle: new Date().toISOString(), lastError: "", lastOutcome: outcome});
    return {sessions, outcome};
  } catch (error) {
    const message = String(error.message || error);
    await chrome.storage.local.set({lastCycle: new Date().toISOString(), lastError: message});
    throw error;
  } finally { running = false; runningSince = 0; stage("空闲"); }
}

chrome.runtime.onInstalled.addListener(() => { ensureAlarm().then(() => cycle({verify: true})).catch(() => {}); });
chrome.runtime.onStartup.addListener(() => { ensureAlarm().then(() => cycle({verify: true})).catch(() => {}); });
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === ALARM) cycle().catch(() => {}); });
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message && message.type === "kz-cycle") { cycle({verify: Boolean(message.verify), activate: Boolean(message.activate)}).then(sendResponse).catch(error => sendResponse({error: String(error.message || error)})); return true; }
  if (message && message.type === "kz-recover-current") { recoverCurrentPlatform().then(sendResponse).catch(error => sendResponse({error: String(error.message || error)})); return true; }
  if (message && message.type === "kz-status") {
    stored().then(state => sendResponse({...state, busy: running, stage: currentStage, elapsed_seconds: running ? Math.round((Date.now() - runningSince) / 1000) : 0})).catch(error => sendResponse({error: String(error.message || error)}));
    return true;
  }
  return false;
});
ensureAlarm().catch(() => {});

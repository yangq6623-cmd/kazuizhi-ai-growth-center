const API = "http://127.0.0.1:8876/api/r8-27/geo-browser-agent";
const ALARM = "kazuizhi-geo-cycle";
const PLATFORMS = {
  doubao_web: {url: "https://www.doubao.com/chat/", hosts: ["www.doubao.com"]},
  douyin_search_web: {url: "https://www.douyin.com/search/", hosts: ["www.douyin.com"], search: true},
  deepseek_web: {url: "https://chat.deepseek.com/", hosts: ["chat.deepseek.com"]},
  qwen_web: {url: "https://www.qianwen.com/", hosts: ["chat.qwen.ai", "tongyi.aliyun.com", "www.tongyi.com", "www.qianwen.com"]},
  so360_ai_search: {url: "https://www.n.cn/", hosts: ["www.n.cn", "so.com"]}
};
let running = false;

async function stored() {
  return chrome.storage.local.get(["agentId", "token", "sessions", "lastCycle", "lastError"]);
}

async function call(path, payload) {
  const response = await fetch(`${API}/${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Kazuizhi-Agent": "r8-28-extension"},
    body: JSON.stringify(payload || {})
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
  return data.result || data;
}

async function ensureAlarm() {
  await chrome.alarms.create(ALARM, {periodInMinutes: 0.5});
}

function tabMatches(tab, hosts) {
  try { return hosts.some(host => new URL(tab.url || "").hostname.endsWith(host)); }
  catch (_) { return false; }
}

async function waitLoaded(tabId, timeoutMs = 45000) {
  const current = await chrome.tabs.get(tabId).catch(() => null);
  if (current && current.status === "complete") return current;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); reject(new Error("page_load_timeout")); }, timeoutMs);
    function listener(id, info, tab) {
      if (id === tabId && info.status === "complete") {
        clearTimeout(timer); chrome.tabs.onUpdated.removeListener(listener); resolve(tab);
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

async function platformTab(platform, question, activate = false) {
  const spec = PLATFORMS[platform];
  if (!spec) throw new Error(`unsupported_platform:${platform}`);
  const tabs = await chrome.tabs.query({});
  let tab = tabs.find(item => tabMatches(item, spec.hosts));
  let created = false;
  let url = spec.url;
  if (spec.search && question) url = `${spec.url}${encodeURIComponent(question)}?type=general`;
  if (!tab) { tab = await chrome.tabs.create({url, active: activate}); created = true; }
  else if (spec.search && question) tab = await chrome.tabs.update(tab.id, {url, active: activate});
  await waitLoaded(tab.id);
  return {tab: await chrome.tabs.get(tab.id), created};
}

async function ask(tabId, message, timeoutMs = 150000) {
  let response = chrome.tabs.sendMessage(tabId, message).catch(async () => {
    await chrome.scripting.executeScript({target: {tabId}, files: ["content-agent.js"]});
    return chrome.tabs.sendMessage(tabId, message);
  });
  const reply = await Promise.race([
    response,
    new Promise((_, reject) => setTimeout(() => reject(new Error("agent_response_timeout")), timeoutMs))
  ]);
  if (!reply) throw new Error("empty_agent_response");
  return reply;
}

async function probe(platform, activate = false) {
  const opened = await platformTab(platform, "", activate);
  try {
    const result = await ask(opened.tab.id, {type: "kz-probe", platform}, 20000);
    if (opened.created && result.state === "ready") await chrome.tabs.remove(opened.tab.id).catch(() => {});
    const normalized = result.state === "captcha" ? "captcha_required" : result.state === "auth_required" || result.state === "error" ? "authorization_required" : result.state;
    return {platform, state: normalized || "authorization_required", session_url: result.url || opened.tab.url, verified_at: new Date().toISOString()};
  } catch (error) {
    if (opened.created) await chrome.tabs.remove(opened.tab.id).catch(() => {});
    return {platform, state: "authorization_required", reason: String(error.message || error), verified_at: new Date().toISOString()};
  }
}

async function verifyAll(activate = false) {
  const sessions = [];
  for (const platform of Object.keys(PLATFORMS)) sessions.push(await probe(platform, activate));
  await chrome.storage.local.set({sessions, lastVerified: new Date().toISOString()});
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
    const result = await ask(opened.tab.id, {type: "kz-execute", platform, question}, 150000);
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

async function cycle(options = {}) {
  if (running) return {skipped: "cycle_already_running"};
  running = true;
  try {
    let state = await stored();
    let sessions = Array.isArray(state.sessions) ? state.sessions : [];
    const lastVerified = Date.parse(state.lastVerified || 0) || 0;
    if (options.verify || sessions.length !== 5 || Date.now() - lastVerified > 6 * 60 * 60 * 1000) sessions = await verifyAll(Boolean(options.activate));
    state = await identity(sessions);
    const auth = {agent_id: state.agentId, agent_token: state.token};
    await call("heartbeat", {...auth, sessions, version: chrome.runtime.getManifest().version});
    let outcome = {idle: true};
    const ready = sessions.filter(item => item.state === "ready").map(item => item.platform);
    for (const platform of ready) {
      const claimed = await call("claim", {...auth, platform});
      const claimedTask = claimed.claim?.task || claimed.task || claimed.claimed_task || (claimed.task_id ? claimed : null);
      if (claimedTask?.task_id) {
        const task = {...claimedTask, platform: claimed.contract?.platform || claimedTask.expected_platform, question_text: claimed.contract?.question_text || claimedTask.question_text};
        outcome = await executeTask(task, auth); break;
      }
    }
    await chrome.storage.local.set({lastCycle: new Date().toISOString(), lastError: "", lastOutcome: outcome});
    return {sessions, outcome};
  } catch (error) {
    const message = String(error.message || error);
    await chrome.storage.local.set({lastCycle: new Date().toISOString(), lastError: message});
    throw error;
  } finally { running = false; }
}

chrome.runtime.onInstalled.addListener(() => { ensureAlarm().then(() => cycle({verify: true})).catch(() => {}); });
chrome.runtime.onStartup.addListener(() => { ensureAlarm().then(() => cycle({verify: true})).catch(() => {}); });
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === ALARM) cycle().catch(() => {}); });
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message && message.type === "kz-cycle") { cycle({verify: Boolean(message.verify), activate: Boolean(message.activate)}).then(sendResponse).catch(error => sendResponse({error: String(error.message || error)})); return true; }
  if (message && message.type === "kz-status") { stored().then(sendResponse); return true; }
  return false;
});
ensureAlarm().catch(() => {});

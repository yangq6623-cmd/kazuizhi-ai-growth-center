const names = {doubao_web:"豆包", douyin_search_web:"抖音", deepseek_web:"DeepSeek", qwen_web:"通义千问", so360_ai_search:"360 AI搜索"};
const summary = document.querySelector("#summary");
const sessionsNode = document.querySelector("#sessions");
let notice = "";

async function refresh() {
  try {
    const s = await chrome.runtime.sendMessage({type:"kz-status"});
    if (s && s.error) throw new Error(s.error);
    const line = s.busy
      ? "正在执行：" + (s.stage || "后台任务") + "（" + (s.elapsed_seconds || 0) + "秒）"
      : "最后运行：" + (s.lastCycle || "尚未执行");
    summary.textContent = notice || line + (s.lastHeartbeatAt ? " · 心跳：" + s.lastHeartbeatAt : "") + (s.lastHeartbeatError ? " · 心跳异常：" + s.lastHeartbeatError : "") + (s.lastError ? " · 上次错误：" + s.lastError : "");
    sessionsNode.replaceChildren();
    if (!(s.sessions || []).length) {
      const info = document.createElement("p");
      info.className = "muted";
      info.textContent = s.busy ? "登录状态正在核查" : "首次验证后显示登录状态";
      sessionsNode.appendChild(info);
    }
    for (const item of (s.sessions || [])) {
      const row = document.createElement("div"); row.className = "row";
      const left = document.createElement("span");
      left.textContent = names[item.platform] || item.platform;
      if (item.reason) {
        const detail = document.createElement("small");
        detail.textContent = item.reason;
        left.appendChild(detail);
      }
      const right = document.createElement("b");
      right.className = item.state === "ready" ? "ready" : "bad";
      right.textContent = item.state || "unknown";
      row.appendChild(left); row.appendChild(right); sessionsNode.appendChild(row);
    }
  } catch (error) {
    summary.textContent = "读取扩展状态失败：" + String(error.message || error);
  }
}
document.querySelector("#verify").onclick = async () => {
  notice = "正在处理平台登录验证请求…"; await refresh();
  try {
    const result = await chrome.runtime.sendMessage({type:"kz-cycle", verify:true, activate:true});
    if (result && result.skipped) notice = "后台已有任务：" + (result.stage || "正在执行") + "（" + (result.elapsed_seconds || 0) + "秒）";
    else if (result && result.error) notice = "验证失败：" + result.error;
    else notice = "验证完成，以下显示实际登录状态";
  } catch(error) { notice = "验证失败：" + String(error.message || error); }
  await refresh();
};
document.querySelector("#recover").onclick = async () => {
  notice = "正在回收当前 AI 完整回答…"; await refresh();
  try {
    const result = await Promise.race([
      chrome.runtime.sendMessage({type:"kz-recover-current"}),
      new Promise((_,reject) => setTimeout(() => reject(new Error("recovery_timeout_45s")), 45000))
    ]);
    if (result && result.error) notice = "回收失败：" + result.error;
    else notice = result && result.already_recovered ? "已正式回收：" + (result.question_id || "当前回答") : "回收成功：" + (result.question_id || "当前回答");
  } catch(error) { notice = "回收失败：" + String(error.message || error); }
  await refresh();
};
document.querySelector("#run").onclick = async () => {
  notice = "正在确认任务状态…"; await refresh();
  try {
    const result = await chrome.runtime.sendMessage({type:"kz-cycle"});
    notice = result && result.skipped ? "后台已有任务：" + (result.stage || "正在执行") + "（" + (result.elapsed_seconds || 0) + "秒）" : result && result.error ? "执行失败：" + result.error : "本轮任务处理完成";
  } catch(error) { notice = "执行失败：" + String(error.message || error); }
  await refresh();
};
refresh();
setInterval(() => { if (!notice || notice.startsWith("后台已有任务") || notice.startsWith("正在处理") || notice.startsWith("正在确认")) { notice = ""; refresh(); } }, 3000);

const SELECTORS = {
  doubao_web: {
    input: ["textarea", "[contenteditable='true']"],
    answer: ["[data-testid*='message']", "[class*='message']", "[class*='answer']"]
  },
  deepseek_web: {
    input: ["textarea", "[contenteditable='true']"],
    answer: [".ds-markdown", "[class*='markdown']", "[class*='message']"]
  },
  qwen_web: {
    input: ["textarea", "[contenteditable='true']"],
    answer: ["[class*='markdown']", "[class*='message']", "[class*='answer']"]
  },
  so360_ai_search: {
    input: ["textarea", "input[type='text']", "[contenteditable='true']"],
    answer: ["[class*='answer']", "[class*='markdown']", "[class*='result']"]
  },
  douyin_search_web: {
    input: ["input[type='search']", "input[type='text']"],
    answer: ["[data-e2e*='search']", "[class*='search-result']", "main"]
  }
};

function visible(element) {
  if (!element) return false;
  const style = getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
}

function firstVisible(selectors) {
  for (const selector of selectors || []) {
    const found = [...document.querySelectorAll(selector)].find(visible);
    if (found) return found;
  }
  return null;
}

function pageState(platform) {
  const body = String(document.body?.innerText || "").slice(0, 30000);
  if (/验证码|安全验证|完成验证|captcha|verify you are human/i.test(body)) return "captcha";
  if (/扫码登录|登录后使用|请先登录|手机号登录|账号登录/.test(body) && !firstVisible(SELECTORS[platform]?.input)) return "auth_required";
  if (platform === "douyin_search_web" && location.pathname.startsWith("/search")) return "ready";
  return firstVisible(SELECTORS[platform]?.input) ? "ready" : "auth_required";
}

function candidateTexts(platform, question) {
  const results = [];
  for (const selector of SELECTORS[platform]?.answer || []) {
    for (const element of document.querySelectorAll(selector)) {
      if (!visible(element)) continue;
      const text = String(element.innerText || element.textContent || "").replace(/\s+/g, " ").trim();
      if (text.length >= 20 && text !== question && !results.some(item => item.text === text)) results.push({element, text});
    }
  }
  return results;
}

function citationUrls(element) {
  return [...(element?.querySelectorAll("a[href]") || [])]
    .map(link => link.href).filter(url => /^https:\/\//.test(url) && !url.startsWith(location.origin))
    .filter((url, index, all) => all.indexOf(url) === index).slice(0, 20);
}

function fillInput(input, question) {
  input.focus();
  if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) {
    const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), "value");
    if (descriptor?.set) descriptor.set.call(input, question); else input.value = question;
    input.dispatchEvent(new Event("input", {bubbles: true}));
    input.dispatchEvent(new Event("change", {bubbles: true}));
  } else {
    input.textContent = question;
    input.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: question}));
  }
}

function submit(input) {
  const button = [...document.querySelectorAll("button")].find(item => visible(item) && /发送|提问|搜索|send|submit/i.test(`${item.innerText} ${item.getAttribute("aria-label") || ""}`));
  if (button && !button.disabled) button.click();
  else input.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", code: "Enter", bubbles: true}));
}

async function execute(platform, question) {
  let state = pageState(platform);
  if (state !== "ready") return {ok: false, state, url: location.href};
  if (platform !== "douyin_search_web") {
    const input = firstVisible(SELECTORS[platform]?.input);
    if (!input) return {ok: false, state: "auth_required", url: location.href};
    const before = new Set(candidateTexts(platform, question).map(item => item.text));
    fillInput(input, question); submit(input);
    let stable = "", stableRounds = 0;
    for (let index = 0; index < 120; index += 1) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      state = pageState(platform);
      if (state === "captcha" || state === "auth_required") return {ok: false, state, url: location.href};
      const candidates = candidateTexts(platform, question).filter(item => !before.has(item.text));
      const best = candidates.sort((a, b) => b.text.length - a.text.length)[0];
      if (!best) continue;
      stableRounds = best.text === stable ? stableRounds + 1 : 0; stable = best.text;
      if (stableRounds >= 2) return {ok: true, state: "ready", raw_answer: best.text, citation_urls: citationUrls(best.element), url: location.href};
    }
    return {ok: false, state: "error", error: "answer_capture_timeout", url: location.href};
  }
  await new Promise(resolve => setTimeout(resolve, 3500));
  const best = candidateTexts(platform, question).sort((a, b) => b.text.length - a.text.length)[0];
  if (!best) return {ok: false, state: "error", error: "search_result_not_captured", url: location.href};
  return {ok: true, state: "ready", raw_answer: best.text, citation_urls: citationUrls(best.element), url: location.href};
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "kz-probe") { sendResponse({state: pageState(message.platform), url: location.href}); return false; }
  if (message?.type === "kz-execute") { execute(message.platform, String(message.question || "")).then(sendResponse).catch(error => sendResponse({ok: false, state: "error", error: String(error.message || error), url: location.href})); return true; }
  return false;
});

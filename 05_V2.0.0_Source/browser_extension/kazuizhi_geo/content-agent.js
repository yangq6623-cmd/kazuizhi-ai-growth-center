(function kzGeoContentAgentBoot() {
  "use strict";
  // Manifest content_scripts and programmatic fallback share the isolated world.
  // A closure prevents global const redeclaration; the per-world guard prevents
  // registering the same onMessage listener twice in one document.
  let runtime;
  try {
    runtime = globalThis.chrome?.runtime;
    if (!runtime?.onMessage || typeof runtime.onMessage.addListener !== "function") return;
  } catch (_) {
    // A detached or invalidated extension context must never crash the page.
    return;
  }
  const marker = "__kazuizhi_geo_agent_registered_2_2_2_804";
  if (globalThis[marker]) return;
  globalThis[marker] = true;
  try {
  const SELECTORS = {
    doubao_web: {
      input: ["textarea", "[contenteditable='true'][role='textbox']", ".ProseMirror[contenteditable='true']", "[contenteditable='true']"],
      answer: ["[data-testid*='message']", "[data-testid*='answer']", "[class*='markdown']", "[class*='message']", "[class*='answer']", "article"]
    },
    deepseek_web: {
      input: ["textarea", "[contenteditable='true'][role='textbox']", ".ProseMirror[contenteditable='true']", "[contenteditable='true']"],
      answer: [".ds-markdown", "[class*='markdown']", "[class*='message']", "article"]
    },
    qwen_web: {
      input: ["textarea", "[contenteditable='true'][role='textbox']", ".ProseMirror[contenteditable='true']", "[contenteditable='true']"],
      answer: ["[data-message-id]", "[data-testid*='message']", "[data-role='assistant']", "[class*='bubble']", "[class*='response']", "[class*='markdown']", "[class*='message']", "[class*='answer']", "article"]
    },
    so360_ai_search: {
      input: ["textarea", "input[type='text']", "[contenteditable='true']", "[role='textbox']", ".ProseMirror[contenteditable]", "div[class*='editor'][contenteditable]"],
      answer: ["[class*='answer']", "[class*='markdown']", "[class*='result']", "[class*='message']", "[role='article']", "article"]
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
  
  function deepElements(selector, root = document) {
    const results = [];
    try { results.push(...root.querySelectorAll(selector)); } catch (_) {}
    const all = [];
    try { all.push(...root.querySelectorAll("*")); } catch (_) {}
    for (const element of all) {
      if (element.shadowRoot) results.push(...deepElements(selector, element.shadowRoot));
    }
    return results;
  }
  
  function nanoReadyMarker() {
    if (location.hostname !== "n.cn" && location.hostname !== "www.n.cn") return false;
    const body = String(document.body?.innerText || "");
    return /输入任何问题|新建任务|大模型聊天/.test(body) && !/扫码登录|请先登录/.test(body);
  }
  
  function nanoConversationPath() {
    return /^\/(?:agentchat|aichat)\//.test(location.pathname);
  }
  
  function nanoHintElement() {
    if (location.hostname !== "n.cn" && location.hostname !== "www.n.cn") return null;
    return [...document.querySelectorAll("body *")]
      .filter(element => visible(element) && /输入任何问题/.test(String(element.innerText || element.textContent || "").trim()))
      .sort((a, b) => a.getBoundingClientRect().width - b.getBoundingClientRect().width)[0] || null;
  }
  
  function bestInput(platform) {
    const candidates = [];
    for (const selector of SELECTORS[platform]?.input || []) {
      for (const element of deepElements(selector)) {
        if (element.disabled || element.getAttribute("aria-disabled") === "true") continue;
        const rect = element.getBoundingClientRect();
        const hint = `${element.getAttribute("placeholder") || ""} ${element.getAttribute("aria-label") || ""}`;
        if (!visible(element) && !(platform === "so360_ai_search" && /提问|输入|发送|搜索|ask|message|search/i.test(hint))) continue;
        const hintScore = /提问|输入|发送|搜索|ask|message|search/i.test(hint) ? 100000 : 0;
        candidates.push({element, score: hintScore + rect.bottom * 10 + Math.min(rect.width, 1200)});
      }
    }
    return candidates.sort((a, b) => b.score - a.score)[0]?.element || null;
  }
  
  async function resolveInput(platform) {
    let input = bestInput(platform);
    if (input || platform !== "so360_ai_search" || !nanoReadyMarker()) return input;
    const hint = nanoHintElement();
    if (hint) {
      hint.click();
      await new Promise(resolve => setTimeout(resolve, 500));
      input = bestInput(platform);
      if (!input && document.activeElement && document.activeElement !== document.body) input = document.activeElement;
    }
    return input;
  }
  
  function pageState(platform) {
    const body = String(document.body?.innerText || "").slice(0, 30000);
    if (/验证码|安全验证|完成验证|captcha|verify you are human/i.test(body)) return "captcha";
    if (/扫码登录|登录后使用|请先登录|手机号登录|账号登录/.test(body) && !firstVisible(SELECTORS[platform]?.input)) return "auth_required";
    if (platform === "douyin_search_web" && location.pathname.startsWith("/search")) return "ready";
    if (platform === "so360_ai_search" && nanoReadyMarker()) return "ready";
    return bestInput(platform) ? "ready" : "auth_required";
  }
  
  function candidateTexts(platform, question) {
    const results = [];
    const selectors = [...(SELECTORS[platform]?.answer || []), "[role='article']", "main p", "main li", "main [data-testid]"];
    for (const selector of selectors) {
      for (const element of deepElements(selector)) {
        if (!visible(element)) continue;
        const text = String(element.innerText || element.textContent || "").replace(/\s+/g, " ").trim();
        if (text.length < 20 || text.length > 30000 || text === question || text.includes(question) && text.length < question.length + 20) continue;
        if (!results.some(item => item.text === text)) results.push({element, text, selector});
      }
    }
    return results;
  }
  
  function bestAnswer(platform, candidates) {
    if (!candidates.length) return null;
    if (platform === "deepseek_web") {
      // DeepSeek continuously changes surrounding conversation containers while
      // streaming. Prefer the final markdown leaf; otherwise a large ancestor can
      // keep changing forever and the stability detector never completes.
      const markdown = candidates.filter(item =>
        item.element?.matches?.(".ds-markdown, [class*='ds-markdown'], [class*='markdown']")
      );
      if (markdown.length) return markdown[markdown.length - 1];
    }
    return [...candidates].sort((a, b) => b.text.length - a.text.length)[0];
  }
  
  function pageTextLines() {
    const lines = [];
    const seen = new Set();
    const roots = [document];
    for (let index = 0; index < roots.length; index += 1) {
      const root = roots[index];
      let elements = [];
      try { elements = [...root.querySelectorAll("*")]; } catch (_) {}
      for (const element of elements) {
        if (element.shadowRoot) roots.push(element.shadowRoot);
      }
      const body = root === document ? document.body : root.host;
      const text = String(body?.innerText || body?.textContent || "");
      for (const line of text.split(/\n+/)) {
        const normalized = line.replace(/\s+/g, " ").trim();
        if (normalized && !seen.has(normalized)) { seen.add(normalized); lines.push(normalized); }
      }
    }
    return lines;
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
      input.focus();
      document.execCommand("selectAll", false, null);
      if (!document.execCommand("insertText", false, question)) {
        input.textContent = "";
        input.append(document.createTextNode(question));
      }
      input.dispatchEvent(new InputEvent("beforeinput", {bubbles: true, inputType: "insertText", data: question}));
      input.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: question}));
    }
  }
  
  async function submit(input, platform = "") {
    const form = input.closest("form");
    const rect = input.getBoundingClientRect();
    if (platform === "so360_ai_search") {
      for (let attempt = 0; attempt < 40; attempt += 1) {
        const sendButton = [...document.querySelectorAll("button.send-btn")].find(visible);
        if (sendButton && !sendButton.disabled && sendButton.getAttribute("aria-disabled") !== "true") {
          sendButton.click();
          return true;
        }
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      return false;
    }
    // Doubao's composer can have adjacent microphone/tool buttons. Never
    // treat an arbitrary nearby button as a confirmed Send control.
    if (platform === "doubao_web") {
      const buttons = [...document.querySelectorAll("button")]
        .filter(item => visible(item) && !item.disabled && item.getAttribute("aria-disabled") !== "true");
      const named = buttons.find(item => /发送|发送消息|send|submit/i.test(
        [item.innerText, item.getAttribute("aria-label"), item.getAttribute("title"),
         item.getAttribute("data-testid")].filter(Boolean).join(" ")
      ));
      if (named) { named.click(); return true; }
      if (form?.requestSubmit) { form.requestSubmit(); return true; }
      // A synthetic Enter may be ignored by some clients, so the caller MUST
      // verify that the question was really posted before polling any answer.
      for (const type of ["keydown", "keypress", "keyup"])
        input.dispatchEvent(new KeyboardEvent(type, {key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true}));
      return true;
    }
    const nearby = [...document.querySelectorAll("button")]
      .filter(item => visible(item) && !item.disabled && item.getAttribute("aria-disabled") !== "true")
      .map(item => ({item, rect: item.getBoundingClientRect()}))
      .filter(value => value.rect.top < rect.bottom + 120 && value.rect.bottom > rect.top - 120 && value.rect.left > rect.left + rect.width * 0.45)
      .sort((a, b) => b.rect.right - a.rect.right || Math.abs(a.rect.top - rect.top) - Math.abs(b.rect.top - rect.top));
    if (platform === "deepseek_web" && nearby[0]) { nearby[0].item.click(); return true; }
    const labeled = [...document.querySelectorAll("button")].find(item => visible(item) && !item.disabled && /发送|提问|send|submit/i.test(`${item.innerText} ${item.getAttribute("aria-label") || ""} ${item.getAttribute("title") || ""}`));
    if (labeled) { labeled.click(); return true; }
    if (nearby[0]) { nearby[0].item.click(); return true; }
    if (form?.requestSubmit) { form.requestSubmit(); return true; }
    for (const type of ["keydown", "keypress", "keyup"]) input.dispatchEvent(new KeyboardEvent(type, {key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true}));
    return true;
  }
  
  function questionCount(text, question) {
    return question ? String(text || "").split(question).length - 1 : 0;
  }

  async function confirmPosted(input, question, beforeCount) {
    // Composer text is not a posted message. Require a NEW question echo in
    // the conversation and a cleared/replaced composer; never resend on timeout.
    for (let i = 0; i < 24; i += 1) {
      await new Promise(resolve => setTimeout(resolve, 500));
      const pageCount = questionCount(document.body?.innerText || "", question);
      const composerText = String(
        input?.value !== undefined ? input.value : input?.innerText || input?.textContent || ""
      ).trim();
      if (pageCount > beforeCount && (!input?.isConnected || composerText !== question)) return true;
    }
    return false;
  }

  const EXECUTION_KEY = "kz_geo_execution_v2";
  
  function saveExecution(value) {
    try { sessionStorage.setItem(EXECUTION_KEY, JSON.stringify(value)); } catch (_) {}
  }
  
  function loadExecution() {
    try { return JSON.parse(sessionStorage.getItem(EXECUTION_KEY) || "null"); } catch (_) { return null; }
  }
  
  async function startExecution(platform, question) {
    let state = pageState(platform);
    for (let attempt = 0; state !== "ready" && state !== "captcha" && attempt < 20; attempt += 1) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      state = pageState(platform);
    }
    if (state !== "ready") return {ok: false, state, url: location.href};
    const input = await resolveInput(platform);
    if (!input) return {ok: false, state: "auth_required", url: location.href};
    const oldQuestionCount = questionCount(document.body?.innerText || "", question);
    saveExecution({
      platform,
      question,
      before: candidateTexts(platform, question).map(item => item.text),
      beforeLines: pageTextLines(),
      stable: "",
      stableRounds: 0,
      submittedAt: Date.now()
    });
    fillInput(input, question);
    if (platform === "doubao_web") {
      const sent = await submit(input, platform);
      const confirmed = sent && await confirmPosted(input, question, oldQuestionCount);
      if (!confirmed) {
        try { sessionStorage.removeItem(EXECUTION_KEY); } catch (_) {}
        return {ok: false, state: "error", error: "question_not_submitted", url: location.href};
      }
      const execution = loadExecution() || {platform, question};
      execution.postConfirmed = true;
      saveExecution(execution);
      return {ok: true, state: "submitted", url: location.href};
    }
    if (platform === "so360_ai_search") {
      const submitted = await submit(input, platform);
      if (!submitted) return {ok: false, state: "error", error: "send_button_not_enabled", url: location.href};
      return {ok: true, state: "submitted", url: location.href};
    }
    // Return the message response before DeepSeek changes the conversation URL.
    setTimeout(() => submit(input, platform), 100);
    return {ok: true, state: "submitted", url: location.href};
  }
  
  function captureExecution(platform, question) {
    const storedExecution = loadExecution();
    const state = pageState(platform);
    if (state === "captcha") return {ok: false, state, url: location.href};
    if (state === "auth_required") {
      if (platform === "so360_ai_search" && storedExecution && nanoConversationPath()) {
        const age = Date.now() - Number(storedExecution.submittedAt || 0);
        if (!storedExecution.blankPageReloaded && age >= 3000) {
          storedExecution.blankPageReloaded = true;
          saveExecution(storedExecution);
          setTimeout(() => location.reload(), 50);
        }
        if (age >= 120000) return {ok: false, state, url: location.href};
        // Conversation result pages do not always retain the composer. Continue
        // below so the generated answer can still be captured while it renders.
      } else if (platform === "so360_ai_search" && storedExecution && Date.now() - Number(storedExecution.submittedAt || 0) < 30000) {
        return {ok: false, state: "pending", url: location.href};
      } else return {ok: false, state, url: location.href};
    }
    if (platform === "doubao_web" && (!storedExecution ||
        storedExecution.platform !== platform || storedExecution.question !== question ||
        storedExecution.postConfirmed !== true)) {
      return {ok: false, state: "error", error: "unconfirmed_question", url: location.href};
    }
    const execution = storedExecution && storedExecution.platform === platform && storedExecution.question === question
      ? storedExecution
      : {platform, question, before: [], beforeLines: [], stable: "", stableRounds: 0, submittedAt: Date.now()};
    const before = new Set(execution.before || []);
    const beforeLines = new Set(execution.beforeLines || []);
    const candidates = candidateTexts(platform, question).filter(item => !before.has(item.text));
    let best = bestAnswer(platform, candidates);
    if (!best && ["qwen_web", "deepseek_web", "so360_ai_search"].includes(platform)) {
      const delta = pageTextLines()
        .filter(line => line.length >= 15 && !beforeLines.has(line) && !(line.includes(question) && line.length < question.length + 60))
        .join("\n").trim();
      if (delta.length >= 40) best = {element: document.body, text: delta};
    }
    if (!best) return {ok: false, state: "pending", url: location.href};
    execution.stableRounds = best.text === execution.stable ? Number(execution.stableRounds || 0) + 1 : 0;
    execution.stable = best.text;
    saveExecution(execution);
    if (execution.stableRounds < 2) return {ok: false, state: "pending", url: location.href};
    try { sessionStorage.removeItem(EXECUTION_KEY); } catch (_) {}
    return {ok: true, state: "ready", raw_answer: best.text, citation_urls: citationUrls(best.element), url: location.href};
  }
  
  function extractCurrentAnswer(platform, question) {
    const state = pageState(platform);
    if (state === "captcha" || state === "auth_required") return {ok: false, state, url: location.href};
    const candidates = candidateTexts(platform, question);
    const best = bestAnswer(platform, candidates);
    if (!best || best.text.length < 20) return {ok: false, state: "error", error: "current_answer_not_found", url: location.href};
    return {ok: true, state: "ready", raw_answer: best.text, citation_urls: citationUrls(best.element), url: location.href};
  }
  
  function identifyCurrentQuestion(items) {
    const text = pageTextLines().join("\n").replace(/\s+/g, "");
    const matches = (Array.isArray(items) ? items : [])
      .map(item => ({...item, index: text.lastIndexOf(String(item.question_text || "").replace(/\s+/g, ""))}))
      .filter(item => item.index >= 0)
      .sort((a, b) => b.index - a.index);
    const match = matches[0];
    return match ? {ok: true, task_id: match.task_id, question_id: match.question_id, question_text: match.question_text} : {ok: false, error: "current_question_not_matched"};
  }
  
  async function execute(platform, question) {
    let state = pageState(platform);
    for (let attempt = 0; state !== "ready" && state !== "captcha" && attempt < 20; attempt += 1) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      state = pageState(platform);
    }
    if (state !== "ready") return {ok: false, state, url: location.href};
    if (platform !== "douyin_search_web") {
      const input = await resolveInput(platform);
      if (!input) return {ok: false, state: "auth_required", url: location.href};
      const before = new Set(candidateTexts(platform, question).map(item => item.text));
      const beforeLines = new Set(pageTextLines());
      fillInput(input, question);
      await new Promise(resolve => setTimeout(resolve, 700));
      await submit(input, platform);
      let stable = "", stableRounds = 0;
      for (let index = 0; index < 90; index += 1) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        state = pageState(platform);
        if (state === "captcha" || state === "auth_required") return {ok: false, state, url: location.href};
        const candidates = candidateTexts(platform, question).filter(item => !before.has(item.text));
        let best = bestAnswer(platform, candidates);
        if (!best && ["qwen_web", "deepseek_web", "so360_ai_search"].includes(platform)) {
          const delta = pageTextLines()
            .filter(line => line.length >= 40 && !beforeLines.has(line) && !(line.includes(question) && line.length < question.length + 60))
            .join("\n").trim();
          if (delta.length >= 80) best = {element: document.body, text: delta};
        }
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
  
  runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "kz-probe") { sendResponse({state: pageState(message.platform), url: location.href, nano_marker: nanoReadyMarker(), input_found: Boolean(bestInput(message.platform))}); return false; }
    if (message?.type === "kz-start") { startExecution(message.platform, String(message.question || "")).then(sendResponse).catch(error => sendResponse({ok: false, state: "error", error: String(error.message || error), url: location.href})); return true; }
    if (message?.type === "kz-capture") { sendResponse(captureExecution(message.platform, String(message.question || ""))); return false; }
    if (message?.type === "kz-extract-current") { sendResponse(extractCurrentAnswer(message.platform, String(message.question || ""))); return false; }
    if (message?.type === "kz-identify-current-question") { sendResponse(identifyCurrentQuestion(message.items)); return false; }
    if (message?.type === "kz-execute") { execute(message.platform, String(message.question || "")).then(sendResponse).catch(error => sendResponse({ok: false, state: "error", error: String(error.message || error), url: location.href})); return true; }
    return false;
  });
  
  } catch (error) {
    globalThis[marker] = false;
    console.warn("[Kazuizhi GEO] content agent registration failed:", String(error?.message || error));
  }
})();

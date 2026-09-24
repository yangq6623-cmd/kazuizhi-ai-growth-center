(() => {
  'use strict';

  const modelContext = document.modelContext || navigator.modelContext;
  const state = {
    available: Boolean(modelContext && typeof modelContext.registerTool === 'function'),
    registered: false,
    pairing: null,
    controller: null,
  };
  window.KazuizhiSiteTools = state;

  const uid = (prefix='KZ') => {
    if (globalThis.crypto?.randomUUID) return `${prefix}-${crypto.randomUUID()}`;
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  };

  async function request(path, options={}) {
    const isWrite = String(options.method || 'GET').toUpperCase() !== 'GET';
    const response = await fetch(path, {
      credentials: 'same-origin',
      cache: 'no-store',
      ...options,
      headers: {
        'Accept': 'application/json',
        ...(options.body ? {'Content-Type': 'application/json'} : {}),
        ...(isWrite ? {'X-KZ-Site-Tools': 'webmcp-local'} : {}),
        ...(options.headers || {}),
      },
    });
    let payload = {};
    try { payload = await response.json(); } catch (_) { payload = {}; }
    if (!response.ok) {
      const message = payload?.error || payload?.message || `HTTP ${response.status}`;
      throw new Error(message);
    }
    return payload;
  }

  async function localStatus() {
    return request('/api/kz-local-control/status');
  }

  async function ensurePairing() {
    if (state.pairing) return state.pairing;
    state.pairing = (async () => {
      const current = await localStatus();
      if (current?.verified) return current;
      const result = await request('/api/kz-local-control/pair', {
        method: 'POST',
        body: JSON.stringify({
          challenge_id: uid('WEBMCP-CHALLENGE'),
          invocation_id: uid('WEBMCP-INVOKE'),
          client: 'chatgpt-desktop-webmcp',
        }),
      });
      window.dispatchEvent(new CustomEvent('kz-local-control-changed', {detail: result}));
      return result?.status || result;
    })();
    try {
      return await state.pairing;
    } catch (error) {
      state.pairing = null;
      throw error;
    }
  }

  async function callLocal(tool, args={}) {
    await ensurePairing();
    const result = await request('/api/kz-local-control/tool', {
      method: 'POST',
      body: JSON.stringify({tool, args, request_id: uid('WEBMCP-REQUEST')}),
    });
    window.dispatchEvent(new CustomEvent('kz-local-control-changed', {detail: result}));
    return JSON.stringify(result, null, 2);
  }

  function tool(name, title, description, inputSchema, readOnly, execute) {
    return {
      name,
      title,
      description,
      inputSchema,
      annotations: {readOnlyHint: Boolean(readOnly), untrustedContentHint: false},
      execute,
    };
  }

  const emptySchema = {type:'object', properties:{}, additionalProperties:false};
  const tools = [
    tool(
      'kazuizhi_connect_local_control',
      '连接卡嘴子本机总控',
      '在当前电脑上把 ChatGPT Site Tools 与卡嘴子 AI 自治运营工作台建立本机直连。不会使用公网服务器，也不会开放 8876 到互联网。',
      emptySchema,
      false,
      async () => JSON.stringify(await ensurePairing(), null, 2),
    ),
    tool(
      'kazuizhi_get_system_status',
      '读取卡嘴子系统状态',
      '读取 ChatGPT 总控、本机执行、当前 Mission、主要阻塞项和世界状态。只读，不修改任何业务数据。',
      emptySchema,
      true,
      async () => callLocal('get_system_status'),
    ),
    tool(
      'kazuizhi_get_current_mission',
      '读取当前 Mission',
      '读取当前经营 Mission、老板目标、阶段、时间线和真实世界状态。',
      emptySchema,
      true,
      async () => callLocal('get_current_mission'),
    ),
    tool(
      'kazuizhi_create_mission',
      '创建经营 Mission',
      '根据老板经营目标创建一个非资金类 Mission，并生成可追溯 Command 和 Receipt。不会自动声称平台发布、SEO 收录、咨询或订单已经发生。',
      {
        type:'object',
        properties:{
          region:{type:'string', description:'运营区域，例如：涟水县'},
          service:{type:'string', description:'服务分类，例如：水电安装维修'},
          title:{type:'string', description:'Mission 标题'},
          evidence:{type:'string', description:'立项依据或老板明确要求'},
          goal:{type:'string', description:'可验证经营目标'},
          reason:{type:'string', description:'ChatGPT 的决策理由'},
          objective:{type:'string', description:'老板原始经营目标，可选'},
        },
        required:['region','service','title','evidence','goal'],
        additionalProperties:false,
      },
      false,
      async input => callLocal('create_mission', input),
    ),
    tool(
      'kazuizhi_set_primary_mission',
      '设置当前 P1 Mission',
      '把一个已存在的 Mission 切换为当前优先经营主线。只调整非资金运营优先级。',
      {
        type:'object',
        properties:{
          mission_id:{type:'string'},
          reason:{type:'string'},
        },
        required:['mission_id'],
        additionalProperties:false,
      },
      false,
      async input => callLocal('set_primary_mission', input),
    ),
    tool(
      'kazuizhi_get_ai_employee_status',
      '读取 AI 员工状态',
      '读取统一 ChatGPT 总脑下八类 AI 员工职责角色和真实注册状态，不虚构员工已经执行完成。',
      emptySchema,
      true,
      async () => callLocal('get_ai_employee_status'),
    ),
    tool(
      'kazuizhi_start_content_task',
      '启动或继续内容执行',
      '让一个 Mission 进入或继续内容生产链。不会绕过最终成片人工审核，也不会把生成视频等同于已经发布。',
      {
        type:'object',
        properties:{
          mission_id:{type:'string'},
          reason:{type:'string'},
        },
        required:['mission_id'],
        additionalProperties:false,
      },
      false,
      async input => callLocal('start_content_task', input),
    ),
    tool(
      'kazuizhi_read_receipts',
      '读取执行回执',
      '读取最近的 ChatGPT/KZ Command 执行 Receipt，用于核验 Mission 是否真实进入本地执行链。',
      {
        type:'object',
        properties:{limit:{type:'integer', minimum:1, maximum:100}},
        additionalProperties:false,
      },
      true,
      async input => callLocal('read_receipts', input || {}),
    ),
    tool(
      'kazuizhi_get_business_results',
      '读取真实经营结果',
      '读取当前 Mission 的可验证经营世界状态、内容/发布回执计数和待处理摘要。没有真实来源的数据不会被填成成功。',
      emptySchema,
      true,
      async () => callLocal('get_business_results'),
    ),
    tool(
      'kazuizhi_get_human_attention',
      '读取待我处理',
      '读取必须由老板本人处理的成片审核、登录验证、真实异常等事项。',
      emptySchema,
      true,
      async () => callLocal('get_human_attention'),
    ),
  ];

  async function register() {
    if (!state.available || state.registered) return;
    const controller = new AbortController();
    try {
      for (const item of tools) {
        await modelContext.registerTool(item, {signal: controller.signal});
      }
      state.controller = controller;
      state.registered = true;
      document.documentElement.dataset.kzSiteTools = 'available';
      window.dispatchEvent(new CustomEvent('kz-site-tools-ready', {detail:{count:tools.length}}));
    } catch (error) {
      controller.abort();
      state.registered = false;
      document.documentElement.dataset.kzSiteTools = 'error';
      console.warn('Kazuizhi Site Tools registration deferred:', error);
    }
  }

  if (state.available) {
    register();
  } else {
    document.documentElement.dataset.kzSiteTools = 'unavailable';
  }
})();

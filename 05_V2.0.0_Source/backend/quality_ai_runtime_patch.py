"""Quality-first runtime policy for long local AI work on RTX 3060 12 GB.

This layer prefers completion quality and stability over latency. Browser model
traffic stays on the 8876 same-origin bridge, while the GPT director is free to
choose a dynamic shot count and dynamic per-shot candidate budget.
"""
from __future__ import annotations

from backend import ai_gateway_patch as _ai

# One local text step may legitimately run for many minutes on a 12 GB card.
# A complete Mission can contain many serialized steps and may run for hours.
_ai._LOCAL_AI_TIMEOUT_SECONDS = 30 * 60

# Structured director/reference JSON can exceed the old 1200-token ceiling and
# get cut in the middle of an object. Quality-first mode therefore gives local
# structured work more output room. Calls are still serialized and the model is
# released after each step, so video generation can reclaim the 12 GB card.
_ai._LOCAL_AI_MAX_TOKENS = 2600

# The native director pipeline is another browser-side model caller. Serve it
# through the same rewrite path so it never calls :17777 directly.
_ai._LOCAL_AI_BROWSER_SCRIPTS["/content-pipeline-native.js"] = "content-pipeline-native.js"

_original_rewrite_browser_script = _ai._rewrite_browser_script


def _quality_rewrite_browser_script(source: str) -> str:
    rewritten = _original_rewrite_browser_script(source)

    # The browser must wait longer than the 30-minute backend request budget.
    rewritten = rewritten.replace(
        "},180000,400);\n      showAnalysis(analyzed);",
        "},1860000,400);\n      showAnalysis(analyzed);",
    )
    rewritten = rewritten.replace(
        "首次调用本地模型可能需要 1–2 分钟，请保持页面打开。",
        "本地 AI 正在按质量优先模式处理；单个文本步骤最长允许约 30 分钟，请保持页面打开。",
    )

    # AI director calls may also take a long time. Do not abort a healthy GPU
    # job after the old 35-second interactive timeout. Shot count remains fully
    # dynamic; the backend production contract validates only safety limits.
    rewritten = rewritten.replace(
        "const timeout = setTimeout(() => controller.abort(), 35000);",
        "const timeout = setTimeout(() => controller.abort(), 1860000);",
    )

    # Reference analysis needs valid machine-readable JSON. Give that request a
    # larger explicit output budget and lower temperature, then automatically
    # retry once with a compact schema if the model returns truncated JSON.
    rewritten = rewritten.replace(
        "temperature:.35})",
        "temperature:.2,max_tokens:2400})",
    )
    if "function analysisPrompt(item)" in rewritten and "parseReferenceJsonWithRetry" not in rewritten:
        rewritten = rewritten.replace(
            "  function analysisPrompt(item){",
            """  function parseReferenceJson(text=''){
    const cleaned=stripJsonFence(text);
    try{return JSON.parse(cleaned);}catch(firstError){
      const start=cleaned.indexOf('{'),end=cleaned.lastIndexOf('}');
      if(start>=0&&end>start)return JSON.parse(cleaned.slice(start,end+1));
      throw firstError;
    }
  }
  async function parseReferenceJsonWithRetry(raw,item){
    try{return parseReferenceJson(raw);}catch(firstError){
      const compactPrompt=analysisPrompt(item)+`\n\n重要：上一次结构化输出没有完整闭合。请重新输出一个更精简但字段完整的 JSON。不要解释，不要 Markdown。structure 保留 5 个阶段；style_dna、learnable、must_recreate、do_not_use 每项最多 3 条且每条尽量 24 字以内；kazuizhi_versions 保留 3 个版本，每个字段简洁。必须输出完整闭合的 JSON 对象。`;
      const retryRaw=await callRouter(compactPrompt);
      try{return parseReferenceJson(retryRaw);}catch(secondError){
        throw new Error('AI 返回的结构化分析不完整，系统已自动重试一次；已完成任务不会丢失，请稍后直接重试本步骤。');
      }
    }
  }
  function analysisPrompt(item){""",
        )
        rewritten = rewritten.replace(
            "const raw=await callRouter(analysisPrompt(item)),parsed=JSON.parse(stripJsonFence(raw));",
            "const raw=await callRouter(analysisPrompt(item)),parsed=await parseReferenceJsonWithRetry(raw,item);",
        )

    # Preserve the reference title/link when a director plan enters production
    # so the durable content task card can trace where an assisted creation came
    # from. No external content is fetched here; this is only existing metadata.
    rewritten = rewritten.replace(
        "reference_id:state.reference?.id||'',creative_id:creative?.id||''",
        "reference_id:state.reference?.id||'',source_title:state.reference?.title||'',source_url:state.reference?.source||'',creative_id:creative?.id||''",
    )

    # Load truthful production telemetry and the persisted content task card in
    # simple mode. Both modules poll real backend state and never fabricate work.
    if "window.__KZ_CONTENT_STUDIO_SIMPLE__" in rewritten and "data-kz-production-monitor-loader" not in rewritten:
        rewritten += """
\n;(() => {
  if (!document.querySelector('script[data-kz-production-monitor-loader]')) {
    const monitor = document.createElement('script');
    monitor.src = 'content-production-monitor.js';
    monitor.async = false;
    monitor.dataset.kzProductionMonitorLoader = '1';
    document.body.appendChild(monitor);
  }
  if (!document.querySelector('script[data-kz-mission-card-loader]')) {
    const mission = document.createElement('script');
    mission.src = 'content-mission-card.js';
    mission.async = false;
    mission.dataset.kzMissionCardLoader = '1';
    document.body.appendChild(mission);
  }
})();
"""
    return rewritten


_ai._rewrite_browser_script = _quality_rewrite_browser_script
_ai.server.DashboardHandler._kz_quality_first_local_ai = True

# Dynamic director policy augments only director requests. It leaves ordinary
# content analysis and rewrite calls unchanged.
from backend import dynamic_director_policy_patch as _dynamic_director_policy_patch  # noqa: E402,F401
# Truthful GPU/runtime telemetry, dynamic-shot candidate review controls and
# final-render queueing.
from backend import production_runtime_monitor_patch as _production_runtime_monitor_patch  # noqa: E402,F401
# Persistent content task card, per-candidate checkpoints, restart recovery and
# bounded automatic retry state used by the upcoming real video executor.
from backend import production_mission_patch as _production_mission_patch  # noqa: E402,F401

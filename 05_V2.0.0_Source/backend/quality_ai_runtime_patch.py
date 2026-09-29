"""Quality-first runtime policy for long local AI work on RTX 3060 12 GB.

This layer intentionally prefers completion quality and stability over latency.
It extends owner-facing local AI steps to long-running serialized work, keeps
browser model traffic on the 8876 same-origin bridge, and loads the truthful
production monitor used by simple mode.
"""
from __future__ import annotations

from backend import ai_gateway_patch as _ai

# One local text step may legitimately run for many minutes on a 12 GB card.
# The complete Mission can contain many serialized steps and may run for hours.
_ai._LOCAL_AI_TIMEOUT_SECONDS = 30 * 60

# The native director pipeline is another browser-side model caller. Serve it
# through the same rewrite path as simple/reference modules so it never calls
# :17777 directly and never trips browser CORS.
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

    # Native AI director: same-origin model bridge, quality-first wait, and a
    # five-shot production contract. The backend still validates/normalizes the
    # imported plan, so the UI never has to fake a five-shot result.
    rewritten = rewritten.replace(
        "const timeout = setTimeout(() => controller.abort(), 35000);",
        "const timeout = setTimeout(() => controller.abort(), 1860000);",
    )
    rewritten = rewritten.replace(
        "const shots = (Array.isArray(raw?.shots) ? raw.shots : []).slice(0,8).map",
        "const shots = (Array.isArray(raw?.shots) ? raw.shots : []).slice(0,5).map",
    )
    rewritten = rewritten.replace(
        "要求真实素材优先；缺口才用图生视频、文生视频或数字人；",
        "必须恰好输出5个镜头；每个镜头候选数量只能是2或3；要求真实素材优先；缺口才用图生视频、文生视频或数字人；",
    )

    # Load the simple-mode production monitor once. It polls real backend state
    # every few seconds and does not use MutationObserver or fake animation.
    if "window.__KZ_CONTENT_STUDIO_SIMPLE__" in rewritten and "data-kz-production-monitor-loader" not in rewritten:
        rewritten += """
\n;(() => {
  if (document.querySelector('script[data-kz-production-monitor-loader]')) return;
  const script = document.createElement('script');
  script.src = 'content-production-monitor.js';
  script.async = false;
  script.dataset.kzProductionMonitorLoader = '1';
  document.body.appendChild(script);
})();
"""
    return rewritten


_ai._rewrite_browser_script = _quality_rewrite_browser_script
_ai.server.DashboardHandler._kz_quality_first_local_ai = True

# Installs truthful GPU/runtime telemetry, exact five-shot import normalization,
# candidate selection/revision controls, and final-render queueing.
from backend import production_runtime_monitor_patch as _production_runtime_monitor_patch  # noqa: E402,F401

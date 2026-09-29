"""Quality-first runtime policy for long local AI work on RTX 3060 12 GB.

This layer intentionally prefers completion quality and stability over latency.
It extends the owner-facing local text step from a short interactive request to
a long-running step while keeping the existing serialized GPU policy and model
release behavior from ai_gateway_patch.
"""
from __future__ import annotations

from backend import ai_gateway_patch as _ai

# One local text step may legitimately run for many minutes on a 12 GB card,
# especially while the model is fully GPU-bound.  Keep a generous per-step
# budget; the complete Mission may contain many such serialized steps.
_ai._LOCAL_AI_TIMEOUT_SECONDS = 30 * 60

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
    return rewritten


_ai._rewrite_browser_script = _quality_rewrite_browser_script
_ai.server.DashboardHandler._kz_quality_first_local_ai = True

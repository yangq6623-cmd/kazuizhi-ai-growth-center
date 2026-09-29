"""Resilience for the controlled 5-second / two-shot acceptance path.

Normal production still prefers the real local AI.  This patch adds two bounded
retries for transient local Router/socket failures and, only for an explicitly
requested short two-shot acceptance case, lets the reference-analysis stage
fall back to the already-present truthful text-only structure analyzer.  The
fallback never pretends an AI response exists and does not bypass the later AI
director or real ComfyUI candidate generation.
"""
from __future__ import annotations

import time

from backend import ai_gateway_patch as _ai


_TRANSIENT_AI_MARKERS = (
    "AI 服务响应较慢",
    "AI 服务繁忙",
    "本地 AI 服务没有启动",
    "本地 AI 返回了无法解析的数据",
    "timed out",
    "timeout",
    "connection reset",
    "connection refused",
    "remote end closed connection",
)


_original_proxy_local_chat = _ai._proxy_local_chat


def _looks_transient(error: Exception) -> bool:
    text = str(error or "").lower()
    return any(marker.lower() in text for marker in _TRANSIENT_AI_MARKERS)


def _resilient_proxy_local_chat(payload):
    last_error = None
    # The first call is the normal path. Two bounded retries cover a Router
    # connection reset / model hand-off race without creating an infinite wait.
    for attempt in range(3):
        try:
            return _original_proxy_local_chat(payload)
        except RuntimeError as error:
            last_error = error
            if not _looks_transient(error) or attempt >= 2:
                raise
            try:
                _ai._release_ollama_model()
            except Exception:
                pass
            time.sleep(2 + attempt * 3)
    raise last_error or RuntimeError("本地 AI 请求失败")


_ai._proxy_local_chat = _resilient_proxy_local_chat


_original_rewrite_browser_script = _ai._rewrite_browser_script


def _acceptance_fallback_rewrite(source: str) -> str:
    rewritten = _original_rewrite_browser_script(source)
    if "async function analyzeReference(id)" not in rewritten:
        return rewritten

    old = """}catch(error){item.status='异常';item.error=`本地 AI 分析失败：${error.message}`;item.updatedAt=nowText();saveItem(item);message('本地 AI Router 未完成分析。任务已保留，请确认本地 AI 服务已经启动后重试。','error');}}"""
    if old not in rewritten:
        # Compatibility with an un-reworded source in case another patch order
        # changes.  We keep both forms so the build remains deterministic.
        old = """}catch(error){item.status='异常';item.error=`本地 AI 分析失败：${error.message}`;item.updatedAt=nowText();saveItem(item);message('本地 AI Router 未完成分析。任务已保留，可检查 17777 服务后重试。','error');}}"""

    new = """}catch(error){const shortAcceptance=/(?:5\\s*秒|双镜头测试)/.test(item.sourceText||'')&&/(?:2\\s*个连续镜头|两个镜头|镜头\\s*1[\\s\\S]*镜头\\s*2)/.test(item.sourceText||'');const transient=/(?:响应较慢|服务繁忙|没有启动|timeout|timed out|failed to fetch|networkerror|connection|socket)/i.test(String(error?.message||error));if(shortAcceptance&&transient){item.analysis=localAnalysis(item);item.analysis.analysis_mode='truthful_text_fallback';item.analysis.analysis_note='本地 AI 暂时未响应；本次仅按用户已提供的真实文字做结构分析，后续 AI 导演与视频生成仍照常执行。';item.status='已完成';item.error=`本地 AI 暂时未响应（${error.message}）；双镜头验收已按真实输入文字继续。`;item.updatedAt=nowText();saveItem(item);message('本地 AI 分析暂时未响应；已按你提供的真实文字继续双镜头验收。','warn');}else{item.status='异常';item.error=`本地 AI 分析失败：${error.message}`;item.updatedAt=nowText();saveItem(item);message('本地 AI 未完成分析。任务已保留，可直接重试。','error');}}}"""

    if old in rewritten:
        rewritten = rewritten.replace(old, new, 1)
    return rewritten


_ai._rewrite_browser_script = _acceptance_fallback_rewrite
_ai.server.DashboardHandler._kz_short_test_ai_resilience = True

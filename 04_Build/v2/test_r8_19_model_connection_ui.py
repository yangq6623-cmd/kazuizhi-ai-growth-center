"""Regression gate for the R8-19 unified model connection center.

This validates the owner-facing product contract without requiring a real cloud
credential or local model process during CI. Backend runtime behavior is covered
by the existing R8-18 model gateway tests.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    js = (SRC / "web" / "model-connection-center.js").read_text(encoding="utf-8")
    css = (SRC / "web" / "model-connection-center.css").read_text(encoding="utf-8")
    gateway = (SRC / "integrations" / "ai_gateway.py").read_text(encoding="utf-8")
    patch = (SRC / "backend" / "ai_gateway_patch.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "build_r8_19_geo_phase1.yml").read_text(encoding="utf-8")

    for marker in (
        "AI 大模型接口中心",
        "本地模型",
        "云端模型",
        "Ollama（本机）",
        "LM Studio（本机）",
        "vLLM（本机）",
        "自定义本机兼容服务",
        "/api/ai-gateway/status",
        "/api/ai-gateway/config",
        "/api/ai-gateway/test",
        "/api/ai-gateway/clear",
        "/api/local-ai/health",
        "本地模型可以参与内容分析、生成、分类和辅助计算",
        "不计入 GEO 正式 A/B 级外部证据",
        "window.kzOpenModelConnectionCenter",
    ):
        check(marker in js, f"unified model center contract missing: {marker}")

    check("api_key: local ? ''" in js, "local route unexpectedly asks the browser to submit an API key")
    check("route: activeEditor" in js and "set_active: true" in js, "route selection is not persisted as the active model route")
    check("fallback_enabled" in js, "verified fallback route control missing")
    check("kz-model-summary-card" in js, "connection-page summary card missing")
    check("ai-base-url" in js and "oldCard.hidden = true" in js, "legacy external-only model form is not superseded")

    for marker in (
        "font-variant-numeric:tabular-nums",
        ".is-success",
        ".is-waiting",
        ".is-danger",
        ".is-neutral",
        ".kz-primary",
    ):
        check(marker in css, f"model center B2B visual semantic missing: {marker}")

    for marker in (
        '"ollama"',
        '"lm_studio"',
        '"vllm"',
        '"custom"',
        '"requires_api_key": needs_key',
        'parsed.hostname in {"127.0.0.1", "localhost", "::1"}',
        '云端模型服务必须使用 HTTPS',
        'fallback_enabled',
    ):
        check(marker in gateway, f"backend model routing contract missing: {marker}")

    for marker in (
        '"/api/ai-gateway/status"',
        '"/api/ai-gateway/config"',
        '"/api/ai-gateway/test"',
        '"/api/ai-gateway/clear"',
        '"/api/local-ai/health"',
    ):
        check(marker in patch, f"backend model-center HTTP surface missing: {marker}")

    # The installer build must explicitly integrate the additive model-center
    # files into both owner-facing shells instead of relying on an unreferenced file.
    check("Integrate unified model connection center into packaged web" in workflow, "installer does not integrate unified model center")
    check("model-connection-center.js" in workflow and "model-connection-center.css" in workflow, "installer is missing model-center assets")
    check("test_r8_19_model_connection_ui.py" in workflow, "installer does not run this regression gate")

    print("PASS: unified local/cloud model center is truth-gated, GEO-safe and packaged into the owner platform")


if __name__ == "__main__":
    main()

"""R8-12/R8-13 official authorization capability registry.

Reports configuration truth only. Provider endpoints come from the official
platform catalog. No plaintext password is ever accepted by Kazuizhi.
"""
from __future__ import annotations

from integrations.platform_auth_catalog import catalog


def provider_status(platform: str) -> dict:
    rows = catalog().get("providers", [])
    provider = next((x for x in rows if x.get("platform") == platform), None)
    if not provider:
        return {
            "platform": platform,
            "configured": False,
            "owner_status": "平台限制",
            "reason": "当前版本尚未登记该平台官方授权适配器",
        }
    result = dict(provider)
    mode = str(result.get("auth_mode") or "")
    result["owner_status"] = "可授权" if result.get("configured") else (
        "官方入口可用" if mode.startswith("official_portal") else "未配置官方应用"
    )
    result["supports_qr_authorization"] = platform in {"douyin", "kuaishou", "wechat_channels"}
    result["publish_scope_requires_platform_approval"] = platform in {"douyin", "kuaishou", "xiaohongshu", "wechat_channels"}
    result["truth"] = (
        "未申请或未配置官方应用凭据时，只显示未配置；不会伪造扫码登录或发布权限。"
        "官方登录由平台页面完成；未完成回调/token/身份验证前不会标记账号为已连接。"
    )
    return result


def all_provider_status() -> dict:
    data = catalog()
    rows = data.get("providers", [])
    return {
        "providers": [provider_status(str(x.get("platform") or "")) for x in rows],
        "configured": sum(1 for x in rows if x.get("configured")),
        "environment_policy": data.get("environment_policy") or {},
        "truth": "授权与账号资产分离；一个平台可有多个账号资产。OAuth/官方入口只负责授权，真实操作能力以平台实际批准 scope 和真实回执为准。",
    }

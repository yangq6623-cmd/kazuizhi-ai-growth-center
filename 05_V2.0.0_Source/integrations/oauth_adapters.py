"""R8-12 OAuth capability registry.

This module reports configuration truth only. It never fabricates platform API
access. A provider becomes configurable only when the operator supplies the
required official app credentials outside GitHub/source control.
"""
from __future__ import annotations

import os

PROVIDERS = {
    "douyin": {
        "name": "抖音",
        "client_id_env": "KZ_DOUYIN_CLIENT_KEY",
        "client_secret_env": "KZ_DOUYIN_CLIENT_SECRET",
        "supports_qr_authorization": True,
        "publish_scope_requires_platform_approval": True,
    },
    "kuaishou": {
        "name": "快手",
        "client_id_env": "KZ_KUAISHOU_CLIENT_ID",
        "client_secret_env": "KZ_KUAISHOU_CLIENT_SECRET",
        "supports_qr_authorization": True,
        "publish_scope_requires_platform_approval": True,
    },
    "xiaohongshu": {
        "name": "小红书",
        "client_id_env": "KZ_XHS_CLIENT_ID",
        "client_secret_env": "KZ_XHS_CLIENT_SECRET",
        "supports_qr_authorization": False,
        "publish_scope_requires_platform_approval": True,
    },
    "wechat_channels": {
        "name": "视频号",
        "client_id_env": "KZ_WECHAT_CHANNELS_CLIENT_ID",
        "client_secret_env": "KZ_WECHAT_CHANNELS_CLIENT_SECRET",
        "supports_qr_authorization": False,
        "publish_scope_requires_platform_approval": True,
    },
}


def provider_status(platform: str) -> dict:
    provider = PROVIDERS.get(platform)
    if not provider:
        return {
            "platform": platform,
            "configured": False,
            "owner_status": "平台限制",
            "reason": "当前版本尚未登记该平台官方 OAuth 适配器",
        }
    client_id = bool(os.environ.get(provider["client_id_env"]))
    client_secret = bool(os.environ.get(provider["client_secret_env"]))
    configured = client_id and client_secret
    return {
        "platform": platform,
        "name": provider["name"],
        "configured": configured,
        "owner_status": "可授权" if configured else "未配置官方授权",
        "supports_qr_authorization": bool(provider["supports_qr_authorization"]),
        "publish_scope_requires_platform_approval": bool(provider["publish_scope_requires_platform_approval"]),
        "missing": [
            env for env in (provider["client_id_env"], provider["client_secret_env"])
            if not os.environ.get(env)
        ],
        "truth": "未申请或未配置官方应用凭据时，只显示未配置；不会伪造扫码登录或发布权限。",
    }


def all_provider_status() -> dict:
    rows = [provider_status(key) for key in PROVIDERS]
    return {
        "providers": rows,
        "configured": sum(1 for x in rows if x.get("configured")),
        "truth": "OAuth 仅负责身份授权；真实发布权限以各平台实际批准的 scope 为准。",
    }

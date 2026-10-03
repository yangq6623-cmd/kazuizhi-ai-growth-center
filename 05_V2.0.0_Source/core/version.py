"""Canonical product/runtime identity for Kazuizhi R8-23.2 Pilot RC1.

Compatibility protocol constants remain unchanged for the inherited R7/R8
shell, while every owner-facing/API runtime identity is sourced from the single
packaged release_manifest.json.  This prevents old module labels from becoming
competing current-version truth.
"""

import json
from copy import deepcopy
from pathlib import Path

# Compatibility protocol fields consumed by the preserved R7/R8 shell.
VERSION = "2.2.0"
BUILD_STAGE = "Operational"
RELEASE = "R8"
BUILD_ID = "KZ-ENTERPRISE-V2.2-R8-OPERATIONAL-20260920"

# Canonical owner-facing identity.
PRODUCT_VERSION = "2.2.2"
PRODUCT_NAME = "Kazuizhi AI Enterprise V2.2.2 R8-23.2 Pilot RC1"
R8_DISPLAY_VERSION = "R8-23.2 · Pilot RC1"
R8_RELEASE = "R8-23.2 Runtime Truth & Closed-Loop Acceptance"
R8_PHASE = "R8-23.2"
R8_RUNTIME_BUILD = "KZ-ENTERPRISE-V2.2.2-R8-23.2-PILOT-RC1"
R8_PRODUCT_NAME = PRODUCT_NAME


def release_manifest():
    path = Path(__file__).with_name("release_manifest.json")
    fallback = {
        "schema": "kz.release-manifest.v2",
        "product": "Kazuizhi AI Enterprise",
        "product_version": PRODUCT_VERSION,
        "release": R8_DISPLAY_VERSION,
        "phase": R8_PHASE,
        "runtime_build": R8_RUNTIME_BUILD,
        "truth_rule": "发布身份不可用；禁止根据模块标题猜测当前版本。",
    }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return deepcopy(value) if isinstance(value, dict) else fallback
    except (OSError, ValueError, json.JSONDecodeError):
        return fallback


def get_version():
    manifest = release_manifest()
    runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), dict) else {}
    product_version = runtime.get("product_version") or manifest.get("product_version") or PRODUCT_VERSION
    display = runtime.get("release") or manifest.get("release") or R8_DISPLAY_VERSION
    phase = runtime.get("phase") or manifest.get("phase") or R8_PHASE
    runtime_build = runtime.get("runtime_build") or manifest.get("runtime_build") or R8_RUNTIME_BUILD
    return {
        # Legacy compatibility handshake remains explicit and non-owner-facing.
        "compatibility_version": VERSION,
        "compatibility_stage": BUILD_STAGE,
        "compatibility_release": RELEASE,
        "compatibility_build": BUILD_ID,
        # Canonical runtime identity used by all current UI/API surfaces.
        "version": product_version,
        "stage": phase,
        "release": display,
        "build": runtime_build,
        "product_version": product_version,
        "product": PRODUCT_NAME,
        "source": "core/release_manifest.json",
        "display_version": display,
        "runtime_build": runtime_build,
        "r8_release": display,
        "r8_phase": phase,
        "r8_product": PRODUCT_NAME,
        "build_number": runtime.get("build_number") or manifest.get("build_number"),
        "commit": runtime.get("commit") or manifest.get("commit"),
        "release_manifest": manifest,
    }

"""Canonical V2.2.2 autonomous Mission runtime identity."""

VERSION = "2.2.2"
BUILD_STAGE = "Autonomous Mission Core"
RELEASE = "R8"
BUILD_ID = "KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922"
PRODUCT_NAME = "Kazuizhi AI Enterprise V2.2.2 R8 Autonomous Mission Core"

# Compatibility fields retained for older R8 UI modules, saved data and diagnostics.
R8_DISPLAY_VERSION = "V2.2.2 自治运营核心"
R8_RELEASE = "R8 Autonomous Mission Core"
R8_PHASE = "R8-09"
R8_RUNTIME_BUILD = BUILD_ID
R8_PRODUCT_NAME = PRODUCT_NAME


def get_version():
    return {
        "version": VERSION,
        "stage": BUILD_STAGE,
        "release": RELEASE,
        "build": BUILD_ID,
        "product": PRODUCT_NAME,
        "source": "05_V2.0.0_Source/web/index.html",
        "display_version": R8_DISPLAY_VERSION,
        "runtime_build": R8_RUNTIME_BUILD,
        "r8_release": R8_RELEASE,
        "r8_phase": R8_PHASE,
        "r8_product": R8_PRODUCT_NAME,
    }

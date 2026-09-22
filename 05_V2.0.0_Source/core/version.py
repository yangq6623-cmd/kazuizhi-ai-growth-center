"""Canonical V2.2.2 autonomous Mission product identity.

The inherited R7/R8 static shell and E2E protocol keep the original V2.2.0
Operational handshake during overwrite upgrades. User-visible/package identity,
R8 phase and runtime build are V2.2.2 Autonomous Mission Core.
"""

# Compatibility protocol fields consumed by the preserved R7/R8 shell.
VERSION = "2.2.0"
BUILD_STAGE = "Operational"
RELEASE = "R8"
BUILD_ID = "KZ-ENTERPRISE-V2.2-R8-OPERATIONAL-20260920"

# Canonical product/runtime identity.
PRODUCT_VERSION = "2.2.2"
PRODUCT_NAME = "Kazuizhi AI Enterprise V2.2.2 R8 Autonomous Mission Core"
R8_DISPLAY_VERSION = "V2.2.2 自治运营核心"
R8_RELEASE = "R8 Autonomous Mission Core"
R8_PHASE = "R8-09"
R8_RUNTIME_BUILD = "KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922"
R8_PRODUCT_NAME = PRODUCT_NAME


def get_version():
    return {
        "version": VERSION,
        "stage": BUILD_STAGE,
        "release": RELEASE,
        "build": BUILD_ID,
        "product_version": PRODUCT_VERSION,
        "product": PRODUCT_NAME,
        "source": "05_V2.0.0_Source/web/index.html",
        "display_version": R8_DISPLAY_VERSION,
        "runtime_build": R8_RUNTIME_BUILD,
        "r8_release": R8_RELEASE,
        "r8_phase": R8_PHASE,
        "r8_product": R8_PRODUCT_NAME,
    }

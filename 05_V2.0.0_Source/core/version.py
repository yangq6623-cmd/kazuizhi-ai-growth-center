"""Canonical V2.2 R8 Operational runtime identity."""

VERSION = "2.2.0"
BUILD_STAGE = "Operational"
RELEASE = "R8"
BUILD_ID = "KZ-ENTERPRISE-V2.2-R8-OPERATIONAL-20260920"
PRODUCT_NAME = "Kazuizhi AI Enterprise V2.2.0 R8 Operational"

# Compatibility fields retained for the R8 UI modules, saved data and diagnostics
# introduced by the #238 build. They now point at the single V2.2 identity.
R8_DISPLAY_VERSION = "V2.2.0 R8 Operational"
R8_RELEASE = "R8 Operational"
R8_PHASE = "R8-08"
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

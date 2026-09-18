"""Canonical V2 runtime identity with an additive R8 Preview layer."""

# R7 compatibility identity stays stable so the proven R7 core, static assets and
# existing user-data migrations keep working while R8 is developed on top.
VERSION = "2.0.0"
BUILD_STAGE = "Beta"
RELEASE = "R7 Final"
BUILD_ID = "KZ-ENTERPRISE-V2-BETA-20260917-R7-FINAL"
PRODUCT_NAME = "Kazuizhi AI Enterprise V2.0.0 Beta R7 Final"

# R8 package/display identity.  This is what the owner should see in R8 Preview
# installers and the dashboard while R8-00 through R8-08 are implemented.
R8_DISPLAY_VERSION = "V2.1.0 Beta R8 Preview"
R8_RELEASE = "R8 Preview"
R8_PHASE = "R8-00"
R8_RUNTIME_BUILD = "KZ-ENTERPRISE-V2.1-BETA-20260918-R8-PREVIEW"
R8_PRODUCT_NAME = "Kazuizhi AI Enterprise V2.1.0 Beta R8 Preview"


def get_version():
    return {
        "version": VERSION,
        "stage": BUILD_STAGE,
        "release": RELEASE,
        "build": BUILD_ID,
        "product": PRODUCT_NAME,
        "source": "05_V2.0.0_Source/web",
        "display_version": R8_DISPLAY_VERSION,
        "runtime_build": R8_RUNTIME_BUILD,
        "r8_release": R8_RELEASE,
        "r8_phase": R8_PHASE,
        "r8_product": R8_PRODUCT_NAME,
    }

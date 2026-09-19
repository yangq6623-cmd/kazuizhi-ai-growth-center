"""Canonical V2 runtime identity with the complete R8 delivery layer."""

# R7 compatibility identity stays stable so the proven R7 core, static assets and
# existing user-data migrations keep working while R8 is developed on top.
VERSION = "2.0.0"
BUILD_STAGE = "Beta"
RELEASE = "R7 Final"
BUILD_ID = "KZ-ENTERPRISE-V2-BETA-20260917-R7-FINAL"
PRODUCT_NAME = "Kazuizhi AI Enterprise V2.0.0 Beta R7 Final"

# R8 final package/display identity. The proven R7 identity above remains as a
# compatibility contract for user-data migration and existing integrations.
R8_DISPLAY_VERSION = "V2.1.0 R8 Final"
R8_RELEASE = "R8 Final"
R8_PHASE = "R8-08"
R8_RUNTIME_BUILD = "KZ-ENTERPRISE-V2.1-R8-FINAL-20260919"
R8_PRODUCT_NAME = "Kazuizhi AI Enterprise V2.1.0 R8 Final"


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

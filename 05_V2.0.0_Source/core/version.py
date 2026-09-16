"""Canonical V2 Beta runtime identity."""
VERSION = "2.0.0"
BUILD_STAGE = "Beta"
RELEASE = "R7"
BUILD_ID = "KZ-ENTERPRISE-V2-BETA-20260916-R7"
PRODUCT_NAME = "Kazuizhi AI Enterprise V2.0.0 Beta R7"

def get_version():
    return {"version": VERSION, "stage": BUILD_STAGE, "release": RELEASE, "build": BUILD_ID,
            "product": PRODUCT_NAME, "source": "05_V2.0.0_Source/web"}



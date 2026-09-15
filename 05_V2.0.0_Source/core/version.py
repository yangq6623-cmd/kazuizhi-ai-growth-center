"""Canonical V2 Beta R1 runtime identity."""
VERSION = "2.0.0"
BUILD_STAGE = "Beta"
RELEASE = "R1"
BUILD_ID = "KZ-ENTERPRISE-V2-BETA-20260915"
PRODUCT_NAME = "Kazuizhi AI Enterprise V2.0.0 Beta R1"

def get_version():
    return {"version": VERSION, "stage": BUILD_STAGE, "release": RELEASE,
            "build": BUILD_ID, "product": PRODUCT_NAME,
            "source": "05_V2.0.0_Source/web"}

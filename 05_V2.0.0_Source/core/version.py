"""Canonical V2 Beta runtime identity."""
VERSION = "2.0.0"
BUILD_STAGE = "Beta"
BUILD_ID = "KZ-ENTERPRISE-V2-BETA-20260915"
PRODUCT_NAME = "Kazuizhi AI Enterprise V2.0.0 Beta"

def get_version():
    return {"version": VERSION, "stage": BUILD_STAGE, "build": BUILD_ID,
            "product": PRODUCT_NAME, "source": "05_V2.0.0_Source/web"}

"""Version manager for Kazuizhi AI Growth Center"""

VERSION = "1.9.5"
BASE_VERSION = "1.8.5"
BUILD_STAGE = "rebuild"


def get_version():
    return {
        "version": VERSION,
        "base": BASE_VERSION,
        "stage": BUILD_STAGE,
    }

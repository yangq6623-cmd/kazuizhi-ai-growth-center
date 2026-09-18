"""External service connection management."""

# R8-01B.3 extends the Android adapter at package import time so the existing
# backend route keeps one stable API while ordinary screen-off recovery and
# safe platform launch are added without duplicating the device stack.
from . import android_device_b3 as _android_device_b3  # noqa: F401,E402

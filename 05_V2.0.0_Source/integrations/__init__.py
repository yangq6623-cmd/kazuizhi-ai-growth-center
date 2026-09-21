"""External service connection management."""

# R8-01B.3 extends the Android adapter at package import time so the existing
# backend route keeps one stable API while ordinary screen-off recovery and
# safe platform launch are added without duplicating the device stack.
from . import android_device_b3 as _android_device_b3  # noqa: F401,E402

# V2.2.1 replaces per-frame ADB screencap polling with a persistent Android
# screenrecord H.264 producer for low-latency live mirroring. The stable device
# status API is patched in place so every page continues to read one truth.
from . import android_live_mirror as _android_live_mirror  # noqa: F401,E402

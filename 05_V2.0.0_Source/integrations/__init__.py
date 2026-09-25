"""External service connection management."""

# R8-01B.3 extends the Android adapter at package import time so the existing
# backend route keeps one stable API while ordinary screen-off recovery and
# safe platform launch are added without duplicating the device stack.
from . import android_device_b3 as _android_device_b3  # noqa: F401,E402

# V2.2.1 replaces per-frame ADB screencap polling with a persistent Android
# screenrecord H.264 producer for low-latency live mirroring. The stable device
# status API is patched in place so every page continues to read one truth.
from . import android_live_mirror as _android_live_mirror  # noqa: F401,E402

# R8-17 production host compatibility: mirror managed SEO index.html files to
# default.htm so Windows Server 2012 R2 / IIS can resolve /seo/<slug>/ even when
# index.html is not present in the site's effective Default Document list.
from . import r8_17_iis_static_compat as _r8_17_iis_static_compat  # noqa: F401,E402

# R8-17 final legacy-IIS fallback: if the directory URL still cannot pass
# truthful public verification, publish and verify a direct /seo/<slug>.html
# copy with a matching canonical. This changes no IIS/server configuration.
from . import r8_17_direct_file_fallback as _r8_17_direct_file_fallback  # noqa: F401,E402

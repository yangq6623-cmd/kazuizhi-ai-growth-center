"""External service connection management.

Retired Android/ADB adapters are intentionally not imported at package load.
They caused cold-start work and device probes even when the owner only used
SEO/GEO or PC browser publishing.  Legacy modules remain importable by their
explicit module path for archival data migration, but are not runtime services.
"""

# Keep the IIS compatibility patch; it is unrelated to phones and supports the
# verified public SEO site on older Windows Server deployments.
from . import r8_17_iis_static_compat as _r8_17_iis_static_compat  # noqa: F401,E402

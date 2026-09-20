"""One-time, non-destructive upgrade snapshot for V2.2 R8 Operational."""

from __future__ import annotations

import shutil

from core.storage import data_root, now_iso, read_json, write_json


MARKER = "r8/migration_v2_2.json"


def migrate_to_v2_2():
    marker = read_json(MARKER, {})
    if marker.get("to") == "V2.2.0 R8 Operational" and marker.get("result") == "complete":
        return marker
    root = data_root()
    backup = root / "r8" / "backup_pre_v2_2"
    copied = []
    sources = [path for path in root.rglob("*") if path.is_file()]
    for source in sorted(sources, key=lambda item: item.as_posix()):
        relative = source.relative_to(root)
        if relative.as_posix() == MARKER or relative.parts[:2] == ("r8", "backup_pre_v2_2"):
            continue
        if source.name.endswith((".tmp", ".uploading")):
            continue
        target = backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(relative.as_posix())
    marker = {
        "from": "existing-user-data", "to": "V2.2.0 R8 Operational",
        "at": now_iso(), "result": "complete", "mode": "full_copy_before_r8_write",
        "copied_count": len(copied), "copied": copied,
        "preserved": ["任务与审计", "运营记忆", "经营数据", "AI连接配置", "同步桥", "账号和设备资料"],
    }
    write_json(MARKER, marker)
    return marker

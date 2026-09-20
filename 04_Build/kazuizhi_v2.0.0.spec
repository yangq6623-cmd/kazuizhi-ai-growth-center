# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all
repo = Path(SPECPATH).resolve().parent
source = repo / "05_V2.0.0_Source"
marker = "KZ-ENTERPRISE-V2.2-R8-OPERATIONAL-20260920"
for filename in ("operational.html", "index.html", "WEB_VERSION.txt"):
    text = (source / "web" / filename).read_text(encoding="utf-8")
    if marker not in text:
        raise ValueError("Invalid V2.2 R8 Operational frontend identity")
ff_datas, ff_binaries, ff_hidden = collect_all("imageio_ffmpeg")
pil_datas, pil_binaries, pil_hidden = collect_all("PIL")
name = "Kazuizhi_AI_Enterprise_V2.0.0_Beta"
a = Analysis([str(source / "run.py")], pathex=[str(source)],
             binaries=ff_binaries + pil_binaries,
             datas=[(str(source / "web"), "web"),
                    (str(source / "config"), "config"),
                    (str(source / "version"), "version")] + ff_datas + pil_datas,
             hiddenimports=ff_hidden + pil_hidden, hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=name, console=False,
          debug=False, strip=False, upx=False, version=str(repo / "04_Build/v2/windows_version.txt"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=name)
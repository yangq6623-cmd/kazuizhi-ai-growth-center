# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
repo = Path(SPECPATH).resolve().parent
source = repo / "05_V2.0.0_Source"
marker = "KZ-ENTERPRISE-V2-BETA-20260916-R4"
for filename in ("index.html", "WEB_VERSION.txt"):
    text = (source / "web" / filename).read_text(encoding="utf-8")
    if marker not in text or "1.9.5" in text:
        raise ValueError("Invalid V2 frontend identity")
name = "Kazuizhi_AI_Enterprise_V2.0.0_Beta"
a = Analysis([str(source / "run.py")], pathex=[str(source)],
             binaries=[], datas=[(str(source / "web"), "web"),
                                  (str(source / "config"), "config"),
                                  (str(source / "version"), "version")],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=name, console=True,
          debug=False, strip=False, upx=False, version=str(repo / "04_Build/v2/windows_version.txt"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=name)


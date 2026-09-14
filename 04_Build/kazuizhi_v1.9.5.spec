# -*- mode: python ; coding: utf-8 -*-

# Kazuizhi AI V1.9.5 Alpha PyInstaller configuration
# Target: Windows executable build

from pathlib import Path

project_root = Path('../03_V1.9.5_Source').resolve()

block_cipher = None

analysis = Analysis(
    [str(project_root / 'run.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name='Kazuizhi_AI_V1.9.5_Alpha',
    debug=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=True,
    name='Kazuizhi_AI_V1.9.5_Alpha',
)

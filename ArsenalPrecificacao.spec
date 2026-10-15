# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import flet_desktop.version

datas = []
binaries = []
hiddenimports = ['openpyxl']
for package in ('flet', 'flet_desktop', 'mysql.connector'):
    tmp_ret = collect_all(package)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

desktop = Path.home() / '.flet' / 'client' / ('flet-desktop-full-' + flet_desktop.version.version) / 'flet'
if not (desktop / 'flet.exe').is_file():
    raise RuntimeError('Runtime desktop do Flet ausente: ' + str(desktop))
datas.append((str(desktop), 'flet_runtime'))


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['empacotamento_runtime.py'],
    excludes=['numpy', 'pandas', 'PIL', 'lxml', 'flet.testing', 'flet.pytest_plugin', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ArsenalPrecificacao',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

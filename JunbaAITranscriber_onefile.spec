# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

# GitHub Actions / Windows one-file build spec.
datas = []
binaries = []
hiddenimports = []

for pkg in [
    'PySide6',
    'faster_whisper',
    'ctranslate2',
    'av',
    'imageio_ffmpeg',
    'google.genai',
    'keyring',
    'docx',
    'platformdirs',
    'huggingface_hub',
]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

for pkg in ['keyring.backends', 'google.genai']:
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

# De-duplicate to keep the spec deterministic.
hiddenimports = list(dict.fromkeys(hiddenimports))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'pyannote', 'tensorflow'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Junba_AI_Transcriber_v2.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

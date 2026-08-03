# -*- mode: python ; coding: utf-8 -*-
"""
AudioClass_v91_onefile.spec — PyInstaller --onefile (UN SOLO .exe)
Genera: dist_onefile/AudioClass.exe (build con --distpath dist_onefile)
Todo autocontenido: doble clic y listo (la primera vez tarda ~30-60s
en descomprimirse a temp). Ver AudioClass_v91.spec para la version
onedir (carpeta, arranque rapido).
"""
import os, sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Fuentes Unicode para los acentos en PDF (se resuelven via sys._MEIPASS
# dentro del bundle gracias al fallback de _pdf_unicode_font).
def _assets():
    datas = []
    for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        src = os.path.join("assets", f)
        if os.path.exists(src):
            datas.append((src, "assets"))
    # Modelo Whisper tiny empaquetado para transcripcion local OFFLINE
    for f in ("tiny.pt",):
        src = os.path.join("models", f)
        if os.path.exists(src):
            datas.append((src, "models"))
    # Datos internos de whisper (mel_filters.npz, gpt2.tiktoken,
    # multilingual.tiktoken) — sin ellos falla la transcripcion en el exe:
    #   FileNotFoundError: whisper/assets/mel_filters.npz
    datas += collect_data_files('whisper')
    return datas

a = Analysis(
    ['audioclass_v91.py'],
    pathex=[],
    binaries=[],
    datas=_assets(),
    hiddenimports=[
        'scipy.special._cdflib',
        'scipy.special.cython_special',
        'noisereduce',
        'sounddevice',
        '_sounddevice_data',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_agg',
        'customtkinter',
        'customtkinter.windows',
        'customtkinter.windows.widgets',
        'customtkinter.windows.widgets.core_rendering',
        'customtkinter.windows.widgets.core_widget_classes',
        'customtkinter.windows.widgets.theme',
        'fpdf',
        'fpdf.fonts',
        'numpy.core._dtype_ctypes',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'darkdetect',
        # Motor local Whisper + torch (transcripcion sin internet)
        'whisper',
        'whisper.tokenizer',
        'whisper.decoding',
        'whisper.model',
        'whisper.audio',
        'whisper.transcribe',
        'whisper.utils',
        'torch',
        'torch._C',
        'torch.utils',
        'torch.utils.data',
        'torch.nn',
        'torch.serialization',
        'tiktoken',
        'tiktoken_ext',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torchaudio',
        'matplotlib.pyplot',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AudioClass',
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

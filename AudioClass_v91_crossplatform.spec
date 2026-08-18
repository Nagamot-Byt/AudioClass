# -*- mode: python ; coding: utf-8 -*-
"""
AudioClass_v91_crossplatform.spec — PyInstaller cross-platform
Genera el ejecutable para la plataforma actual:
  - Windows: AudioClass.exe
  - macOS:   AudioClass.app (onefile) o AudioClass (onedir)
  - Linux:   AudioClass (onefile o onedir)

Uso:
  pyinstaller AudioClass_v91_crossplatform.spec                    # onefile
  pyinstaller --onedir AudioClass_v91_crossplatform.spec           # onedir

Auto-detecta la plataforma y ajusta:
  - Extensión del ejecutable (.exe en Windows, .app en macOS)
  - Console=False (GUI mode)
  - UPX en Windows/Linux (en macOS puede causar problemas)
  - Codigo de firma en macOS (codesign)
"""
import os
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# ── Assets ──────────────────────────────────────────────────────────────────
def _assets():
    datas = []
    for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        src = os.path.join("assets", f)
        if os.path.exists(src):
            datas.append((src, "assets"))
    src = os.path.join("assets", "audioclass_theme.json")
    if os.path.exists(src):
        datas.append((src, "assets"))
    for f in ("tiny.pt",):
        src = os.path.join("models", f)
        if os.path.exists(src):
            datas.append((src, "models"))
    for name in ("tiny", "base"):
        d = os.path.join("models_ct2", name)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "model.bin")):
            for f in os.listdir(d):
                datas.append((os.path.join(d, f), os.path.join("models_ct2", name)))
    datas += collect_data_files('whisper')
    datas += collect_data_files('faster_whisper')
    return datas

# ── Platform-specific settings ──────────────────────────────────────────────
is_windows = sys.platform == "win32"
is_macos = sys.platform == "darwin"
is_linux = sys.platform.startswith("linux")

# Nombre del ejecutable
exe_name = "AudioClass"
if is_windows:
    exe_name += ".exe"

# Console mode (False = GUI, True = terminal)
# En macOS/Linux, False abre Terminal; para .app bundle se necesita True
# o un wrapper shell. Usamos False y el usuario ejecuta desde terminal.
console = False

# UPX: funciona bien en Windows/Linux, puede causar problemas en macOS
use_upx = not is_macos

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
        'numpy.testing',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'darkdetect',
        'faster_whisper',
        'faster_whisper.transcribe',
        'faster_whisper.audio',
        'faster_whisper.feature_extractor',
        'faster_whisper.tokenizer',
        'faster_whisper.utils',
        'faster_whisper.vad',
        'ctranslate2',
        'av',
        'tokenizers',
        'tqdm',
        'onnxruntime',
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
        'audioclass_core',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torchaudio',
        'torch.utils.tensorboard',
        'matplotlib.pyplot',
        'matplotlib.tests',
        'scipy.tests',
        'IPython',
        'jupyter',
        'notebook',
        'pandas',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'tkinter.test',
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
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=is_linux,  # Strip symbols on Linux to reduce size
    upx=use_upx,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,  # Fill with identity for macOS signing
    entitlements_file=None,
)

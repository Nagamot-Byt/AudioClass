# -*- mode: python ; coding: utf-8 -*-
"""
AudioClass_v91_linux.spec — Linux-optimized onedir build.
Excludes collect_data_files('faster_whisper') which adds ~2GB of .so
shared libraries on Linux that aren't needed at runtime (CT2 models
are loaded from models_ct2/ directory).
"""
import os, sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

def _assets():
    datas = []
    for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        src = os.path.join("assets", f)
        if os.path.exists(src):
            datas.append((src, "assets"))
    src = os.path.join("assets", "audioclass_theme.json")
    if os.path.exists(src):
        datas.append((src, "assets"))
    src = os.path.join("models", "tiny.pt")
    if os.path.exists(src):
        datas.append((src, "models"))
    for name in ("tiny", "base"):
        d = os.path.join("models_ct2", name)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "model.bin")):
            for f in os.listdir(d):
                datas.append((os.path.join(d, f), os.path.join("models_ct2", name)))
    datas += collect_data_files('whisper')
    try:
        datas += collect_data_files('sherpa_onnx')
    except Exception:
        pass
    # EXCLUDED: collect_data_files('faster_whisper') — saves ~2GB of .so on Linux
    return datas

a = Analysis(
    ['audioclass_v91.py'],
    pathex=[],
    binaries=collect_dynamic_libs('sherpa_onnx') if 'sherpa_onnx' in sys.modules or os.path.exists('/usr') else [],
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
        # Modulos nuevos (refactor v9.2+)
        'config_manager',
        'config_dialog',
        'mic_optimizer_ui',
        'mic_troubleshooter',
        'ai_providers',
        'update_checker',
        'theme',
        'recording_engine',
        'transcription_engines',
        'export_utils',
        'ui_builder',
        'audio_quality_checker',
        'sound_error_solver',
        # Modulos nuevos (v9.1+)
        'template_plugins',
        'plugin_manager_ui',
        'waveform_widget',
        'locales',
        'locales.i18n',
        'sherpa_onnx',
        'soundfile',
        '_soundfile',
        'cffi',
        'services',
        'services.transcription_service',
        'services.mic_service',
        'services.recording_service',
        'services.update_service',
        'toast_ui',
        'update_dialog_ui',
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
        'onnxruntime',
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
    [],
    exclude_binaries=True,
    name='AudioClass',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='AudioClass',
)

# -*- mode: python ; coding: utf-8 -*-
"""
AudioClass_v91.spec — PyInstaller --onedir (carpeta unica)
Genera: dist/AudioClass/AudioClass.exe
Para distribuir: comprimir la carpeta dist/AudioClass/ entera.
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
    # Tema CTk custom (escala azul-gris-blanco-negro). Sin el, los widgets CTk
    # por defecto del exe usarian el tema 'gold' de respaldo (inconsistente).
    src = os.path.join("assets", "audioclass_theme.json")
    if os.path.exists(src):
        datas.append((src, "assets"))
    # Modelo Whisper tiny empaquetado para transcripcion local OFFLINE
    # (backend openai, respaldo de los exes que aun no llevan CT2)
    for f in ("tiny.pt",):
        src = os.path.join("models", f)
        if os.path.exists(src):
            datas.append((src, "models"))
    # Modelos CT2 de faster-whisper (tiny + base) — el exe prefiere este
    # backend (CTranslate2 int8, ~2x mas rapido); autocontenidos, sin internet.
    for name in ("tiny", "base"):
        d = os.path.join("models_ct2", name)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "model.bin")):
            for f in os.listdir(d):
                datas.append((os.path.join(d, f), os.path.join("models_ct2", name)))
    # Datos internos de whisper (mel_filters.npz, gpt2.tiktoken,
    # multilingual.tiktoken) — sin ellos falla la transcripcion en el exe:
    #   FileNotFoundError: whisper/assets/mel_filters.npz
    datas += collect_data_files('whisper')
    # faster-whisper: silero VAD (aunque no usamos vad_filter, el paquete lo
    # referencian algunos imports) — se empaqueta por robustez.
    datas += collect_data_files('faster_whisper')
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
        # numpy.testing se accede dinamicamente via scipy._external.array_api_compat
        # (getattr(numpy,'testing')), el analisis estatico no lo detecta: hay que
        # forzarlo aqui o el exe muere al arrancar con ModuleNotFoundError.
        'numpy.testing',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'darkdetect',
        # Motor local Whisper + torch (transcripcion sin internet)
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
        # #9: nucleo separado de la UI
        'audioclass_core',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # #3 Shrink: modulos pesados o de tests que la app no usa en runtime.
        # NOTA: torch.cuda NO se excluye: aunque el motor es CPU, el propio
        # import de torch ejecuta _C._initExtension(_manager_path()) que hace
        # `import torch.cuda`; excluirlo rompe el arranque (ModuleNotFoundError).
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
    [],
    exclude_binaries=True,
    name='AudioClass',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    # True: la app ya muestra sus propios errores (mb.showerror en __main__);
    # con False cualquier excepcion no capturada abre un dialogo de PyInstaller
    # que cuelga el proceso en silencio en maquinas de usuarios.
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
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AudioClass',
)

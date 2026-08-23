#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — Script de build unificado multiplataforma para AudioClass
====================================================================

Detecta el SO automáticamente y ejecuta el build correcto:
  - Windows: onefile.exe + .app (vía PyInstaller)
  - macOS:   .app bundle + .dmg (vía PyInstaller)
  - Linux:   AppImage + tar.xz (vía PyInstaller)

Uso:
    python build.py                    # Build completo para tu SO
    python build.py --onedir           # Build onedir (carpeta, arranque rápido)
    python build.py --onefile          # Build onefile (ejecutable único)
    python build.py --appimage         # Solo AppImage (Linux)
    python build.py --app              # Solo .app bundle (macOS)
    python build.py --skip-models      # No descargar modelos whisper
    python build.py --skip-tests       # No ejecutar tests post-build
"""
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# ── Configuración ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
SO = platform.system()  # 'Windows', 'Darwin', 'Linux'
PY = sys.executable

# Archivos de PyInstaller
SPECS = {
    "onedir": {
        "Windows": "AudioClass_v91.spec",
        "Darwin": "AudioClass_v91.spec",
        "Linux": "AudioClass_v91_linux.spec",
    },
    "onefile": {
        "Windows": "AudioClass_v91_onefile.spec",
        "Darwin": "AudioClass_v91_onefile.spec",
        "Linux": "AudioClass_v91_onefile_linux.spec",
    },
}

# Assets necesarios
REQUIRED_ASSETS = [
    "assets/audioclass_theme.json",
    "assets/DejaVuSans.ttf",
    "assets/DejaVuSans-Bold.ttf",
]

REQUIRED_MODELS = [
    "models_ct2/tiny/model.bin",
    "models_ct2/base/model.bin",
]

DOCS = [
    "LEEME.txt", "LICENCIA.txt", "EULA.txt",
    "AVISO_DE_PRIVACIDAD.txt", "TERCEROS_Y_LICENCIAS.md",
]


def log(msg, color=""):
    """Imprime un mensaje con color opcional."""
    colors = {"green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m",
              "blue": "\033[36m", "bold": "\033[1m", "end": "\033[0m"}
    prefix = colors.get(color, "")
    suffix = colors.get("end", "") if color else ""
    print(f"{prefix}{msg}{suffix}")


def run(cmd, cwd=None, check=True):
    """Ejecuta un comando y retorna el resultado."""
    log(f"  $ {cmd}", "blue")
    result = subprocess.run(
        cmd, shell=True, cwd=cwd or ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if check and result.returncode != 0:
        log(f"ERROR: {result.stderr[:500]}", "red")
        sys.exit(1)
    return result


def check_prerequisites():
    """Verifica que las dependencias estén instaladas."""
    log(f"\n{'='*60}", "bold")
    log(f"  AudioClass — Build {SO}", "bold")
    log(f"{'='*60}\n", "bold")

    # Python
    log(f"Python: {PY} ({sys.version.split()[0]})", "green")

    # PyInstaller
    try:
        import PyInstaller
        log(f"PyInstaller: {PyInstaller.__version__}", "green")
    except ImportError:
        log("PyInstaller no instalado. Instalando...", "yellow")
        run(f'"{PY}" -m pip install pyinstaller', check=True)

    # Assets
    for asset in REQUIRED_ASSETS:
        if not (ROOT / asset).exists():
            log(f"WARNING: Asset faltante: {asset}", "yellow")

    # Modelos
    models_ok = all((ROOT / m).exists() for m in REQUIRED_MODELS)
    return models_ok


def download_models():
    """Descarga modelos whisper tiny + base."""
    log("\n[1/4] Descargando modelos whisper...", "bold")

    cache_dir = ROOT / "models"
    cache_dir.mkdir(exist_ok=True)

    # whisper tiny.pt
    tiny_pt = cache_dir / "tiny.pt"
    if not tiny_pt.exists():
        run(f'"{PY}" -c "'
            'import os, shutil, whisper; '
            'whisper.load_model(\"tiny\"); '
            'shutil.copy(os.path.expanduser(\"~/.cache/whisper/tiny.pt\"), \"models/tiny.pt\")'
            '"', check=False)

    # CT2 models
    ct2_dir = ROOT / "models_ct2"
    for name in ("tiny", "base"):
        model_dir = ct2_dir / name
        if not (model_dir / "model.bin").exists():
            log(f"  Descargando CT2 {name}...", "blue")
            run(f'"{PY}" -c "'
                'from huggingface_hub import snapshot_download; '
                f'snapshot_download(\"Systran/faster-whisper-{name}\", local_dir=\"models_ct2/{name}\")'
                '"', check=False)

    log("Modelos listos", "green")


def build_onedir():
    """Build onedir (carpeta con ejecutable + dependencias)."""
    spec = SPECS["onedir"][SO]
    log(f"\n[2/4] Build onedir ({spec})...", "bold")
    run(f'"{PY}" -m PyInstaller --noconfirm "{spec}"')

    if SO == "Windows":
        exe = ROOT / "dist" / "AudioClass" / "AudioClass.exe"
    else:
        exe = ROOT / "dist" / "AudioClass" / "AudioClass"

    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        log(f"Onedir generado: {exe} ({size_mb:.0f} MB)", "green")
        return exe
    else:
        log("ERROR: No se generó el ejecutable onedir", "red")
        sys.exit(1)


def build_onefile():
    """Build onefile (ejecutable único autocontenido)."""
    spec = SPECS["onefile"][SO]
    distpath = "dist_onefile"
    log(f"\n[2/4] Build onefile ({spec})...", "bold")
    run(f'"{PY}" -m PyInstaller --noconfirm --distpath {distpath} "{spec}"')

    if SO == "Windows":
        exe = ROOT / distpath / "AudioClass.exe"
    else:
        exe = ROOT / distpath / "AudioClass"

    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        log(f"Onefile generado: {exe} ({size_mb:.0f} MB)", "green")
        return exe
    else:
        log("ERROR: No se generó el ejecutable onefile", "red")
        sys.exit(1)


def build_windows(exe_path):
    """Empaquetado para Windows: zip con exe + docs."""
    log("\n[3/4] Empaquetado Windows...", "bold")

    zip_name = "AudioClass_v9.1_WINDOWS.zip"
    with zipfile.ZipFile(ROOT / zip_name, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(exe_path, exe_path.name)
        for doc in DOCS:
            if (ROOT / doc).exists():
                z.write(ROOT / doc, doc)

    zip_size = (ROOT / zip_name).stat().st_size / (1024 * 1024)
    log(f"ZIP Windows: {zip_name} ({zip_size:.0f} MB)", "green")

    # Crear .bat de inicio rápido
    bat_content = f'''@echo off
cd /d "%~dp0"
start "" "{exe_path.name}"
'''
    (ROOT / "Iniciar AudioClass.bat").write_text(bat_content, encoding="utf-8")
    log("Creado: Iniciar AudioClass.bat", "green")


def build_macos(exe_path):
    """Empaquetado para macOS: .app bundle + .dmg."""
    log("\n[3/4] Empaquetado macOS...", "bold")

    # Crear .app bundle
    app_dir = ROOT / "dist" / "AudioClass.app"
    contents = app_dir / "Contents"
    macos_dir = contents / "MacOS"
    resources_dir = contents / "Resources"

    # Limpiar y crear estructura
    if app_dir.exists():
        shutil.rmtree(app_dir)
    macos_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)

    # Copiar ejecutable
    shutil.copy2(exe_path, macos_dir / "AudioClass")
    (macos_dir / "AudioClass").chmod(0o755)

    # Copiar dependencias del onedir
    onedir = ROOT / "dist" / "AudioClass"
    if onedir.exists():
        for item in onedir.iterdir():
            if item.name != "AudioClass":
                dest = macos_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

    # Info.plist
    plist = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>AudioClass</string>
    <key>CFBundleDisplayName</key><string>AudioClass</string>
    <key>CFBundleIdentifier</key><string>com.audioclass.app</string>
    <key>CFBundleVersion</key><string>9.1.0</string>
    <key>CFBundleShortVersionString</key><string>9.1.0</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleExecutable</key><string>AudioClass</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSMicrophoneUsageDescription</key><string>AudioClass necesita acceso al micrófono para grabar clases.</string>
    <key>LSMinimumSystemVersion</key><string>10.15</string>
    <key>LSApplicationCategoryType</key><string>public.app-category.education</string>
</dict>
</plist>'''
    (contents / "Info.plist").write_text(plist, encoding="utf-8")

    # Docs legales
    for doc in DOCS:
        if (ROOT / doc).exists():
            shutil.copy2(ROOT / doc, macos_dir / doc)

    log(f".app bundle creado: {app_dir}", "green")

    # Crear .dmg
    dmg_name = "AudioClass_v9.1_MACOS.dmg"
    dmg_path = ROOT / dmg_name
    if shutil.which("hdiutil"):
        log("Creando .dmg...", "blue")
        run(f'hdiutil create -volname "AudioClass" -srcfolder "{app_dir}" -ov -format UDZO "{dmg_path}"',
            check=False)
        if dmg_path.exists():
            dmg_size = dmg_path.stat().st_size / (1024 * 1024)
            log(f".dmg creado: {dmg_name} ({dmg_size:.0f} MB)", "green")

    # Zip del .app
    zip_name = "AudioClass_v9.1_MACOS_APP.zip"
    with zipfile.ZipFile(ROOT / zip_name, "w", zipfile.ZIP_DEFLATED) as z:
        for item in app_dir.rglob("*"):
            if item.is_file():
                z.write(item, item.relative_to(ROOT))
        for doc in DOCS:
            if (ROOT / doc).exists():
                z.write(ROOT / doc, doc)

    zip_size = (ROOT / zip_name).stat().st_size / (1024 * 1024)
    log(f"ZIP .app: {zip_name} ({zip_size:.0f} MB)", "green")


def build_linux_appimage():
    """Build AppImage para Linux."""
    log("\n[3/4] Build AppImage...", "bold")

    appdir = ROOT / "AudioClass.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)

    # Estructura AppDir
    (appdir / "usr" / "bin").mkdir(parents=True)
    (appdir / "usr" / "share" / "applications").mkdir(parents=True)
    (appdir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps").mkdir(parents=True)

    # Copiar ejecutable
    onedir_exe = ROOT / "dist" / "AudioClass" / "AudioClass"
    shutil.copy2(onedir_exe, appdir / "usr" / "bin" / "AudioClass")
    (appdir / "usr" / "bin" / "AudioClass").chmod(0o755)

    # Copiar dependencias del onedir
    onedir = ROOT / "dist" / "AudioClass"
    for item in onedir.iterdir():
        if item.name != "AudioClass":
            dest = appdir / "usr" / "bin" / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

    # Desktop file
    desktop = '''[Desktop Entry]
Name=AudioClass
Comment=Graba, transcribe y exporta clases universitarias con IA
Exec=AudioClass
Icon=AudioClass
Terminal=false
Type=Application
Categories=Audio;Education;
'''
    (appdir / "AudioClass.desktop").write_text(desktop, encoding="utf-8")
    (appdir / "usr" / "share" / "applications" / "AudioClass.desktop").write_text(desktop, encoding="utf-8")

    # Icono SVG
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="#0F172A"/><text x="32" y="44" text-anchor="middle" font-size="32" font-weight="bold" fill="#60A5FA">AC</text></svg>'
    (appdir / "AudioClass.svg").write_text(svg, encoding="utf-8")
    (appdir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "AudioClass.svg").write_text(svg, encoding="utf-8")

    # Docs legales
    for doc in DOCS:
        if (ROOT / doc).exists():
            shutil.copy2(ROOT / doc, appdir / "usr" / "bin" / doc)

    # Empaquetar AppImage
    appimage_tool = shutil.which("appimagetool")
    if not appimage_tool:
        log("Descargando appimagetool...", "blue")
        run("curl -sL https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage "
            "-o /tmp/appimagetool && chmod +x /tmp/appimagetool", check=False)
        appimage_tool = "/tmp/appimagetool"

    if appimage_tool and Path(appimage_tool).exists():
        appimage_name = "AudioClass_v9.1_LINUX.AppImage"
        run(f'ARCH=x86_64 "{appimage_tool}" "{appdir}" "{appimage_name}"', check=False)
        if (ROOT / appimage_name).exists():
            ai_size = (ROOT / appimage_name).stat().st_size / (1024 * 1024)
            log(f"AppImage creado: {appimage_name} ({ai_size:.0f} MB)", "green")
    else:
        log("WARNING: No se pudo crear AppImage (falta appimagetool)", "yellow")

    # Tar.xz
    tar_name = "AudioClass_v9.1_LINUX.tar.xz"
    run(f'tar -cJf "{tar_name}" -C dist AudioClass', check=False)
    if (ROOT / tar_name).exists():
        tar_size = (ROOT / tar_name).stat().st_size / (1024 * 1024)
        log(f"Tar.xz: {tar_name} ({tar_size:.0f} MB)", "green")


def run_selftest(exe_path):
    """Ejecuta selftest del ejecutable."""
    log("\n[4/4] Selftest del ejecutable...", "bold")

    audio_test = ROOT / "tts_clase.wav"
    if not audio_test.exists():
        log("WARNING: tts_clase.wav no encontrado, saltando selftest", "yellow")
        return

    out_file = ROOT / "selftest_result.txt"
    out_file.unlink(missing_ok=True)

    cmd = f'"{exe_path}" --selftest-transcribe "{audio_test}" "{out_file}"'
    result = run(cmd, check=False)

    if out_file.exists() and out_file.stat().st_size > 0:
        content = out_file.read_text(encoding="utf-8", errors="replace")
        log(f"Selftest: {len(content)} bytes de texto generado", "green")
        out_file.unlink(missing_ok=True)
    else:
        log("WARNING: Selftest no generó output", "yellow")


def main():
    """Build principal."""
    import argparse
    parser = argparse.ArgumentParser(description="Build de AudioClass")
    parser.add_argument("--onedir", action="store_true", help="Build onedir")
    parser.add_argument("--onefile", action="store_true", help="Build onefile")
    parser.add_argument("--appimage", action="store_true", help="Solo AppImage (Linux)")
    parser.add_argument("--app", action="store_true", help="Solo .app bundle (macOS)")
    parser.add_argument("--skip-models", action="store_true", help="No descargar modelos")
    parser.add_argument("--skip-tests", action="store_true", help="No ejecutar selftest")
    args = parser.parse_args()

    # Determinar modo de build
    build_onedir_mode = args.onedir or (not args.onefile and not args.appimage and not args.app)
    build_onefile_mode = args.onefile or args.appimage or args.app

    # Verificar prerequisitos
    models_ok = check_prerequisites()

    # Descargar modelos si faltan
    if not args.skip_models and not models_ok:
        download_models()

    # Build
    exe_path = None

    if SO == "Linux" and args.appimage:
        # Para AppImage necesitamos onedir primero
        exe_path = build_onedir()
        build_linux_appimage()
    elif SO == "Darwin" and args.app:
        # Para .app necesitamos onedir primero
        exe_path = build_onedir()
        build_macos(exe_path)
    elif build_onefile_mode:
        exe_path = build_onefile()
    else:
        exe_path = build_onedir()

    # Empaquetado por plataforma
    if exe_path:
        if SO == "Windows":
            build_windows(exe_path)
        elif SO == "Darwin":
            build_macos(exe_path)
        elif SO == "Linux":
            build_linux_appimage()

    # Selftest
    if exe_path and not args.skip_tests:
        run_selftest(exe_path)

    # Resumen
    log(f"\n{'='*60}", "bold")
    log(f"  BUILD {SO} COMPLETADO", "green")
    log(f"{'='*60}\n", "bold")

    # Listar artifacts generados
    artifacts = []
    for pattern in ["*.exe", "*.AppImage", "*.dmg", "*.zip", "*.tar.xz", "*.app"]:
        artifacts.extend(ROOT.glob(pattern))
    if artifacts:
        log("Artifacts generados:", "bold")
        for a in sorted(artifacts):
            if a.is_file():
                size = a.stat().st_size / (1024 * 1024)
                log(f"  {a.name} ({size:.0f} MB)")


if __name__ == "__main__":
    main()

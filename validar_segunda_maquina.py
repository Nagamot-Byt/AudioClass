# -*- coding: utf-8 -*-
"""validar_segunda_maquina.py — Validacion TURNKEY en una segunda maquina.

Confirma el flujo completo del exe con MICROFONO REAL y VOZ REAL:

  1. [opcional --quick] mide el nivel del micro (p90) y da veredicto
     OK / DEBIL / SILENCIO (misma metrica que la app).
  2. Graba ~12 s de voz real con auto-deteccion (habla cuando lo indique).
  3. Ejecuta el exe:  --selftest-transcribe voz.wav salida.txt progreso.txt
  4. Comprueba: exit=0, texto no vacio y sin alucinacion, progreso 100%,
     y tiempo <= 2x la duracion del audio (requisito de la app).

Uso (Windows, con Python 3.12 + numpy/scipy/sounddevice):
    python validar_segunda_maquina.py [ruta_al_exe] [--dur 12] [--quick]
    python validar_segunda_maquina.py --list-devices        # microfonos disponibles
    python validar_segunda_maquina.py --device <id|nombre> ...

Se usa el microfono por defecto del sistema salvo que elijas otro con
--device (id numerico de --list-devices, o parte del nombre, p. ej. "USB").

Exit 0 = TODO OK. Exit 1 = algo fallo (imprime el detalle).
"""
import os
import sys
import time
import subprocess

import numpy as np

SR = 16000

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def find_exe():
    cands = sys.argv[1:2]
    cands += ["AudioClass COMPLETA v9.1.exe", "dist_onefile/AudioClass.exe"]
    for c in cands:
        if c and os.path.exists(c):
            return c
    sys.exit("No encuentro el exe. Pasalo como argumento o ejecuta desde la carpeta del proyecto.")


def default_input_id():
    """Id real del microfono por defecto del sistema (resuelve -1/None)."""
    import sounddevice as sd
    info = sd.query_devices(kind="input")
    return info["index"]


def resolve_device(sel):
    """Convierte un selector (None, id numerico o subcadena del nombre) en el
    id de un microfono de entrada. Sale con error claro si no es valido."""
    import sounddevice as sd
    devs = sd.query_devices()
    if sel is None:
        return default_input_id()
    try:
        i = int(sel)
    except ValueError:
        i = None
    if i is not None:
        if not (0 <= i < len(devs)) or devs[i]["max_input_channels"] < 1:
            sys.exit(f"El dispositivo {i} no es un microfono valido. Usa --list-devices.")
        return i
    matches = [k for k, d in enumerate(devs) if sel.lower() in str(d["name"]).lower()]
    if not matches:
        sys.exit(f"Ningun microfono coincide con '{sel}'. Usa --list-devices.")
    if len(matches) > 1:
        print(f"Varios microfonos coinciden con '{sel}' -> uso el primero (id {matches[0]}).")
    return matches[0]


def list_devices_cli():
    """Imprime los microfonos disponibles con su id y sale con 0."""
    import sounddevice as sd
    devs = sd.query_devices()
    if not len(devs):
        sys.exit("No hay dispositivos de audio en esta maquina.")
    did = default_input_id()
    print("=" * 62)
    print("  MICRÓFONOS DISPONIBLES")
    print("=" * 62)
    for i, d in enumerate(devs):
        if d["max_input_channels"] < 1:
            continue
        mark = "  [DEFAULT]" if i == did else ""
        print(f"  {i:3d}  {str(d['name'])[:52]}{mark}")
    print("=" * 62)
    print("  Uso:  python validar_segunda_maquina.py --device <id> ...")
    return 0


def mic_p90(dur=4.0, device=None):
    """Mide el p90 del RMS (misma metrica que optimizar_mic.py)."""
    import sounddevice as sd
    buf = []

    def cb(indata, frames, ti, status):
        buf.append(indata.copy().flatten())

    print(f" PRUEBA DE SEÑAL ({dur:.0f} s) — HABLA AHORA en voz alta cerca del microfono...")
    with sd.InputStream(samplerate=SR, channels=1, dtype=np.float32,
                        blocksize=800, callback=cb, device=device):
        sd.sleep(int(dur * 1000))
    x = np.concatenate(buf).flatten() if buf else np.zeros(0, np.float32)
    n = len(x)
    if n < SR:
        return 0.0
    fr = np.array([np.sqrt(np.mean(c.astype(np.float64) ** 2))
                   for c in np.array_split(x, max(1, n // 1600))])
    return float(np.percentile(fr, 90))


def record_voice(dur=12.0, device=None):
    """Graba voz real con auto-deteccion; guarda mic_voz_user.wav (16k mono)."""
    import sounddevice as sd
    from scipy.io import wavfile
    VOICE_THR = 0.0015
    LISTEN_MAX_S = 90
    QUIET_STOP_S = 2.5
    buf = []
    quiet_since = None
    t0 = time.time()

    def cb(indata, frames, ti, status):
        nonlocal quiet_since
        x = indata.copy().flatten()
        r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
        if r > VOICE_THR:
            buf.append(x)
            quiet_since = None
        elif buf and quiet_since is None:
            quiet_since = time.time()

    print(f"ESCUCHANDO (max {LISTEN_MAX_S}s)... HABLA AHORA en voz alta ~{dur:.0f} s. Paro al callar.")
    stream = sd.InputStream(samplerate=SR, channels=1, dtype=np.float32,
                            blocksize=800, callback=cb, device=device)
    stream.start()
    try:
        while True:
            time.sleep(0.05)
            have = sum(len(c) for c in buf) / SR
            wall = time.time() - t0
            if quiet_since is not None and have > 0.5 and time.time() - quiet_since > QUIET_STOP_S:
                break
            if have >= dur:
                break
            if wall > LISTEN_MAX_S:
                break
    finally:
        stream.stop()
        stream.close()

    x = np.concatenate(buf).flatten() if buf else np.zeros(0, np.float32)
    wavfile.write("mic_voz_user.wav", SR, np.int16(np.clip(x, -1.0, 1.0) * 32767))
    return len(x) / SR


def main():
    args = sys.argv[1:]
    do_quick = "--quick" in args
    do_list = "-l" in args or "--list-devices" in args
    device = None
    for flag in ("--device", "-d"):
        if flag in args:
            try:
                device = args[args.index(flag) + 1]
            except IndexError:
                sys.exit(f"Falta el valor de {flag}: usa --device <id|nombre>")
            break
    dur = 12.0
    if "--dur" in args:
        try:
            dur = float(args[args.index("--dur") + 1])
        except Exception:
            pass

    if do_list:
        return list_devices_cli()

    exe = find_exe()
    # subprocess.run en Windows no resuelve rutas relativas con "/"
    # (WinError 2): hay que pasar la ruta absoluta.
    exe = os.path.abspath(exe)

    import sounddevice as sd
    try:
        did = resolve_device(device)
        dname = sd.query_devices(did)["name"]
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"No pude resolver el microfono: {e}")

    print("=" * 62)
    print(f"  VALIDACIÓN SEGUNDA MÁQUINA — AudioClass v9.1")
    print(f"  exe: {exe}")
    print(f"  microfono: {dname}  (id {did})")
    print("=" * 62)

    # 1) Nivel del micro
    try:
        p90 = mic_p90(min(dur, 4.0), device=did)
    except Exception as e:
        print(f"No pude abrir el microfono (id {did}): {e}")
        return 1
    if p90 < 0.005:
        v = "SILENCIO"
    elif p90 < 0.03:
        v = "DÉBIL"
    else:
        v = "OK"
    print(f"  Nivel del micro: p90={p90:.4f} -> {v}")
    if do_quick:
        print("\n" + "=" * 62)
        print(f"  {'' if v == 'OK' else ''}VEREDICTO MICRO: {v}")
        print("=" * 62)
        return 0 if v == "OK" else 1

    # 2) Grabacion real
    seg = record_voice(dur, device=did)
    print(f"  Capturados {seg:.1f} s de voz -> mic_voz_user.wav")
    if seg < 1.0:
        print("No se capturo voz suficiente. Revisa el microfono y repite HABLANDO.")
        return 1

    # 3) Selftest del exe
    out_txt, out_prog = "st_salida.txt", "st_progreso.txt"
    for f in (out_txt, out_prog):
        try:
            os.remove(f)
        except Exception:
            pass
    t0 = time.time()
    print(f"  Transcribiendo con el exe ({seg:.0f}s de audio)...")
    rc = subprocess.run([exe, "--selftest-transcribe", "mic_voz_user.wav",
                         out_txt, out_prog], timeout=600)
    elapsed = time.time() - t0

    fails = []
    if rc.returncode != 0:
        fails.append(f"exit={rc.returncode}")
    texto = ""
    if os.path.exists(out_txt):
        with open(out_txt, encoding="utf-8", errors="replace") as f:
            texto = f.read().strip()
    if not texto or texto in ("SIN TEXTO", ""):
        fails.append("texto vacio")
    if "Transcribe faithfully" in texto or "Transcribe faithfully" in texto[:200]:
        fails.append("parece alucinacion de whisper")
    prog_ok = False
    if os.path.exists(out_prog):
        with open(out_prog, encoding="utf-8", errors="replace") as f:
            prog = f.read()
        prog_ok = "100%" in prog
    if not prog_ok:
        fails.append("progreso no llego a 100%")
    if elapsed > 2 * seg:
        fails.append(f"tiempo {elapsed:.0f}s > 2x ({2*seg:.0f}s) la duracion del audio")

    print()
    print("=" * 62)
    print(f"  duracion audio: {seg:.1f}s | tiempo exe: {elapsed:.0f}s (x{elapsed/max(seg,0.1):.2f})")
    print(f"  progreso: {'100% OK' if prog_ok else 'NO llego a 100%'}")
    print(f"  texto: {texto[:100]}{'…' if len(texto) > 100 else ''}")
    if fails:
        print(f"  FALLO: {', '.join(fails)}")
    else:
        print("  VALIDACIÓN SEGUNDA MÁQUINA: TODO OK")
    print("=" * 62)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())

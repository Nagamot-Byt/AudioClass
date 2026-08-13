# -*- coding: utf-8 -*-
"""optimizar_mic.py — Optimizador del microfono para AudioClass (Windows).

Diagnostica y corrige el problema de "grabaciones en silencio / vu_low bajo":

  1. DIAGNOSTICO (por defecto, solo lectura):
       - nivel y mute del microfono por defecto (CoreAudio IAudioEndpointVolume)
       - nivel de TODOS los microfonos activos
       - permiso de microfono de Windows (privacidad)
       - prueba de senal real (4 s): piso, p90 (voz), SNR y veredicto
  2. --apply  aplica la optimizacion:
       - nivel del microfono al 100% y desmute
       - boost del nodo de volumen (hasta +30 dB) si el driver lo expone
       - desmute de nodos de audio (IAudioMute)
       - re-ejecuta la prueba de senal y compara antes/despues
  3. --test   solo la prueba de senal (habla durante la grabacion)

Sin dependencias: llama a CoreAudio directamente con ctypes (vtable COM).
Uso:  python optimizar_mic.py [--apply] [--test] [--dur 4]
"""
import sys
import time
from ctypes import (CFUNCTYPE, POINTER, Structure, WinDLL, byref, c_bool,
                    c_float, c_int, c_long, c_ubyte, c_ulong, c_ushort,
                    c_void_p, c_wchar_p, cast)

import numpy as np
import sounddevice as sd

if sys.platform != "win32":
    print("Este optimizador solo aplica en Windows.")
    sys.exit(1)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── CoreAudio via ctypes ────────────────────────────────────────────────────
HRESULT = c_long

class GUID(Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort),
                ("Data4", c_ubyte * 8)]

def guid(s):
    """Convierte '{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}' a GUID. Data1-3 son
    valores (ctypes los guarda little-endian en memoria); Data4 son bytes."""
    s = s.strip("{}").replace("-", "")
    b = bytes.fromhex(s)
    return GUID(int(b[0:4].hex(), 16), int(b[4:6].hex(), 16),
                int(b[6:8].hex(), 16), (c_ubyte * 8)(*b[8:16]))

# GUIDs verificados (mmdeviceapi.h / endpointvolume.h / devicetopology.h)
G_CLSID_MMDEVICE_ENUM = guid("BCDE0395-E52F-467C-8E3D-C4579291692E")
G_IMMDEVICE_ENUM = guid("A95664D2-9614-4F35-A746-DE8DB63617E6")
G_IMMDEVICE = guid("D666063F-1587-4E43-81F1-B948E807363F")
G_ENDPOINT_VOL = guid("5CDF2C82-841E-4546-9722-0CF74078229A")
G_DEVICE_TOPOLOGY = guid("2A07407E-6497-4A18-9787-32F79BD0D98F")
G_ICONNECTOR = guid("9C2C4058-23F5-41DE-877A-DF3AF236A09E")
G_IPART = guid("AE2DE0E4-5BCA-4F2D-AA46-5D13F8FDB3A9")
G_ICONTROL_IFACE = guid("45D37C3F-5140-444A-AE24-400789F3CBF3")
G_AUDIO_VOL_LEVEL = guid("7FB7B48F-531D-44A2-BCB3-5AD5A134B3DC")
G_AUDIO_MUTE = guid("DF45AEEA-B74A-4B6B-AFAD-2366B6AA012E")

CLSCTX_INPROC_SERVER = 0x1
ECapture, EMultimedia = 1, 1
DEVICE_STATE_ACTIVE = 0x1

_ole32 = WinDLL("ole32")
_ole32.CoCreateInstance.restype = HRESULT
_ole32.CoCreateInstance.argtypes = [POINTER(GUID), c_void_p, c_ulong, POINTER(GUID), POINTER(c_void_p)]


def _vcall(this, idx, restype, argtypes):
    """Llama al metodo 'idx' de la vtable COM del puntero 'this'."""
    vt = cast(this, POINTER(c_void_p)).contents.value      # direccion de la vtable
    slot = (c_void_p * (idx + 1)).from_address(vt)[idx]    # funcion del slot idx
    func_addr = slot.value if hasattr(slot, "value") else int(slot)
    fn = CFUNCTYPE(restype, c_void_p, *argtypes)(func_addr)
    return fn


def _qi(iface, iid):
    """QueryInterface: devuelve el puntero (c_void_p) o None."""
    out = c_void_p()
    hr = _vcall(iface, 0, HRESULT, (POINTER(GUID), POINTER(c_void_p)))(iface, byref(iid), byref(out))
    return out if hr == 0 else None


def _create_enumerator():
    p = c_void_p()
    hr = _ole32.CoCreateInstance(byref(G_CLSID_MMDEVICE_ENUM), None, CLSCTX_INPROC_SERVER,
                                 byref(G_IMMDEVICE_ENUM), byref(p))
    if hr != 0:
        raise RuntimeError(f"CoCreateInstance MMDeviceEnumerator HR={hr:#x}")
    return p


def _default_capture_device():
    enum = _create_enumerator()
    dev = c_void_p()
    # IMMDeviceEnumerator::GetDefaultAudioEndpoint (slot 4)
    hr = _vcall(enum.value, 4, HRESULT, (c_int, c_int, POINTER(c_void_p)))(enum.value, ECapture, EMultimedia, byref(dev))
    if hr != 0:
        raise RuntimeError(f"GetDefaultAudioEndpoint HR={hr:#x}")
    return dev


def _all_capture_devices():
    enum = _create_enumerator()
    col = c_void_p()
    # IMMDeviceEnumerator::EnumAudioEndpoints (slot 3)
    hr = _vcall(enum.value, 3, HRESULT, (c_int, c_int, POINTER(c_void_p)))(enum.value, ECapture, DEVICE_STATE_ACTIVE, byref(col))
    if hr != 0:
        return []
    n = c_ulong()
    _vcall(col.value, 3, HRESULT, (POINTER(c_ulong),))(col.value, byref(n))
    devs = []
    for i in range(n.value):
        d = c_void_p()
        # IMMDeviceCollection::Item (slot 4)
        hr2 = _vcall(col.value, 4, HRESULT, (c_ulong, POINTER(c_void_p)))(col.value, i, byref(d))
        if hr2 == 0:
            devs.append(d)
    return devs


def _device_id(dev):
    s = c_wchar_p()
    # IMMDevice::GetId (slot 5)
    try:
        hr = _vcall(dev, 5, HRESULT, (POINTER(c_wchar_p),))(dev, byref(s))
        if hr != 0 or not s.value:
            return "?"
        return s.value
    except Exception:
        return "?"


def _activate(dev, iid):
    out = c_void_p()
    # IMMDevice::Activate (slot 3)
    hr = _vcall(dev, 3, HRESULT, (POINTER(GUID), c_int, c_void_p, POINTER(c_void_p)))(
        dev, byref(iid), CLSCTX_INPROC_SERVER, None, byref(out))
    return out if hr == 0 else None


def get_mic_state(dev):
    """(nivel_0_100, mute_bool) o None si no accesible."""
    vol = _activate(dev, G_ENDPOINT_VOL)
    if not vol or not vol.value:
        return None
    f = c_float()
    # IAudioEndpointVolume::GetMasterVolumeLevelScalar (slot 9)
    _vcall(vol.value, 9, HRESULT, (POINTER(c_float),))(vol.value, byref(f))
    m = c_bool()
    # IAudioEndpointVolume::GetMute (slot 15)
    _vcall(vol.value, 15, HRESULT, (POINTER(c_bool),))(vol.value, byref(m))
    return round(f.value * 100), bool(m.value)


def apply_mic_level(dev, level=100):
    vol = _activate(dev, G_ENDPOINT_VOL)
    if not vol or not vol.value:
        return False, "IAudioEndpointVolume no disponible"
    # SetMasterVolumeLevelScalar (slot 7) y SetMute (slot 14)
    _vcall(vol.value, 7, HRESULT, (c_float, c_void_p))(vol.value, level / 100.0, None)
    _vcall(vol.value, 14, HRESULT, (c_bool, c_void_p))(vol.value, False, None)
    return True, ""


def apply_boost(dev):
    """Sube el boost del nodo de volumen del microfono (hasta +30 dB) y desmuta
    nodos, si el driver los expone. Devuelve (ok, descripcion)."""
    log = []
    topo = _activate(dev, G_DEVICE_TOPOLOGY)
    if not topo or not topo.value:
        return False, "IDeviceTopology no disponible"

    def safe(fn, *a):
        """Ejecuta una llamada COM; si el driver la rechaza (p. ej. Realtek no
        implementa IDeviceTopology completo), devuelve None sin matar la app."""
        try:
            return fn(*a)
        except Exception:
            return None

    def walk(t):
        n = c_ulong()
        if safe(_vcall(t, 5, HRESULT, (POINTER(c_ulong),)), t, byref(n)) is None:
            return
        for i in range(n.value):
            part = c_void_p()
            if safe(_vcall(t, 6, HRESULT, (c_ulong, POINTER(c_void_p))), t, i, byref(part)) is None:
                continue
            if not part.value:
                continue
            nci = c_ulong()
            if safe(_vcall(part.value, 8, HRESULT, (POINTER(c_ulong),)), part.value, byref(nci)) is None:
                continue
            for j in range(nci.value):
                ci = c_void_p()
                if safe(_vcall(part.value, 9, HRESULT, (c_ulong, POINTER(c_void_p))), part.value, j, byref(ci)) is None:
                    continue
                if not ci.value:
                    continue
                vol = _qi(ci.value, G_AUDIO_VOL_LEVEL)
                if vol and vol.value:
                    ch = c_ulong()
                    if safe(_vcall(vol.value, 3, HRESULT, (POINTER(c_ulong),)), vol.value, byref(ch)) is None:
                        continue
                    for chn in range(ch.value):
                        mn, mx, stp = c_float(), c_float(), c_float()
                        cur = c_float()
                        safe(_vcall(vol.value, 5, HRESULT, (c_ulong, POINTER(c_float), POINTER(c_float), POINTER(c_float))),
                             vol.value, chn, byref(mn), byref(mx), byref(stp))
                        safe(_vcall(vol.value, 4, HRESULT, (c_ulong, POINTER(c_float))), vol.value, chn, byref(cur))
                        if mx.value > 0.5:
                            tgt = min(mx.value, 30.0)
                            safe(_vcall(vol.value, 6, HRESULT, (c_ulong, c_float, c_void_p)),
                                 vol.value, chn, tgt, None)
                            log.append(f"boost nodo volumen a +{tgt:.0f} dB (rango [{mn.value:.0f},{mx.value:.0f}] dB)")
                        else:
                            log.append(f"nodo volumen sin boost (max {mx.value:.0f} dB), nivel actual {cur.value:.1f} dB")
                mute = _qi(ci.value, G_AUDIO_MUTE)
                if mute and mute.value:
                    m = c_bool()
                    if safe(_vcall(mute.value, 4, HRESULT, (POINTER(c_bool),)), mute.value, byref(m)) is None:
                        continue
                    if m.value:
                        safe(_vcall(mute.value, 3, HRESULT, (c_bool, c_void_p)), mute.value, False, None)
                        log.append("nodo mute desactivado")

    walk(topo.value)
    nc = c_ulong()
    if safe(_vcall(topo.value, 3, HRESULT, (POINTER(c_ulong),)), topo.value, byref(nc)) is None:
        return True, "; ".join(log) if log else "driver sin IDeviceTopology accesible"
    for i in range(nc.value):
        try:
            conn = c_void_p()
            if safe(_vcall(topo.value, 4, HRESULT, (c_ulong, POINTER(c_void_p))), topo.value, i, byref(conn)) is None:
                continue
            if not conn.value:
                continue
            isc = c_bool()
            if safe(_vcall(conn.value, 7, HRESULT, (POINTER(c_bool),)), conn.value, byref(isc)) is None:
                continue
            if not isc.value:
                continue
            dconn = c_void_p()
            if safe(_vcall(conn.value, 8, HRESULT, (POINTER(c_void_p),)), conn.value, byref(dconn)) is None:
                continue
            if not dconn.value:
                continue
            dtopo = c_void_p()
            # Algunos drivers (Realtek) no implementan IConnector::GetDeviceTopology
            if safe(_vcall(dconn.value, 11, HRESULT, (POINTER(c_void_p),)), dconn.value, byref(dtopo)) is None:
                log.append("driver no expone topologia del dispositivo (GetDeviceTopology)")
                continue
            if dtopo.value:
                walk(dtopo.value)
        except Exception as e:
            log.append(f"topologia dispositivo: {type(e).__name__}")
            break
    return True, "; ".join(log) if log else "sin nodos de volumen/mute expuestos"


def list_mics():
    """[(id, nivel, mute)] de todos los microfonos activos."""
    out = []
    for d in _all_capture_devices():
        st = get_mic_state(d)
        out.append((_device_id(d), st[0] if st else None, st[1] if st else None))
    return out


def privacy_mic():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone")
        v = winreg.QueryValueEx(k, "Value")[0]
        k.Close()
        return v
    except Exception:
        return "desconocido"


def measure_signal(dur=4.0, on_level=None):
    """Graba dur segundos y mide la senal. Devuelve dict con piso, p90, peak.

    on_level (opcional): callback que recibe el RMS de cada bloque de 100 ms
    (para medidores de nivel EN VIVO en la app, sin imprimir nada)."""
    SR = 16000
    buf = []

    def cb(indata, frames, ti, status):
        x = indata.copy().flatten()
        buf.append(x)
        if on_level is not None:
            r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) if len(x) else 0.0
            on_level(r)

    try:
        with sd.InputStream(samplerate=SR, channels=1, dtype=np.float32,
                            blocksize=800, callback=cb):
            sd.sleep(int(dur * 1000))
    except Exception as e:
        return {"dur": 0.0, "piso": 0.0, "p90": 0.0, "peak": 0.0, "veredicto": f"ERROR: {e}"}
    x = np.concatenate(buf).flatten() if buf else np.zeros(0, dtype=np.float32)
    n = len(x)
    if n < SR:
        return {"dur": n / SR, "piso": 0.0, "p90": 0.0, "peak": 0.0, "veredicto": "SIN_DATOS"}
    fr = np.array([np.sqrt(np.mean(c.astype(np.float64) ** 2))
                   for c in np.array_split(x, max(1, n // 1600))])
    piso = float(np.percentile(fr, 10))
    p90 = float(np.percentile(fr, 90))
    pk = float(np.max(np.abs(x)))
    if p90 < 0.005:
        v = "SILENCIO"
    elif p90 < 0.03:
        v = "DÉBIL"
    else:
        v = "OK"
    return {"dur": n / SR, "piso": piso, "p90": p90, "peak": pk, "veredicto": v}


def test_signal(dur=4.0):
    """Prueba de senal para CLI: avisa por pantalla y delega en measure_signal."""
    print(f"\n🎙️  PRUEBA DE SEÑAL ({dur:.0f} s) — HABLA AHORA en voz alta cerca del microfono...")
    return measure_signal(dur)


def main():
    args = sys.argv[1:]
    do_apply = "--apply" in args
    do_test = "--test" in args
    dur = 4.0
    if "--dur" in args:
        try:
            dur = float(args[args.index("--dur") + 1])
        except Exception:
            pass

    print("=" * 62)
    print("  OPTIMIZADOR DE MICRÓFONO — AudioClass")
    print("=" * 62)

    dev = _default_capture_device()
    did = _device_id(dev)
    st = get_mic_state(dev)
    sname = "?"
    try:
        sname = sd.query_devices(sd.default.device[0])["name"]
    except Exception:
        pass

    print(f"\n[1] DISPOSITIVO POR DEFECTO")
    print(f"    {sname}  (id {did})")
    if st:
        print(f"    Nivel: {st[0]}%  |  Mute: {'SÍ ⚠️' if st[1] else 'No'}")
    else:
        print("    (nivel no accesible)")

    print(f"\n[2] PERMISO DE MICRÓFONO (privacidad Windows)")
    pv = privacy_mic()
    print(f"    {pv}{'  ⚠️ DENEGADO — permite el acceso en Configuración > Privacidad > Micrófono' if pv != 'Allow' else ''}")

    print(f"\n[3] TODOS LOS MICRÓFONOS ACTIVOS")
    try:
        for did2, lvl, mute in list_mics():
            mark = " [DEFAULT]" if did2 == did else ""
            extra = f"nivel {lvl}%" + (" mute ⚠️" if mute else "")
            print(f"    {extra}{mark}  {did2[:64]}")
    except Exception as e:
        print(f"    (no enumerable: {e})")

    print(f"\n[4] PRUEBA DE SEÑAL")
    antes = test_signal(dur)
    print(f"    duración {antes['dur']:.1f}s | piso {antes['piso']:.4f} | p90(voz) {antes['p90']:.4f} | peak {antes['peak']:.3f}")
    print(f"    → {antes['veredicto']}")

    if not do_apply:
        print("\n" + "=" * 62)
        if antes["veredicto"] != "OK":
            print("  Si NO hablaste durante la prueba, repitela HABLANDO en voz alta:")
            print("      python optimizar_mic.py --test")
            print("  Si hablaste y sigue debil, ejecuta  python optimizar_mic.py --apply")
            print("  (sube nivel a 100% si hace falta, activa boost si el driver lo permite).")
        else:
            print("  El microfono captura bien. No se requiere optimizacion.")
        print("=" * 62)
        return 0

    # ── APLICAR OPTIMIZACION ────────────────────────────────────────────────
    print("\n" + "=" * 62)
    print("  APLICANDO OPTIMIZACIÓN")
    print("=" * 62)
    ok1, err1 = apply_mic_level(dev, 100)
    print(f"  [{'OK ' if ok1 else 'NO '}] nivel del microfono → 100% + desmute  {err1}")
    ok2, msg2 = apply_boost(dev)
    print(f"  [{'OK ' if ok2 else 'NO '}] boost del nodo de volumen  {msg2}")

    time.sleep(0.5)
    st2 = get_mic_state(dev)
    if st2:
        print(f"  Estado tras aplicar: nivel {st2[0]}% | mute {'SÍ ⚠️' if st2[1] else 'No'}")

    print("\n[5] PRUEBA DE SEÑAL POST-OPTIMIZACIÓN")
    despues = test_signal(dur)
    print(f"    duración {despues['dur']:.1f}s | piso {despues['piso']:.4f} | p90(voz) {despues['p90']:.4f} | peak {despues['peak']:.3f}")
    print(f"    → {despues['veredicto']}")

    print("\n" + "=" * 62)
    mejo = despues["p90"] / max(antes["p90"], 1e-6)
    print(f"  RESUMEN: p90(voz) {antes['p90']:.4f} → {despues['p90']:.4f}  (x{mejo:.1f})")
    if despues["veredicto"] == "OK":
        print("  ✅ El microfono quedó optimizado. La app ya capturará tu voz.")
    elif despues["veredicto"] == "DÉBIL":
        print("  ⚠️ Sigue débil. Si NO hablaste en la prueba, repitela hablando:")
        print("      python optimizar_mic.py --test")
        print("  Si hablaste y sigue débil: acércate al microfono, revisa el boost en")
        print("     Realtek Audio Console o desactiva la supresión de ruido agresiva.")
    else:
        print("  ❌ Sigue sin señal: revisa que el microfono no esté físicamente")
        print("     desactivado y que el dispositivo por defecto sea el correcto.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())

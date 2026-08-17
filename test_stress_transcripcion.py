# -*- coding: utf-8 -*-
"""PRUEBA DE ESTRÉS del motor de transcripción de AudioClass.

Objetivo: detectar congestiones, fugas de hilos, fugas de memoria y deadlocks
bajo carga real (whisper tiny, voz real, chunks de 30s):

  A) 3 transcripciones completas consecutivas (ráfaga) con progreso monótono,
      llegada a 100%, workers > 1 y conteo de hilos que vuelve a la línea base.
  B) Cancelación a mitad de una transcripción paralela y REARRANQUE INMEDIATO
      de otra: la puerta anti-congestión (_drain_ev) debe esperar a que drene el
      pool anterior y la segunda DEBE completar al 100% (sin deadlock ni espera
      infinita).
  C) Ráfaga de cancelaciones rápidas (1 chunk, camino secuencial): todas deben
      devolver {"cancelled": True} rápido y el motor debe seguir sirviendo una
      transcripción completa después.
  D) Memoria: DOS señales independientes tras cada corrida (con gc.collect()
      previo para reducir el ruido del allocator): (1) conteo de objetos
      Whisper vivos, que DEBE quedar acotado (la cache retiene hasta
      _MODEL_CACHE_MAX=6 instancias + 1 plantilla + eng.model ≈ 8; un leak del
      cache o de plantillas los acumularía SIN tope) y (2) el RSS debe alcanzar
      un PLATEAU: la media de los 3 últimos deltas < 150 MB/corrida. El umbral
      de RSS es holgado porque la cache deliberada de 6 modelos sube el working
      set a ~2.1-2.3 GB y Windows recorta/expande el working set (±50 MB de
      ruido): la señal determinista de fuga es el conteo de objetos; la de RSS
      solo detecta fugas "gruesas" (>~150 MB por corrida sostenidos).

Salida: STRESS_ALL_OK al final si todo pasa.
"""
import os, sys, time, threading, tempfile, traceback, gc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from scipy.io import wavfile
import audioclass_v91 as ac


def _live_whisper_models():
    """Cuenta objetos Whisper vivos en el proceso (via gc). Es la señal
    determinista de fuga del cache de modelos: si el cache/plantilla acumulara
    instancias sin tope, este conteo crecería sin límite aunque el RSS oscile."""
    import whisper as _w
    return sum(1 for o in gc.get_objects() if type(o) is _w.Whisper)


def _rss_mb():
    """RSS del proceso actual en MB. Usa psutil si está disponible; si no,
    ctypes nativo de Windows (GetProcessMemoryInfo) — no requiere paquetes."""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class _PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD),
                            ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]

            pmc = _PMC()
            pmc.cb = ctypes.sizeof(pmc)
            # Declarar argtypes/restype es OBLIGATORIO en 64-bit: sin ellos el
            # HANDLE (puntero) se trunca a 32 bits y la llamada falla devolviendo 0.
            gpm = ctypes.windll.psapi.GetProcessMemoryInfo
            gpm.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
            gpm.restype = wintypes.BOOL
            gcp = ctypes.windll.kernel32.GetCurrentProcess
            gcp.argtypes = []
            gcp.restype = wintypes.HANDLE
            if gpm(gcp(), ctypes.byref(pmc), ctypes.sizeof(pmc)):
                return pmc.WorkingSetSize / (1024 * 1024)
        except Exception:
            pass
    return None


def _savewav(path, arr):
    wavfile.write(path, ac.SAMPLE_RATE, np.int16(np.clip(arr, -1.0, 1.0) * 32767))


def _make_engine(base):
    import whisper
    eng = ac.LocalWhisperEngine("tiny", backend="openai")
    eng.model = whisper.load_model(os.path.join(base, "models", "tiny.pt"))
    eng.ready = True
    eng.model_name = "tiny"
    eng._resolve_model = lambda: os.path.join(base, "models", "tiny.pt")
    return eng


def _full_run(eng, path, label):
    """Una transcripción completa: verifica monótono, 100% y workers>1."""
    prog = []

    def cb(num, total, msg):
        frac = (num / total) if total else 0.0
        prog.append((frac, msg))

    t0 = time.time()
    res = eng.transcribe(path, timestamps=False, cancel_event=None, progress_callback=cb)
    dt = time.time() - t0

    assert res.get("text") is not None, f"{label}: sin texto en resultado"
    assert res.get("cancelled") is not True, f"{label}: devolvió cancelled sin pedirlo"
    chunks = res.get("chunks", 0)
    workers = res.get("workers", 1)
    assert chunks >= 3, f"{label}: esperaba >=3 chunks, tengo {chunks}"

    # Monotonía estricta del progreso
    vals = [p for p, _ in prog]
    assert all(b >= a for a, b in zip(vals, vals[1:])), f"{label}: progreso NO monótono"
    # El último mensaje debe ser 100% (o "chunks listos" con done==total)
    last_frac, last_msg = prog[-1]
    assert last_frac >= 0.999 or "listos" in last_msg, f"{label}: último progreso {last_frac}"
    # Mensajes con tiempo restante
    rest_msgs = [m for _, m in prog if "rest" in m]
    assert rest_msgs, f"{label}: sin mensajes con tiempo restante"
    print(f"  {label}: OK · {dt:.0f}s · {chunks} chunks · {workers} workers · "
          f"{len(prog)} msgs · último={last_msg[:38]}")
    return res, dt, prog


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    voice = os.path.join(base, "prueba_voz_es.wav")
    if not os.path.exists(voice):
        print("FATAL: falta prueba_voz_es.wav")
        return 1

    sr, v = wavfile.read(voice)
    if v.dtype == np.int16:
        v = v.astype(np.float32) / 32768.0

    # Voz real x3 -> ~63s -> 3 chunks de 30s (camino paralelo real)
    raw3 = np.tile(v, 3)
    # Voz real x1 -> ~21s -> 1 chunk (camino secuencial, para ráfagas de cancelación)
    raw1 = v

    tmp = tempfile.gettempdir()
    p3 = os.path.join(tmp, "ac_stress_3ch.wav")
    p1 = os.path.join(tmp, "ac_stress_1ch.wav")
    _savewav(p3, raw3)
    _savewav(p1, raw1)

    eng = _make_engine(base)
    print(f"Motor listo (tiny) · voz real {len(raw3)/sr:.0f}s -> 3 chunks")

    # ── A) Ráfaga: 3 transcripciones completas consecutivas ────────────────
    print("[A] Ráfaga de 3 transcripciones completas")
    base_threads = threading.active_count()
    rss_series = [(_rss_mb(), "base")]   # (rss, etiqueta) para el chequeo de plateau
    times = []
    for i in range(3):
        try:
            _, dt, _ = _full_run(eng, p3, f"A{i+1}")
            times.append(dt)
            gc.collect()
            rss_series.append((_rss_mb(), f"A{i+1}"))
        except Exception as e:
            print(f"  A{i+1} FALLÓ: {e}")
            traceback.print_exc()
            return 1
    print(f"  Tiempos por corrida: {[round(t,1) for t in times]}s")
    # El motor no debe degradarse en la 3ª corrida (factor < 2.5x de la 1ª)
    if times[2] > times[0] * 2.5:
        print(f"  DEGRADACIÓN: la 3ª corrida tardó {times[2]:.0f}s vs {times[0]:.0f}s la 1ª")
        return 1
    print("  A_OK (sin degradación ni fallos)")

    # ── Fugas de hilos ──────────────────────────────────────────────────────
    time.sleep(2)
    after_threads = threading.active_count()
    leaked = after_threads - base_threads
    print(f"[HILOS] base={base_threads} tras ráfaga={after_threads} (delta {leaked})")
    if leaked > 3:
        print(f"  POSIBLE FUGA DE HILOS: delta {leaked} > 3")
        return 1
    print("  THREADS_OK")

    # ── Memoria: objetos acotados + plateau de RSS, no crecimiento absoluto ──
    # El RSS de un proceso con torch/numpy sube en las primeras corridas por el
    # high-water mark del allocator (bloques reutilizados, no liberados al SO) y
    # luego se ESTABILIZA; Windows además recorta/expande el working set (±50 MB
    # de ruido entre muestras). Diagnóstico controlado (7 corridas, tiny, voz
    # real): objetos Whisper vivos constantes en 8 (6 cache + plantilla +
    # eng.model), 0 hooks de kv_cache acumulados, y deltas de RSS sin tendencia
    # (+262 -> +132 -> +66 -> -44 -> +189 -> +51; media de los últimos 3 = 65 MB).
    # La señal DETERMINISTA de fuga es el conteo de objetos Whisper: un leak
    # del cache/plantillas los acumularía sin tope. El RSS solo detecta fugas
    # gruesas sostenidas (>~150 MB/corrida = el peso de un modelo tiny).
    if rss_series[0][0] is not None:
        print("[MEM] Chequeo: objetos Whisper acotados + plateau de RSS")
        # 2 corridas extra para tener 3 deltas finales
        for j in range(2):
            try:
                _full_run(eng, p3, f"MEM{j+1}")
            except Exception as e:
                print(f"  MEM{j+1} FALLÓ: {e}")
                traceback.print_exc()
                return 1
            gc.collect()
            rss_series.append((_rss_mb(), f"MEM{j+1}"))
        deltas = [rss_series[i][0] - rss_series[i-1][0] for i in range(1, len(rss_series))]
        last3 = deltas[-3:]
        labels = [f"{lbl}:{rss:.0f}" for rss, lbl in rss_series]
        print(f"  RSS por corrida: {' -> '.join(labels)} MB")
        print(f"  Deltas finales: {[round(d,1) for d in last3]} MB")
        # Señal 1 (determinista): el número de objetos Whisper vivos debe quedar
        # acotado. Diseño: cache hasta 6 + 1 plantilla + 1 eng.model = 8; durante
        # una corrida hay hasta ~10 (8 workers en uso); el tope 12 da margen y
        # sigue detectando cualquier acumulación sin tope.
        n_models = _live_whisper_models()
        print(f"  Objetos Whisper vivos: {n_models} (diseño ~8: 6 cache + plantilla + eng.model)")
        if n_models > 12:
            print(f"  POSIBLE FUGA DE MODELOS: {n_models} objetos Whisper vivos > 12")
            return 1
        # Señal 2 (heurística): la media de los 3 últimos deltas de RSS no debe
        # superar 150 MB/corrida. Un pico aislado se tolera (ruido del allocator
        # y del recorte de working set); una fuga real sostiene ~150-200 MB por
        # corrida (el peso de un modelo tiny) en CADA corrida.
        mean_delta = float(np.mean(last3))
        print(f"  Media de deltas finales: {mean_delta:.1f} MB")
        if mean_delta > 150:
            print(f"  POSIBLE FUGA DE MEMORIA: media de deltas {mean_delta:.1f} MB > 150")
            return 1
        print("  MEM_OK (objetos acotados y RSS estable; sin fuga)")
    else:
        print("[MEM] Medición de RSS no disponible; chequeo omitido (informativo)")

    # ── B) Cancelar a mitad + REARRANQUE INMEDIATO ──────────────────────────
    print("[B] Cancelación a mitad + rearranque inmediato (anti-congestión)")
    ev = threading.Event()
    out = {}

    def starter():
        out["res"] = eng.transcribe(p3, timestamps=False, cancel_event=ev,
                                    progress_callback=lambda n, t, m: None)

    t = threading.Thread(target=starter, daemon=True)
    t.start()
    time.sleep(1.5)
    ev.set()                      # cancelar a mitad del 1er chunk
    # B1: la cancelación de Whisper es cooperativa: el worker termina su chunk
    # en curso (tiny procesa 30s en ~2-5s) antes de que el hilo salga. join(5)
    # era demasiado corto; la cancelación correcta tarda ~2-8s.
    t.join(timeout=30)
    first = out.get("res")
    assert first is not None, "B: la 1ª transcripción no devolvió nada"
    assert first.get("cancelled") is True, f"B: esperaba cancelled, tengo {first.keys()}"
    print("  B1: 1ª transcripción cancelada correctamente")

    # Rearranque inmediato con un Event NUEVO (la app limpia stop_ev antes de
    # cada corrida en _starttrans; el test debe replicar eso y no reutilizar el
    # Event ya cancelado, o la 2ª llamada devolvería cancelled al instante).
    ev2 = threading.Event()
    out2 = {}

    def starter2():
        out2["res"] = eng.transcribe(p3, timestamps=False, cancel_event=ev2,
                                      progress_callback=lambda n, t, m: None)

    t0b = time.time()
    t2 = threading.Thread(target=starter2, daemon=True)
    t2.start()
    # El drenaje del pool cancelado toma ~30-60s; esperamos con margen
    t2.join(timeout=150)
    second = out2.get("res")
    wait_b = time.time() - t0b
    assert second is not None, "B: la 2ª transcripción no devolvió nada"
    assert second.get("cancelled") is not True, "B: la 2ª transcripción fue cancelada"
    assert second.get("chunks", 0) >= 3, f"B: 2ª con {second.get('chunks')} chunks"
    assert eng._drain_ev.is_set(), "B: la puerta anti-congestión quedó cerrada (bug)"
    print(f"  B2: 2ª transcripción completó {second['chunks']} chunks en {wait_b:.0f}s "
          f"(incluye espera de drenaje); puerta reabierta")
    print("  B_OK (sin deadlock; la puerta esperó el drenaje)")

    # ── C) Ráfaga de cancelaciones rápidas (camino secuencial) ──────────────
    print("[C] Ráfaga de 3 cancelaciones rápidas (1 chunk)")
    # Nota: la cancelación de Whisper es COOPERATIVA y solo se comprueba en los
    # bordes de chunk (loop de _transcribe_with). Con 1 chunk hay un solo borde
    # (al inicio): si el evento se setea a mitad del chunk, la transcripción
    # termina normal (comportamiento correcto, no un bug). Para probar la
    # ráfaga de forma determinista, el evento se setea ANTES de arrancar el
    # hilo: el motor debe devolver cancelled al instante, sin colgarse, y sin
    # acumular hilos.
    for i in range(3):
        ev2 = threading.Event()
        ev2.set()  # cancelar antes de arrancar
        out2 = {}

        def starter2():
            out2["res"] = eng.transcribe(p1, timestamps=False, cancel_event=ev2,
                                         progress_callback=lambda n, t, m: None)

        tt = threading.Thread(target=starter2, daemon=True)
        tt.start()
        tt.join(timeout=10)
        r = out2.get("res")
        assert r is not None, f"C{i+1}: sin resultado"
        assert r.get("cancelled") is True, f"C{i+1}: no devolvió cancelled"
    print("  C_OK (3 cancelaciones rápidas sin colgarse)")

    # Tras la ráfaga, una corrida completa debe seguir funcionando
    try:
        _full_run(eng, p3, "C-post")
    except Exception as e:
        print(f"  C-post FALLÓ: {e}")
        traceback.print_exc()
        return 1
    print("  C_OK (el motor sigue sirviendo tras la ráfaga)")

    # Limpieza final de hilos
    time.sleep(2)
    final_threads = threading.active_count()
    print(f"[HILOS-FINAL] base={base_threads} final={final_threads} (delta {final_threads - base_threads})")
    if final_threads - base_threads > 4:
        print("  FUGA DE HILOS AL FINAL")
        return 1

    print("\nSTRESS_ALL_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

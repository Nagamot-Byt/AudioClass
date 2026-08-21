# -*- coding: utf-8 -*-
"""diagnostico_mic.py — Diagnóstico completo del micrófono para AudioClass.

Ejecuta:
  python diagnostico_mic.py          (diagnóstico interactivo)
  python diagnostico_mic.py --quick  (solo enum + nivel, 3 segundos)

Prueba:
  1. Enumeración de dispositivos de entrada
  2. Dispositivo por defecto del sistema
  3. Configuración de formato (sample rate, channels, dtype)
  4. Grabación real de 3 segundos
  5. Cálculo de nivel (RMS, p90, peak)
  6. Verificación de silencio digital vs nivel real
"""
import sys
import time
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("[FATAL] sounddevice no instalado. Ejecuta: pip install sounddevice")
    sys.exit(1)


def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def step1_enumerate():
    """Paso 1: Enumerar todos los dispositivos de entrada."""
    separator("PASO 1: Enumeración de dispositivos de entrada")
    try:
        devs = sd.query_devices()
        hostapis = sd.query_hostapis()
        print(f"Host APIs disponibles: {len(hostapis)}")
        for i, ha in enumerate(hostapis):
            n_devs = len(ha.get('devices', []))
            print(f"  [{i}] {ha['name']} ({n_devs} dispositivos)")
        
        print(f"\nDispositivos totales: {len(devs)}")
        input_devs = []
        for i, d in enumerate(devs):
            if d["max_input_channels"] >= 1:
                api_idx = d.get("hostapi", -1)
                api_name = hostapis[api_idx]["name"] if api_idx < len(hostapis) else "?"
                print(f"  [{i:2d}] {d['name']}")
                print(f"       Canales: {d['max_input_channels']} entr / {d['max_output_channels']} sal")
                print(f"       Sample rates: {d['default_samplerate']:.0f} Hz (default)")
                print(f"       Host API: {api_name}")
                input_devs.append((i, d["name"]))
        
        if not input_devs:
            print("\n[ERROR] No se encontraron dispositivos de entrada!")
            print("  Posibles causas:")
            print("  - No hay micrófono conectado")
            print("  - No hay driver de audio instalado")
            print("  - PortAudio no detecta los dispositivos")
            return None
        return input_devs
    except Exception as e:
        print(f"[ERROR] No se pudo enumerar dispositivos: {e}")
        return None


def step2_default_device():
    """Paso 2: Verificar el dispositivo por defecto."""
    separator("PASO 2: Dispositivo por defecto del sistema")
    try:
        default = sd.default.device[0]  # input device
        if default is None:
            print("  No hay dispositivo de entrada por defecto configurado")
            print("  sounddevice usará el primero que encuentre")
        else:
            info = sd.query_devices(default)
            print(f"  ID por defecto: {default}")
            print(f"  Nombre: {info['name']}")
            print(f"  Canales: {info['max_input_channels']}")
            print(f"  Sample rate: {info['default_samplerate']:.0f} Hz")
        return default
    except Exception as e:
        print(f"[ERROR] No se pudo obtener dispositivo por defecto: {e}")
        return None


def step3_check_settings(device_id=None):
    """Paso 3: Verificar configuración de formato."""
    separator("PASO 3: Verificación de formato de audio")
    sample_rate = 16000
    channels = 1
    dtype = "float32"
    
    configs_to_try = [
        (sample_rate, channels, dtype, "Estándar AudioClass"),
        (44100, channels, dtype, "44.1kHz"),
        (48000, channels, dtype, "48kHz"),
        (sample_rate, 2, dtype, "2 canales"),
    ]
    
    working_config = None
    for sr, ch, dt, desc in configs_to_try:
        try:
            sd.check_input_settings(device=device_id, samplerate=sr, channels=ch, dtype=dt)
            print(f"  [OK] {desc}: {sr}Hz, {ch}ch, {dt}")
            if working_config is None:
                working_config = (sr, ch, dt)
        except Exception as e:
            print(f"  [FAIL] {desc}: {e}")
    
    if working_config:
        print(f"\n  Configuración recomendada: {working_config[0]}Hz, {working_config[1]}ch, {working_config[2]}")
    else:
        print("\n[ERROR] Ninguna configuración de audio es válida!")
    return working_config


def step4_record_test(device_id=None, duration=3.0):
    """Paso 4: Grabación real de prueba."""
    separator(f"PASO 4: Grabación de prueba ({duration}s)")
    sample_rate = 16000
    channels = 1
    dtype = "float32"
    
    print(f"  Grabando {duration}s de audio...")
    print(f"  (Habla al micrófono o haz ruido)")
    
    try:
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=channels,
            dtype=dtype,
            device=device_id
        )
        sd.wait()
        
        if recording is None or len(recording) == 0:
            print("  [ERROR] La grabación devolvió datos vacíos")
            return None
        
        print(f"  Grabación completada: {len(recording)} muestras, {len(recording)/sample_rate:.1f}s")
        return recording.flatten()
    except Exception as e:
        print(f"[ERROR] No se pudo grabar: {e}")
        print("  Posibles causas:")
        print("  - Micrófono en uso por otra aplicación")
        print("  - Permisos de micrófono denegados (Windows Privacy)")
        print("  - Dispositivo no disponible")
        return None


def step5_analyze_audio(audio_data):
    """Paso 5: Análisis de nivel del audio grabado."""
    separator("PASO 5: Análisis de nivel de audio")
    
    if audio_data is None or len(audio_data) == 0:
        print("  No hay datos para analizar")
        return
    
    sample_rate = 16000
    win = int(0.1 * sample_rate)  # ventanas de 100ms
    
    # RMS por ventana
    frames = []
    for i in range(0, len(audio_data) - win, win // 2):
        chunk = audio_data[i:i+win]
        rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
        frames.append(rms)
    
    if not frames:
        print("  No se pudieron calcular ventanas")
        return
    
    rms_arr = np.array(frames)
    p50 = float(np.percentile(rms_arr, 50))
    p90 = float(np.percentile(rms_arr, 90))
    peak = float(np.max(np.abs(audio_data)))
    mean = float(np.mean(rms_arr))
    
    # Clasificación (misma que optimizar_mic.py)
    SILENCIO = 0.005
    DEBIL = 0.03
    
    if p90 < SILENCIO:
        verdict = "SILENCIO DIGITAL"
        verdict_color = "ROJO"
    elif p90 < DEBIL:
        verdict = "DÉBIL (posible problema)"
        verdict_color = "AMARILLO"
    else:
        verdict = "OK (nivel adecuado)"
        verdict_color = "VERDE"
    
    # dB
    def to_db(v):
        if v <= 0:
            return -120
        return 20 * np.log10(v)
    
    print(f"  RMS medio:  {mean:.4f} ({to_db(mean):.1f} dB)")
    print(f"  RMS p50:    {p50:.4f} ({to_db(p50):.1f} dB)")
    print(f"  RMS p90:    {p90:.4f} ({to_db(p90):.1f} dB)")
    print(f"  Peak:       {peak:.4f} ({to_db(peak):.1f} dB)")
    print(f"  Muestras:   {len(rms_arr)} ventanas de 100ms")
    
    print(f"\n  VEREDICTO: {verdict} [{verdict_color}]")
    
    if verdict_color == "ROJO":
        print("\n  CAUSAS POSIBLES:")
        print("  1. El micrófono seleccionado no es el correcto")
        print("  2. El micrófono está mutado (hardware o software)")
        print("  3. El driver de audio no funciona correctamente")
        print("  4. Windows/OS ha denegado permisos de micrófono")
        print("  5. Otro programa está usando el micrófono exclusivamente")
        print("\n  SOLUCIONES:")
        print("  - Abre Configuración de AudioClass y selecciona otro micrófono")
        print("  - En Windows: Configuración > Privacidad > Micrófono > Permitir")
        print("  - Reinicia el servicio de audio: services.msc > Windows Audio")
        print("  - Prueba otro puerto USB si es micrófono externo")
    
    elif verdict_color == "AMARILLO":
        print("\n  RECOMENDACIONES:")
        print("  - Acércate más al micrófono")
        print("  - Verifica que no esté en modo silencio")
        print("  - Ajusta el nivel de entrada en Configuración de Sonido de Windows")
    
    return {
        "rms_mean": mean,
        "rms_p50": p50,
        "rms_p90": p90,
        "peak": peak,
        "verdict": verdict,
        "verdict_color": verdict_color,
        "frames": len(rms_arr),
    }


def step6_test_callback(device_id=None):
    """Paso 6: Probar el callback (como lo usa la app)."""
    separator("PASO 6: Prueba de callback (modo app)")
    sample_rate = 16000
    channels = 1
    dtype = "float32"
    win = 4096
    
    print("  Probando InputStream con callback (2 segundos)...")
    buf = []
    
    def cb(indata, frames, ti, status):
        if status:
            print(f"    Callback status: {status}")
        buf.append(indata.copy().flatten())
    
    try:
        with sd.InputStream(
            samplerate=sample_rate, channels=channels, dtype=dtype,
            blocksize=win, callback=cb, device=device_id
        ):
            time.sleep(2.0)
        
        if buf:
            raw = np.concatenate(buf).flatten()
            rms = float(np.sqrt(np.mean(raw.astype(np.float64) ** 2)))
            peak = float(np.max(np.abs(raw)))
            print(f"  [OK] Callback funcionó: {len(buf)} bloques, RMS={rms:.4f}, Peak={peak:.4f}")
        else:
            print("  [WARN] Callback no recibió datos (buffer vacío)")
    except Exception as e:
        print(f"  [ERROR] Callback falló: {e}")
        print("  Esto indica un problema con PortAudio o el driver de audio")


def main():
    print("=" * 60)
    print("  DIAGNÓSTICO DE MICRÓFONO — AudioClass v9.1")
    print("=" * 60)
    
    quick = "--quick" in sys.argv
    
    # Paso 1: Enumerar dispositivos
    input_devs = step1_enumerate()
    if not input_devs:
        print("\n[FATAL] No hay micrófonos disponibles. Revisa la conexión y drivers.")
        sys.exit(1)
    
    # Paso 2: Dispositivo por defecto
    default_id = step2_default_device()
    
    # Paso 3: Verificar configuración
    config = step3_check_settings(default_id)
    
    if not quick:
        # Paso 4: Grabación real
        audio = step4_record_test(default_id)
        
        # Paso 5: Análisis
        result = step5_analyze_audio(audio)
        
        # Paso 6: Callback
        step6_test_callback(default_id)
        
        # Resumen final
        separator("RESUMEN FINAL")
        if result:
            print(f"  Dispositivos de entrada: {len(input_devs)}")
            print(f"  Dispositivo usado: {'Por defecto' if default_id is None else default_id}")
            print(f"  Formato: 16000Hz, 1ch, float32")
            print(f"  Nivel p90: {result['rms_p90']:.4f} ({result['verdict']})")
            
            if result["verdict_color"] == "VERDE":
                print("\n  [OK] El micrófono funciona correctamente.")
                print("  Si AudioClass no graba, el problema puede estar en la configuración de la app.")
                print("  Abre AudioClass > Configuración y verifica que el micrófono seleccionado sea:")
                for dev_id, dev_name in input_devs[:5]:
                    print(f"    [{dev_id}] {dev_name}")
            else:
                print(f"\n  [PROBLEMA] El micrófono tiene nivel {result['verdict_color'].lower()}.")
                print("  Soluciones:")
                print("  1. Selecciona otro micrófono en Configuración de AudioClass")
                print("  2. Verifica permisos de micrófono en tu sistema operativo")
                print("  3. Prueba otro dispositivo de entrada")
    else:
        print("\n  Modo rápido: solo enumeración + configuración")
        print("  Para diagnóstico completo ejecuta sin --quick")


if __name__ == "__main__":
    main()

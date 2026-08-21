# -*- coding: utf-8 -*-
"""test_mic_detection.py — Test de auto-deteccion de microfono.

Verifica que _find_best_mic retorna un dispositivo valido cuando hay
microfonos disponibles, y que la funcion no crashea cuando no los hay.

Ejecucion:
    python test_mic_detection.py
"""
import sys
import os
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

passed = 0
failed = 0
total = 0


def check(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  OK   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} -- {detail}")


# ── Imports ────────────────────────────────────────────────────────────────
print("=== test_mic_detection ===\n")

try:
    from audioclass_v91 import _find_best_mic, _input_devices, _mic_device_id_for
    check("imports OK", True)
except Exception as e:
    check("imports OK", False, str(e))
    print(f"\nMIC_DETECTION_FAIL (imports failed)")
    sys.exit(1)

import sounddevice as sd
import numpy as np


# ── Test 1: _find_best_mic retorna tupla (int|None, float) ────────────────
print("\n-- Formato de retorno --")
result = _find_best_mic()
check("retorna tupla", isinstance(result, tuple), f"tipo={type(result)}")
check("longitud 2", len(result) == 2, f"len={len(result)}")
check("primer elemento int o None", result[0] is None or isinstance(result[0], (int, np.integer)),
      f"tipo={type(result[0])}")
check("segundo elemento float", isinstance(result[1], (float, np.floating)),
      f"tipo={type(result[1])}")


# ── Test 2: Si hay dispositivos de entrada, el id es valido ───────────────
print("\n-- Dispositivos --")
devs = _input_devices()
check("lista dispositivos no vacia", len(devs) > 0, f"count={len(devs)}")

if result[0] is not None:
    all_devs = sd.query_devices()
    check("id dentro de rango", 0 <= result[0] < len(all_devs),
          f"id={result[0]}, total={len(all_devs)}")
    if 0 <= result[0] < len(all_devs):
        d = all_devs[result[0]]
        check("dispositivo es entrada", d["max_input_channels"] >= 1,
              f"ch={d['max_input_channels']}")
        name = str(d["name"])
        check("tiene nombre", len(name) > 0, f"name={name!r}")
        # No debe ser un altavoz/speaker
        check("no es altavoz", "altavoz" not in name.lower() and "speaker" not in name.lower(),
              f"name={name!r}")
else:
    check("sin dispositivos: None aceptado", result[0] is None)


# ── Test 3: p90 >= 0 ──────────────────────────────────────────────────────
print("\n-- Nivel p90 --")
check("p90 >= 0", result[1] >= 0.0, f"p90={result[1]}")
check("p90 razonable (< 100)", result[1] < 100.0, f"p90={result[1]}")


# ── Test 4: _find_best_mic con config mock (sin mic real) ──────────────────
print("\n-- Fallback sin dispositivos --")
# _mic_device_id_for con config vacia debe devolver None
dev_id = _mic_device_id_for({})
check("config vacia -> None", dev_id is None, f"dev_id={dev_id}")

dev_id2 = _mic_device_id_for({"mic_device": ""})
check("config string vacia -> None", dev_id2 is None, f"dev_id={dev_id2}")

dev_id3 = _mic_device_id_for({"mic_device": "Microfono Inexistente XYZ"})
check("mic inexistente -> None", dev_id3 is None, f"dev_id={dev_id3}")


# ── Test 5: _input_devices retorna lista de tuplas ─────────────────────────
print("\n-- _input_devices --")
check("lista", isinstance(devs, list), f"tipo={type(devs)}")
if devs:
    first = devs[0]
    check("tupla (id, nombre)", isinstance(first, tuple) and len(first) == 2,
          f"first={first}")
    check("id es int", isinstance(first[0], (int, np.integer)),
          f"id_type={type(first[0])}")
    check("nombre es str", isinstance(first[1], str),
          f"name_type={type(first[1])}")


# ── Test 6: _find_best_mic no crashea en multiples llamadas ──────────────
# (El nivel p90 fluctua entre llamadas, asi que solo validamos que el
# device_id sea valido y que la funcion no lanz excepciones.)
print("\n-- Estabilidad --")
all_devs = sd.query_devices()
for call_n in range(3):
    r = _find_best_mic()
    if r[0] is not None:
        d = all_devs[r[0]]
        check(f"llamada {call_n+1}: id valido",
              0 <= r[0] < len(all_devs) and d["max_input_channels"] >= 1,
              f"id={r[0]}")
    else:
        check(f"llamada {call_n+1}: None aceptado", True)


# ── Resultado ──────────────────────────────────────────────────────────────
print()
if failed == 0:
    print(f"MIC_DETECTION_OK ({passed}/{total})")
else:
    print(f"MIC_DETECTION_FAIL ({failed}/{total} failed)")
    sys.exit(1)

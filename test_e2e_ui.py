# -*- coding: utf-8 -*-
"""E2E de UI headless: corre los 4 escenarios (wizard, config, widgets, mic)
con el MISMO modo --e2e-ui que validan los exes en produccion. Es el ancla
de regresion para el flujo real de la interfaz sin depender de entrada
sintetica: cada escenario instancia la app completa, ejercita widgets y
callbacks, y reporta por archivo + exit code (PASS/FAIL)."""
import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIOS = ("wizard", "config", "widgets", "mic")

def main():
    ok_all = True
    for sc in SCENARIOS:
        out = os.path.join(HERE, f"_e2eui_{sc}.txt")
        for f in (out, os.path.join(HERE, "e2e_ui_error.txt")):
            if os.path.exists(f):
                os.remove(f)
        try:
            rc = subprocess.call([sys.executable, os.path.join(HERE, "audioclass_v91.py"),
                                  "--e2e-ui", sc, out], timeout=240)
        except subprocess.TimeoutExpired:
            rc = 124
        passed = rc == 0 and os.path.exists(out) and "PASS" in open(out, encoding="utf-8").read()
        print(f"{'OK  ' if passed else 'FAIL'} --e2e-ui {sc} (rc={rc})")
        if not passed:
            ok_all = False
            if os.path.exists(out):
                print(open(out, encoding="utf-8").read(), end="")
        else:
            os.remove(out)
    print("E2E_UI_OK" if ok_all else "E2E_UI_FAIL")
    return 0 if ok_all else 1

if __name__ == "__main__":
    sys.exit(main())

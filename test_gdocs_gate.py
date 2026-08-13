# -*- coding: utf-8 -*-
"""Test del gate de Google Docs (no disponible en el exe de distribucion).

En este entorno google-auth-oauthlib NO esta instalado, asi que la ruta
real es: boton desactivado con etiqueta clara + mensaje claro en
_export_docs y en la config. FALLA si el gate no bloquea o si el mensaje
no es claro; tambien verifica que con el componente disponible el flujo
sigue (no rompe la ruta habilitada).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import audioclass_v91 as ac

failures = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        failures.append(name)


# ── 1) Disponibilidad real en este entorno ────────────────────────────────────
v = ac._gdocs_importable()
check("_gdocs_importable devuelve bool", isinstance(v, bool), f"v={v!r}")
check("en este entorno sin oauth -> False", v is False)

# ── 2) Gate en _export_docs cuando NO disponible ─────────────────────────────
class Stub:
    def __init__(self):
        self.msgs = []
        self.last_text = "texto"   # si el gate no cortara, seguiria el flujo
        self.touched = False

    def _msg(self, kind, title, msg):
        self.msgs.append((kind, title, msg))


s = Stub()
ac.App._export_docs(s)            # no tiene docs_exporter: si el gate falla, AttributeError
check("gate corta sin tocar el exportador", len(s.msgs) == 1 and s.last_text == "texto",
      str(s.msgs))
check("mensaje menciona 'no disponible'", any("no está disponible" in m[2] for m in s.msgs))
check("mensaje menciona google-auth-oauthlib",
      any("google-auth-oauthlib" in m[2] for m in s.msgs))

# ── 3) Con el componente disponible, el gate deja pasar ───────────────────────
class Stub2:
    def __init__(self):
        self.msgs = []
        self.last_text = ""

    def _msg(self, kind, title, msg):
        self.msgs.append((kind, title, msg))


s2 = Stub2()
orig = ac._gdocs_importable
ac._gdocs_importable = lambda: True
try:
    ac.App._export_docs(s2)
finally:
    ac._gdocs_importable = orig
check("con componente disponible sigue al flujo (Sin contenido)",
      any(m[1] == "Sin contenido" for m in s2.msgs), str(s2.msgs))

print()
if failures:
    print(f"RESULTADO: GDOCS_GATE FAIL ({len(failures)} fallos)")
    sys.exit(1)
print("RESULTADO: GDOCS_GATE_OK")

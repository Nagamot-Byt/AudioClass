# -*- coding: utf-8 -*-
"""test_colab_server_security.py — Endurecimiento del servidor Colab.

Verifica con stubs ligeros (sin GPU ni instalar fastapi):
  1. /download rechaza path traversal (../ fuera de TEMP_DIR).
  2. La clave se acepta por header X-API-Key y se rechaza la invalida.
  3. Rate limit: >30 peticiones por ventana por clave -> 429.
  4. Tope de tamano de subida: archivo grande -> 413.
  5. Las URLs generadas por /compile NO llevan la clave (?key= desaparece).

Ejecutar:  python test_colab_server_security.py
"""
import asyncio, importlib.util, os, sys, types, tempfile
from pathlib import Path

# ── Stubs de dependencias pesadas (whisper/torch/fpdf/fastapi) ───────────────
def _mkmod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m

# whisper: solo hace falta load_model() -> objeto con transcribe()
def _load_model(*a, **k):
    m = types.SimpleNamespace()
    m.transcribe = lambda *a2, **k2: {"text": "prueba", "segments": [{"start": 0.0, "end": 1.0}]}
    m.to = lambda d: m
    return m

_mkmod("whisper", load_model=_load_model)
_Tensor = type("Tensor", (), {})
_mkmod("torch", cuda=types.SimpleNamespace(is_available=lambda: False), Tensor=_Tensor)

# fpdf: stub minimo (generate_pdf no se ejecuta en estos tests)
class _FPDF:
    def __getattr__(self, name):
        return lambda *a, **k: None
_mkmod("fpdf", FPDF=_FPDF)

# fastapi: FastAPI con decoradores get/post que guardan los handlers,
# HTTPException, respuestas y middleware.
class HTTPException(Exception):
    def __init__(self, status_code=500, detail=""):
        self.status_code, self.detail = status_code, detail
        super().__init__(detail)

class _FastAPI:
    def __init__(self, *a, **k):
        self.handlers = {}
    def add_middleware(self, *a, **k):
        pass
    def _route(self, method, path):
        def deco(fn):
            self.handlers[(method, path)] = fn
            return fn
        return deco
    def get(self, path):
        return self._route("GET", path)
    def post(self, path):
        return self._route("POST", path)

fastapi = _mkmod("fastapi", FastAPI=_FastAPI, HTTPException=HTTPException,
                 File=lambda *a, **k: "FILE", Form=lambda *a, **k: "FORM",
                 UploadFile=object, Request=object)
_mkmod("fastapi.responses",
       JSONResponse=type("JSONResponse", (), {"__init__": lambda self, d, **k: setattr(self, "data", d)}),
       FileResponse=type("FileResponse", (), {"__init__": lambda self, p, filename=None: (setattr(self, "path", Path(p)), setattr(self, "filename", filename))[1]}))
_mkmod("fastapi.middleware.cors", CORSMiddleware=object)
_mkmod("uvicorn")
_mkmod("pyngrok", ngrok=types.SimpleNamespace(set_auth_token=lambda *a, **k: None,
                                              connect=lambda *a, **k: types.SimpleNamespace(public_url="http://localhost:8000")))

# ── Importar el servidor REAL con los stubs ───────────────────────────────────
SPEC = Path(__file__).parent / "audioclass_colab_server_v91.py"
spec = importlib.util.spec_from_file_location("colab_server_under_test", SPEC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# ── Helpers ───────────────────────────────────────────────────────────────────
class FakeRequest:
    def __init__(self, headers=None, query=None, form=None):
        self.headers = headers or {}
        self.query_params = query or {}
        self._form = form or {}
    async def form(self):
        return self._form

def run(coro):
    return asyncio.run(coro)

PASS = FAIL = 0
def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"OK  {name}")
    else:
        FAIL += 1
        print(f"FAIL {name}  {extra}")

# ── 1. Path traversal en /download ────────────────────────────────────────────
mod._rate_hits = {}
outside = Path(tempfile.gettempdir()) / "colab_test_secret.txt"
outside.write_text("TOP SECRET", encoding="utf-8")
rel = os.path.relpath(outside, mod.TEMP_DIR)  # contiene ../../
req = FakeRequest(headers={"X-API-Key": mod.API_KEY})
try:
    run(mod.download(req, file=rel))
    check("download rechaza path traversal", False, "devolvio archivo fuera de TEMP_DIR")
except HTTPException as e:
    check("download rechaza path traversal", e.status_code == 404, f"status={e.status_code}")

# 1b. Archivo legitimo DENTRO de TEMP_DIR si se descarga
mod.TEMP_DIR.mkdir(exist_ok=True)
legit = mod.TEMP_DIR / "compilado_test.txt"
legit.write_text("contenido", encoding="utf-8")
res = run(mod.download(req, file=legit.name))
check("download acepta archivo dentro de TEMP_DIR",
      str(Path(res.path).resolve()) == str(legit.resolve()),
      f"{res.path} != {legit}")

# ── 2. Clave por header X-API-Key ─────────────────────────────────────────────
mod._rate_hits = {}
try:
    run(mod.download(FakeRequest(headers={"X-API-Key": "clave-mala"}), file=legit.name))
    check("key invalida rechazada", False)
except HTTPException as e:
    check("key invalida rechazada", e.status_code == 403, f"status={e.status_code}")

try:
    run(mod.download(FakeRequest(), file=legit.name))
    check("sin key rechazada", False)
except HTTPException as e:
    check("sin key rechazada", e.status_code == 403, f"status={e.status_code}")

# ── 3. Rate limit por clave ───────────────────────────────────────────────────
mod._rate_hits = {}
raised = None
for i in range(mod._RATE_MAX + 1):
    try:
        mod._check_rate("clave-rate")
    except HTTPException as e:
        raised = e
        break
check("rate limit -> 429 tras el maximo", raised is not None and raised.status_code == 429,
      f"raised={raised}")

# ── 4. Tope de tamano de subida ───────────────────────────────────────────────
old_max = mod.MAX_UPLOAD_BYTES
mod.MAX_UPLOAD_BYTES = 1024  # 1 KB para el test
class FakeUpload:
    filename = "grande.wav"
    async def read(self, n):
        return b"x" * 2048  # 2 KB > 1 KB
try:
    run(mod._save_upload(FakeUpload()))
    check("tope de subida -> 413", False)
except HTTPException as e:
    check("tope de subida -> 413", e.status_code == 413, f"status={e.status_code}")
finally:
    mod.MAX_UPLOAD_BYTES = old_max

# ── 5. Las URLs generadas ya NO llevan la clave ───────────────────────────────
src = (SPEC).read_text(encoding="utf-8")
check("ninguna URL generada con &key=", "&key=" not in src,
      "aun se genera una URL con la clave")

# ── Limpieza ──────────────────────────────────────────────────────────────────
outside.unlink(missing_ok=True)
legit.unlink(missing_ok=True)
try:
    for f in mod.TEMP_DIR.glob("*"):
        f.unlink(missing_ok=True)
    mod.TEMP_DIR.rmdir()
except Exception:
    pass

print(f"\nCOLAB_SERVER_SECURITY: {PASS} OK, {FAIL} fallos")
sys.exit(0 if FAIL == 0 else 1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AudioClass Cloud Server v9.1 — Google Colab Edition
=====================================================
Servidor complementario para AudioClass v9.1 Desktop.
Soporta modelos Medium y Large-v3 de Whisper en GPU.

Instrucciones:
1. Cambia runtime a GPU (T4 o superior)
2. Ejecuta esta celda completa
3. Copia la URL de ngrok que aparece
4. Pegala en AudioClass Desktop → Configuracion → URL Colab
5. Copia la API Key que imprime y pegala en Configuracion → Clave Colab
   (la clave se lee de la variable de entorno COLAB_API_KEY; si no existe,
   se genera una ALEATORIA fuerte en cada arranque — ya no hay clave fija
   trivial).

Endpoints:
  POST /transcribe      → Audio → texto
  POST /transcribe_ts   → Audio → texto + timestamps
  POST /compile         → Compilar multiples transcripciones
  GET  /status          → Estado del servidor
"""

import subprocess, sys, os, json, warnings, tempfile, secrets, hmac
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import torch
import whisper
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pyngrok import ngrok
from scipy.io import wavfile
from scipy import signal
from fpdf import FPDF

# ─── Seguridad: API key ───────────────────────────────────────────────────────
# Ya NO hay clave fija trivial ('audioclass'): un servidor publico con clave
# adivinable dejaria que cualquiera transcribiera gratis. La clave se lee de
# la variable de entorno COLAB_API_KEY (>= 16 caracteres y no trivial) o se
# genera una ALEATORIA fuerte que el arranque imprime para copiarla a la app.
_TRIVIAL_KEYS = {"audioclass", "admin", "password", "1234", "test",
                  "audioclass123", "clave", "api_key", "secret"}


def _resolve_api_key():
    k = os.environ.get("COLAB_API_KEY", "").strip()
    if k:
        if len(k) < 16 or k.lower() in _TRIVIAL_KEYS:
            print(f"⚠️  COLAB_API_KEY rechazada ('{k}') — necesita >= 16 caracteres "
                  "y no ser trivial. Se generara una aleatoria.")
            k = ""
    if not k:
        k = secrets.token_urlsafe(24)
    return k


API_KEY = _resolve_api_key()
NGROK_TOKEN = ""                # ← PEGA AQUI TU TOKEN DE NGROK
MODEL_NAME = "large-v3"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
TEMP_DIR = Path("/tmp/audioclass_cloud")
TEMP_DIR.mkdir(exist_ok=True)

# ─── Fuente Unicode para PDF (DejaVu Sans) ────────────────────────────────────
# La fuente core "Arial" de fpdf2 es latin-1: los acentos y simbolos
# tipograficos (— • → …) salen como "?" o rompen el PDF. DejaVu Sans
# cubre todo el rango Unicode. Se busca en el sistema (Colab/Ubuntu suele
# traerla) y si no, se descarga una vez a TEMP_DIR.
PDF_FONT_PATH = None
PDF_FONT_BOLD = None

_PDF_FALLBACK_CHARS = {
    "—": "-", "–": "-", "…": "...", "•": "-", "→": "->",
    "├": "|", "└": "`", "“": '"', "”": '"', "‘": "'", "’": "'",
}


def _ensure_pdf_font():
    """Localiza DejaVu Sans (sistema o descargada a TEMP_DIR) y guarda las
    rutas globales. Devuelve True si hay fuente Unicode disponible."""
    global PDF_FONT_PATH, PDF_FONT_BOLD
    if PDF_FONT_PATH:
        return True
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans.ttf",
              str(TEMP_DIR / "DejaVuSans.ttf")):
        if os.path.exists(p):
            PDF_FONT_PATH = p
            b = os.path.join(os.path.dirname(p), "DejaVuSans-Bold.ttf")
            if os.path.exists(b):
                PDF_FONT_BOLD = b
            return True
    try:
        import urllib.request
        dest = TEMP_DIR / "DejaVuSans.ttf"
        urllib.request.urlretrieve(
            "https://cdn.jsdelivr.net/gh/py-pdf/fpdf2@master/test/fonts/DejaVuSans.ttf", dest)
        PDF_FONT_PATH = str(dest)
        bdest = TEMP_DIR / "DejaVuSans-Bold.ttf"
        urllib.request.urlretrieve(
            "https://cdn.jsdelivr.net/gh/py-pdf/fpdf2@master/test/fonts/DejaVuSans-Bold.ttf", bdest)
        PDF_FONT_BOLD = str(bdest)
        return True
    except Exception:
        return False


def _pdf_fallback_text(t):
    """Prepara el texto para la fuente core latin-1 (sin fuente Unicode):
    sustituye los simbolos tipograficos por ASCII y descarta el resto."""
    for k, v in _PDF_FALLBACK_CHARS.items():
        t = t.replace(k, v)
    return t.encode("latin-1", "replace").decode("latin-1")

print(f"Dispositivo: {DEVICE.upper()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

print(f"Cargando Whisper {MODEL_NAME}...")
model = whisper.load_model(MODEL_NAME).to(DEVICE)
print(f"Modelo listo en {DEVICE.upper()}")

HISTORY = []

app = FastAPI(title="AudioClass Cloud v9.1", version="9.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Headers de seguridad básicos en TODAS las respuestas (endurecimiento web):
#   X-Content-Type-Options: nosniff          -> no adivinar el tipo MIME
#   X-Frame-Options: DENY                    -> no incrustar en iframes (clickjacking)
#   Referrer-Policy: strict-origin-when-cross-origin -> no filtrar la URL origen
#   Content-Security-Policy: default-src 'none'      -> API JSON pura, sin HTML/JS
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    )
    return resp

def verify_key(key: str):
    # Comparacion en tiempo constante (evita medir la longitud con timing).
    if not hmac.compare_digest(str(key or ""), API_KEY):
        raise HTTPException(status_code=403, detail="API key invalida")

async def get_key(request: Request) -> str:
    """Lee la clave con prioridad: header X-API-Key (recomendado, NO filtra a
    logs/historial), luego query string y luego form (compatibilidad con
    clientes antiguos)."""
    k = request.headers.get("X-API-Key")
    if k:
        return k
    q = request.query_params.get("key")
    if q:
        return q
    try:
        form = await request.form()
        fk = form.get("key")
        if fk:
            return fk
    except Exception:
        pass
    return ""

# Rate limit simple en memoria por clave: un tunel publico con la key no debe
# permitir abuso (coste de Colab, almacenamiento, fuerza bruta).
_RATE_WINDOW = 60.0   # segundos
_RATE_MAX = 30        # peticiones por ventana por clave
_rate_hits = {}

def _check_rate(key: str):
    now = datetime.now().timestamp()
    hits = [t for t in _rate_hits.get(key, []) if now - t < _RATE_WINDOW]
    if len(hits) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="Demasiadas peticiones. Espera un momento.")
    hits.append(now)
    _rate_hits[key] = hits

MAX_UPLOAD_MB = 200
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

async def _save_upload(file: UploadFile) -> str:
    """Guarda la subida en TEMP_DIR con tope de tamano (evita llenar el disco
    del servidor con un archivo enorme)."""
    suffix = Path(file.filename).suffix or ".wav"
    tmp = TEMP_DIR / f"upload_{datetime.now().strftime('%H%M%S%f')}{suffix}"
    size = 0
    with open(tmp, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                f.close()
                tmp.unlink(missing_ok=True)
                raise HTTPException(status_code=413,
                                    detail=f"Archivo demasiado grande (maximo {MAX_UPLOAD_MB} MB)")
            f.write(chunk)
    return str(tmp)

def preprocess_for_whisper(path: str) -> str:
    sr, data = wavfile.read(path)
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    else:
        data = data.astype(np.float32)

    if len(data.shape) > 1:
        data = np.mean(data, axis=1)

    if sr != 16000:
        num_samples = int(len(data) * 16000 / sr)
        data = signal.resample(data, num_samples)

    peak = np.max(np.abs(data))
    if peak > 0:
        data = data * (0.95 / peak)

    out_path = str(TEMP_DIR / f"proc_{datetime.now().strftime('%H%M%S%f')}.wav")
    wavfile.write(out_path, 16000, (data * 32767).astype(np.int16))
    return out_path

def transcribe_audio(path: str, timestamps: bool = False, language: str = "es"):
    proc_path = preprocess_for_whisper(path)

    # Idioma: "auto" deja que whisper detecte el idioma del audio solo
    # (language=None + sin initial_prompt en espanol, que sesgaria la salida);
    # cualquier otro valor es un codigo ISO (es, en, pt, ...) que se fuerza.
    lang = (language or "es").strip().lower()
    if lang == "auto":
        lang_kw = {"language": None, "initial_prompt": None}
    else:
        lang_kw = {
            "language": lang,
            "initial_prompt": (
                "Esta es una transcripcion de una clase universitaria o conferencia academica en espanol. "
                "El orador principal es el docente o conferencista. "
                "Ignora murmullos de fondo, interrupciones breves y preguntas sin respuesta del docente. "
                "Preserva datos duros: numeros, fechas, dosis, nomenclaturas tecnicas y definiciones literales exactas. "
                "Transcribe fielmente solo lo dicho por el orador principal."
                if lang == "es" else
                "This is a transcription of a university lecture or academic conference. "
                "The main speaker is the lecturer or presenter. "
                "Ignore background murmurs, brief interruptions and unanswered questions. "
                "Preserve hard facts: numbers, dates, dosages, technical terms and literal definitions. "
                "Transcribe faithfully only what the main speaker said."
            ),
        }

    result = model.transcribe(
        proc_path,
        task="transcribe",
        fp16=(DEVICE == "cuda"),
        verbose=False,
        condition_on_previous_text=True,
        **lang_kw
    )

    text = result.get("text", "").strip()
    segments = result.get("segments", [])

    response = {
        "text": text,
        "model": MODEL_NAME,
        "device": DEVICE,
        "duration": segments[-1]["end"] if segments else 0,
        "segments_count": len(segments)
    }

    if timestamps:
        response["segments"] = [
            {"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()}
            for s in segments
        ]

    os.remove(proc_path)
    return response

def generate_pdf(text: str, title: str = "Transcripcion", timestamps_data=None) -> str:
    pdf = FPDF()
    uni = _ensure_pdf_font()
    if uni:
        pdf.add_font("Uni", "", PDF_FONT_PATH)
        if PDF_FONT_BOLD:
            pdf.add_font("Uni", "B", PDF_FONT_BOLD)
    fam = "Uni" if uni else "Arial"
    has_bold = bool(PDF_FONT_BOLD) if uni else True
    tit_style = "B" if has_bold else ""
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font(fam, tit_style, 20)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 15, title, ln=True, align="C")
    pdf.ln(2)
    pdf.set_font(fam, "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.cell(0, 8, f"Modelo: Whisper {MODEL_NAME} ({DEVICE.upper()})", ln=True, align="C")
    pdf.cell(0, 8, "Transcripcion automatica - puede contener errores. No constituye acta oficial.", ln=True, align="C")
    pdf.ln(5)
    pdf.set_draw_color(14, 165, 233)
    pdf.set_line_width(0.8)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)
    pdf.set_font(fam, "", 11)
    pdf.set_text_color(30, 30, 30)

    if timestamps_data:
        for seg in timestamps_data:
            ts = str(timedelta(seconds=int(seg["start"])))[2:]
            te = str(timedelta(seconds=int(seg["end"])))[2:]
            pdf.set_font(fam, tit_style, 10)
            pdf.set_text_color(14, 165, 233)
            pdf.cell(0, 7, f"[{ts} - {te}]", ln=True)
            pdf.set_font(fam, "", 11)
            pdf.set_text_color(30, 30, 30)
            txt = seg["text"] if uni else _pdf_fallback_text(seg["text"])
            pdf.multi_cell(0, 6.5, txt)
            pdf.ln(2)
    else:
        t = text if uni else _pdf_fallback_text(text)
        pdf.multi_cell(0, 7, t)

    out = str(TEMP_DIR / f"trans_{datetime.now().strftime('%H%M%S')}.pdf")
    pdf.output(out)
    return out

@app.get("/status")
def status():
    return {
        "status": "online",
        "model": MODEL_NAME,
        "device": DEVICE,
        "cuda_available": torch.cuda.is_available(),
        "cuda_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "version": "9.1"
    }

@app.post("/transcribe")
async def transcribe(request: Request, file: UploadFile = File(...),
                     language: str = Form("es")):
    key = await get_key(request)
    verify_key(key)
    _check_rate(key)
    tmp = await _save_upload(file)

    try:
        result = transcribe_audio(str(tmp), timestamps=False, language=language)
        result["filename"] = file.filename
        result["processed_at"] = datetime.now().isoformat()
        HISTORY.append({"type": "transcription", "filename": file.filename, "text": result["text"], "model": MODEL_NAME, "time": datetime.now().isoformat()})
        os.remove(tmp)
        return JSONResponse(result)
    except Exception as e:
        os.remove(tmp)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe_ts")
async def transcribe_ts(request: Request, file: UploadFile = File(...),
                        language: str = Form("es")):
    key = await get_key(request)
    verify_key(key)
    _check_rate(key)
    tmp = await _save_upload(file)

    try:
        result = transcribe_audio(str(tmp), timestamps=True, language=language)
        result["filename"] = file.filename
        result["processed_at"] = datetime.now().isoformat()
        HISTORY.append({"type": "transcription_ts", "filename": file.filename, "text": result["text"], "segments": result.get("segments", []), "model": MODEL_NAME, "time": datetime.now().isoformat()})
        os.remove(tmp)
        return JSONResponse(result)
    except Exception as e:
        os.remove(tmp)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compile")
async def compile_transcriptions(request: Request, title: str = Form("Compilacion de Clases"), mode: str = Form("full")):
    key = await get_key(request)
    verify_key(key)
    _check_rate(key)
    if not HISTORY:
        raise HTTPException(status_code=400, detail="No hay transcripciones en el historial")

    compiled = []
    for i, h in enumerate(HISTORY, 1):
        if h["type"] in ("transcription", "transcription_ts"):
            compiled.append(f"\n{'='*60}\nCLASE {i}: {h['filename']}\n{'='*60}\n\n{h['text']}\n")

    full_text = "\n".join(compiled)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    txt_path = str(TEMP_DIR / f"compilado_{ts}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"{title}\nCompilado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nModelo: Whisper {MODEL_NAME}\nTotal clases: {len(compiled)}\n{'='*60}\n\n")
        f.write(full_text)

    pdf_path = generate_pdf(full_text, title=title)

    return JSONResponse({
        "status": "compiled",
        "title": title,
        "classes_count": len(compiled),
        # La clave NUNCA va en la URL (se filtra a logs de ngrok/historial):
        # /download la exige via header X-API-Key (o query/form si el cliente
        # la anade explicitamente).
        "txt_url": f"/download?file={Path(txt_path).name}",
        "pdf_url": f"/download?file={Path(pdf_path).name}",
        "preview": full_text[:2000] + "..." if len(full_text) > 2000 else full_text
    })

@app.get("/download")
async def download(request: Request, file: str):
    key = await get_key(request)
    verify_key(key)
    _check_rate(key)
    # Anti path-traversal: el archivo debe quedar DENTRO de TEMP_DIR.
    base = TEMP_DIR.resolve()
    fpath = (TEMP_DIR / file).resolve()
    if not fpath.is_relative_to(base) or not fpath.exists() or not fpath.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(str(fpath), filename=fpath.name)

@app.get("/history")
async def get_history(request: Request):
    key = await get_key(request)
    verify_key(key)
    _check_rate(key)
    return JSONResponse({"history": HISTORY})

@app.post("/clear")
async def clear_history(request: Request):
    key = await get_key(request)
    verify_key(key)
    _check_rate(key)
    HISTORY.clear()
    for f in TEMP_DIR.glob("*"):
        try: f.unlink()
        except: pass
    return JSONResponse({"status": "cleared"})

if __name__ == "__main__":
    # Dependencias SOLO al ejecutar como script (no al importar como modulo).
    for pkg in ["fastapi", "uvicorn", "pyngrok", "python-multipart", "fpdf2", "openai-whisper", "torch", "numpy", "scipy"]:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])
    try:
        if NGROK_TOKEN:
            ngrok.set_auth_token(NGROK_TOKEN)
        else:
            print("⚠️  NGROK_TOKEN vacio: ngrok necesita un authtoken (gratis en ngrok.com).")
        public_url = ngrok.connect(8000).public_url
    except Exception as e:
        print("❌ No se pudo abrir el tunel de ngrok:", e)
        print("   Crea un authtoken gratuito en ngrok.com y pegalo en NGROK_TOKEN,")
        print("   o usa el servidor solo en local: http://localhost:8000")
        public_url = "http://localhost:8000"

    print("\n" + "="*60)
    print(f"SERVIDOR AUDIOCLASS CLOUD v9.1 ACTIVO")
    print(f"URL: {public_url}")
    print(f"API Key: {API_KEY}   ← copiala a AudioClass → Configuracion → Clave Colab")
    print(f"Modelo: {MODEL_NAME} | Dispositivo: {DEVICE.upper()}")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)

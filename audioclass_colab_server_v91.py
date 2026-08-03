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

Endpoints:
  POST /transcribe      → Audio → texto
  POST /transcribe_ts   → Audio → texto + timestamps
  POST /compile         → Compilar multiples transcripciones
  GET  /status          → Estado del servidor
"""

import subprocess, sys, os, json, warnings, tempfile
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

for pkg in ["fastapi", "uvicorn", "pyngrok", "python-multipart", "fpdf2", "openai-whisper", "torch", "numpy", "scipy"]:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

import numpy as np
import torch
import whisper
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pyngrok import ngrok
from scipy.io import wavfile
from scipy import signal
from fpdf import FPDF

API_KEY = "audioclass"
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

def verify_key(key: str):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="API key invalida")

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

def transcribe_audio(path: str, timestamps: bool = False):
    proc_path = preprocess_for_whisper(path)

    result = model.transcribe(
        proc_path,
        language="es",
        task="transcribe",
        fp16=(DEVICE == "cuda"),
        verbose=False,
        condition_on_previous_text=True,
        initial_prompt=(
            "Esta es una transcripcion de una clase universitaria o conferencia academica en espanol. "
            "El orador principal es el docente o conferencista. "
            "Ignora murmullos de fondo, interrupciones breves y preguntas sin respuesta del docente. "
            "Preserva datos duros: numeros, fechas, dosis, nomenclaturas tecnicas y definiciones literales exactas. "
            "Transcribe fielmente solo lo dicho por el orador principal."
        )
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
async def transcribe(file: UploadFile = File(...), key: str = Form(...)):
    verify_key(key)
    suffix = Path(file.filename).suffix or ".wav"
    tmp = TEMP_DIR / f"upload_{datetime.now().strftime('%H%M%S%f')}{suffix}"

    with open(tmp, "wb") as f:
        f.write(await file.read())

    try:
        result = transcribe_audio(str(tmp), timestamps=False)
        result["filename"] = file.filename
        result["processed_at"] = datetime.now().isoformat()
        HISTORY.append({"type": "transcription", "filename": file.filename, "text": result["text"], "model": MODEL_NAME, "time": datetime.now().isoformat()})
        os.remove(tmp)
        return JSONResponse(result)
    except Exception as e:
        os.remove(tmp)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe_ts")
async def transcribe_ts(file: UploadFile = File(...), key: str = Form(...)):
    verify_key(key)
    suffix = Path(file.filename).suffix or ".wav"
    tmp = TEMP_DIR / f"upload_{datetime.now().strftime('%H%M%S%f')}{suffix}"

    with open(tmp, "wb") as f:
        f.write(await file.read())

    try:
        result = transcribe_audio(str(tmp), timestamps=True)
        result["filename"] = file.filename
        result["processed_at"] = datetime.now().isoformat()
        HISTORY.append({"type": "transcription_ts", "filename": file.filename, "text": result["text"], "segments": result.get("segments", []), "model": MODEL_NAME, "time": datetime.now().isoformat()})
        os.remove(tmp)
        return JSONResponse(result)
    except Exception as e:
        os.remove(tmp)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compile")
async def compile_transcriptions(key: str = Form(...), title: str = Form("Compilacion de Clases"), mode: str = Form("full")):
    verify_key(key)
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
        "txt_url": f"/download?file={Path(txt_path).name}&key={key}",
        "pdf_url": f"/download?file={Path(pdf_path).name}&key={key}",
        "preview": full_text[:2000] + "..." if len(full_text) > 2000 else full_text
    })

@app.get("/download")
def download(file: str, key: str):
    verify_key(key)
    fpath = TEMP_DIR / file
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(str(fpath), filename=file)

@app.get("/history")
def get_history(key: str):
    verify_key(key)
    return JSONResponse({"history": HISTORY})

@app.post("/clear")
def clear_history(key: str):
    verify_key(key)
    HISTORY.clear()
    for f in TEMP_DIR.glob("*"):
        try: f.unlink()
        except: pass
    return JSONResponse({"status": "cleared"})

if __name__ == "__main__":
    if NGROK_TOKEN:
        ngrok.set_auth_token(NGROK_TOKEN)

    public_url = ngrok.connect(8000).public_url
    print("\n" + "="*60)
    print(f"SERVIDOR AUDIOCLASS CLOUD v9.1 ACTIVO")
    print(f"URL: {public_url}")
    print(f"API Key: {API_KEY}")
    print(f"Modelo: {MODEL_NAME} | Dispositivo: {DEVICE.upper()}")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)

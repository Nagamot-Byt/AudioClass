#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audioclass_server.py — Servidor de transcripción headless para AudioClass
==========================================================================

Servidor REST que ejecuta la pipeline de AudioClass sin GUI.
Ideal para ejecutar como servicio systemd en servidores Linux.

Endpoints:
  POST /transcribe          -> Transcribe un archivo de audio
  POST /transcribe/advanced -> Transcribe + adapta con IA (resumen, flashcards, etc.)
  GET  /status              -> Estado del servidor y modelos
  GET  /health              -> Health check para monitoreo
  GET  /models              -> Lista de modelos disponibles

Uso:
    # Desarrollo
    python audioclass_server.py --port 8000

    # Producción (con uvicorn)
    uvicorn audioclass_server:app --host 0.0.0.0 --port 8000 --workers 1

    # Como servicio systemd
    sudo systemctl start audioclass
"""
import argparse
import asyncio
import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Optional

# ── Verificar dependencias mínimas ───────────────────────────────────────────
try:
    from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Header, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError:
    print("ERROR: Dependencias del servidor no instaladas.")
    print("  pip install fastapi uvicorn python-multipart websockets")
    sys.exit(1)

import numpy as np

# ── Imports del core ─────────────────────────────────────────────────────────
try:
    from audioclass_core import (
        AudioPipeline, LocalWhisperEngine, GeminiAdaptationEngine,
        OpenAIAdaptationEngine, SAMPLE_RATE, CHANNELS, DTYPE,
    )
    from config_manager import load_config
except ImportError as e:
    print(f"ERROR: No se pudo importar el core: {e}")
    print("  Asegúrate de ejecutar desde la raíz del proyecto.")
    sys.exit(1)

# ── Configuración ────────────────────────────────────────────────────────────
CONFIG = load_config()
API_KEY = os.environ.get("AUDIOCLASS_API_KEY", CONFIG.get("server_api_key", ""))
HOST = os.environ.get("AUDIOCLASS_HOST", "0.0.0.0")
PORT = int(os.environ.get("AUDIOCLASS_PORT", "8000"))
MAX_UPLOAD_MB = int(os.environ.get("AUDIOCLASS_MAX_UPLOAD_MB", "200"))
RATE_LIMIT_PER_MIN = int(os.environ.get("AUDIOCLASS_RATE_LIMIT", "30"))

# ── App FastAPI ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="AudioClass Transcription Server",
    description="API REST para transcripción y adaptación de audio universitario",
    version="9.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Estado global ────────────────────────────────────────────────────────────
_pipeline = None
_local_engine = None
_adapt_engine_gemini = None
_adapt_engine_openai = None
_start_time = None
_request_count = 0
_rate_limits = {}  # ip -> [timestamps]


def _init_engines():
    """Inicializa los motores de transcripción y adaptación."""
    global _pipeline, _local_engine, _adapt_engine_gemini, _adapt_engine_openai

    print("Inicializando AudioPipeline...")
    _pipeline = AudioPipeline(
        profile=CONFIG.get("audio_profile", "Clase Universitaria"),
        fast_mode=False,
        use_vad=True,
    )

    print("Inicializando LocalWhisperEngine...")
    _local_engine = LocalWhisperEngine(
        model_size=CONFIG.get("local_model", "base"),
        device=CONFIG.get("whisper_device", "cpu"),
    )

    # Motores de adaptación (lazy: se cargan bajo demanda)
    gemini_key = CONFIG.get("gemini_api_key", "")
    openai_key = CONFIG.get("openai_api_key", "")

    if gemini_key:
        print("Inicializando GeminiAdaptationEngine...")
        _adapt_engine_gemini = GeminiAdaptationEngine(
            api_key=gemini_key,
            model=CONFIG.get("gemini_model", "flash"),
        )

    if openai_key:
        print("Inicializando OpenAIAdaptationEngine...")
        _adapt_engine_openai = OpenAIAdaptationEngine(
            api_key=openai_key,
            model=CONFIG.get("openai_model", "mini"),
        )

    print("Motores inicializados correctamente.")


# ── Seguridad ────────────────────────────────────────────────────────────────
def _check_api_key(authorization: Optional[str] = Header(None)):
    """Verifica la API key si está configurada."""
    if not API_KEY:
        return  # Sin key configurada: acceso abierto (desarrollo)

    if not authorization:
        raise HTTPException(status_code=401, detail="API key requerida")

    # Soportar "Bearer <key>" o solo "<key>"
    token = authorization.replace("Bearer ", "").strip()
    if not hmac.compare_digest(token, API_KEY):
        raise HTTPException(status_code=403, detail="API key inválida")


def _check_rate_limit(ip: str):
    """Rate limiting simple por IP."""
    now = time.time()
    if ip not in _rate_limits:
        _rate_limits[ip] = []

    # Limpiar timestamps viejos (>60s)
    _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < 60]

    if len(_rate_limits[ip]) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit: máximo {RATE_LIMIT_PER_MIN} requests/minuto"
        )

    _rate_limits[ip].append(now)


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Health check para monitoreo."""
    return {"status": "ok", "uptime": time.time() - _start_time if _start_time else 0}


@app.get("/status")
async def status(authorization: Optional[str] = Header(None)):
    """Estado del servidor y modelos."""
    _check_api_key(authorization)

    return {
        "status": "running",
        "version": "9.1.0",
        "uptime_seconds": time.time() - _start_time if _start_time else 0,
        "models": {
            "local": {
                "ready": _local_engine is not None and _local_engine.ready,
                "model": CONFIG.get("local_model", "base"),
                "device": CONFIG.get("whisper_device", "cpu"),
            },
            "gemini": {
                "configured": _adapt_engine_gemini is not None,
                "model": CONFIG.get("gemini_model", "flash"),
            },
            "openai": {
                "configured": _adapt_engine_openai is not None,
                "model": CONFIG.get("openai_model", "mini"),
            },
        },
        "pipeline_profile": CONFIG.get("audio_profile", "Clase Universitaria"),
        "requests_served": _request_count,
    }


@app.get("/models")
async def models(authorization: Optional[str] = Header(None)):
    """Lista de modelos disponibles."""
    _check_api_key(authorization)

    available = []
    if _local_engine and _local_engine.ready:
        available.append({
            "id": "local",
            "name": f"Local Whisper ({CONFIG.get('local_model', 'base')})",
            "type": "local",
            "requires_key": False,
        })
    if _adapt_engine_gemini:
        available.append({
            "id": "gemini",
            "name": "Gemini (Google AI)",
            "type": "adaptation",
            "requires_key": True,
        })
    if _adapt_engine_openai:
        available.append({
            "id": "openai",
            "name": "OpenAI (GPT)",
            "type": "adaptation",
            "requires_key": True,
        })

    return {"models": available}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    model: str = Form("local"),
    fast_mode: bool = Form(False),
    authorization: Optional[str] = Header(None),
):
    """Transcribe un archivo de audio.

    Args:
        file: Archivo de audio (WAV, MP3, FLAC, OGG).
        language: Código de idioma ISO 639-1 o "auto" para detección automática.
        model: Motor de transcripción ("local", "gemini", "openai").
        fast_mode: Si es True, usa modo rápido (menos procesamiento de audio).
    """
    global _request_count
    _check_api_key(authorization)

    # Rate limit
    client_ip = "unknown"  # En producción, extraer de X-Forwarded-For
    _check_rate_limit(client_ip)

    # Validar tamaño
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande: {size_mb:.1f}MB (máximo {MAX_UPLOAD_MB}MB)"
        )

    # Guardar archivo temporal
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        t0 = time.time()

        if model == "local":
            # Transcripción local
            if not _local_engine or not _local_engine.ready:
                raise HTTPException(status_code=503, detail="Motor local no disponible")

            text = _local_engine.transcribe(
                tmp_path,
                language=language if language != "auto" else None,
            )
            elapsed = time.time() - t0

        elif model in ("gemini", "openai"):
            # Transcripción en la nube
            engine = _adapt_engine_gemini if model == "gemini" else _adapt_engine_openai
            if not engine:
                raise HTTPException(
                    status_code=503,
                    detail=f"Motor {model} no configurado (falta API key)"
                )
            # Para motores cloud, primero transcribimos local y luego adaptamos
            if not _local_engine or not _local_engine.ready:
                raise HTTPException(status_code=503, detail="Motor local no disponible para pre-procesamiento")

            text = _local_engine.transcribe(
                tmp_path,
                language=language if language != "auto" else None,
            )
            elapsed = time.time() - t0

        else:
            raise HTTPException(status_code=400, detail=f"Modelo no soportado: {model}")

        _request_count += 1

        return {
            "success": True,
            "text": text,
            "model": model,
            "language": language,
            "duration_seconds": elapsed,
            "audio_size_mb": size_mb,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en transcripción: {str(e)[:200]}")
    finally:
        # Limpiar archivo temporal
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.post("/transcribe/advanced")
async def transcribe_advanced(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    template: str = Form("resumen"),
    provider: str = Form("gemini"),
    authorization: Optional[str] = Header(None),
):
    """Transcribe un audio y genera un análisis estructurado con IA.

    Args:
        file: Archivo de audio.
        language: Código de idioma ISO 639-1 o "auto".
        template: Tipo de análisis ("resumen", "flashcards", "examen", "guia", etc.).
        provider: Proveedor de IA para adaptación ("gemini", "openai").
    """
    global _request_count
    _check_api_key(authorization)
    _check_rate_limit("unknown")

    # Validar tamaño
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande: {size_mb:.1f}MB (máximo {MAX_UPLOAD_MB}MB)"
        )

    # Guardar archivo temporal
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        t0 = time.time()

        # Paso 1: Transcribir
        if not _local_engine or not _local_engine.ready:
            raise HTTPException(status_code=503, detail="Motor local no disponible")

        text = _local_engine.transcribe(
            tmp_path,
            language=language if language != "auto" else None,
        )
        t_transcribe = time.time() - t0

        # Paso 2: Adaptar con IA
        engine = _adapt_engine_gemini if provider == "gemini" else _adapt_engine_openai
        if not engine:
            raise HTTPException(
                status_code=503,
                detail=f"Proveedor {provider} no configurado (falta API key)"
            )

        adapted = engine.adapt(
            text,
            template=template,
            language=language if language != "auto" else "es",
        )
        t_adapt = time.time() - t0 - t_transcribe

        _request_count += 1

        return {
            "success": True,
            "transcription": text,
            "adaptation": adapted,
            "template": template,
            "provider": provider,
            "timing": {
                "transcribe_seconds": round(t_transcribe, 2),
                "adapt_seconds": round(t_adapt, 2),
                "total_seconds": round(time.time() - t0, 2),
            },
            "audio_size_mb": size_mb,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)[:200]}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# WebSocket: Transcripción en tiempo real
# ═══════════════════════════════════════════════════════════════════════════

# Buffer por conexión WebSocket
_ws_buffers = {}  # connection_id -> audio_buffer
_ws_connections = {}  # connection_id -> websocket


@app.websocket("/ws/transcribe")
async def websocket_transcribe(
    websocket: WebSocket,
    language: str = "auto",
    chunk_duration: float = 2.0,
):
    """WebSocket para transcripción en tiempo real.
    
    Protocolo:
      1. Cliente se conecta
      2. Servidor envía: {"type": "connected", "session_id": "..."}
      3. Cliente envía chunks de audio: {"type": "audio", "data": [float, ...]}
      4. Servidor envía resultados parciales: {"type": "partial", "text": "...", "is_final": false}
      5. Cliente envía fin: {"type": "end"}
      6. Servidor envía resultado final: {"type": "final", "text": "...", "duration": 1.23}
    
    Args:
        websocket: Conexión WebSocket.
        language: Código de idioma ISO 639-1 o "auto".
        chunk_duration: Duración del chunk en segundos para transcripción parcial.
    """
    import uuid
    import threading
    
    session_id = str(uuid.uuid4())[:8]
    _ws_connections[session_id] = websocket
    _ws_buffers[session_id] = []
    
    try:
        await websocket.accept()
        
        # Enviar confirmación de conexión
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "language": language,
            "chunk_duration": chunk_duration,
        })
        
        # Buffer acumulado para transcripción parcial
        accumulated_audio = []
        chunk_samples = int(chunk_duration * SAMPLE_RATE)
        last_transcription = ""
        
        while True:
            # Recibir mensaje
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            
            if msg_type == "audio":
                # Recibir chunk de audio
                audio_data = data.get("data", [])
                if audio_data:
                    audio_array = np.array(audio_data, dtype=np.float32)
                    accumulated_audio.extend(audio_data)
                    
                    # Transcribir parcialmente si hay suficiente audio
                    if len(accumulated_audio) >= chunk_samples:
                        # Transcribir el chunk actual
                        partial_audio = np.array(accumulated_audio[-chunk_samples:], dtype=np.float32)
                        
                        try:
                            # Guardar temporalmente
                            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                                from scipy.io import wavfile
                                wavfile.write(tmp.name, SAMPLE_RATE, (partial_audio * 32767).astype(np.int16))
                                
                                # Transcribir
                                if _local_engine and _local_engine.ready:
                                    partial_text = _local_engine.transcribe(
                                        tmp.name,
                                        language=language if language != "auto" else None,
                                    )
                                    
                                    # Enviar resultado parcial solo si cambió
                                    if partial_text != last_transcription:
                                        last_transcription = partial_text
                                        await websocket.send_json({
                                            "type": "partial",
                                            "text": partial_text,
                                            "is_final": False,
                                            "samples": len(accumulated_audio),
                                            "duration": len(accumulated_audio) / SAMPLE_RATE,
                                        })
                                
                                # Limpiar temporal
                                try:
                                    os.unlink(tmp.name)
                                except Exception:
                                    pass
                                    
                        except Exception as e:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Error en transcripción parcial: {str(e)[:100]}",
                            })
            
            elif msg_type == "end":
                # Fin de la transmisión - transcripción final
                if accumulated_audio:
                    try:
                        # Guardar audio completo
                        full_audio = np.array(accumulated_audio, dtype=np.float32)
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                            from scipy.io import wavfile
                            wavfile.write(tmp.name, SAMPLE_RATE, (full_audio * 32767).astype(np.int16))
                            
                            t0 = time.time()
                            if _local_engine and _local_engine.ready:
                                final_text = _local_engine.transcribe(
                                    tmp.name,
                                    language=language if language != "auto" else None,
                                )
                                elapsed = time.time() - t0
                                
                                await websocket.send_json({
                                    "type": "final",
                                    "text": final_text,
                                    "is_final": True,
                                    "samples": len(accumulated_audio),
                                    "duration": len(accumulated_audio) / SAMPLE_RATE,
                                    "processing_time": elapsed,
                                })
                            
                            try:
                                os.unlink(tmp.name)
                            except Exception:
                                pass
                                
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Error en transcripción final: {str(e)[:100]}",
                        })
                else:
                    await websocket.send_json({
                        "type": "final",
                        "text": "",
                        "is_final": True,
                        "samples": 0,
                        "duration": 0,
                    })
                
                # Limpiar
                accumulated_audio.clear()
                last_transcription = ""
            
            elif msg_type == "config":
                # Actualizar configuración de la sesión
                if "language" in data:
                    language = data["language"]
                if "chunk_duration" in data:
                    chunk_duration = data["chunk_duration"]
                    chunk_samples = int(chunk_duration * SAMPLE_RATE)
                
                await websocket.send_json({
                    "type": "config_updated",
                    "language": language,
                    "chunk_duration": chunk_duration,
                })
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Error de conexión: {str(e)[:100]}",
            })
        except Exception:
            pass
    finally:
        # Limpiar
        _ws_connections.pop(session_id, None)
        _ws_buffers.pop(session_id, None)


@app.websocket("/ws/stream")
async def websocket_stream(
    websocket: WebSocket,
    language: str = "auto",
):
    """WebSocket simplificado para streaming de audio bidireccional.
    
    Envía y recibe chunks de audio en formato binario.
    
    Protocolo:
      - Cliente envía: bytes de audio (float32, little-endian)
      - Servidor responde: JSON con texto parcial/final
    
    Más eficiente que /ws/transcribe para streaming de alta frecuencia.
    """
    import uuid
    
    session_id = str(uuid.uuid4())[:8]
    _ws_connections[session_id] = websocket
    
    try:
        await websocket.accept()
        await websocket.send_json({"type": "connected", "session_id": session_id})
        
        accumulated = []
        chunk_size = int(2.0 * SAMPLE_RATE)  # 2 segundos
        
        while True:
            # Recibir audio binario
            data = await websocket.receive_bytes()
            
            # Convertir bytes a numpy array
            audio_chunk = np.frombuffer(data, dtype=np.float32)
            accumulated.extend(audio_chunk.tolist())
            
            # Transcribir parcialmente
            if len(accumulated) >= chunk_size:
                try:
                    partial = np.array(accumulated[-chunk_size:], dtype=np.float32)
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        from scipy.io import wavfile
                        wavfile.write(tmp.name, SAMPLE_RATE, (partial * 32767).astype(np.int16))
                        
                        if _local_engine and _local_engine.ready:
                            text = _local_engine.transcribe(
                                tmp.name,
                                language=language if language != "auto" else None,
                            )
                            await websocket.send_json({
                                "type": "partial",
                                "text": text,
                                "is_final": False,
                            })
                        
                        try:
                            os.unlink(tmp.name)
                        except Exception:
                            pass
                except Exception:
                    pass
    
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _ws_connections.pop(session_id, None)


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AudioClass Transcription Server")
    parser.add_argument("--host", default=HOST, help="Host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=PORT, help="Port (default: 8000)")
    parser.add_argument("--workers", type=int, default=1, help="Workers (default: 1)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on changes")
    args = parser.parse_args()

    global _start_time
    _start_time = time.time()

    print(f"AudioClass Server v9.1.0")
    print(f"Host: {args.host}:{args.port}")
    print(f"API Key: {'configurada' if API_KEY else 'sin autenticación (desarrollo)'}")
    print()

    _init_engines()

    print()
    print(f"Servidor listo en http://{args.host}:{args.port}")
    print(f"Docs API: http://{args.host}:{args.port}/docs")
    print()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level="info",
    )


if __name__ == "__main__":
    main()

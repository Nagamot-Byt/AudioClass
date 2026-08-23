#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_client_example.py — Cliente WebSocket para transcripción en tiempo real
===========================================================================

Ejemplo de cliente que envía audio por WebSocket y recibe transcripciones
parciales en tiempo real.

Uso:
    # Transcribir un archivo de audio
    python ws_client_example.py audio.wav

    # Grabar del micrófono y transcribir en vivo
    python ws_client_example.py --mic

    # Conectar a servidor remoto
    python ws_client_example.py --host 192.168.1.100 --port 8000 audio.wav

Requisitos:
    pip install websockets sounddevice numpy scipy
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

try:
    import websockets
except ImportError:
    print("ERROR: websockets no instalado")
    print("  pip install websockets")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("ERROR: numpy no instalado")
    print("  pip install numpy")
    sys.exit(1)


async def transcribe_file(
    file_path: str,
    host: str = "localhost",
    port: int = 8000,
    language: str = "auto",
    chunk_duration: float = 2.0,
):
    """Transcribe un archivo de audio usando WebSocket."""
    from scipy.io import wavfile

    # Leer archivo de audio
    sr, audio = wavfile.read(file_path)

    # Convertir a float32 si es necesario
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32767.0
    elif audio.dtype == np.int32:
        audio = audio.astype(np.float32) / 2147483647.0

    # Si es estéreo, convertir a mono
    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)

    # Resamplear a 16kHz si es necesario
    if sr != 16000:
        from scipy.signal import resample
        num_samples = int(len(audio) * 16000 / sr)
        audio = resample(audio, num_samples)
        sr = 16000

    print(f"Archivo: {file_path}")
    print(f"Duración: {len(audio)/sr:.1f}s")
    print(f"Sample rate: {sr}Hz")
    print()

    # Conectar al WebSocket
    uri = f"ws://{host}:{port}/ws/transcribe?language={language}&chunk_duration={chunk_duration}"
    print(f"Conectando a {uri}...")

    async with websockets.connect(uri) as websocket:
        # Esperar confirmación de conexión
        response = await websocket.recv()
        data = json.loads(response)
        print(f"Conectado. Session: {data['session_id']}")
        print()

        # Enviar audio en chunks
        chunk_samples = int(chunk_duration * sr)
        total_chunks = len(audio) // chunk_samples + 1
        print(f"Enviando {total_chunks} chunks...")

        t0 = time.time()
        for i in range(0, len(audio), chunk_samples):
            chunk = audio[i:i + chunk_samples]
            chunk_data = chunk.tolist()

            await websocket.send_json({
                "type": "audio",
                "data": chunk_data,
            })

            # Esperar resultado parcial
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)

                if data["type"] == "partial":
                    elapsed = time.time() - t0
                    duration = data.get("duration", 0)
                    print(f"\r[{elapsed:.1f}s] {data['text']}", end="", flush=True)
                elif data["type"] == "error":
                    print(f"\nError: {data['message']}")

            except asyncio.TimeoutError:
                pass

        # Enviar fin de transmisión
        print("\n\nEnviando señal de fin...")
        await websocket.send_json({"type": "end"})

        # Esperar resultado final
        response = await websocket.recv()
        data = json.loads(response)

        if data["type"] == "final":
            elapsed = time.time() - t0
            print(f"\n{'='*60}")
            print(f"TRANSCRIPCIÓN COMPLETA")
            print(f"{'='*60}")
            print(data["text"])
            print(f"{'='*60}")
            print(f"Duración audio: {data.get('duration', 0):.1f}s")
            print(f"Tiempo procesamiento: {data.get('processing_time', elapsed):.1f}s")
            print(f"Tiempo total: {elapsed:.1f}s")


async def transcribe_microphone(
    host: str = "localhost",
    port: int = 8000,
    language: str = "auto",
    chunk_duration: float = 2.0,
):
    """Graba del micrófono y transcribe en tiempo real."""
    try:
        import sounddevice as sd
    except ImportError:
        print("ERROR: sounddevice no instalado")
        print("  pip install sounddevice")
        sys.exit(1)

    print("Grabando del micrófono... (Ctrl+C para detener)")
    print()

    uri = f"ws://{host}:{port}/ws/transcribe?language={language}&chunk_duration={chunk_duration}"

    async with websockets.connect(uri) as websocket:
        # Esperar confirmación
        response = await websocket.recv()
        data = json.loads(response)
        print(f"Conectado. Session: {data['session_id']}")
        print()

        # Configurar audio
        sr = 16000
        chunk_samples = int(chunk_duration * sr)
        buffer = []

        # Callback de audio
        def audio_callback(indata, frames, time_info, status):
            nonlocal buffer
            if status:
                print(f"Audio status: {status}")
            buffer.extend(indata[:, 0].tolist())

        # Iniciar grabación
        with sd.InputStream(samplerate=sr, channels=1, dtype="float32",
                           callback=audio_callback, blocksize=chunk_samples // 4):
            try:
                while True:
                    # Esperar suficiente audio
                    if len(buffer) >= chunk_samples:
                        chunk = buffer[:chunk_samples]
                        buffer = buffer[chunk_samples:]

                        # Enviar chunk
                        await websocket.send_json({
                            "type": "audio",
                            "data": chunk,
                        })

                        # Esperar resultado parcial
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                            data = json.loads(response)

                            if data["type"] == "partial":
                                print(f"\r💬 {data['text']}", end="", flush=True)

                        except asyncio.TimeoutError:
                            pass

                    await asyncio.sleep(0.1)

            except KeyboardInterrupt:
                print("\n\nDeteniendo grabación...")

            # Enviar fin
            await websocket.send_json({"type": "end"})

            # Esperar resultado final
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                if data["type"] == "final" and data["text"]:
                    print(f"\n{'='*60}")
                    print(f"TRANSCRIPCIÓN COMPLETA")
                    print(f"{'='*60}")
                    print(data["text"])
                    print(f"{'='*60}")
            except asyncio.TimeoutError:
                pass


def main():
    parser = argparse.ArgumentParser(
        description="Cliente WebSocket para transcripción en tiempo real"
    )
    parser.add_argument("file", nargs="?", help="Archivo de audio a transcribir")
    parser.add_argument("--mic", action="store_true", help="Grabar del micrófono")
    parser.add_argument("--host", default="localhost", help="Host del servidor")
    parser.add_argument("--port", type=int, default=8000, help="Puerto del servidor")
    parser.add_argument("--language", default="auto", help="Idioma (auto, es, en, pt)")
    parser.add_argument("--chunk", type=float, default=2.0, help="Duración del chunk en segundos")
    args = parser.parse_args()

    if not args.file and not args.mic:
        parser.print_help()
        sys.exit(1)

    if args.mic:
        asyncio.run(transcribe_microphone(
            args.host, args.port, args.language, args.chunk
        ))
    else:
        if not os.path.exists(args.file):
            print(f"Error: Archivo no encontrado: {args.file}")
            sys.exit(1)
        asyncio.run(transcribe_file(
            args.file, args.host, args.port, args.language, args.chunk
        ))


if __name__ == "__main__":
    main()

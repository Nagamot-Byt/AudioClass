# TERCEROS Y LICENCIAS — AudioClass v9.1

AudioClass se distribuye como exe autocontenido (onefile/onedir) que **empaqueta**
las bibliotecas de terceros listadas abajo. La lista se verificó contra el build
real (`dist/AudioClass/_internal` + PYZ) del commit `2c1405c` (17 agosto 2026).

> **Importante:** este aviso de atribución es un requisito de las licencias
> MIT/BSD/Apache/MPL (incluir el aviso de copyright). Su ausencia es una vía de
> reclamación por incumplimiento de licencia — por eso se distribuye con la app
> y las licencias originales viajan además dentro del bundle (`*.dist-info`).

## 1. Dependencias directas (usadas por el código de AudioClass, empaquetadas)

| Biblioteca | Licencia | Uso en AudioClass |
|---|---|---|
| customtkinter | MIT (© Tom Schimansky) | Interfaz gráfica |
| numpy | BSD-3-Clause | Cálculo numérico / audio |
| scipy | BSD-3-Clause | Procesado de señal (VAD, filtros) |
| sounddevice | MIT (© Matthias Geier) | Captura de micrófono |
| openai-whisper | MIT (© OpenAI) | Transcripción local (modelos .pt) |
| faster-whisper | MIT (© Guillaume Klein) | Backend CT2 de transcripción |
| ctranslate2 | MIT | Motor de inferencia de faster-whisper |
| torch | BSD-3-Clause | Motor de whisper |
| noisereduce | MIT (© Tim Sainburg) | Reducción de ruido |
| matplotlib | Licencia Matplotlib (estilo BSD, basada en PSF) | Gráficas / visualización |
| fpdf2 | LGPL-3.0-only | Exportación PDF |
| requests | Apache-2.0 | Llamadas a APIs (Gemini/OpenAI/Colab) |

## 2. Dependencias transitivas empaquetadas (vienen con las anteriores)

| Biblioteca | Licencia | Viene con |
|---|---|---|
| Pillow (PIL) | MIT-CMU (Pillow) | matplotlib / exportación |
| PyAV (av) | BSD-3-Clause | Procesado de video/audio |
| PyYAML (yaml) | MIT | huggingface_hub / config |
| onnxruntime | MIT | faster-whisper (optimización) |
| tiktoken | MIT | tokenización |
| tokenizers | Apache-2.0 | tokenización (Hugging Face) |
| huggingface_hub | Apache-2.0 | descarga de modelos |
| hf_xet | Apache-2.0 | transferencia rápida (HF) |
| fsspec | BSD-3-Clause | huggingface_hub |
| filelock | MIT | huggingface_hub / torch |
| urllib3 | MIT | requests |
| idna | BSD-3-Clause | requests |
| charset_normalizer | MIT | requests |
| certifi | MPL-2.0 | requests |
| click | BSD-3-Clause | CLI / herramientas |
| python-dateutil | Apache-2.0 / BSD-3-Clause (dual) | matplotlib |
| contourpy | BSD-3-Clause | matplotlib |
| kiwisolver | BSD-3-Clause (Modified BSD) | matplotlib |
| fontTools | MIT | fuentes PDF |
| numba | BSD-2-Clause | compilación JIT |
| llvmlite | BSD-2-Clause + Apache-2.0 WITH LLVM-exception | numba |
| regex | Apache-2.0 + CNRI-Python | tokenización |
| markupsafe | BSD-3-Clause | jinja2 / tiktoken |
| jinja2 | BSD-3-Clause | torch / empaquetado |
| setuptools | MIT | runtime |
| sympy | BSD | torch (gráficos simbólicos) |
| mpmath | BSD-3-Clause | sympy |
| networkx | BSD-3-Clause | torch |
| joblib | BSD-3-Clause | numba / scipy |
| anyio | MIT | httpx |
| httpx | BSD-3-Clause | huggingface_hub |
| httpcore | BSD-3-Clause | httpx |
| h11 | MIT | httpcore |
| cffi | MIT | PyAV / llvmlite |
| packaging | Apache-2.0 / BSD-2-Clause | varios |
| pyparsing | MIT | matplotlib |
| defusedxml | PSF / MIT | procesado XML seguro |
| tqdm | MPL-2.0 AND MIT | barras de progreso |
| Tcl/Tk (tcl8, _tcl_data, _tk_data) | Licencia Tcl/Tk (estilo BSD) | runtime tkinter de la GUI |
| win32 / pywin32 | PSF + BSD (pywin32) | integración Windows |

## 3. Solo en modo desarrollo (NO se empaquetan en el exe)

| Biblioteca | Licencia | Uso |
|---|---|---|
| PyInstaller | GPL-2.0 con excepción del bootloader (permite empaquetar apps propietarias) | Herramienta de build del exe |
| google-api-python-client | Apache-2.0 | Exportación a Google Docs (desde el fuente) |
| google-auth / google-auth-oauthlib | Apache-2.0 | Autenticación Google (desde el fuente) |

## Notas legales

1. **Copyleft en el bundle y por qué no obliga a liberar AudioClass:**
   - `fpdf2` es **LGPL-3.0-only**: permite distribuir obras combinadas (el exe) si
     se conserva el aviso, se indica la modificación y la biblioteca sigue siendo
     sustituible (su código fuente es público). No obliga a licenciar la app.
   - `tqdm` y `certifi` son **MPL-2.0** (copyleft a nivel de archivo): se cumple
     conservando sus avisos, que ya viajan en el bundle (`*.dist-info/licenses`).
   - Ninguna dependencia GPL/AGPL se distribuye ni se enlaza. Esto cierra la vía
     de demanda más citada contra apps generadas con IA (código copiado con
     licencia GPL).
2. **customtkinter:** el METADATA de PyPI declara CC0-1.0, pero el archivo LICENSE
   del paquete es **MIT (© 2023 Tom Schimansky)** — se atribuye según el LICENSE
   real distribuido.
3. **El código de AudioClass es del autor** (generado con asistencia de IA). El
   copyright de código generado por IA está en disputa legal; la práctica
   recomendada es documentar autoría y licenciar explícitamente (ver
   `LICENCIA.txt`).
4. **Modelos de IA:** whisper (MIT) y los modelos CT2 (`models_ct2/`) se
   distribuyen bajo sus propios términos (MIT/BSD). Los modelos se empaquetan
   para que la transcripción funcione sin internet.

## Verificación

- Lista auditada contra el build onedir del commit `2c1405c`:
  `dist/AudioClass/_internal` (122 entradas, incluidas las `*.dist-info` con sus
  licencias) + módulos del PYZ (torch, sympy, scipy, numba, networkx, fontTools,
  huggingface_hub, matplotlib, Pillow, fsspec, fpdf, requests, whisper, etc.).
- Licencias confirmadas desde los archivos LICENSE/METADATA de las mismas
  versiones empaquetadas en el entorno de build.
- `requirements_v91.txt` lista las dependencias en modo desarrollo.
- El exe onefile/onedir empaqueta las bibliotecas anteriores (verificado en el
  despliegue: `desplegar_produccion.sh`).

# 🎙️ AudioClass v9.1 — Progreso de Auditoría (31 julio 2026)

> Documento de recuperación: guardado antes de reiniciar el equipo.
> Si lo lees después del reinicio, esto es exactamente donde quedamos.

---

## ✅ Estado general

| Archivo | Compila (py_compile) |
|---|---|
| `audioclass_v91.py` | ✅ OK |
| `audioclass_colab_server_v91.py` | ✅ OK |
| `test_gemini_v91.py` | ✅ OK |

## 🔄 ACTUALIZACIÓN TRAS REINICIO (31 julio 2026, tarde)

- ✅ **ENDURECIMIENTO LEGAL/SEGURIDAD (12 agosto 2026, tarde)**: revisión de ciberseguridad antidemandas (`REVISION_CYBERSECURIDAD.md` §12-13) basada en investigación web de vectores de litigio de apps con IA (Otter.ai class action 2025, Moffatt v. Air Canada 2024, Character.AI, FTC Operation AI Comply, Doe v. GitHub, ADA, NOYB/GDPR). **Arreglos aplicados:** (1) **Consentimiento de privacidad en la app** — asistente de primer uso con tarjeta "Privacidad y consentimiento" (casilla obligatoria + opt-in de IA), `_adapt` no envía nada a IA sin `ia_consent` (diálogo `_prompt_ia_consent`, revocable en Configuración), sección "🔒 Privacidad" en el diálogo de config; (2) **Disclaimers** "Transcripción automática — puede contener errores. No constituye acta oficial" en exportaciones PDF/DOCX/GDocs/Colab y en archivos de adaptación; (3) **Servidor Colab endurecido**: anti **path-traversal** en `/download`, **key por header `X-API-Key`** (URLs generadas sin `?key=`), **rate-limit** 30 peticiones/min por clave, **tope de subida 200 MB**, `pip install` solo bajo `__main__`; (4) **Licencias**: `TERCEROS_Y_LICENCIAS.md` (atribución de dependencias — todas permisivas, sin contaminación GPL) + `LICENCIA.txt` (MIT, plantilla por completar). Validado: `test_colab_server_security.py` (NUEVO, 7/7) + `test_privacy_consent.py` (NUEVO, 7/7) + ADAPT_ENGINES_ALL_OK + EXPORT_OK + SMOKE_OK + py_compile OK. Completado después: aviso de grabación al iniciar la primera grabación + "mayor precisión" (claim factual) + retención del proveedor en los avisos + nota "generado automáticamente" en el panel de adaptación. **Documentos legales**: `LICENCIA.txt` (MIT, © Daniel Pérez), `EULA.txt` y `AVISO_DE_PRIVACIDAD.txt` generados e **integrados en el zip** del despliegue (onefile y onedir). Pendiente P1: SHA-256 público, firma del exe, borrado de grabaciones.
- ✅ **SEGUNDO PROVEEDOR DE IA: OPENAI (GPT)** (12 agosto 2026): la "Adaptación Inteligente" ya no es solo Gemini. Nuevo `OpenAIAdaptationEngine` en `audioclass_core.py` (misma interfaz `test_key()`/`adapt()`, reutiliza los TEMPLATES, Chat Completions contra `api.openai.com`, modelos `gpt-4o-mini` (mini) / `gpt-4o` (gpt4o), test de key vía `GET /v1/models`); `GeminiAdaptationEngine` refactorizado internamente (nuevo `_call()` común + `PROVIDER`) **sin cambiar comportamiento** (mismos payloads/URLs/timeouts, resultado añade `provider`). En la GUI: selector **"🤖 Proveedor de IA para el análisis"** (Gemini / OpenAI) en Configuración, secciones de API Key + modelo + "Probar Conexión" por proveedor, estado en el panel de Adaptación ("Gemini listo"/"OpenAI listo"), banner "Siguiente paso" y aviso de "Sin API Key" provider-aware, y `_SECRET_FIELDS` incluye `openai_api_key` (cifrada con DPAPI igual que Gemini). Config: `adapt_provider` (default `gemini`), `openai_api_key`, `openai_model` (default `mini`); configs antiguas reciben los defaults al cargar. Validado: `test_adapt_engines.py` (5 tests offline: contrato común, modelos, sin key, template inválido, fábrica) + smoke del diálogo de config + EXPORT_OK + MEJORAS_V10/LANG_AUTO/WATCHDOG en verde. (Nota: la transcripción LOCAL sigue siendo faster-whisper/openai-whisper — esto es solo para el análisis con IA.)
- ✅ **Python 3.12.8 instalado correctamente** (solo-usuario en `%LOCALAPPDATA%\Programs\Python\Python312`, con tkinter).
- ✅ **Dependencias GUI instaladas**: numpy, scipy, sounddevice, customtkinter 6.0.0, matplotlib, requests, fpdf2, noisereduce.
- ✅ **Smoke test de la app PASADO (3 escenarios, HOME temporal, sin tocar datos reales)**:
  1. Arranque con asistente → finalizar wizard → Modo Guiado (resumen "Usando perfil: … motor: local · modelo: tiny" + toast ✓).
  2. Arranque directo en Modo Guiado con el perfil "Cerca del Micrófono" (el que antes rompía el pipeline) + guía contextual clicable ✓.
  3. Toggle Opciones avanzadas ↔ Modo Guiado (mostrar/ocultar Perfil/Motor/Modelo) ✓.
- ✅ **BUG DE ACENTOS EN PDFs CORREGIDO** (app + servidor Colab): se empaquetaron `assets/DejaVuSans.ttf` + `DejaVuSans-Bold.ttf` (fuente Unicode completa: acentos, — • → … ├ └). La app usa DejaVu de `assets/` (o fuente del sistema con sanitizado como respaldo; la fuente core latin-1 como último recurso). El servidor busca DejaVu del sistema o la descarga a TEMP_DIR. Validado end-to-end extrayendo el texto de PDFs reales con pypdf (8/8 caracteres, con timestamps y fallback sin crashear).
- ✅ **VAD ADAPTATIVO CORREGIDO** (hallazgo de calidad de audio): el umbral de voz ya no es fijo (0.01). `_agc_vad_limiter` estima el piso de ruido con el percentil 10 del RMS de tramas de 40ms y deriva `vad_thr = max(fijo, piso×3)` y `silence_thr = max(fijo×0.4, piso×0.5)`. Resultado medido: un aula con ventilador constante pasó de **re-amplificarse +21 dB a atenuarse −21.2 dB**; la voz se conserva y se normaliza (banda 200–3000Hz ×3.37); el limitador y el recorte de silencios siguen funcionando (25s → 10.7s útiles); los 4 perfiles pasan sin errores. Demos actualizadas en `demo_audio/`.
- ✅ **RMS DE TRAMAS VECTORIZADO** (sliding_window_view, sin doble pase): nuevo método `_frame_rms(audio, window, hop, batch=16384)` calcula el RMS de todas las tramas (0, hop, 2*hop...) en UNA pasada vectorizada con `np.lib.stride_tricks.sliding_window_view`, procesada por bloques (memoria acotada ~84MB por bloque, clave para clases de 3h → ~540k tramas). `_agc_vad_limiter` ahora calcula `frames_rms` UNA vez y el bucle de ganancia reutiliza `frames_rms[k]` en vez de recalcular `np.sqrt(np.mean(chunk**2))` por trama. Validado con **igualdad EXACTA bit a bit** (maxdiff=0.00e+00) viejo-vs-nuevo en 4 escenarios de audio real (solo-ruido, normal, extremo, voz-suave) + 5 edge cases de longitud (vacío, corto, justo window, impar, largo); métricas intactas (−21.2 dB, voz ×3.37, limitador 0.608, 4 perfiles OK); **benchmark 5 min: 0.334s → 0.202s (1.7×)**, proyección 3h: 12.0s → 7.3s (ahorra ~4.7s). Revisor de código: aprobado sin bugs (verificó alineación de índices `frames_rms[k]↔k*hop`, equivalencia del slicing `[0:n-window:hop]` con `range(0, n-window, hop)` stop-exclusivo, rama `n<=window`, y que tope/silence_thr/_remove_silences quedaron intactos).
- ✅ **TOPE ANTI-CASO-LÍMITE AÑADIDO** (complemento del VAD adaptativo, tras feedback del revisor): con ventilador TAN ruidoso que el piso se acerca a la voz, el x3.0 comía la voz suave. Ahora: `speech_ref = percentil 90` (nivel de habla), `spread = p90/p10`; si `spread > 2.0` (hay habla real; solo-ruido da ~1.53) **y** `piso×3 > habla×0.6` (el umbral viejo quedaría por encima del habla), el umbral baja a `habla×0.6`. Calibrado con sonda empírica (percentiles reales p10/p50/p90/p99 de 4 escenarios). Validado: regresión solo-ruido intacta (−21.2 dB), caso normal sin cambios (vad 0.2067), ventilador extremo topea 0.2608→0.2050 (voz ×2.15), voz suave+fan 0.12 topea 0.3014→0.1436 (voz ×1.95, y A/B vs fórmula vieja: rescata ×1.31 de voz y 169k muestras vs 24k antes — ya no borra las frases). Revisión de código: **aprobada sin bugs** (salvedades honestas: en el régimen de tope el fan entre frases se oye algo más — tradeoff inherente a SNR baja; y un solo-ruido con transitorios bruscos podría superar p90/p10=2.0 — heurística aceptable).
- ✅ **SCRIPT DE PRUEBA CON AUDIO REAL CREADO**: `grabar_prueba.py` — para validar la calidad del pipeline con TU microfono. Pulsa Enter, habla ~15s, y guarda en `~/AudioClass_Recordings` los `clase_<ts>_raw.wav` y `clase_<ts>_mejorado.wav` usando EXACTAMENTE la ruta de la app (`_procsave` → `AudioPipeline('Clase Universitaria', fast_mode=False, use_vad=True)` → `_savewav` int16). Compara objetivamente: % de tramas en silencio recortadas (noise gate), nivel de habla p90, SNR habla/piso, banda de voz 200–3000Hz, agudos 7.1–7.9kHz, pico vs limiter real del perfil (0.920). Incluye `voice_gate=True` (escucha hasta 90s, captura solo al detectar voz y para tras 2.5s de silencio). Validado headless con audio sintético: **TODO OK (22 checks)**, py_compile OK, revisor aprobado sin bugs. (Nota honesta: los intentos de grabación automática por mi cuenta capturaron silencio porque no había voz en la ventana; el micrófono hardware SÍ funciona — la sonda inicial capturó señal real pico 0.52.)
- ✅ **UI MEJORADA + PRUEBA DE MICRÓFONO NATIVA** (31 julio 2026): (1) **Funcionalidad nueva integrada**: ventana `_test_mic` (600x440) con **medidor de nivel en vivo** (barra + dB), graba 8s en hilo, procesa con el pipeline activo y muestra las métricas de `grabar_prueba.py` integradas (voz detectada, % silencio recortado, SNR, banda de voz, agudos con guard anti-'-inf dB', pico vs limitador). Accesible desde el pie de página y desde Configuración. (2) **Diseño**: pasos del indicador como píldoras con estados (actual=acento, completado=verde, futuro=gris), tarjetas con borde sutil, REC parpadeante ●/○, botón "Abrir carpeta" (`_open_output_dir`). Validado: py_compile OK + test headless (21 checks) + smoke test GUI (App completa con HOME temporal) TODO OK; revisor aprobado sin bugs (2 fixes aplicados: -inf dB y ventanas duplicadas).
- ✅ **EXE COMPILADO Y VALIDADO** (31 julio 2026): `dist/AudioClass/AudioClass.exe` (onedir, 170MB carpeta / 16MB exe) con PyInstaller 6.21.0. Empaqueta numpy/scipy/customtkinter/matplotlib/sounddevice/noisereduce/fpdf2/PIL + **fuentes DejaVu en `_internal/assets/`** (acentos de PDF OK; `_pdf_unicode_font` ahora busca en 3 bases: dir del script, `sys._MEIPASS` y dir del exe). **Bug real detectado y corregido por smoke test**: excluir `unittest` del spec rompía el arranque (scipy → numpy.testing → import unittest) — se quitó de excludes. **Smoke test aislado final**: proceso vivo a los 20s + stderr vacío (0 bytes) ✅. Revisor: aprobado sin bugs. ⚠️ Limitaciones honestas del exe: whisper/torch NO están instalados en este Python → la transcripción LOCAL mostrará mensaje claro (cloud Colab + Gemini + grabación + pipeline + PDF sí funcionan); Google Docs necesita google-auth-oauthlib (no empaquetado).
- ✅ **EXE COMPLETO CON WHISPER LOCAL INTEGRADO** (31 julio 2026): (1) **Se instaló torch 2.13.0+cpu + openai-whisper 20250625** en el Python del usuario; (2) **`LocalWhisperEngine` ahora transcribe offline de verdad**: pasa el array float32 directo a Whisper (sin WAV temporal ni ffmpeg), con `.astype(np.float32)` tras el resample y `_resolve_model()` que carga `models/tiny.pt` del bundle (con fallback que actualiza `self.model_name` si solo tiny va empaquetado); (3) **modo headless `--selftest-transcribe`** para validar el exe sin GUI; (4) **spec onedir `AudioClass_v91.spec`** con whisper/torch/tiktoken/collect_data_files('whisper') y `models/tiny.pt` → `dist/AudioClass/` (767 MB). Tres bugs de empaquetado cazados por smoke tests reales y corregidos: excluir `unittest` rompía scipy→numpy.testing; excluir `pydoc` rompía scipy._lib._docscrape; faltaba `whisper/assets/mel_filters.npz` (arreglado con collect_data_files). **Validación**: selftest del exe exit 0 transcribiendo audio TTS real ("…la fotosíntesis en las plantas… los cloroplastos… glucosa y oxígeno…") + smoke test GUI con stderr vacío y carpeta creada. (5) **ONE FILE**: `AudioClass_v91_onefile.spec` → `dist_onefile/AudioClass.exe` (314 MB, UPX, un solo archivo autocontenido) validado igual (selftest exit 0 + GUI limpia); copiado a la raíz como **`AudioClass COMPLETA v9.1.exe`**. Nota: el onefile descomprime ~314 MB en temp cada arranque (primera vez 30-60s).

(Además: Python 3.12.8 embebido en `%TEMP%\audit_py312` para validar lógica sin tocar el sistema.)

---

## 🐛 Bugs reales encontrados y CORREGIDOS en `audioclass_v91.py`

### Fix 1 — El botón "Grabar mi clase" crasheaba (AttributeError)
`_startrec` llamaba a `self._disk_ok(100)` pero el método **no existía** en el archivo.
- **Añadido** `_disk_ok(self, mb_needed)` (aprox. línea 2074): mide espacio libre con
  `shutil.disk_usage(OUTPUT_DIR).free` y devuelve `True` si no se puede medir
  (no bloquea la grabación). `shutil` ya estaba importado.
- **Validado**: fix presente en disco, lógica probada, revisor de código aprobó.

### Fix 2 — 3 de los 4 perfiles de audio rompían el pipeline (ValueError)
Los perfiles `Conferencia / Webinar` (8000Hz), `Podcast / Entrevista` (8500Hz) y
`Cerca del Micrófono` (9000Hz) tenían `lp_freq ≥ fs/2` (8000Hz con fs=16000).
`scipy.signal.butter()` exige `0 < Wn < fs/2` → lanzaba `ValueError` y el
procesado de audio fallaba (solo "Clase Universitaria" con 7000Hz funcionaba).
- **Corregido** (aprox. línea 193): `lp_freq = min(self.p["lp_freq"], SAMPLE_RATE // 2 - 1)`
  antes de `butter()`. El progreso reporta el valor real usado.
- **Validado**: prueba de ejecución real con los **4 perfiles** → todos OK (9 etapas,
  salida float32, sin valores infinitos). Revisor de código aprobó.

---

## 🔬 Validaciones ejecutadas (lógica real, sin GUI)

1. **Pipeline DSP de 9 etapas** probado sobre audio sintético (tono 440Hz + ruido +
   2s de silencio) en los 4 perfiles + modo rápido sin VAD → **TODO OK**.
2. **Gemini actualizado (julio 2026)**: `GEMINI_MODELS` = `flash → gemini-2.0-flash`,
   `pro → gemini-2.5-pro`. `test_key()` contra la API real con clave falsa devuelve
   *"API Key inválida (cópiala completa…)"* → integración actual funcionando.
3. **No se tocó nada del usuario**: no existe `~/AudioClass_Recordings/audioclass_config.json`
   (los tests usaron un HOME temporal).

---

## 📋 Hallazgos pendientes (sin corregir, decisiones tuyas)

- ✅ **Acentos en PDFs: CORREGIDO** (ver ACTUALIZACIÓN TRAS REINICIO). Los `.txt` ya se guardaban en UTF-8.
- **Servidor Colab**:
  - `NGROK_TOKEN = ""` → sin tu token, `ngrok.connect()` falla al arrancar sin
    mensaje claro (no hay try/except).
  - API key del servidor es `"audioclass"` (trivial) y la URL ngrok es pública →
    considera rotarla. La key viaja en la URL de `/download`.
  - Reinstala todas las dependencias (`pip install`) en cada arranque del notebook.

---

## ⏭️ Próximos pasos (retomar aquí tras el reinicio)

### 1. Resolver los permisos de Python (bloqueante, lo ibas a hacer tú)
El instalador falló con EXIT=66 (permisos/UAC del sistema). Opciones:
- **Doble clic en `build.bat`** → si Windows pide permisos: clic derecho → *"Ejecutar como administrador"*.
  Instala Python con winget, crea `audioclass_env`, instala dependencias y abre la app.
- O instalar Python 3.12 desde python.org marcando **"[x] Add python.exe to PATH"**.

### 2. Una vez con Python funcionando
1. `python test_gemini_v91.py` → validar API key real (paso 1 y 2: key + Análisis Académico).
2. `python audioclass_v91.py` → prueba final de la GUI (asistente, Modo Guiado, grabación).
3. (Opcional) Probar el servidor Colab con tu token de ngrok.

### 3. Mejoras opcionales propuestas
- Arreglar acentos en PDF (fpdf2 + fuente UTF-8).
- Blindar el servidor Colab (token obligatorio con error claro, API key fuerte).

---

## 🎯 ENTREGA FINAL CON INSTALADOR Y .ZIP (1 agosto 2026)

### 1. Claridad de UI tras el asistente (bug reportado por el usuario)
> "después de llenar la información no tiene claro el siguiente paso, la UI no es clara"

**Corregido en `audioclass_v91.py`** (revisado por code-reviewer, sin bugs):
- **Banner permanente "Siguiente paso"**: tarjeta con borde de color debajo del
  indicador de pasos que SIEMPRE dice qué hacer a continuación y cambia solo
  según el estado: 1) pulsa GRABAR MI CLASE, 2) pulsa TRANSCRIBIR,
  3) pulsa ANÁLISIS ACADÉMICO PROFUNDO (o añade API Key si falta),
  4) guarda con PDF / Google Docs. Botón "❓ ¿Cómo se hace?" abre la Guía
  Rápida en la sección del paso actual.
- **Pulso animado del botón rojo**: cuando toca grabar, el botón 🎙️ parpadea
  suavemente (450 ms) para llamar la atención; se detiene al grabar o al
  cambiar de paso.
- **Toast verde "¡Configuración lista!"** al terminar el asistente.
- Nuevos métodos: `_update_next_step()`, `_start_pulse_rec()`, `_stop_pulse_rec()`;
  `_set_step()` mantiene el banner sincronizado. `_update_next_step()` tiene
  guardas `hasattr`/`winfo_exists` (se llama antes de existir el banner) y
  `configure(fg_color/text_color/border_color)` protegido para modo no-CTK.

### 2. Recompilado y validado (entregable COMPLETO)
- Onefile reconstruido: `dist_onefile/AudioClass.exe` (314 MB) con whisper +
  torch CPU + modelo tiny + mel_filters + fuentes DejaVu empaquetados.
- **Validado con audio real SIN red**: `--selftest-transcribe` → exit 0, texto
  real transcrito ("…la fotosíntesis en las plantas…"). Smoke test GUI: proceso
  vivo, stderr 0 bytes. (Nota: el primer intento en paralelo falló por el
  `taskkill` del smoke test matando el selftest a los 70 s; relanzado solo → OK.)
- Copia actualizada en la raíz: `AudioClass COMPLETA v9.1.exe` (314 MB).

### 3. Instalador + .zip para compartir
- `instalar_audioclass.bat` — instalador de 1 clic: copia `AudioClass.exe` a
  `%USERPROFILE%\AudioClass`, crea acceso directo "AudioClass" en el escritorio
  (PowerShell + WScript.Shell) y ofrece abrir la app. ASCII puro (sin acentos)
  y sin `goto`/labels para máxima compatibilidad cmd.
- `desinstalar_audioclass.bat` — borra acceso directo y carpeta del programa,
  conserva `~/AudioClass_Recordings` (las grabaciones).
- `LEEME.txt` — guía de instalación y uso en lenguaje simple (no-programador).
- **`AudioClass_v9.1_COMPLETA.zip` (312 MB)** en la raíz del proyecto:
  `AudioClass_v9.1/{AudioClass.exe, instalar_audioclass.bat, desinstalar_audioclass.bat, LEEME.txt, GUIA_DE_USO.md}`.

### 4. Pendientes del usuario (fuera de esta entrega)
- Probar el Análisis Académico con una API Key real (`test_gemini_v91.py`).
- Blindar servidor Colab (token ngrok + API key fuerte).

---

## 🔧 FIX DEL CUELLO DE BOTELLA DEL ASISTENTE (1 agosto 2026, tarde)

> "no hay boton para seguir avanzando, existe un cuello de botella" (captura:
> asistente cortado en la seccion 3, sin boton visible)

**Causa raíz**: el asistente empaquetaba todo (titulo + 4 secciones + boton
"Comenzar") SIN scroll en una ventana fija; en pantallas normales el boton
"🚀 Comenzar a usar AudioClass" quedaba fuera de la vista y no habia forma de
continuar.

**Corregido en `audioclass_v91.py`** (revisado por code-reviewer, sin bugs;
validado desde fuente y dentro del exe):
- **Barra fija inferior SIEMPRE visible** con el boton "Comenzar" (fuera del
  scroll): es imposible quedarse sin boton para avanzar.
- **Cuerpo desplazable**: CTkScrollableFrame (CTK) / Canvas+Scrollbar (fallback
  tk) con rueda del raton vinculada tambien al cuerpo.
- **Ventana compacta en primer uso**: 1120x720 (minsize 900x560) para que quepa
  en portatiles; al terminar se restaura 1450x1050 (minsize 1250x900).
- **Enter** en el campo de la API Key tambien continua, con guarda
  anti-doble-disparo (`_wiz_finishing`) para Enter+clic rapidos.
- **Validacion**: fuente (wizard construido, boton visible, finish OK, banner
  "🎙️ Pulsa el botón rojo: GRABAR MI CLASE") y exe (selftest-transcribe exit 0
  + smoke GUI con asistente, stderr 0 bytes).
- **Recompilado y re-empaquetado**: `dist_onefile/AudioClass.exe` (314 MB),
  raiz `AudioClass COMPLETA v9.1.exe` y `AudioClass_v9.1_COMPLETA.zip`
  actualizados con el fix.

---

## 🧰 Utilidades de auditoría (se crean solas en %TEMP%, no en el proyecto)
- `%TEMP%\audit_py312` — Python 3.12.8 embebido + numpy/scipy/requests (validación sin permisos).
- `%TEMP%\pyfull.exe` — instalador de Python 3.12.8 descargado (NO instalado; falló por permisos).
- `%TEMP%\audit_py312\python312._pth` — ajustado con `Lib\site-packages` + `import site` para pip.

---

## 🔧 FIX DEL FALLO/CUELGUE DE LA TRANSCRIPCIÓN LOCAL (7 agosto 2026)

> Reporte del usuario: "sigue fallando la transcripción local, se estacionó en 98% por 3 horas para un audio de 30 segundos".

**Causa raíz CONFIRMADA en `~/AudioClass_Recordings/logs/audioclass.log`** (6 ago 2026):
la app llamaba a whisper con `verbose=False`, y openai-whisper 20250625 con ese valor
**ACTIVA una barra tqdm** (`disable=verbose is not False`) que escribe a `sys.stdout`.
En el exe compilado con `console=False` (o pythonw), `sys.stdout` es `None` y tqdm
reventaba con `AttributeError: 'NoneType' object has no attribute 'write'` dentro de
cada worker → la transcripción local fallaba al instante (traceback completo en el log).

**Corregido en `audioclass_core.py` + `audioclass_v91.py`** (defensa en profundidad):
1. **`verbose=None`** en `_transcribe_with` (camino secuencial y paralelo): desactiva
   tqdm por completo → whisper ya no escribe a stdout (fix de la causa raíz).
2. **Sumidero nulo de stdout/stderr** al arrancar la app si están en `None` (exe sin
   consola): red de seguridad para cualquier otra librería que escriba.
3. **Chunking corregido**: un audio de 30s generaba 2 chunks (30s + cola de 2s por el
   overlap), forzando el camino paralelo con un chunk casi vacío propenso a que whisper
   alucine timestamps. Ahora la cola ≤ overlap se fusiona: 30s → 1 chunk (secuencial).
4. **Watchdog por chunk** (nuevo `CHUNK_BUDGET_FLOOR=120s`, `max(120, 4×media real)`):
   si whisper se cuelga (bucle de timestamps sin avanzar en la misma ventana), el chunk
   se omite y la transcripción continúa con el resto, reportando `chunks_omitidos` y
   avisando en la UI. Antes podía esperar horas.

**Validado** (todo con `models/tiny.pt`, mismo modelo del bundle):
- `test_transcribe_headless.py` (NUEVO): simula el exe sin consola (`sys.stdout=None`)
  — 30s → 1 chunk en **11s**, 100s → 4 workers en **21s**, progreso 100% y monótono, sin
  AttributeError. Antes el mismo exe moría al instante.
- `test_watchdog.py` (NUEVO): modelo falso que se cuelga → secuencial omite en 2s y
  paralelo en 6s (4/4 chunks omitidos), en vez de colgar para siempre.
- `test_parallel_transcribe.py`: OK (4 chunks, 4 workers, 3s, monótono).
- Estabilidad A/B/C/E: OK. `py_compile`: OK.
- Pendiente de voz real: `test_stress_transcripcion.py`, `test_stability.D` y
  `test_funcional_independiente.py` requieren `prueba_voz_es.wav` (no está en el repo).
- **Validación adicional (revisión de código)**: tras aplicar el fix de "error en vez
  de texto vacío cuando TODOS los chunks fallan", se detectó y corrigió un bug de
  anidamiento que dejaba el procesamiento del texto del camino secuencial como código
  muerto (la transcripción volvía vacía). Se verificó que el callback final dispara
  1.0 ("Chunk 1/1 listo"), que el texto se acumula y que los tiempos de chunks que
  hacen timeout NO contaminan la media móvil del presupuesto (el siguiente presupuesto
  ya no se infla ×4 del tiempo de cuelgue). Watchdog final: secuencial 2.0s, paralelo
  4.7s, parcial 2.0s — siempre acotado, nunca horas.
- **RECOMPILADO Y VALIDADO (7 agosto 2026, tarde)** tras el fix de transcripción:
  `AudioClass_v91.spec` (onedir, `dist/AudioClass/AudioClass.exe`) y
  `AudioClass_v91_onefile.spec` (onefile, `dist/AudioClass.exe`) recompilados con
  PyInstaller 6.21.0. Entregables actualizados: `dist_onefile/AudioClass.exe`,
  raíz `AudioClass COMPLETA v9.1.exe` y `AudioClass_v9.1_COMPLETA.zip` (mismos 5
  archivos). Validación con `--selftest-transcribe`:
  - Grabación real del usuario que falló (clase_20260806_194205, 57.8s): EXIT=0,
    sin errores, 100%, 2/2 chunks (antes: AttributeError de tqdm). El audio es
    silencio real (vu_low=687, raw rms=0.0014) → "SIN TEXTO" es el resultado
    correcto (la app ya advertía del micro).
  - Voz TTS real de Windows (22.4s → 1 chunk, camino secuencial, el caso "30s"
    del usuario): EXIT=0, texto extraído, 100%. Ambos exes.
  - Smoke GUI: ambos exes vivos a los 25s (vía subprocess; el arranque con
    `&` de Git Bash no es fiable para exes GUI).

## 🌐 Idioma 'auto' en la transcripción (whisper)

**Problema**: la app forzaba `language="es"` en whisper; audio en otro idioma
(o TTS en inglés) salía distorsionado en español.

**Cambios**:
- `audioclass_core.py` `LocalWhisperEngine(language=...)`: `"auto"` detecta el
  idioma con `whisper.detect_language` sobre el primer chunk y lo aplica a
  TODOS los chunks (consistencia); un código ISO (es/en/pt/...) lo fuerza.
  Prompts académicos bilingües PROMPT_ES/PROMPT_EN según el idioma efectivo.
  El resultado incluye `language`. En el camino paralelo el probe solo se
  adquiere en modo auto y con fallback a 'es' si la carga/detección falla.
- `audioclass_v91.py`: config `whisper_language="auto"` (default), selector
  "Idioma" en la barra de configuración, `_chlang()` actualiza ambos motores.
- `audioclass_colab_server_v91.py`: endpoints `/transcribe` y `/transcribe_ts`
  aceptan `language` (Form, default "es"); `"auto"` → `language=None` sin
  prompt (whisper detecta solo). `CloudColabEngine` envía el idioma.
- `test_lang_auto.py` (5 casos con whisper falso: es forzado, auto→en,
  auto→es, paralelo consistente, cloud envía language). Suite existente
  (headless, paralelo, estabilidad, watchdog) pasa; selftest OK.

**Validación**: `test_lang_auto.py` LANG_AUTO_ALL_OK · py_compile OK ·
regresiones OK.

## 🚀 Iteración v10 — 3 mejoras aplicadas y validadas (7-ago)

**#1 faster-whisper (backend dual):** LocalWhisperEngine auto-elige faster-whisper
(CTranslate2 int8, cpu_threads=1) en desarrollo y openai-whisper en el exe frozen
(los .pt empaquetados no los lee CTranslate2). Deteccion de idioma via info.language,
transcripcion via generador de segmentos, cache sin deepcopy (CTranslate2 no lo
soporta), torch.set_num_threads solo openai. Medido: base 7 min -> 28.6s faster vs
51s openai (1.8x); tiny cache caliente 6.5s vs 8.9s (1.4x). benchmark_results.json
registra backend. NOTA: el exe compilado sigue con openai hasta recompilar con
faster-whisper + modelos CT2 empaquetados.

**#2 Pre-validacion de silencio:** audio_silence_stats + is_digital_silence
(>50% muestras en cero o RMS < 5e-5, min 1s) antes de chunking; devuelve
{silence: True, silence_msg} en <1s sin gastar transcripcion. La UI muestra aviso
claro. El caso real (77% ceros) se detecta; voz TTS (rms 0.098) no da falso
positivo. Flag check_silence para tests.

**#3 Streaming + ETA:** partial_callback opcional emite texto parcial acumulado
(secuencial por chunk, paralelo en orden por indice); la UI lo muestra en vivo con
resaltado dorado (throttle 200 chars) y el ticker calcula ETA desde el progreso.
El log final muestra el backend usado.

**Tests:** nuevo test_mejoras_v10.py (6 casos: silencio, no-falso-positivo,
streaming secuencial/paralelo, faster secuencial/paralelo con SKIP si falta
faster-whisper). Tests existentes forzados a backend="openai" (parchean whisper/
miden deepcopies del camino del exe). requirements_v91.txt incluye faster-whisper.
Suite completa verde: HEADLESS, LANG_AUTO, WATCHDOG, PARALLEL, STABILITY,
FUNCIONAL, STRESS, E2E, EXPORT, UI_SMOKE, UI_V91, BENCH (base 15.7% < tiny 30.0%).

## 📦 Iteración v10 — exes recompilados con faster-whisper + modelos CT2 (7-ago)

- models_ct2/tiny y models_ct2/base descargados (formato CT2: model.bin +
  tokenizer.json + vocabulary.txt + config.json) y empaquetados en ambos specs.
- Core: _pick_backend en frozen elige faster si existe models_ct2/ en el bundle
  y faster_whisper importa (fallback openai para bundles antiguos solo .pt);
  _resolve_model resuelve el directorio CT2 del modelo empaquetado.
- Specs: +faster_whisper, ctranslate2, av, tokenizers, tqdm, onnxruntime en
  hiddenimports; collect_data_files('faster_whisper') (silero VAD); modelos CT2
  en datas. Se mantiene whisper/torch como respaldo.
- Compilado con PyInstaller 6.21.0. Validado:
  * dist/AudioClass/AudioClass.exe (onedir, 52 MB exe) --selftest: exit=0,
    45s/138.5s (0.32x) con texto real es; TTS en ingles -> 'en' correcto en 14s.
  * dist_onefile/AudioClass.exe (onefile, 599 MB) --selftest: exit=0, texto real,
    100% progreso. GUI viva a los 30s.
  * Bundle autosuficiente verificado: faster_whisper 1.2.1 + ctranslate2.dll +
    _ext.pyd cargan desde _internal y WhisperModel(models_ct2/tiny) carga OK.
  * El speedup real en el exe: 45s vs 84s del exe anterior (1.87x).
- Entregables actualizados: AudioClass COMPLETA v9.1.exe (599 MB, 23:15),
  AudioClass_v9.1_COMPLETA.zip (597 MB).
- Regresion: MEJORAS_V10_OK, py_compile OK.

## ✅ Auditoría de uso, esfuerzo y control (2026-08-08)

- Suite de control (13 tests): PY_OK, LANG_AUTO_ALL_OK, WATCHDOG_ALL_OK (3/3 anti-cuelgue),
  EXPORT_OK, SMOKE_OK, HEADLESS_ALL_OK (30s→5.8s, 100s→19.6s, monótono a 100%),
  ALL_OK (paralelo), MEJORAS_V10_OK (faster 3.9s/chunk, streaming con partials),
  STABILITY_ALL_OK, E2E_TRANS_OK, INDEPENDENT_FUNC_OK, BENCH_MODELS_OK
  (base 15.7% < tiny 30.0%, std 0.00), UI_V91 TODO OK. Gemini: solo falta API key (ambiental).
- Estrés: test_stress_transcripcion.py detectó falso positivo de memoria (media 105 MB > 100).
  Diagnóstico de 7 corridas: objetos Whisper vivos CONSTANTES en 8 (6 cache + plantilla +
  eng.model), 0 hooks de kv_cache, deltas sin tendencia (+262→+132→+66→-44→+189→+51,
  media últimos 3 = 65 MB) → NO hay fuga real; es el high-water mark del allocator + el
  working set deliberado de la cache (6 modelos ~2.1-2.3 GB) + recorte de Windows.
  Fix del test: señal determinista = conteo de objetos Whisper vivos (tope 12) + umbral RSS
  robusto 150 MB. Re-ejecutado COMPLETO: STRESS_ALL_OK — A (ráfaga 23s/21s/23s sin
  degradación), THREADS_OK (delta 1), MEM_OK (objetos 8, deltas 49.8 MB), B (cancelación a
  mitad + rearranque inmediato: 2ª completó 15 chunks en 27s, puerta anti-congestión
  reabierta, sin deadlock), C (3 cancelaciones rápidas + motor sigue sirviendo).
- Uso real: exe onefile "AudioClass COMPLETA v9.1.exe" --selftest-transcribe
  prueba_voz_es.wav (139s) → exit=0, 71s total (incluye descompresión onefile), texto real
  en español, progreso 100% (5/5 chunks).
- Micrófono: AHORA FUNCIONA. diag_mic: SNR 142.5x, 43.1% tramas con voz, 10.6% ceros
  (antes 77-100% = silencio digital). Dispositivo: "Varios micrófonos (Realtek)". Captura
  real guardada en AudioClass_Recordings (5s → 3s tras VAD, sin clipping). Transcrita en
  2.5s (faster, 1 chunk); texto vacío correcto (solo ambiente, sin alucinar) y sin falso
  positivo de silencio (silence=None).

## 🎨 Mejora de UI: paleta cómoda + medidor de sonido + layout adaptativo (2026-08-08)

- Paletas rediseñadas (cómodas para los ojos): oscuro pasa del navy saturado
  #0A1F44/#12264E a pizarra suave #171D26/#1E2632 con dorado cálido #D9B64C y
  rojo/verde/ámbar apagados; claro usa gris cálido #F4F6F8 con dorado oscuro
  #A87F1E de buen contraste. Sin rojos neón ni azul saturado.
- Nuevo tema CTk custom (assets/audioclass_theme.json) basado en gold: elimina el
  azul por defecto de CTk (#1F6AA5) que se filtraba en option menus/sliders y el
  fondo gris del root (antes el vacío inferior quedaba NEGRO).
- Ventana adaptativa: antes fijaba 1450x1050 y en pantallas <= 1050px el editor
  de transcripción quedaba recortado fuera de vista con un vacío negro abajo.
  Ahora se ajusta a la pantalla (máx 1450x1050, margen de barra de tareas) y en
  pantallas < 950px entra en modo compacto (oculta el banner "Siguiente paso" y
  el subtítulo de Modo Fácil, encoge waveform y editor).
- Fila Gemini flexa (weight) y el resto conserva su tamaño: la transcripción
  NUNCA colapsa ni se sale de pantalla (fix del gutter que pedía 24 líneas).
- Cronómetro de grabación ahora visible junto a "● GRABANDO" en la zona de
  controles (antes solo en el pie, que puede quedar cortado en pantallas pequeñas).
- Medidor de sonido VERIFICADO en vivo durante grabación real: barra 0.0→0.164
  reaccionando al micro, dB en vivo (-50), aviso "⚡ Bajo", mini-histórico
  llenándose (10 lecturas), visible en pantalla. 
- Hovers literales que no seguían la paleta -> claves C[...] (siguen al tema).
- Regresión: PY_OK, SMOKE_OK, UI_V91 TODO OK, GRABAR_PRUEBA TODO OK, toggle de
  tema claro/oscuro OK. Capturas: dark #171D26/#D9B64C, light #F4F6F8/#A87F1E,
  vacío negro 64% -> 5-10% (solo texto).
- Escala azul-gris-blanco-negro: acento AZUL #3B82F6 (oscuro) / #2563EB (claro),
  fondos pizarra #0F172A/#1E293B (oscuro) y #F1F5F9/#FFFFFF (claro), ROJO
  reservado a GRABACIÓN (botón grabar, REC, detener, errores #E5484D/#DC2626).
  0 px dorados en capturas. Cian #22D3EE para éxito, ámbar para avisos.
- Botón de grabar ahora ROJO (C["mic"]) con pulso rojo #F87171.
- Ventana cabalga por completo en pantallas pequeñas: h = sh-70 (descuenta barra
  de tareas + título), centrada; antes el borde inferior quedaba FUERA de
  pantalla (captura negra). Verificado: 1366x698 en (8,46), 0% negro en todas
  las bandas, pie (footer) visible, transcripción 5 líneas + scroll.
- Tema CTk actualizado a la escala azul (assets/audioclass_theme.json).
- Regresión: PY_OK, SMOKE_OK.
- Recompilado el exe onefile con la escala azul (2 builds): el primero reveló que
  el spec NO empaquetaba assets/audioclass_theme.json (el exe habría usado el tema
  'gold' de respaldo en los widgets CTk por defecto). Añadido a ambos specs y
  recompilado. Verificado en el CArchive: assets/audioclass_theme.json presente.
- Validación --selftest-transcribe del exe nuevo: exit=0, 73s para 139s de audio,
  texto real en español, progreso 100% (5/5 chunks).
- Entregables actualizados: AudioClass COMPLETA v9.1.exe (599.740.452 B, 20:48),
  AudioClass_v9.1_COMPLETA.zip.

## 🎨 WCAG AA + exe recompilado (2026-08-08 21:10)

- **Contraste WCAG AA**: paleta azul auditada y corregida — todas las combinaciones texto/fondo ≥4.5:1 (texto normal) y ≥3:1 (UI). Acento dark `#60A5FA`, borde `#64748B`, rojo grabación `#F07171` (dark) / `#DC2626` (light). Helper `_btn_fg` elige texto blanco o negro por luminancia por botón.
- **Tema CTk actualizado** (`assets/audioclass_theme.json`) con los valores WCAG.
- **Exe recompilado** (build 3) con los fixes de contraste + tema JSON empaquetado. Validado: `--selftest-transcribe tts_clase.wav` → **exit=0, 47s** (139s de audio), texto real en español, progreso 100% (5/5 chunks).
- **Zip actualizado**: `AudioClass_v9.1_COMPLETA.zip` contiene el exe nuevo (599.742.039 bytes, 21:06).
- **Regresión**: PY_OK · SMOKE_OK · UI_V91 OK. App relanzada (PID 15964) con la paleta corregida.
- **Nota**: el selftest requiere el argumento del audio (`--selftest-transcribe audio.wav [salida] [progreso]`); sin él termina con exit=1 por IndexError (esperado).

## 🔤 Letras negras en tema claro (2026-08-08 21:40)

- **Tema claro: texto `#000000` (negro puro)** en paleta, tema CTk (labels, entries, checkboxes, switches, radio, option/combo, textbox, dropdown) y `_btn_text_color`.
- **`_btn_text_color` reescrito**: elige negro o blanco por el que da MAYOR contraste (antes umbral fijo elegía mal en azules medios: `#0F172A` sobre `#2563EB` = 3.45:1 < 4.5). Ahora: botones azules → texto blanco (5.17:1 claro / 8.26:1 oscuro), botones claros → negro (17:1).
- **Matriz final**: claro texto/bg 19.17:1, texto/card 21:1; oscuro 14.5:1 / 11.9:1. Todos los botones ≥5.17:1. WCAG AA ✓.
- **Verificado**: JSON válido (19 widgets), CTk carga `#000000` en claro y `#FFFFFF` en botones, widgets tk vivos con `fg=#000000` (12). SMOKE_OK · UI_V91 OK · PY_OK.
- App relanzada (PID 1236) con el cambio. **Nota**: el exe sigue con la versión anterior (recompilar = ~8-20 min).

## 📦 Exe recompilado con letras negras + fix contraste (2026-08-08 22:20)

- **Build onefile** (PyInstaller 6.21.0, ~9 min) con el código de letras negras (`#000000` en claro) y `_btn_text_color` que maximiza contraste.
- **Nota de proceso**: el build salió a `dist/` (no pasé `--distpath dist_onefile`); copiado manual a `dist_onefile/` y a la raíz.
- **Verificado en el CArchive**: `assets\audioclass_theme.json` presente (entrada 9375581) junto con modelos CT2 y faster_whisper.
- **Validado**: `--selftest-transcribe tts_clase.wav` → **exit=0, 82s** (139s de audio), texto real en español, progreso 100% (5/5 chunks).
- **Zip actualizado**: `AudioClass_v9.1_COMPLETA.zip` (597.381.300 bytes) con el exe nuevo (599.775.732 bytes, 22:14).

## 🎨 Unificación de colores de texto en dark (2026-08-08 22:45)

**Auditoría**: 80 widgets de texto en dark → 38 fuera de paleta. Corregidos:
- **Botones sin fg_color** (Transcribir, Configuración, PDF/DOCX, etc.): usaban el azul por defecto de CTk con texto gray60 en disabled (contraste ~2:1). Ahora default `C["button"]`, texto por contraste y disabled `C["muted"]` (7:1).
- **Historial del sidebar**: `#FFFFFF` fijo → `text_color=C["text"]` y registrado para re-tematizar (con restauración de selección en `_apply_palette`).
- **Nombre de la app** en header: `#FFFFFF` literal → `C["text"]`.
- **Toasts**: hex literales fijos → paleta dark/light (ok/err/warn) con contraste.
- **Pulso de grabación**: `#F87171` literal → `C["err"]`.
- **Pills de pasos del wizard**: texto `C["bg"]` → `C["header"]` (mismo valor en dark, con contraste en light).
- **Tema CTk**: CTkFrame default gray → card de paleta; text_color_disabled gray → muted.
- **Quedan 10 widgets "fuera"**: son el texto CALCULADO de contraste de `_btn_text_color` (negro sobre azul acento 8.3:1, blanco sobre gris botón 10.4:1, negro sobre rojo 7.3:1) — intencional WCAG, no literales.
- Regresión: PY_OK · SMOKE_OK · UI_V91 OK. App relanzada.

## 🧪 Test de contraste WCAG AA automático (2026-08-08 23:15)

- **Nuevo `test_wcag_contrast.py`** + **`wcag_check.py`** (módulo reutilizable): instancia la app, camina los widgets (tk + CTk con resolución de 'transparent' por padres y pares [light,dark]), y FALLA si algún texto baja de 4.5:1 o UI de 3:1 en dark/light. Los disabled quedan exentos (WCAG 1.4.3).
- **Integrado en `test_ui_smoke.py`**: tras el toggle de tema, valida contraste en ambos temas y sale con error si hay violación.
- **Violaciones reales encontradas y corregidas**:
  - Header en claro: labels con `text` (#000) sobre header oscuro (1.44:1) → nuevo color `head_text` (claro en ambos temas) con `theme_key` forzado (en dark `head_text`==`text`, `_palette_key` mapeaba mal).
  - `_chmode` sobrescribía `lconn` con `muted` → `head_text`.
  - CTkSegmentedButton (modo Local/Cloud): texto único para segmentos activo/inactivo → imposible WCAG en ambos → reemplazado por radiobuttons (texto propio por opción, re-tematizados).
  - Tema JSON: CTkButton dark texto blanco sobre acento (2.54:1) → `#0F172A` (7.02:1); segmented `#0F172A` en dark; CTkRadioButton claves `border_width_checked/unchecked` añadidas.
  - Pills futuras del wizard: `muted` (4.04:1) → `text`.
- **Resultado: 0 violaciones en dark y light** (87 pares evaluados por tema, 22 disabled exentos). Regresión: SMOKE_OK · UI_V91 OK · WCAG OK. App relanzada.

## 🪟 Contraste WCAG en diálogos secundarios (2026-08-08 23:40)

- `wcag_check.collect_all_pairs()` recoge pares del root + todos los CTkToplevel (config, mic, guía).
- `test_wcag_contrast.py` ahora abre cada diálogo y lo valida en dark y light:
  - **Config**: 147 pares/tema. 2 violaciones del CTkSegmentedButton del modelo Gemini ('pro'/'flash') → reemplazado por radiobuttons (texto por opción, re-tematizados). 0 violaciones.
  - **Mic**: 103 pares/tema, 0 violaciones.
  - **Guía**: 91 pares/tema, 0 violaciones.
- Regresión: PY_OK · SMOKE_OK · UI_V91 OK · WCAG OK (main + 3 diálogos, dark y light). App relanzada.

## ✅ Contraste WCAG verificado en el exe empaquetado (2026-08-08 23:15)

- **Recompilado** el exe onefile (22:48) con todos los fixes de contraste. `run_wcag_on_exe.py` valida el CÓDIGO EMPAQUETADO:
  1. Extrae `audioclass_v91` (bytecode marshal) del CArchive y verifica las marcas de los fixes: head_text, theme_key, RadioButton (Local/Cloud + Flash/Pro) → 4/4 OK.
  2. Extrae `assets/audioclass_theme.json` del exe → **idéntico al fuente** (radio border_width_unchecked, button text_color_disabled, segmented dark, frame card).
  3. **Ejecuta la validación de contraste sobre el módulo del exe**: dark 0, light 0, config dark 0, config light 0 violaciones (87-149 pares, 22 disabled exentos).
- **RESULTADO: TODO OK — los fixes de contraste sobreviven al empaquetado.**
- Selftest del exe nuevo: exit=0, 77s, texto real, 100% (5/5 chunks). Zip actualizado.

## 🎛️ Micrófono: pre-check p90 + medidor en vivo, optimizador integrado y validación en el pipeline (2026-08-09)

### 1. Pre-check de nivel ANTES de grabar (evita clases grabadas en silencio)
- `_startrec` lanza `_mic_probe_worker` (~1.5 s en hilo, UI sigue respondiendo): mide el **p90 del RMS** con la misma métrica calibrada de `optimizar_mic.py` (SILENCIO < 0.005 · DÉBIL < 0.03 · voz real ≥ 0.03; umbral de aviso `MIC_PROBE_P90_MIN = 0.01`).
- `_mic_probe_done` (vía la cola `_poll`): si p90 < umbral abre el diálogo de advertencia; si no, graba directo. El cuerpo original de arranque quedó en `_begin_recording`. Idempotencia cubierta con `_mic_probe_pending` (doble clic durante la sonda).
- Nunca bloquea: si el stream falla (None) se graba igual (el flujo real ya reporta errores de dispositivo).

### 2. Diálogo de advertencia "🎤 Micrófono muy bajo" (p90 + medidor en vivo)
- Muestra **p90 medido + dB**, barra de nivel **en vivo** (`_mic_live_probe_worker`, RMS por bloque ~100 ms vía la cola), **"Mejor p90" running max** (ventana ~3 s, meta 0.03 / -30 dB, no baja aunque la voz baje) y **mini-gráfico de tendencia de ~10 s** (`_draw_mic_warn_trend`: barras por ventana de 0.5 s con línea punteada de la meta; arranca con el p90 del pre-check como punto de partida).
- Botones: **🎙️ Continuar grabando** (arranca `_begin_recording`), **Cancelar** (restaura UI) y **⚡ Abrir optimizador (corregir nivel ahora)** → cierra la advertencia y lanza el optimizador con "Aplicar optimización" directamente (`_mic_warn_open_opt` → `_open_mic_opt()` + `_mic_opt_start(True)`), sin cancelar el flujo.

### 3. Optimizador de micrófono INTEGRADO en la app (sin salir de la ventana)
- Botón "🎛️ Optimizar micrófono" en el pie de página → diálogo con log del tema, medidor en vivo y dos acciones: **🔍 Diagnosticar** (dispositivo por defecto, nivel %, mute, permiso de privacidad, todos los mics, prueba de 4 s con piso/p90/peak/veredicto) y **⚡ Aplicar optimización** (nivel 100 % + desmute + boost del nodo hasta +30 dB con fallback seguro si el driver no lo expone; prueba antes/después con resumen xN).
- `optimizar_mic.py` refactorizado: se extrajo **`measure_signal(dur, on_level=None)`** (sin prints; callback por bloque de 100 ms para el medidor en vivo); el CLI `test_signal` quedó como wrapper. Acceso CoreAudio con **ctypes puro** (comtypes 1.4.16 estaba roto para interfaces custom en este entorno).
- Empaguetado: el módulo `optimizar_mic` viaja en el PYZ del exe (verificado: las 7 funciones presentes).

### 4. Validación (todo verde)
- **`test_mic_probe_warning.py`** (35 checks): diálogo abre con nivel débil, graba directo con OK/None, Continuar/Cancelar, live worker (alto/bajo/stream roto), running max, tendencia (ventanas 0.5 s, cap 20 barras).
- **`test_mic_opt_integration.py`** (27 checks): `measure_signal` con stream fake, flujo del worker de diagnóstico y de aplicar con módulo `optimizar_mic` fake.
- **`test_wcag_contrast.py`** extendido a los diálogos nuevos: opt 150 pares, **micwarn 154 pares**, 0 violaciones en dark y light (más config/mic/guía/wizard).
- **`test_mic_warn_on_exe.py`** (19 checks): EJECUTA el bytecode empaquetado del exe y verifica el flujo completo — fuerza p90 0.003 → abre diálogo → voz fuerte → barra verde (#22D3EE) + "Meta alcanzada" + tendencia dibujada → la voz baja y el running max no cae → Continuar arranca la grabación real (GRABANDO + botón Detener) → nivel OK graba directo sin diálogo.
- **Pipeline**: `desplegar_produccion.sh` ahora ejecuta `test_mic_warn_on_exe.py` en la fase [5] (validación del exe) tras cada build; timeouts por fase (tests Tk flaky: el smoke cancelaba el toast a mitad de animación — ahora se cancela la animación antes del chequeo WCAG).

### 5. Estado final de entregables (2026-08-09)
- **`AudioClass COMPLETA v9.1.exe`** — 599.804.130 bytes (build 14:51 con pre-check + diálogo p90/medidor/Mejor p90/tendencia + optimizador + botón Abrir optimizador).
- **`AudioClass_v9.1_COMPLETA.zip`** — 597.412.736 bytes, SHA-256 del exe == entregable raíz (verificado en cada despliegue).
- Despliegue completo: **21 OK · 0 fallos** · selftest exit=0 en 57 s para 139 s de audio (0.41×) · WCAG empaquetado TODO OK · marcas del diálogo/tendencia verificadas dentro del binario.

## 🚀 Preparación de lanzamiento (2026-08-09): default base, onedir, firma, Colab y validación 2.ª máquina

### 1. ✅ Default del modelo local → `base`
- `DEFAULT_CONFIG["local_model"] = "base"` (+ fallbacks de config/UI y `LocalWhisperEngine(model_name="base")`). Respaldo del benchmark reproducible: WER base 15.7 % vs tiny 30.0 %; CT2 base ya va empaquetado y `_resolve_model` lo resuelve offline.
- El **selftest del exe ahora usa el modelo por defecto de la config** (antes forzaba tiny): el despliegue valida así el modelo real que recibe el usuario. Verificado en el bytecode del exe: `local_model default: base`.

### 2. ✅ Build onedir (carpeta, arranque rápido) como alternativa
- Nueva opción **`--with-onedir`** en `desplegar_produccion.sh`: compila `AudioClass_v91.spec` → `dist/AudioClass/` (exe 52 MB), corre su selftest (exit=0 en **41 s**, texto + 100 %) y genera **`AudioClass_v9.1_ONEDIR.zip`** (601 MB, carpeta completa + LEEME.txt). Arranque casi instantáneo vs 30-60 s del onefile. El onefile sigue siendo el entregable principal.

### 3. ✅ Firma de código: documentado (FIRMAR.md)
- La firma real requiere un **certificado OV/EV de pago** (DigiCert/Sectigo/GlobalSign ~200-400 USD/año); un self-signed NO elimina SmartScreen (peor: editor desconocido).
- **`FIRMAR.md`**: pasos `signtool sign /fd SHA256 /tr timestamp /td SHA256 /sha1 …` + verificación, y nota de firmar tras cada build ANTES del zip.
- Mientras no haya certificado ya está cubierto: **LEEME.txt dentro del zip** (Más información → Ejecutar de todos modos; Propiedades → Desbloquear) y sección SmartScreen en `CHECKLIST_INSTALACION.md` (con nota de NO desactivar SmartScreen).

### 4. ✅ Servidor Colab endurecido (`audioclass_colab_server_v91.py`)
- **API key**: ya no hay clave fija trivial `"audioclass"`. Se lee de la env `COLAB_API_KEY` (≥16 caracteres, no trivial — se rechaza y regenera si no cumple) o se **genera una aleatoria fuerte** (`secrets.token_urlsafe(24)`) que el arranque imprime para copiarla a la app. `verify_key` usa `hmac.compare_digest` (tiempo constante).
- **ngrok**: `ngrok.connect(8000)` con try/except y mensaje claro (falta authtoken → servidor local `http://localhost:8000`).
- Lógica de la clave validada: aleatoria ≥16, trivial rechazada, env fuerte aceptada. py_compile OK.

### 5. ✅ Validación en segunda máquina: script turnkey
- **`validar_segunda_maquina.py`**: mide el mic (p90 → OK/DÉBIL/SILENCIO), graba ~12 s de voz real con auto-detección, ejecuta `--selftest-transcribe` del exe y comprueba exit=0, texto no vacío ni alucinado, progreso 100 % y tiempo ≤ 2× la duración. `--quick` solo mide el mic. Probado localmente (mic midió p90 0.0497 → OK).
- Paso final pendiente (requiere una máquina con mic sano y una persona hablando): correrlo allí y confirmar el flujo advertencia → acercarse → verde → Continuar → transcripción.

### 📦 Entregables actualizados (build 16:20-16:29)
- `AudioClass COMPLETA v9.1.exe` — 599.805.837 bytes (default base + gate Google Docs + todo lo anterior).
- `AudioClass_v9.1_COMPLETA.zip` — 597.414.895 bytes (exe + LEEME.txt).
- `AudioClass_v9.1_ONEDIR.zip` — 601.467.543 bytes (carpeta onedir + LEEME.txt).
- Despliegue con `--with-onedir`: **26 OK · 0 fallos** · selftest onefile 63 s / onedir 41 s para 139 s de audio.

---

## 🎨 Checklist "vibe profesional" aplicado a escritorio (13 agosto 2026)

Checklist genérica (Tailwind/.env/Vercel, pensada para web) mapeada y aplicada a
la app de escritorio:

### 1. Diseño profesional → unificación del sistema de diseño
- **Unificación tipográfica completa** (`audioclass_v91.py`): el asistente de
  primer arranque, Configuración, guía, prueba/optimizador de micrófono y VU
  meter usaban `"Segoe UI"` hardcodeado (125 usos) mientras la UI principal ya
  usaba los tokens del sistema. Ahora todo usa `self.FH` (serif para títulos,
  31 usos) y `self.FB` (sans para cuerpo/controles, 117 usos). Botones y pills
  quedan en sans a propósito (la guía reserva la serif para encabezados).
- Validado: `test_ui_v91` TODO OK, `test_ui_smoke` SMOKE_OK, WCAG TODO OK,
  `test_privacy_consent` 9/9 (el asistente toca el código tipografiado).

### 2. Seguridad básica → ya superada + headers de seguridad
- **Secrets**: la app NO usa `.env` porque es mejor: las API keys van cifradas
  con DPAPI ligadas al usuario de Windows (`_encrypt_secret`). Añadido `.env*`
  a `.gitignore` como red de seguridad por si alguien introduce uno.
- **Sanitización de entradas**: ya hecha (anti path-traversal, `compare_digest`,
  rate-limit, tope de subida 200 MB).
- **Headers de seguridad** (lo que faltaba del checklist): middleware en el
  servidor Colab que añade a TODAS las respuestas `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
  strict-origin-when-cross-origin` y `Content-Security-Policy: default-src
  'none'`. Test ampliado a **11/11** (`test_colab_server_security.py`).

### 3. Post-producción → GitHub Actions Release (equivalente desktop de Vercel/Render)
- **`.github/workflows/release.yml`** (nuevo): al pushear un tag `v*` compila en
  un runner Windows los DOS ejecutables (onefile + onedir) reutilizando
  `desplegar_produccion.sh --with-onedir --skip-benchmark` (descarga antes los
  modelos whisper/CT2 que exige el preflight), corre selftests + WCAG
  empaquetados, sube artifacts y crea un **GitHub Release** con los zips y los
  documentos legales. Rollback = desplegar un tag anterior. Disparo manual
  incluido (build + artifacts sin release).

**Archivos tocados:** `audioclass_v91.py`, `audioclass_colab_server_v91.py`,
`test_colab_server_security.py`, `.gitignore`, `.github/workflows/release.yml`
(nuevo), `GUIA_DE_ESTILO.md`, `REVISION_CYBERSECURIDAD.md`.

### 4. Verificación visual de la tipografía (capturas en pantalla)
- **Commit `a0b4ed0`** — "Diseño y seguridad web: tipografía unificada en la UI,
  headers de seguridad en el servidor Colab y workflow de release
  automatizado" (8 archivos: `audioclass_v91.py`, `audioclass_colab_server_v91.py`,
  `test_colab_server_security.py`, `.gitignore`, `.github/workflows/release.yml`,
  `GUIA_DE_ESTILO.md`, `REVISION_CYBERSECURIDAD.md`, `PROGRESO_AUDITORIA.md`).
- **Exes recompilados con la tipografía** (13 agosto, 10:34→10:54): onefile
  `AudioClass COMPLETA v9.1.exe` (10:44) y onedir `dist/AudioClass/AudioClass.exe`
  (10:49), **26 OK · 0 fallos · 0 advertencias** con selftests reales (57 s / 31 s
  para 139 s de audio, exit=0, 100%).
- **Verificación de bytecode de ambos exes**: el literal `"Segoe UI"` ya NO está
  en la interfaz empaquetada (solo queda en `_resolve_fonts` como fallback
  correcto) → la versión distribuida lleva la tipografía unificada.
- **Capturas**: `_captura_asistente.png` (del **exe real** vía PrintWindow,
  1044x759) con el título serif de 30 px medido en píxeles (glifo ~25 px, banda
  accent y 70-95) + `_captura_asistente_privacidad.png` (sección de
  consentimiento), `_captura_principal.png` y `_captura_config.png` (harness —
  mismo código/fuentes que el exe, render idéntico).
- **Galería en Preview**: `_capturas_vista.html` (imágenes incrustadas en base64,
  238 KB) registrada en la pestaña Preview de la sesión para revisión humana.
- **Nota del entorno**: el exe no recibe clics sintéticos en el sandbox de
  Freebuff (ventana en superficie lógica 1366x768 vs framebuffer físico
  inestable 1024/1366; `GetWindowThreadProcessId` devuelve pid=0). Por eso las
  3 vistas restantes se capturaron con el harness y se investigó la solución
  para el E2E empaquetado — ver `INVESTIGACION_E2E_EXE.md` (modo headless
  propuesto `--e2e-ui`, ya **IMPLEMENTADO** y validado en los exes — ver abajo).

## 🧪 Validación completa en clone limpio de master (15 agosto 2026)

Se clonó el repo a una carpeta temporal (HEAD **`e4be953`**, working tree
limpio, sin `models/` ni exes — como un clone real de GitHub), se replicó el
paso de modelos del CI (copiar `tiny.pt` a `models/`; cachés whisper/CT2
compartidas de la máquina) y se ejecutó la **suite completa de 14 tests** más el
job de compilación:

| Job / test | Resultado en el clone |
|---|---|
| py_compile (todos los .py) | `COMPILE_OK` |
| Import núcleo + faster-whisper | `CORE_IMPORT_OK` / `FASTER_WHISPER_OK` |
| `test_privacy_consent` | `PRIVACY_SMOKE: 9 OK, 0 fallos` |
| `test_wcag_contrast` | `RESULTADO: TODO OK` (dark + light, WCAG AA) |
| `test_colab_server_security` | `COLAB_SERVER_SECURITY: 11 OK, 0 fallos` |
| `test_ui_smoke` | `SMOKE_OK` |
| `test_ui_v91` | `RESULTADO: TODO OK` |
| `test_parallel_transcribe` | `ALL_OK` |
| `test_lang_auto` | `LANG_AUTO_ALL_OK` |
| `test_watchdog` | `WATCHDOG_ALL_OK` |
| `test_export_docx_pdf` | `EXPORT_OK` |
| `test_mejoras_v10` | `MEJORAS_V10_OK` (faster tiny) |
| `test_stress_transcripcion` | `STRESS_ALL_OK` |
| `test_e2e_ui` | `E2E_UI_OK` (wizard 17 + config 14 + widgets 13) |
| `test_benchmark_models` | `BENCH_MODELS_OK` (base 15.7% vs tiny 30.0% WER) |

Notas:
- **14/14 en verde**, clone eliminado después de la validación.
- La validación **amplió la cobertura anterior** del clone con los 3 tests de
  privacidad / WCAG / seguridad del servidor Colab. Poco después esos 3 quedaron
  **integrados en la suite unificada** `run_ci_suite.py` (única fuente de
  verdad de los 13 tests, consumida por `ci.yml` y por la fase [1] de
  `desplegar_produccion.sh`), así que CI y despliegue validan exactamente los
  mismos tests.
- Contexto del commit validado: **`e4be953`** — "E2E de UI headless (`--e2e-ui`)
  y CI hermético": modo `--e2e-ui` (wizard/config/widgets) en `audioclass_v91.py`,
  `test_e2e_ui.py` integrado en `ci.yml` con xvfb, fase `[4b]` de
  `desplegar_produccion.sh` que valida los exes recién compilados, y fix de
  `test_export_docx_pdf` (config aislada con `first_run=False` + `ci.yml` exige
  `EXPORT_OK` en vez de enmascararlo con `| tail`).

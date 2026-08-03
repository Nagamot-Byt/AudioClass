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

# TERCEROS Y LICENCIAS — AudioClass v9.1

AudioClass se distribuye como exe autocontenido que **empaqueta** las siguientes
bibliotecas de terceros. Todas son de **licencias permisivas (MIT/BSD/Apache)**
o **LGPL/GPL con excepción que permite la distribución sin contaminar la app**:
**ninguna obliga a liberar el código de AudioClass**.

> **Importante:** este aviso de atribución es un requisito de las licencias
> MIT/BSD/Apache (incluir el aviso de copyright). Su ausencia es una vía de
> reclamación por incumplimiento de licencia — por eso se distribuye con la app.

| Biblioteca | Licencia | Uso en AudioClass |
|---|---|---|
| customtkinter | MIT (© Tom Schimansky) | Interfaz gráfica |
| numpy | BSD-3-Clause | Cálculo numérico / audio |
| scipy | BSD-3-Clause | Procesado de señal (VAD, filtros) |
| sounddevice | MIT (© Matthias Geier) | Captura de micrófono |
| openai-whisper | MIT (© OpenAI) | Transcripción local (modelos .pt) |
| faster-whisper | MIT (© Guillaume Klein) | Backend CT2 (modo desarrollo) |
| torch / torchvision | BSD-3-Clause | Motor de whisper |
| noisereduce | MIT (© Tim Sainburg) | Reducción de ruido |
| matplotlib | Licencia Matplotlib (BSD-style, basada en PSF) | Gráficas/visualización |
| fpdf2 | **LGPL-3.0** (enlace dinámico — no obliga a liberar la app) | Exportación PDF |
| PyInstaller | **GPL-2.0 con excepción de bootloader** (permite empaquetar apps propietarias) | Empaquetado del exe |
| requests | Apache-2.0 | Llamadas a APIs (Gemini/OpenAI/Colab) |
| google-api-python-client | Apache-2.0 | Exportación a Google Docs |
| google-auth / google-auth-oauthlib | Apache-2.0 | Autenticación Google |

## Notas legales

1. **Sin contaminación copyleft:** ninguna dependencia GPL/AGPL se enlaza
   estáticamente. `fpdf2` es LGPL (enlace dinámico permitido) y PyInstaller
   tiene excepción expresa para distribución. Esto **cierra la vía de demanda**
   más citada contra apps generadas con IA (código copiado con licencia GPL).
2. **El código de AudioClass es del autor** (generado con asistencia de IA).
   El copyright de código generado por IA está en disputa legal; la práctica
   recomendada es documentar autoría y licenciar explícitamente (ver
   `LICENCIA.txt`).
3. **Modelos de IA:** whisper (MIT) y los modelos CT2 (`models_ct2/`) se
   distribuyen bajo sus propios términos (MIT/BSD). Los modelos se empaquetan
   para que la transcripción funcione sin internet.

## Verificación

- `requirements_v91.txt` lista las dependencias en modo desarrollo.
- El exe onefile/onedir empaqueta las bibliotecas anteriores (verificado en el
  despliegue: `desplegar_produccion.sh`).

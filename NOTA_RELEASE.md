# AudioClass v9.1-final

**Fecha:** 17 de agosto de 2026 · **Rama:** `main` · **Commit:** `304a36e`

AudioClass es una aplicación de escritorio para grabar clases y reuniones, transcribirlas **localmente sin conexión** y exportarlas a PDF o DOCX. Esta versión final reúne el endurecimiento de privacidad y seguridad, la compatibilidad con dos proveedores de IA y el pulido completo de la experiencia de micrófono.

## Novedades principales

- **Selector de proveedor de IA en Configuración**: elige entre **Gemini y OpenAI** (motor de adaptación OpenAI incluido). Las API keys se guardan cifradas (DPAPI), nunca en texto plano.
- **Selectores de micrófono en toda la app**: Configuración, ventana *Optimizador de micrófono* y **asistente de primer arranque** — grabación, pre-check de nivel y diagnóstico usan siempre el micrófono elegido.
- **Diálogo de Configuración desplazable**: toda la sección de micrófono y "Guardar cambios" quedan accesibles en pantallas de 768 px.
- **Detección de alucinaciones de transcripción**: si el audio es débil o vacío, la app detecta las frases repetidas típicas de whisper y avisa ("revisa el micrófono") en lugar de guardar texto basura.
- **Reporter de progreso blindado**: la transcripción paralela reporta el progreso de forma determinista (sin estimaciones viejas al finalizar).
- **Tipografía unificada** en toda la interfaz (asistente, Configuración, optimizador) y **código 100% sin emojis** (UI y mensajes en texto ASCII limpio).
- **Modo E2E de UI headless** (`--e2e-ui`): 4 escenarios automatizados (asistente, Configuración, widgets y micrófono) para validar el binario empaquetado.

## Correcciones incluidas

- Fix del fallo de transcripción sobre audio débil (alucinación de whisper) — el escenario exacto fue reproducido y verificado en el exe.
- Carrera del reporter de progreso paralelo eliminada (último mensaje siempre correcto).
- Integridad garantizada de los zips (SHA-256 del exe dentro del zip == entregable).
- `LICENCIA.txt` ahora viaja dentro de ambos zips.

## Seguridad y privacidad

- **Consentimiento de grabación** documentado y verificado (vector principal de riesgo en apps de grabación).
- **Headers de seguridad** en el servidor Colab (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).
- Contraste **WCAG AA** validado tanto en el código fuente como en el binario empaquetado.
- Sin secrets en el repo: las claves van cifradas en la config local, con `.gitignore` de red de seguridad.

## Documentación legal (incluida en los zips)

- `LICENCIA.txt` (MIT, © Daniel Pérez 2026)
- `EULA.txt` (términos de uso final)
- `AVISO_DE_PRIVACIDAD.txt`
- `TERCEROS_Y_LICENCIAS.md` (auditoría de las 50 dependencias empaquetadas, licencias verificadas del build)

## Validación de calidad

- Suite de regresión completa: **13/13 tests en verde** (UI, WCAG, privacidad, seguridad del servidor Colab, transcripción paralela, exportación DOCX/PDF, E2E de UI headless, estrés, mejoras v10, idioma 'auto', watchdog y benchmark de modelos) — en clone limpio, local y en el CI de GitHub (ubuntu).
- E2E de UI headless: **4/4 escenarios** (asistente, Configuración, widgets y micrófono) validados en ambos binarios empaquetados.
- Selftest de transcripción local y contraste WCAG AA validados en los binarios compilados en GitHub Actions (Windows).
- Pipeline automático (CI + Release) validado de punta a punta en la nube: compila, valida y publica el Release con sus assets sin intervención manual.

## Descarga

- **Onefile** (`AudioClass COMPLETA v9.1.exe`): un solo ejecutable autocontenido (arranque más lento la primera vez).
- **Onedir** (`AudioClass_v9.1_ONEDIR.zip`): carpeta con arranque casi instantáneo.
- Requisito mínimo: Windows 10/11 de 64 bits. La transcripción funciona sin conexión; solo las funciones de nube (Gemini/OpenAI/Colab) requieren internet y tu propia API key.

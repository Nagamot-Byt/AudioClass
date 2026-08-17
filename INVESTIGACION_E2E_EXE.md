# Investigación: por qué el exe no recibe clics sintéticos — y solución para el E2E empaquetado

Fecha: 13 agosto 2026 · Entorno: Windows, sesión interactiva, AudioClass COMPLETA v9.1.exe (PyInstaller onefile)

## 1. Resumen ejecutivo

La ventana del exe **existe, renderiza y responde a mensajes directos de ventana**, pero **no recibe entrada sintética de ratón/teclado** en este entorno. La causa no es un fallo de la app ni un problema de empaquetado: es el **entorno de ejecución** (sandbox de Freebuff), que filtra la introspección de ventanas/procesos y no compone la ventana de forma estable sobre el framebuffer físico. La solución robusta para el E2E del paquete es **ejecutar los flujos de UI dentro del propio proceso del exe** mediante un modo headless (`--e2e-ui <escenario>`), el mismo patrón que ya usa `--selftest-transcribe` — funciona en cualquier entorno porque no depende de entrada sintética.

## 2. Metodología

Se probaron 5 métodos de interacción contra la ventana real del exe, verificando cada uno por su efecto observable (marcado de casilla, aparición del messagebox de aviso, `first_run` en la config, píxeles del render):

| # | Método | Coordenadas usadas | Resultado |
|---|---|---|---|
| 1 | `SetCursorPos` + `SendInput` (LEFTDOWN/UP) | pantalla = captura (ventana en 0,0) | no llega |
| 2 | `PostMessage` WM_LBUTTONDOWN/UP | cliente = captura − origen (8,31) | no marca |
| 3 | `SendMessage` WM_LBUTTONDOWN/UP | cliente | no marca |
| 4 | `PostMessage` WM_MOUSEMOVE + WM_LBUTTONDOWN/UP | cliente | no marca |
| 5 | Teclado `keybd_event` (Tab×14 + Espacio) | — | no marca |

**Sí funciona** (vía mensajes directos, sin cursor):
- `PrintWindow` -> renderiza la ventana desde su propio DC (capturas válidas).
- `PostMessage` WM_MOUSEWHEEL con delta grande -> desplaza el scroll al fondo.
- `FindWindowW` / `GetWindowRect` / `SetWindowPos` / `ClientToScreen` / `GetWindowDC`.

## 3. Evidencia del diagnóstico

1. **Misma sesión, pero introspección bloqueada.** El exe corre en la **Sesión 1 (Console)**, la misma que el proceso que lo lanza. Sin embargo `GetWindowThreadProcessId(hwnd)` devuelve **pid=0** y `GetThreadDesktop(hilo)` da un **nombre vacío** (el mío es `Default` en `WinSta0`). El sandbox filtra la consulta de propietario/desktop de la ventana.
2. **Framebuffer físico inestable.** `ImageGrab.grab()` devolvió **1366x768** en una ejecución y **1024x768** en otra; en una ejecución los píxeles de pantalla en la posición de la ventana mostraban el fondo de la app y en otra **negro puro**. La composición de la ventana sobre el escritorio visible no es fiable -> los clics basados en cursor (`SetCursorPos`+`SendInput`) apuntan al escritorio físico y no a la ventana lógica.
3. **El render es correcto.** `PrintWindow` de la misma ventana muestra el asistente completo, y las casillas/radios se detectan por píxeles en las coordenadas esperadas del layout (con la corrección de marco: cliente 1120x720 dentro de 1136x759, origen de cliente (8,31)).
4. **Causa probable del fallo de clic directo.** Incluso `PostMessage` WM_LBUTTONDOWN (que no depende del cursor ni del desktop) no activa los widgets CTk, mientras que el mismo canal (PostMessage WM_MOUSEWHEEL) sí desplaza el scroll. Esto es consistente con que el runtime del sandbox **descarte la entrega de mensajes de botón** o que Tk exija estado de ratón/foco real para traducir botones a eventos `<Button-1>` (no ocurre con la rueda, que convierte el mensaje directamente en el window proc). En ambos casos, **no hay forma fiable de inyectar clics desde fuera** en este entorno.

## 4. Solución propuesta: modo headless `--e2e-ui <escenario>` dentro del exe

> **Estado: IMPLEMENTADO (14 agosto 2026).** El modo ya vive en `audioclass_v91.py`
> (`_run_e2e_ui` + rama `--e2e-ui` en `__main__`), con test de la suite
> (`test_e2e_ui.py`, integrado en `ci.yml` con xvfb) y fase `[4b]` en
> `desplegar_produccion.sh` que lo ejecuta sobre los exes recién compilados
> (onefile y onedir) — los tres escenarios pasan desde el fuente (17/17,
> 14/14, 13/13) y se validan sobre los binarios en cada despliegue.

En lugar de simular clics desde fuera, el exe **ejecuta el flujo real de UI dentro de su propio proceso** y reporta el resultado por archivos + exit code. Es el mismo patrón que `--selftest-transcribe` (ya empaquetado y validado), ampliado a la UI:

```
AudioClass.exe --e2e-ui wizard    # asistente: widgets, gate de consentimiento, completar
AudioClass.exe --e2e-ui config    # dialogo de Configuracion: selector de proveedor, privacidad
AudioClass.exe --e2e-ui widgets   # inventario de widgets clave de la UI principal
AudioClass.exe --e2e-ui mic       # selectores de microfono + medicion de nivel (audio sintetico)
```

**Cómo funciona (boceto en `audioclass_v91.py`, bloque `__main__`):**
- `wizard`: crea `App()` con `first_run=True` -> comprueba que existen `wiz_priv_ack`, `wiz_ia_consent`, `wiz_gemini`, `wiz_mode`, `wiz_mic_menu` (selector de microfono) -> verifica el **gate** (llamar `_finish_wizard()` sin aceptar -> `first_run` sigue `True` y se registra el aviso) -> simula el aceptado real (`wiz_priv_ack.set(True)` + `_finish_wizard()`, eligiendo el primer microfono real si hay) -> verifica `first_run=False`, `ia_consent=False` (opt-in), `mic_device` persistido y que la UI principal se construyó.
- `config`: `first_run=False` -> `_open_config()` -> verifica selector de proveedor Gemini/OpenAI, selector de microfono ("Micrófono de grabación"), sección "Privacidad", botones clave, y la ventana del optimizador de microfono con su selector propio -> cierra.
- `mic`: `first_run=False` -> selectores de microfono (Configuracion + Optimizador) -> resolucion por nombre (`_mic_device_id_for`: sin config -> `None`, inexistente -> `None`, real -> id) -> **medicion de nivel del pre-check con AUDIO SINTETICO** (sin abrir el microfono real: `sd.InputStream` se reemplaza por un stream fake): `_mic_probe_worker` mide p90 alto/silencio, `_mic_probe_done` decide advertencia vs grabar (callbacks sustituidos, sin dialogos ni grabacion real), y el medidor en vivo del dialogo emite niveles por la cola -> cierra.
- `widgets`: recorre el árbol de la UI principal y escribe un inventario (botones, etiquetas, estado) para verificar que el empaquetado no perdió nada.
- Resultado: `e2e_report.txt` + `exit 0/1` (con traceback en `e2e_error.txt`).

**Integración:** `desplegar_produccion.sh` (fase [4]) y `.github/workflows/release.yml` ejecutan los tres escenarios sobre **los exes recién compilados** (onefile y onedir). Esto cierra el hueco del E2E empaquetado con una prueba real del binario, independiente del entorno.

**Ventajas:** funciona en CI (GitHub Actions) y en el sandbox local; prueba el código que realmente se distribuye; sin coordenadas ni entrada sintética; reutiliza el patrón ya probado.

## 5. Complementos (visual y harness)

- **Visual:** `PrintWindow` sí funciona en este entorno -> se mantienen las capturas reales del exe (`_captura_*.png`) como artefacto de revisión humana de la tipografía/layout.
- **Interacción fina:** los flujos con mucho diálogo se cubren con el **harness** (mismo código/fuentes en proceso) y los tests existentes (`test_privacy_consent.py`, `test_ui_v91.py`, `test_wcag_contrast.py`).

## 6. Alternativas evaluadas y descartadas

| Alternativa | Motivo de descarte |
|---|---|
| UI Automation (pywinauto/uiautomation) | Depende de la superficie UIA de Tk en el bundle (no garantizada) y de la misma cola de entrada en algunos casos; añade dependencia pesada. |
| Arreglar la composición de la ventana en el sandbox | El framebuffer varía entre ejecuciones (1024 vs 1366) — es inestable por diseño del entorno; no hay API fiable para forzarlo. |
| Enviar clics al hilo del exe vía `SendInput` cruzando sesiones | `GetWindowThreadProcessId` devuelve pid=0 (introspección filtrada); no se puede localizar el hilo objetivo de forma fiable. |
| `event_generate`/`invoke` desde fuera | Imposible: requiere ejecutar código dentro del proceso del exe (justo lo que `--e2e-ui` hace de forma soportada). |

## 7. Conclusión

El exe no recibe clics sintéticos por el **aislamiento del entorno** (filtro de entrada + composición inestable), no por un defecto de la app. La vía fiable de E2E empaquetado es el **modo headless `--e2e-ui` dentro del exe** (patrón ya existente con `--selftest-transcribe`), complementado por capturas `PrintWindow` para lo visual y el harness para interacciones finas.

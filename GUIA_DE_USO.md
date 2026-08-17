# AudioClass — Guía de Uso Súper Fácil

> **¿Para quién es esta guía?** Para ti, que quieres grabar tus clases y convertirlas en
> apuntes listos para estudiar, **sin necesidad de saber programar ni usar la terminal**.

AudioClass hace **3 cosas por ti**:

1. **Graba** tu clase con el micrófono (y limpia el audio automáticamente).
2. **Transcribe** lo que dijo el profesor (convierte la voz en texto).
3. **Analiza** el texto con inteligencia artificial (resúmenes, guías, exámenes, tarjetas).

---

## Paso 0 — Instalar (solo una vez, 5-20 minutos)

### Opción A — La más fácil: un solo clic (recomendada)

1. Entra a la carpeta del proyecto.
2. Haz **doble clic en `build.bat`**.
3. El instalador hace **todo por ti**, paso a paso:
   - Detecta si tienes Python (y si no, lo instala solo con winget).
   - Crea un espacio aislado (no toca el resto de tu PC).
   - Instala todas las librerías y el modelo de voz.
   - Prueba la conexión con Gemini (opcional).
   - Crea un acceso directo **"AudioClass" en tu escritorio** y abre la app.
4. Espera a que diga "¡TODO LISTO!".

> La primera vez tarda 10-20 minutos (descarga Python, librerías y el modelo de voz).
> No cierres la ventana mientras instala.

### Opción B — Manual (solo si prefieres la terminal)

1. Instala **Python** desde [python.org/downloads](https://www.python.org/downloads/).
   - **Importante:** al instalar, marca la casilla **"Add python.exe to PATH"**.
2. Abre una **terminal** (busca "cmd" o "Terminal" en tu PC).
3. Pega esto y presiona Enter (tarda unos minutos, es normal):

```bash
pip install -r requirements_v91.txt
```

4. Cierra la terminal. ¡Listo!

> Si tu PC no reconoce el comando `pip`, busca en YouTube "instalar Python en Windows
> marcar add to PATH" — hay cientos de videos paso a paso.

---

## Paso 1 — Abrir la app

1. Entra a la carpeta del proyecto.
2. Haz doble clic en el icono **"AudioClass" de tu escritorio** (creado en el Paso 0),
   o en **`Iniciar AudioClass.bat`** dentro de la carpeta.
   (O, si prefieres la terminal, escribe:)

```bash
audiclass_env\Scripts\python.exe audioclass_v91.py
```

3. Aparecerá una pantalla de bienvenida con **3 preguntas fáciles**:
   - **¿Dónde grabarás?** -> Elige tu ambiente (Clase Universitaria, Conferencia, etc.)
   - **¿Tienes API Key de Gemini?** -> **Puedes dejarlo vacío** y añadirla después.
     (Opcional pero recomendado: consíguela gratis en [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey))
   - **¿Cómo transcribirás?** -> Elige **"En mi computadora"** (rápido y sin internet).

4. Pulsa **"Comenzar a usar AudioClass"**.

---

## Paso 2 — Grabar tu clase

1. Pulsa el botón rojo **"Grabar mi clase"**.
2. **Mantén silencio los primeros segundos** (así la app "aprende" el ruido del aula).
3. Habla con normalidad durante la clase.
4. Cuando termines, pulsa **"Detener"**.

La app mejora el audio sola: quita ruido, silencios y hace que la voz se escuche clara.

---

## Paso 3 — Transcribir (la voz se vuelve texto)

1. Pulsa **"Transcribir"**.
2. Espera: verás una barra de progreso mientras el texto aparece en pantalla.
3. ¿Quieres que cada frase lleve su **hora**? Pulsa **"Con tiempos"** en su lugar.

> La **primera vez** que transcribes en tu PC, la app descarga un pequeño modelo de
> voz (unos minutos). Las siguientes veces es más rápido.

---

## Paso 4 — Analizar con Inteligencia Artificial

En el panel **"Adaptación Inteligente"**:

1. Pulsa **"Análisis Académico Profundo"** -> obtienes:
   - **Resumen ejecutivo** (el tema de la clase en un párrafo)
   - **Tesis central** (la idea principal)
   - **Pilares argumentales** (hasta 5 ideas clave)
   - **Evidencia y datos duros** (cifras, fechas, definiciones textuales)
   - **Registro de filtrado** (lo que se descartó: murmullos, anécdotas)

2. Otras opciones: **Resumen**, **Guía de estudio**, **Tarjetas**,
   **Preguntas de examen**, **Mapa conceptual**, **Texto limpio**, **Cronología**.

> Esto necesita una **API Key de IA**. En **Configuración -> Proveedor de IA**
> elige **Gemini** (gratis en aistudio.google.com/app/apikey) u **OpenAI**
> (platform.openai.com/api-keys), pega tu key -> **Probar Conexión** ->
> debe decir "[OK] API Key válida". La clave se guarda cifrada en tu PC.

---

## Paso 5 — Guardar o compartir

- **"Guardar PDF"** -> crea un PDF con la transcripción.
- **"Google Docs"** -> crea un documento en tu Google Drive
  (requiere configurarse una sola vez, ver abajo).
- Todo se guarda solo en tu carpeta:
  **`~/AudioClass_Recordings`** (dentro de tu carpeta de usuario).

---

## MODO FÁCIL (recomendado)

1. Activa el interruptor verde **"MODO FÁCIL"** arriba.
2. Grabas tu clase -> pulsas Detener -> **la app hace TODO sola**:
   procesa -> transcribe -> analiza académicamente.
3. Solo esperas y listo. 

---

## MODO GUIADO (lo esencial a la vista)

La app arranca en **Modo Guiado**: solo ves lo importante —
grabar, transcribir, analizar y guardar. Sin distracciones.

**La primera vez que abres la app**, el asistente de bienvenida te pregunta:

- **"Soy nuevo — vista simple (recomendado)"** -> Modo Guiado activado.
- **"Soy avanzado — quiero ver todas las opciones"** -> todo visible.

Después puedes cambiarlo cuando quieras:

1. Pulsa el botón **"Opciones avanzadas"** en la barra lateral para
   mostrar los paneles avanzados (perfil de audio, motor, modelo, plantillas extra).
2. Para volver a la vista simple, pulsa **"Modo Guiado"** (el mismo botón).
3. La app recuerda tu elección: si la desactivas, seguirá desactivada
   la próxima vez que la abras.

---

## Configurar Google Docs (opcional, una sola vez)

1. Ve a [console.cloud.google.com](https://console.cloud.google.com) (inicia sesión con tu Google).
2. Crea un proyecto -> busca **"Google Docs API"** -> **Habilitar**.
3. **Credenciales -> Crear credenciales -> ID de cliente de OAuth -> Aplicación de escritorio**.
4. Descarga el archivo **`client_secret.json`**.
5. En AudioClass: **Configuración -> Google Docs -> Examinar…** (elige el json)
   -> **Conectar con Google** -> autoriza en tu navegador.
6. Ya puedes pulsar **"Google Docs"** para exportar tus clases.

---

## Problemas comunes

| Situación | Solución |
|---|---|
| "no se encontró Python" | No marcaste *Add to PATH* al instalar. Reinstala Python marcando la casilla. |
| El botón Transcribir está gris | Primero graba una clase y pulsa Detener. |
| "Sin API Key" | Configuración -> pega tu key de aistudio.google.com/app/apikey -> Probar Conexión. |
| La clase duró 3 horas | No pasa nada: la app la divide sola en partes. |
| Sin internet | Usa modo local con el modelo *tiny*: todo funciona sin conexión. |
| La primera transcripción tarda | Es normal: descarga el modelo de voz. Espera a que termine. |

---

## Preguntas frecuentes

- **¿Necesito saber programar?** No. Todo se controla con botones.
- **¿Necesito internet?** Para grabar y transcribir en tu PC, no. Solo para la IA de Gemini.
- **¿Funciona en español?** Sí, automáticamente.
- **¿Dónde están mis archivos?** En `~/AudioClass_Recordings`.
- **¿Es seguro?** Tu audio y tus textos se quedan en tu computadora (solo la IA de Gemini
  recibe el texto cuando analizas, y Google Docs cuando exportas).

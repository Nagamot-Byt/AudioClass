# Politica de Privacidad — AudioClass

**Ultima actualizacion:** 24 de agosto de 2026  
**Version:** 1.0

---

## 1. Resumen

AudioClass es una aplicacion de escritorio para la transcripcion y analisis de clases grabadas. Esta politica describe como se maneja la informacion dentro de la aplicacion.

**Principio clave:** AudioClass procesa audio localmente por defecto. Los datos solo se envian a servicios externos cuando el usuario lo configura y autoriza explicitamente.

---

## 2. Datos que recopila AudioClass

### 2.1 Datos procesados localmente (no salen de tu equipo)

- **Archivos de audio** (.wav, .mp3, etc.): Se procesan localmente con los motores Whisper o faster-whisper.
- **Texto transcrito**: Se genera y almacena localmente en tu equipo.
- **Configuracion de la app**: Preferencias, modelo seleccionado, tema, idioma.

### 2.2 Datos que se envian externamente (solo si tu lo configuras)

| Servicio | Datos enviados | Cuando se envian | Requisito |
|----------|---------------|------------------|-----------|
| **Google Gemini API** | Audio o texto transcrito + prompt de analisis | Solo al usar Adaptacion con Gemini habilitada | API key del usuario |
| **OpenAI API** | Texto transcrito + prompt de analisis | Solo al usar Adaptacion con OpenAI habilitada | API key del usuario |
| **Google Colab** | Audio crudo para transcripcion | Solo al usar el modo Colab server | Servidor Colab configurado |

**Importante:** Las API keys (Gemini, OpenAI) se almacenan localmente en `~/.audioclass/config.json` cifradas con DPAPI (Windows) o en texto plano (Linux/macOS). Nunca se envian a servidores de AudioClass.

### 2.3 Datos de uso (metricas internas)

AudioClass registra metricas de uso locales (duracion de transcripciones, formatos exportados, errores). Estas metricas:
- Se almacenan SOLO en tu equipo (`~/.audioclass/metrics.json`)
- No se envian a ningun servidor externo
- Puedes eliminarlas borrando el archivo

---

## 3. Cookies y Tracking

AudioClass NO utiliza:
- Cookies
- Google Analytics ni ningun tracker de analytics
- Pixel de rastreo
- Identificadores de publicidad
- Telemetria automatica

---

## 4. Almacenamiento y Seguridad

- **Archivos de audio**: Se procesan en memoria o en archivos temporales que se eliminan despues del procesamiento.
- **Transcripciones**: Se almacenan solo si el usuario exporta explicitamente (PDF, DOCX, etc.).
- **API Keys**: Se almacenan localmente y nunca se transmiten a servidores de AudioClass.
- **Backups de configuracion**: Se guardan en `~/.audioclass/backups/` solo en tu equipo.

---

## 5. Derechos GDPR / LGPD

Si eres usuario en la Union Europea o Brasil, tienes derecho a:

- **Acceso**: Saber qué datos procesa AudioClass (esta politica).
- **Rectificacion**: Modificar tu configuracion en cualquier momento.
- **Eliminacion**: Borrar `~/.audioclass/` para eliminar todos los datos locales.
- **Portabilidad**: Exportar tu configuracion desde la app.
- **Oposicion**: No usar los motores de IA externos (usar solo transcripcion local).

---

## 6. Menores de edad

AudioClass no recopila datos personales identificables. Si eres menor de 18 anos, utiliza la app con supervision de un adulto, especialmente si configuras servicios de IA externos.

---

## 7. Cambios en esta politica

Si esta politica cambia, la nueva version se incluira en la siguiente release de AudioClass y se actualizara la fecha al inicio de este documento.

---

## 8. Contacto

Si tienes preguntas sobre esta politica de privacidad, contacta al desarrollador a traves de:
- GitHub Issues: https://github.com/Nagamot-Byt/AudioClass/issues
- Email: [consultar en el repositorio]

---

## 9. servicios de terceros

Las politicas de privacidad de los servicios de terceros que AudioClass puede utilizar son:

- **Google Gemini API**: https://policies.google.com/privacy
- **OpenAI API**: https://openai.com/privacy
- **Whisper / faster-whisper**: Procesamiento 100% local, sin envio de datos.

---

*Este documento es informativo y no constituye asesoramiento legal. Consulta a un profesional para compliance especifico.*

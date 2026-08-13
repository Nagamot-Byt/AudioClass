# 🔏 Firma de código de AudioClass (eliminar SmartScreen)

El aviso "Windows protegió tu PC" aparece porque el exe **no está firmado**.
La solución definitiva es firmar con un **certificado de firma de código**
(de pago). Un certificado **self-signed NO sirve** para SmartScreen: Windows
lo trata como editor desconocido (a veces peor que no firmar).

## Opción real (recomendada): certificado OV/EV de firma de código
1. Comprar un certificado de firma de código en un proveedor conocido
   (p. ej. DigiCert, Sectigo, GlobalSign) — OV ~200-400 USD/año, EV más caro
   pero sin advertencias desde el primer día.
2. Instalar el certificado en la máquina de build y anotar su huella:
   ```powershell
   Get-ChildItem Cert:\CurrentUser\My | Format-Table Thumbprint, Subject
   ```
3. Firmar el exe (incluye timestamp para que no expire la firma):
   ```powershell
   signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
     /sha1 <THUMBPRINT> "AudioClass COMPLETA v9.1.exe"
   ```
   `signtool` viene con el Windows SDK o con Visual Studio.
4. Verificar:
   ```powershell
   signtool verify /pa /v "AudioClass COMPLETA v9.1.exe"
   Get-AuthenticodeSignature "AudioClass COMPLETA v9.1.exe" | Select Status
   ```
5. Re-firmar tras **cada** build (añadirlo al final de `desplegar_produccion.sh`):
   ```bash
   signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /sha1 "$CERT_THUMBPRINT" "AudioClass COMPLETA v9.1.exe"
   ```
   ⚠️ Firmar después de compilar y ANTES de crear el zip (el zip debe contener
   el exe firmado).

## Mientras no haya certificado (ya implementado)
- **`LEEME.txt` dentro del zip** con los pasos exactos:
  "Más información" → "Ejecutar de todos modos"; o clic derecho →
  Propiedades → **Desbloquear** (para archivos bajados de internet).
- **`CHECKLIST_INSTALACION.md`**: sección SmartScreen con los pasos del
  usuario limpio y la nota de NO desactivar SmartScreen ni el antivirus.

## Notas
- La reputación de SmartScreen también mejora con el tiempo si el exe se
  descarga y ejecuta sin quejas (aunque sin firma seguirá avisando).
- El aviso es **solo del primer arranque**: una vez ejecutado "de todos
  modos", Windows recuerda la decisión para ese archivo.

#!/usr/bin/env bash
# apply_signpath.sh — Guia interactiva para aplicar a SignPath Foundation
# Ejecuta: bash apply_signpath.sh

set -e

echo "============================================================"
echo "  AudioClass — Aplicacion a SignPath Foundation"
echo "============================================================"
echo ""
echo "SignPath Foundation provee certificados de firma de codigo"
echo "GRATUITOS para proyectos de open source."
echo ""
echo "Tu proyecto ya cumple estos requisitos:"
echo "  [OK] Licencia MIT (OSI-approved)"
echo "  [OK] Sin codigo propietario"
echo "  [OK] Proyecto activamente mantenido"
echo "  [OK] Release publicada en GitHub"
echo "  [OK] Documentacion completa (README, EULA, Privacidad)"
echo "  [OK] CODE_SIGNING_POLICY.md creado"
echo "  [OK] Self-signing implementado en CI"
echo ""
echo "Pendientes:"
echo "  [  ] Habilitar MFA en GitHub"
echo "  [  ] Crear organizacion GitHub (si Nagamot-Byt es cuenta personal)"
echo "  [  ] Crear teams maintainers y approvers"
echo "  [  ] Enviar solicitud en signpath.org"
echo ""

echo "PASO 1: Habilitar MFA en GitHub"
echo "  1. Ve a https://github.com/settings/security"
echo "  2. En 'Two-factor authentication', clic 'Enable'"
echo "  3. Sigue los pasos con tu telefono"
echo "  4. GUARDA los codigos de recuperacion"
echo ""
read -p "  Ya habilitaste MFA? (s/n): " mfa
if [ "$mfa" != "s" ]; then
    echo "  Hazlo primero y vuelve a ejecutar este script."
    exit 0
fi

echo ""
echo "PASO 2: Crear organizacion GitHub"
echo "  1. Ve a https://github.com/organizations/plan"
echo "  2. Selecciona el plan gratuito"
echo "  3. Nombre: Nagamot-Byt (o el que prefieras)"
echo "  4. Clic 'Complete setup'"
echo ""
read -p "  Ya creaste la organizacion? (s/n): " org
if [ "$org" != "s" ]; then
    echo "  Hazlo primero y vuelve a ejecutar este script."
    exit 0
fi

echo ""
echo "PASO 3: Crear teams en GitHub"
echo "  Ve a https://github.com/orgs/Nagamot-Byt/teams/new"
echo "  Crea el team 'maintainers' (tu como unico miembro)"
echo "  Luego crea 'approvers' (tu como unico miembro)"
echo ""
read -p "  Ya creaste los teams? (s/n): " teams
if [ "$teams" != "s" ]; then
    echo "  Hazlo primero y vuelve a ejecutar este script."
    exit 0
fi

echo ""
echo "PASO 4: Enviar solicitud a SignPath"
echo "  1. Ve a https://signpath.org"
echo "  2. Clic 'Apply'"
echo "  3. Crea cuenta (gratis)"
echo "  4. Vincula el repositorio Nagamot-Byt/AudioClass"
echo "  5. Selecciona 'SignPath Foundation' como certificate provider"
echo "  6. Espera 2-3 semanas de revision"
echo ""
echo "Una vez aprobado, actualiza release.yml con:"
echo "  - name: Sign with SignPath"
echo "    uses: SignPath/signpath-action@v1"
echo ""
echo "============================================================"
echo "  Solicitud lista para enviar. Suerte!"
echo "============================================================"

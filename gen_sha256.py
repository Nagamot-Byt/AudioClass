#!/usr/bin/env python3
"""
gen_sha256.py — Genera checksums SHA-256 para los ejecutables de release.

Uso:
    python gen_sha256.py                        # busca en dist/
    python gen_sha256.py dist_onefile/AudioClass.exe  # archivo específico

Genera SHA256SUMS.txt con los hashes de todos los .exe/.AppImage encontrados.
"""

import hashlib
import os
import sys

SEARCH_DIRS = ["dist", "dist_onefile", "."]
EXTENSIONS = (".exe", ".AppImage")


def sha256_file(path: str) -> str:
    """Calcula el SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def find_executables() -> list:
    """Busca ejecutables en los directorios de búsqueda."""
    found = []
    for d in SEARCH_DIRS:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(EXTENSIONS):
                path = os.path.join(d, f)
                if os.path.isfile(path):
                    found.append(path)
    # Buscar también en la raíz
    for f in os.listdir("."):
        if f.endswith(EXTENSIONS) and os.path.isfile(f):
            if f not in [os.path.basename(p) for p in found]:
                found.append(f)
    return sorted(set(found))


def main():
    if len(sys.argv) > 1:
        files = [f for f in sys.argv[1:] if os.path.isfile(f)]
    else:
        files = find_executables()

    if not files:
        print("No se encontraron ejecutables (.exe, .AppImage)")
        return 1

    lines = []
    for path in files:
        h = sha256_file(path)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        lines.append(f"{h}  {path}")
        print(f"  {h}  {path}  ({size_mb:.1f} MB)")

    out_path = "SHA256SUMS.txt"
    with open(out_path, "w") as f:
        f.write("# SHA-256 checksums de AudioClass v9.1\n")
        f.write("# Verifica: sha256sum -c SHA256SUMS.txt\n")
        f.write('# O manualmente: sha256sum "AudioClass COMPLETA v9.1.exe"\n\n')
        f.write("\n".join(lines) + "\n")

    print(f"\nGenerado: {out_path} ({len(lines)} archivos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

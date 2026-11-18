"""Empaqueta la carpeta mkx/ como mkx.apworld y (opcional) la instala en Archipelago.

    python tools/build_apworld.py            # crea dist/mkx.apworld
    python tools/build_apworld.py --instalar # además la copia a C:\\ProgramData\\Archipelago\\custom_worlds
"""
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "mkx")
DIST = os.path.join(ROOT, "dist")
AP_DIR = os.environ.get("ARCHIPELAGO_DIR", r"C:\ProgramData\Archipelago")


def build() -> str:
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "mkx.apworld")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in sorted(files):
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, ROOT))
    return out


if __name__ == "__main__":
    path = build()
    print("Creado:", path)
    if "--instalar" in sys.argv:
        dest = os.path.join(AP_DIR, "custom_worlds", "mkx.apworld")
        shutil.copy2(path, dest)
        print("Instalado en:", dest, "(reinicia el Launcher)")

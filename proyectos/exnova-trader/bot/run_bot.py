#!/usr/bin/env python3
"""
Script wrapper para ejecutar el bot con configuración UTF-8
"""
import os
import sys
import io

# Configurar UTF-8 para la consola de Windows
if sys.platform == "win32":
    # Redirigir stdout y stderr a UTF-8
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Importar y ejecutar main
from main import main

if __name__ == "__main__":
    print("Usá 'python console_setup.py' para arrancar el bot con configuración interactiva.")
    print("Ejecutando console_setup.py...")
    import console_setup
    try:
        console_setup.run_setup()
    except KeyboardInterrupt:
        print("\n\n[STOP] Bot detenido por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

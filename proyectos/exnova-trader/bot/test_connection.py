#!/usr/bin/env python3
"""
Script de prueba para verificar la conexión a Exnova
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from exnovaapi.stable_api import Exnova

email = os.getenv("EXNOVA_EMAIL", "")
password = os.getenv("EXNOVA_PASSWORD", "")

print(f"Email: {email}")
print(f"Password: {'*' * len(password) if password else 'NO CONFIGURADA'}")
print()

if not email or not password:
    print("ERROR: Credenciales no configuradas en .env")
    sys.exit(1)

print("Intentando conectar a Exnova PRACTICE...")
print("-" * 50)

try:
    api = Exnova(email, password, active_account_type="PRACTICE")
    print("✓ Objeto Exnova creado")
    
    print("Conectando...")
    check, reason = api.connect()
    
    if check:
        print("✓ CONEXIÓN EXITOSA")
        print()
        
        # Intentar obtener balance
        try:
            balance = api.get_balance()
            print(f"✓ Balance: {balance}")
        except Exception as e:
            print(f"⚠ Error obteniendo balance: {e}")
        
        # Intentar obtener activos
        try:
            actives = api.get_all_ACTIVES()
            print(f"✓ Activos disponibles: {len(actives) if actives else 0}")
        except Exception as e:
            print(f"⚠ Error obteniendo activos: {e}")
            
    else:
        print(f"✗ CONEXIÓN FALLIDA")
        print(f"Razón: {reason}")
        
except Exception as e:
    print(f"✗ EXCEPCIÓN: {e}")
    import traceback
    traceback.print_exc()

print("-" * 50)

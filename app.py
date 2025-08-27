import os
import time
import json
import requests
from tuya_iot import TuyaOpenAPI, AuthType

# --- Variables de entorno ---
ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
ACCESS_SECRET = os.getenv("TUYA_ACCESS_SECRET")
REGION = os.getenv("TUYA_REGION", "eu")  # 'eu' para Western Europe
ENDPOINT = f"https://openapi.tuya{REGION}.com"
DEVICE_ID = os.getenv("DEVICE_ID")       # <- PON AQUÍ el Device ID en Railway (variable)
VSH_URL = os.getenv("VSH_URL")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "20"))  # cada cuántos segundos consultar

if not all([ACCESS_ID, ACCESS_SECRET, DEVICE_ID, VSH_URL]):
    raise RuntimeError("Faltan variables: TUYA_ACCESS_ID, TUYA_ACCESS_SECRET, DEVICE_ID, VSH_URL")

# --- Cliente Tuya OpenAPI ---
openapi = TuyaOpenAPI(ENDPOINT, ACCESS_ID, ACCESS_SECRET, AuthType.CUSTOM)
openapi.connect()
print("✅ Conectado a Tuya OpenAPI:", ENDPOINT)

# Recordar último estado para no disparar repetido
last_leak = None

def read_leak_status():
    """
    Lee el estado del sensor por API.
    Devuelve True si hay fuga, False si no, None si no se encuentra el código.
    """
    path = f"/v1.0/devices/{DEVICE_ID}/status"
    res = openapi.get(path)
    # Estructura esperada: {'code': 200, 'success': True, 'result': [{'code':'water_leak','value':False}, ...]}
    if not res or not res.get("success"):
        print("⚠️ Respuesta API no válida:", res)
        return None

    statuses = res.get("result", [])
    leak = None
    # Códigos típicos de sensores de agua en Tuya
    for st in statuses:
        code = st.get("code")
        value = st.get("value")
        if code in ("water_leak", "watersensor_state", "alarm", "flood"):
            leak = bool(value)
            break

    return leak

while True:
    try:
        leak = read_leak_status()
        if leak is None:
            print("ℹ️ No encontré código de fuga en el dispositivo (aún). Reintentando...")
        else:
            if last_leak is None:
                last_leak = leak

            if leak and not last_leak:
                print("💧 Fuga detectada → llamo a Alexa…")
                try:
                    r = requests.get(VSH_URL, timeout=10)
                    print("➡️ Alexa respondió:", r.status_code)
                except Exception as e:
                    print("❌ Error llamando a Alexa:", e)

            last_leak = leak

        time.sleep(POLL_SECONDS)

    except Exception as e:
        print("❌ Error en bucle principal:", e)
        time.sleep(POLL_SECONDS)

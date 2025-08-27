import os
import time
import json
import requests
from tuya_iot import TuyaOpenAPI, TuyaOpenPulsar, AuthType

# Credenciales desde variables de entorno
ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
ACCESS_KEY = os.getenv("TUYA_ACCESS_SECRET")
REGION = os.getenv("TUYA_REGION", "eu")
ENDPOINT = f"https://openapi.tuya{REGION}.com"
PROJECT_ID = os.getenv("TUYA_PROJECT_ID")
PULSAR_URL = os.getenv("TUYA_PULSAR_URL")
VSH_URL = os.getenv("VSH_URL")

openapi = TuyaOpenAPI(ENDPOINT, ACCESS_ID, ACCESS_KEY, AuthType.CUSTOM)
openapi.connect()

def on_message(msg):
    try:
        payload = json.loads(msg.data())
        print("Evento recibido:", payload)

        for status in payload.get("status", []):
            code = status.get("code")
            value = status.get("value")

            if code in ["water_leak", "watersensor_state", "alarm", "flood"] and value:
                print("💧 Fuga detectada → apagando aire…")
                requests.get(VSH_URL)

    except Exception as e:
        print("Error procesando mensaje:", e)

pulsar = TuyaOpenPulsar(
    ACCESS_ID, ACCESS_KEY, PULSAR_URL, "default", on_message, AuthType.CUSTOM
)
pulsar.start()

while True:
    time.sleep(5)

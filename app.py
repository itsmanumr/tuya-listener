import os
import time
import json
import requests
import pulsar
import hmac
import hashlib

# --- Variables de entorno ---
ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
ACCESS_SECRET = os.getenv("TUYA_ACCESS_SECRET")
PROJECT_ID = os.getenv("TUYA_PROJECT_ID")
PULSAR_URL = os.getenv("TUYA_PULSAR_URL")
VSH_URL = os.getenv("VSH_URL")

# --- Función para generar token de autenticación ---
def gen_token():
    t = str(int(time.time() * 1000))
    message = ACCESS_ID + t
    sign = hmac.new(
        ACCESS_SECRET.encode(),
        msg=message.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    # El formato real del token Tuya lleva también el método de firma
    token = f"{ACCESS_ID}:{t}:{sign}:hmacSha256"
    return token

token = gen_token()

print("🔌 Conectando a Tuya Pulsar en", PULSAR_URL)

client = pulsar.Client(
    service_url=PULSAR_URL,
    authentication=pulsar.AuthenticationToken(token)
)

# --- Topic correcto para mensajes de estado ---
topic = f"persistent://{ACCESS_ID}/out/event"

consumer = client.subscribe(topic, subscription_name="railway-listener")

print("✅ Suscrito al topic:", topic)

# --- Bucle principal ---
while True:
    msg = consumer.receive()
    try:
        payload = json.loads(msg.data())
        print("📩 Evento recibido:", json.dumps(payload, indent=2))

        # Procesar estados reportados
        if "status" in payload:
            for status in payload["status"]:
                code = status.get("code")
                value = status.get("value")
                if code in ["water_leak", "watersensor_state", "alarm", "flood"] and value:
                    print("💧 Fuga detectada → apagando aire…")
                    try:
                        r = requests.get(VSH_URL, timeout=10)
                        print("➡️ Alexa respondió:", r.status_code)
                    except Exception as e:
                        print("❌ Error llamando a Alexa:", e)

        consumer.acknowledge(msg)

    except Exception as e:
        print("⚠️ Error procesando mensaje:", e)
        consumer.negative_acknowledge(msg)

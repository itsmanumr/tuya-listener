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
PULSAR_URL = os.getenv("TUYA_PULSAR_URL")
VSH_URL = os.getenv("VSH_URL")
SUBSCRIPTION_NAME = os.getenv("SUBSCRIPTION_NAME")  # ej: y4kfus98qc93u8hfpjs4-sub

if not SUBSCRIPTION_NAME:
    raise RuntimeError("Falta SUBSCRIPTION_NAME (pon el nombre exacto de Subscription en Tuya).")

# --- Token Tuya (HMAC-SHA256 en HEX MAYÚSCULAS) ---
def gen_token():
    t = str(int(time.time() * 1000))
    msg = (ACCESS_ID + t).encode()
    key = ACCESS_SECRET.encode()
    sign = hmac.new(key, msg=msg, digestmod=hashlib.sha256).hexdigest().upper()
    # Formato de token usado por Tuya Token Auth
    return f"{ACCESS_ID}:{t}:{sign}:hmacSha256"

token = gen_token()

print("🔌 Conectando a Tuya Pulsar en", PULSAR_URL)
client = pulsar.Client(
    service_url=PULSAR_URL,
    authentication=pulsar.AuthenticationToken(token)
)

# Topic correcto
topic = f"persistent://{ACCESS_ID}/out/event"
print("➡️ Topic:", topic)
print("➡️ Subscription:", SUBSCRIPTION_NAME)

# Intentos de suscripción con reintentos suaves
for attempt in range(1, 8):
    try:
        consumer = client.subscribe(topic, subscription_name=SUBSCRIPTION_NAME)
        print("✅ Suscrito OK")
        break
    except Exception as e:
        print(f"❌ Fallo suscribiendo (intento {attempt}):", e)
        time.sleep(2 * attempt)
else:
    raise RuntimeError("No fue posible suscribirse al topic de Tuya.")

# --- Bucle principal ---
while True:
    msg = consumer.receive()
    try:
        payload = json.loads(msg.data())
        print("📩 Evento:", json.dumps(payload, indent=2))

        # Procesar estados reportados
        if isinstance(payload, dict) and "status" in payload:
            for status in payload.get("status", []):
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

import os
import time
import json
import requests
import pulsar
import hmac
import hashlib

ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
ACCESS_SECRET = os.getenv("TUYA_ACCESS_SECRET")
PULSAR_URL = os.getenv("TUYA_PULSAR_URL")
VSH_URL = os.getenv("VSH_URL")
SUBSCRIPTION_NAME = os.getenv("SUBSCRIPTION_NAME")  # p.ej. y4kfus98qc93u8hfpjs4-sub

if not all([ACCESS_ID, ACCESS_SECRET, PULSAR_URL, VSH_URL, SUBSCRIPTION_NAME]):
    raise RuntimeError("Faltan variables de entorno. Revisa TUYA_ACCESS_ID/SECRET, TUYA_PULSAR_URL, VSH_URL, SUBSCRIPTION_NAME")

def now_ms():
    return str(int(time.time() * 1000))

def sign_hex_upper(key: str, msg: str) -> str:
    return hmac.new(key.encode(), msg=msg.encode(), digestmod=hashlib.sha256).hexdigest().upper()

def build_tokens():
    """
    Tuya usa distintos formatos de token según la versión del tenant.
    Probamos varios hasta que funcione.
    """
    t = now_ms()
    s = sign_hex_upper(ACCESS_SECRET, ACCESS_ID + t)

    candidates = [
        # 1) Formato v2 clásico
        f"v2/{ACCESS_ID}/{t}/{s}",
        # 2) v2 + método
        f"v2/{ACCESS_ID}/{t}/{s}|signMethod=hmacSha256",
        # 3) Formato con separadores ':'
        f"{ACCESS_ID}:{t}:{s}",
        # 4) Con método al final
        f"{ACCESS_ID}:{t}:{s}:hmacSha256",
    ]
    return candidates

def try_connect_with_token(token: str):
    print(f"🔑 Probando token: {token[:20]}... (oculto)")
    client = pulsar.Client(
        service_url=PULSAR_URL,
        authentication=pulsar.AuthenticationToken(token),
        operation_timeout_seconds=10,
        io_threads=1,
        message_listener_threads=1,
    )
    topic = f"persistent://{ACCESS_ID}/out/event"
    print("➡️ Topic:", topic)
    print("➡️ Subscription:", SUBSCRIPTION_NAME)

    consumer = client.subscribe(topic, subscription_name=SUBSCRIPTION_NAME)
    print("✅ Suscrito OK con este token")
    return client, consumer

# ---------- Conexión con prueba de formatos ----------
client = None
consumer = None
last_err = None

for token in build_tokens():
    try:
        client, consumer = try_connect_with_token(token)
        break
    except Exception as e:
        last_err = e
        print("❌ Fallo suscribiendo con este token:", e)
        time.sleep(1)

if consumer is None:
    raise RuntimeError(f"No fue posible suscribirse a Tuya Pulsar. Último error: {last_err}")

# ---------- Loop principal ----------
while True:
    msg = consumer.receive()
    try:
        payload = json.loads(msg.data())
        print("📩 Evento:", json.dumps(payload, indent=2))

        if isinstance(payload, dict) and "status" in payload:
            for st in payload.get("status", []):
                code = st.get("code")
                value = st.get("value")
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

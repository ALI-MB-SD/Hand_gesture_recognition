import json
import ssl

from datetime import datetime, timezone
import paho.mqtt.client as mqtt

from app.database import SessionLocal
from app.models.command import CommandEvent

BROKER_HOST = "localhost"
BROKER_PORT = 8883  #1883

MQTT_USERNAME = "fastapi"
MQTT_PASSWORD = "1234"

client = mqtt.Client()
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

client.tls_set(
    ca_certs=r"C:\Projects\Hand_ges\My_Hands\Server\mqtt_certs\ca.crt",
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLS_CLIENT,
)

client.tls_insecure_set(False)

def handle_ack_message(payload_bytes):

    try:
        payload = json.loads(payload_bytes.decode())
        event_id = payload["event_id"]
        db = SessionLocal()
        command = (
            db.query(CommandEvent)
            .filter(CommandEvent.event_id == event_id)
            .first()
        )
        if command:
            command.status = "acked"
            command.acked_at = datetime.now(timezone.utc)
            db.commit()
            print(f"[MQTT ACK] {event_id} -> acked")
        db.close()

    except Exception as e:
        print(f"[MQTT ACK ERROR] {e}")


# MQTT MESSAGE CALLBACK
def on_message(client, userdata, msg):
    topic = msg.topic
    print(f"[MQTT RX] {topic}")
    
    if topic.endswith("/ack"):
        handle_ack_message(msg.payload)


# MQTT CONNECTION CALLBACK
def on_connect(client, userdata, flags, rc):

    print(f"[MQTT] Connected rc={rc}")
    client.subscribe(
        "gesture/device/+/ack",
        qos=1
    )
    print("[MQTT] Subscribed to ACK topics")


client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER_HOST,BROKER_PORT,60)
client.loop_start()


def publish_command(device_id: str, event_id: str, action_code: str):
    topic = f"gesture/device/{device_id}/cmd"
    payload ={
        "event_id": event_id,
        "action": action_code,
    }
    
    client.publish(
        topic,
        json.dumps(payload),
        qos=1
    )
  
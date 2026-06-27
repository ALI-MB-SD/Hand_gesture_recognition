import json
import paho.mqtt.client as mqtt

BROKER_HOST = "localhost"
BROKER_PORT = 1883

client = mqtt.Client()

client.connect(BROKER_HOST, BROKER_PORT, 60)
client.loop_start()

def publish_command(device_id: str, event_id: str, action_id: str):
    topic = f"gesture/device/{device_id}/cmd"
    payload ={
        "event_id": event_id,
        "action": action_id,
    }
    
    client.publish(
        topic,
        json.dumps(payload),
        qos=1
    )
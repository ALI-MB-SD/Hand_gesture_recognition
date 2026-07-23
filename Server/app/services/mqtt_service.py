import json
import ssl
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app.database import SessionLocal
from app.models import Device, DeviceStatusEvent, DeviceTelemetryEvent, CommandEvent, BrokerStatusEvent

from app.settings import settings

client = mqtt.Client()
client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

client.tls_set(
    ca_certs=settings.MQTT_CA_CERT ,
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLS_CLIENT,
)

client.tls_insecure_set(False)

mqtt_running = False
mqtt_thread = None
publish_lock = threading.Lock()

mqtt_broker_connected = False

broker_last_connected_at  = None
broker_last_disconnected_at  = None

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

def handle_status_message(topic: str, payload_bytes):
    now = datetime.now(timezone.utc)
    
    try:
        payload = json.loads( payload_bytes.decode())
        device_id = topic.split("/")[2]
        new_status = str(payload.get("status","")).strip().lower()
        source = str(payload.get("source","unknown")).strip().lower()
        
        if new_status not in ("online","offline"):
            print(f"[MQTT STATUS] Ignored invalid status:{new_status}")
            return
        
        
        db = SessionLocal()
        try:
            device = ( db.query(Device).filter(Device.device_id == device_id).first() )     

            if not device:
                print(f"[MQTT STATUS] Unknown device_id = {device_id}")
                return
            
            current_status = (device.status or "unknown").lower()
            
            # Update current device state
            if new_status == "online":
                device.status = "online"
                device.status_changed_at = now
                device.online_since = now
                device.offline_at = None
            
            elif new_status == "offline":
                device.status = "offline"
                device.status_changed_at = now
                device.offline_at = now
            
            # Only insert a log row when the status actually changes
            if current_status != new_status:
                db.add(DeviceStatusEvent(
                    device_id = device.id,
                    status = new_status,
                    source=source,
                ))
            
            db.commit()
            print(f"[MQTT STATUS] {device_id} -> {new_status}")
            
        finally:
            db.close()
        
    except Exception as e:
        print(f"[MQTT STATUS ERROR] {e}")

def handle_heartbeat_message(topic: str, payload_bytes):
    try:
        payload = json.loads(payload_bytes.decode())
        device_id = topic.split("/")[2]

        uptime_seconds = payload.get("uptime_seconds", None)
        wifi_rssi = payload.get("wifi_rssi", None)
        wifi_quality = payload.get("wifi_quality", None)

        if uptime_seconds is None:
            print("[MQTT HEARTBEAT] Missing uptime_seconds")
            return
        if wifi_rssi is None or wifi_quality is None:
            print("[MQTT HEARTBEAT] Missing wifi_rssi or wifi_quality")
            return

        db = SessionLocal()
        try:
            device = (
                db.query(Device)
                .filter(Device.device_id == device_id)
                .first()
            )

            if not device:
                print(f"[MQTT HEARTBEAT] Unknown device_id={device_id}")
                return

            device.current_uptime_seconds = int(uptime_seconds)
            device.current_wifi_rssi = int(wifi_rssi)
            device.current_wifi_quality = str(wifi_quality)

            db.add(
                DeviceTelemetryEvent(
                    device_id=device.id,
                    wifi_rssi=int(wifi_rssi),
                    wifi_quality=str(wifi_quality),
                    uptime_seconds=int(uptime_seconds),
                )
            )

            db.commit()
            print(
                f"[MQTT HEARTBEAT] {device_id} "
                f"rssi={wifi_rssi} quality={wifi_quality} uptime={uptime_seconds}"
            )

        finally:
            db.close()

    except Exception as e:
        print(f"[MQTT HEARTBEAT ERROR] {e}")             
                   
# MQTT MESSAGE CALLBACK
def on_message(client, userdata, msg):
    topic = msg.topic
    print(f"[MQTT RX] {topic}")
    
    if topic.endswith("/ack"):
        handle_ack_message(msg.payload)
    elif topic.endswith("/status"):
        handle_status_message(topic, msg.payload)
    elif topic.endswith("/heartbeat"):
        handle_heartbeat_message(topic, msg.payload)

# MQTT CONNECTION CALLBACK
def on_connect(client, userdata, flags, rc):
    global mqtt_broker_connected
    global broker_last_connected_at
    
    if rc == 0:
        mqtt_broker_connected = True
        broker_last_connected_at = datetime.now(timezone.utc)
        save_broker_status_event(
            connected=True,
            source="mqtt_connect",
            reason="connected successfully",
        )
        print("[MQTT] Connected")
        
        client.subscribe("gesture/device/+/ack", qos=1)
        client.subscribe("gesture/device/+/status", qos=1)
        client.subscribe("gesture/device/+/heartbeat", qos=1)
                    
        print("[MQTT] Subscribed to ACK, STATUS, HEARTBEAT, topics")
    else:
        mqtt_broker_connected = False
        save_broker_status_event(
            connected=False,
            source="mqtt_connect",
            reason=f"connection failed rc={rc}",
        )
        
        print(f"[MQTT] Connection failed rc={rc}")


def on_disconnect(client, userdata, rc):
    global mqtt_broker_connected
    global broker_last_disconnected_at
    
    mqtt_broker_connected = False
    broker_last_disconnected_at = datetime.now(timezone.utc)
    
    save_broker_status_event(
        connected=False,
        source="mqtt_disconnect",
        reason=f"disconnect rc={rc}",
    )
    
    if rc != 0:
        print("[MQTT] Connection lost")
    else:
        print("[MQTT] Disconnected")    

def save_broker_status_event(connected: bool, source: str, reason: str | None = None):
    db = SessionLocal()
    try:
        db.add(
            BrokerStatusEvent(
                connected=connected,
                source=source,
                reason=reason,
                host=settings.BROKER_HOST,
                port=settings.BROKER_PORT,
            )
        )
        db.commit()
    finally:
        db.close()
        
def get_broker_status():
    return {
        "connected": mqtt_broker_connected,
        "host": settings.BROKER_HOST,
        "port": settings.BROKER_PORT,
        "tls_enabled": True,
        "last_connected_at": broker_last_connected_at,
        "last_disconnected_at": broker_last_disconnected_at,
        "client_connected": client.is_connected(),
        "subscriptions": [
            "gesture/device/+/ack",
            "gesture/device/+/status",
            "gesture/device/+/heartbeat",
        ],
    }
    
def mqtt_connect_loop():
    while mqtt_running:
        if client.is_connected():
            time.sleep(5)
            continue
        
        try:
            print("[MQTT] Trying to connect...")

            client.connect(
                settings.BROKER_HOST,
                settings.BROKER_PORT,
                60
            )

        except Exception as e:
            print(f"[MQTT] Connect failed: {e}")

        time.sleep(5)
                
def start_mqtt():
    global mqtt_running
    global mqtt_thread
    mqtt_running = True

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    client.loop_start()

    mqtt_thread = threading.Thread(
        target=mqtt_connect_loop,
        daemon=True
    )
    
    mqtt_thread.start()
    print("[MQTT] Service started")

def stop_mqtt():
    global mqtt_running
    mqtt_running = False

    try:
        client.loop_stop()
        client.disconnect()
        print("[MQTT] Service stopped")
        
    except Exception:
        pass

def publish_command(device_id: str, event_id: str, action_code: str):
    if not client.is_connected():
        print("[MQTT] Publish skipped (broker offline)")
        return False

    topic = f"gesture/device/{device_id}/cmd"
    payload = {
        "event_id": event_id,
        "action": action_code,
    }

    with publish_lock:
        info = client.publish(
            topic,
            json.dumps(payload),
            qos=1
        )
    return info.rc == mqtt.MQTT_ERR_SUCCESS
  
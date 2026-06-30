#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>

const char ROOT_CA[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFszCCA5ugAwIBAgIUFq2F9FrMyjAeLoKkngh6tY20INAwDQYJKoZIhvcNAQEL
BQAwaTELMAkGA1UEBhMCSVIxDzANBgNVBAgMBlRlaHJhbjEPMA0GA1UEBwwGVGVo
cmFuMRAwDgYDVQQKDAdNeUhhbmRzMQwwCgYDVQQLDANJb1QxGDAWBgNVBAMMD015
SGFuZHMgTVFUVCBDQTAeFw0yNjA2MjgyMDI4MjFaFw0zNjA2MjUyMDI4MjFaMGkx
CzAJBgNVBAYTAklSMQ8wDQYDVQQIDAZUZWhyYW4xDzANBgNVBAcMBlRlaHJhbjEQ
MA4GA1UECgwHTXlIYW5kczEMMAoGA1UECwwDSW9UMRgwFgYDVQQDDA9NeUhhbmRz
IE1RVFQgQ0EwggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQCjrL2gVtQq
3AdxJBlelb+TpRFxy2LpnkPH3HU2td8WNgkewFQzzD9HOvmAmc/gXeDIxNQMI1kn
GvpqmKWvmvVUwz4sD6Tf/gc2vTG1Js9aiqVHadyM8FIcYovonjvJFN31yPzwUB6F
9pANXxnRIfWtyymggVroDVkUdooy/A65KxdB2b9SG9XTmJSjZlWX/1ILIaQUYFhr
rK7kvlrRY/48t2+3DOfptrz4okJecX7CM66u+bmy7NHzxCvE6CKbQbO7voGcynjw
X7e3lGXoUdDg9LKVq0kwo894/NHcwr08g6vt+sVblh+SlwcqOlGewDpfVtEhMDz0
Idu9BQRQcM/3PA1XgEIPEl1c8jy2hnSN7bhfBfe8kSqTvOQvIOR9IqnoyxKPB+ks
DP3lhT0jxtG4t33F3O24ipHznPplERdRHZVFYUYVzvbe27gPjMdQ85D0fykXHT7t
bPmP6ILRP2nfTAziye4DKcdikAkFoZtW53obDFm/7RkcAxgVhMKENKP+1BUEjBnp
z6U5vSgT4xuo6caIV6QP8b6O0Y4OIRPQOV5su+vsf8Pap5h8JHRGndE6KDz69t6B
nQFGqib9jEblLflVXI/K/WzosOip/9E4JqiTRFDQivpvg8NEf5tclnV7sbNC4mVc
QGalyHX8wxYp0mhraxpjcThWV0Iab8TfhwIDAQABo1MwUTAdBgNVHQ4EFgQUu/lb
oRJ+j69z//02KHUWM1WOtt8wHwYDVR0jBBgwFoAUu/lboRJ+j69z//02KHUWM1WO
tt8wDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAgEAgb1P6VE8BY4z
qcGhOmmermj2VYi5CZBAz695tM/b3BjS/o87zELD1CUG/RbissyjC1D+Y7pkyGCA
csjcGLBLdR91T0oF2F/aYqRsi2rRql1tuHuL3AVp/3yriJUhfoMWZHdNMGN+Rop6
/7pqQwR6NuB38JFXVgOl6xHxHzw5VNy1JAKPb6imGvcFfabx0JkgYQin6ZZG0+so
NZRq1iNj4WkrWn3r2NDNkcIsITqhX61QbKQoVzc2KtXMG19kznPqWprU62w9PslL
h0Z+/maHiLTBlwnblfG9ySfIgKZG1AgXP5HcB93l2O7oOZxefQh8RQ7Jt64SO6Qw
/fcZEYnUsXQJZJ9d5fqcUczqy4OYwMJAsI0dD/KwMxtzfGj2j0mtEQGDvXWuZHMS
713NFzEkVYjiUcshLeOtB51Y6adgg4seLZ+XTNhyzONRMFg15f5fTPNjoKvK0Fg+
4B2mK3KfYENzOoz4PgG7lhhpefMa8rNWWSHE5wVQuNyhnDNkzB9q+uGvSF4LMaVf
9W7YEplPbWuW1/2Lmldi59TBc2ag91dHs+XblreSnYzq4lsD5VMa8MVGtoNPhSUE
d0X/2jTehnXJH7IisKwU8coMNGyru0iMCZUh5rgNUUPBsqJohTj/lv99OOa+d451
jc2zay08JZsCsR4M5xSVVVnMoRJEnAw=
-----END CERTIFICATE-----
)EOF";

// WIFI CONFIG
const char* WIFI_SSID = "Hmb1";
const char* WIFI_PASSWORD = "15891589";

// FASTAPI SERVER
const char* SERVER_URL = "https://10.0.0.5:8443";

// MQTT BROKER
const char* MQTT_BROKER = "10.0.0.5";
//const char* MQTT_BROKER = "mqtt.local";
const int MQTT_PORT = 8883;

// DEVICE
const char* DEVICE_ID = "esp32_light_2";

const char* DEVICE_API_KEY =
"7a7263fdc19fdfba496f8dcb01be74c2ce0d3fc12cef56989c5932136e062e59";

const int LED_PIN = 4;

WiFiClientSecure wifiClient;
PubSubClient mqttClient(wifiClient);

// WIFI
void connectWifi(){
    Serial.print("Connecting WiFi");
    WiFi.begin(WIFI_SSID,WIFI_PASSWORD);

    while (WiFi.status() != WL_CONNECTED){
        delay(500);
        Serial.print(".");
    }

    Serial.println();
    Serial.println("WiFi Connected");
    Serial.println(WiFi.localIP());
}

// ACTIONS
void handleLightOn(){
    digitalWrite(LED_PIN, HIGH);
    Serial.println("LIGHT ON");
}

void handleLightOff(){
    digitalWrite(LED_PIN, LOW);
    Serial.println("LIGHT OFF");
}

void executeAction(String actionCode){
    Serial.print("Executing: ");
    Serial.println(actionCode);

    if (actionCode == "LIGHT_ON")
        handleLightOn();

    else if (actionCode == "LIGHT_OFF")
        handleLightOff();

    else
        Serial.println("Unknown Action");
}
//MQTT-ack
void publishAck(String eventId){
    JsonDocument doc;

    doc["event_id"] = eventId;
    doc["status"] = "acked";
    String payload;
    serializeJson(doc,payload);

    String topic =
        "gesture/device/"
        + String(DEVICE_ID)
        + "/ack";

    mqttClient.publish(
        topic.c_str(),
        payload.c_str(),
        false
    );
}

// MQTT CALLBACK
void mqttCallback( char* topic, byte* payload,unsigned int length){
    String message;

    for (unsigned int i = 0; i < length; i++)
        message += (char)payload[i];

    Serial.println();
    Serial.println("MQTT MESSAGE:");
    Serial.println(message);

    JsonDocument doc;
    DeserializationError err =
        deserializeJson(
            doc,
            message
        );

    if (err)
    {
        Serial.println("JSON Parse Error");
        return;
    }

    String eventId = doc["event_id"].as<String>();
    String action =doc["action"].as<String>();

    executeAction(action);
    publishAck(eventId);
}

// MQTT
void connectMQTT(){
    while (!mqttClient.connected()){
        Serial.print("Connecting MQTT...");

        String clientId =
            "ESP32-"
            + String(
                random(0xffff),
                HEX
            );

        if( mqttClient.connect(clientId.c_str(),"esp32_light_2","esp321234") ){
            Serial.println("Connected");
            String topic =
                "gesture/device/"
                + String(DEVICE_ID)
                + "/cmd";

            mqttClient.subscribe(topic.c_str(), 1);

            Serial.print("Subscribed: ");
            Serial.println(topic);
        }
        else
        {
            Serial.print("Failed rc=");
            Serial.println(mqttClient.state());
            delay(3000);
        }
    }

}

// SETUP
void setup(){
    Serial.begin(115200);

    pinMode(LED_PIN,OUTPUT);
    digitalWrite(LED_PIN,LOW);

    connectWifi();
    wifiClient.setCACert(ROOT_CA);

    mqttClient.setServer(MQTT_BROKER,MQTT_PORT);
    mqttClient.setCallback(mqttCallback);
}

// LOOP
void loop(){
    if (!mqttClient.connected())
        connectMQTT();

    mqttClient.loop();
}

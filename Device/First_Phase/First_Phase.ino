#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// WIFI CONFIG
const char* WIFI_SSID = "Hmb1";
const char* WIFI_PASSWORD = "15891589";

// SERVER CONFIG
const char* SERVER_URL = "http://10.0.0.5:8000";
const char* DEVICE_API_KEY =
"7a7263fdc19fdfba496f8dcb01be74c2ce0d3fc12cef56989c5932136e062e59";

// DEVICE CONFIG
const int LED_PIN = 4;

// WIFI
void connectWifi()
{
    Serial.print("Connecting to WiFi");

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
    }

    Serial.println();
    Serial.println("WiFi Connected");

    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
}

// ============================
// ACTION HANDLERS
void handleLightOn()
{
    digitalWrite(LED_PIN, HIGH);
    Serial.println("LIGHT_ON executed");
}

void handleLightOff()
{
    digitalWrite(LED_PIN, LOW);
    Serial.println("LIGHT_OFF executed");
}

// ACTION DISPATCHER
void executeAction(String actionCode)
{
    Serial.print("Executing: ");
    Serial.println(actionCode);

    if (actionCode == "LIGHT_ON")
    {
        handleLightOn();
    }
    else if (actionCode == "LIGHT_OFF")
    {
        handleLightOff();
    }
    else
    {
        Serial.println("Unknown action");
    }
}

// ACKNOWLEDGE COMMAND
void acknowledgeCommand(String eventId)
{
    HTTPClient http;
    String url =
        String(SERVER_URL)
        + "/commands/ack";

    http.begin(url);

    http.addHeader(
        "Content-Type",
        "application/json"
    );

    http.addHeader(
        "X-API-Key",
        DEVICE_API_KEY
    );

    JsonDocument doc;
    doc["event_id"] = eventId;
    String payload;

    serializeJson(doc, payload);
    int responseCode = http.POST(payload);

    Serial.print("ACK Response: ");
    Serial.println(responseCode);

    if (responseCode > 0)
    {
        String body = http.getString();
        Serial.println(body);
    }

    http.end();
}

// POLL SERVER
void checkPendingCommands()
{
    if (WiFi.status() != WL_CONNECTED)
        return;

    HTTPClient http;
    String url =
        String(SERVER_URL)
        + "/commands/pending";

    http.begin(url);

    http.addHeader(
        "X-API-Key",
        DEVICE_API_KEY
    );

    int responseCode = http.GET();

    Serial.print("Pending Response: ");
    Serial.println(responseCode);

    if (responseCode == 200)
    {
        String body = http.getString();
        Serial.println(body);
        
        JsonDocument doc;
        DeserializationError error =
            deserializeJson(doc, body);

        if (error)
        {
            Serial.println("JSON Parse Error");
            http.end();
            return;
        }

        JsonArray commands =
            doc.as<JsonArray>();
        for (JsonObject cmd : commands)
        {
            String eventId =
                cmd["event_id"]
                    .as<String>();

            String actionCode =
                cmd["action_code"]
                    .as<String>();

            executeAction(actionCode);
            acknowledgeCommand(eventId);
        }
    }

    http.end();
}

// SETUP
void setup()
{
    Serial.begin(115200);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
    connectWifi();
}

// LOOP
void loop()
{
    checkPendingCommands();
    delay(500);
}
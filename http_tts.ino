#include <WiFi.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include "AudioFileSourceICYStream.h"
#include "AudioGeneratorMP3.h"
#include "AudioOutputI2S.h"

const char* ssid     = "abhihome";
const char* password = "abhi6674";

const char* mqtt_server = "broker.hivemq.com";
const char* mqtt_topic  = "stella/play";

const char* serverURL = "http://192.168.29.142:5000/play";

// Audio components
AudioGeneratorMP3 *mp3 = nullptr;
AudioFileSourceICYStream *file = nullptr;
AudioOutputI2S *out = nullptr;

// WiFi + MQTT clients
WiFiClient espClient;
PubSubClient client(espClient);

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("🔔 MQTT Trigger: ");
  String message;
  for (int i = 0; i < length; i++) message += (char)payload[i];
  Serial.println(message);

  if (message == "play") {
    Serial.println("🎵 Starting playback...");
    if (file) delete file;
    if (mp3) delete mp3;

    file = new AudioFileSourceICYStream(serverURL);
    mp3 = new AudioGeneratorMP3();
    mp3->begin(file, out);
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Reconnecting to MQTT...");
    if (client.connect("ESP32AudioPlayer")) {
      Serial.println("connected!");
      client.subscribe(mqtt_topic);
    } else {
      Serial.print(" failed, rc=");
      Serial.print(client.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi Connected");

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);

  out = new AudioOutputI2S();
  out->SetPinout(26, 25, 22); // BCLK, LRC, DIN
  out->SetGain(0.5);
}

void loop() {
  if (!client.connected()) reconnect();
  client.loop();

  if (mp3 && mp3->isRunning()) {
    mp3->loop();
  }
}

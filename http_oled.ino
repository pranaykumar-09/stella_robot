#include <WiFi.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <PubSubClient.h>

// WiFi & Flask server
const char* ssid = "Pranay";
const char* password = "abhi6674";
const char* serverUrl = "http://192.168.111.135:5000/audio";  // Flask server

// MQTT
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* mqtt_topic = "stella/audio/text";
bool shutdownRequested = false;

WiFiClient espClient;
PubSubClient client(espClient);

// OLED
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
String scrollText = "";
int16_t scrollX = 0;
uint32_t lastScrollTime = 0;
const uint16_t scrollDelay = 75;

// I2S
#define I2S_SAMPLE_RATE   16000
#define I2S_BITS_PER_SAMPLE I2S_BITS_PER_SAMPLE_16BIT
#define I2S_BUFFER_SIZE   1024
#define I2S_WS  15
#define I2S_SD  32
#define I2S_SCK 14
int16_t i2s_buffer[I2S_BUFFER_SIZE];

void displayScrollingText() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Recognized:");

  int16_t x1, y1;
  uint16_t textWidth, textHeight;
  display.getTextBounds(scrollText, 0, 16, &x1, &y1, &textWidth, &textHeight);

  if (textWidth <= SCREEN_WIDTH) {
    display.setCursor(0, 16);
    display.println(scrollText);
  } else {
    display.setCursor(-scrollX, 16);
    display.print(scrollText);
    scrollX++;
    if (scrollX > textWidth) scrollX = -SCREEN_WIDTH;
  }
  display.display();
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  scrollText = "";
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  scrollText = message;
  Serial.println("📩 MQTT: " + scrollText);
  scrollX = 0;

  if (message == "SHUTDOWN") {
    shutdownRequested = true;
    Serial.println("🛑 Shutdown signal received.");
    scrollText = "Shutdown received!";
  }
}

void mqttReconnect() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    if (client.connect("ESP32_OLED_MIC")) {
      Serial.println("connected");
      client.subscribe(mqtt_topic);
    } else {
      Serial.print("Failed: ");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED failed");
    while (true);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Connecting WiFi...");
  display.display();

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("WiFi Connected");
  display.display();
  delay(1000);

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);

  // I2S setup
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = I2S_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S_MSB,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = I2S_BUFFER_SIZE,
    .use_apll = true,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = -1,
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
  Serial.println("🎙️ Mic initialized");
}

void loop() {
  if (!client.connected()) {
    mqttReconnect();
  }
  client.loop();

  static bool serverAvailable = false;
  static unsigned long lastCheckTime = 0;
  const unsigned long checkInterval = 1000; // check every 1 second

  // Check server availability periodically
  if (millis() - lastCheckTime > checkInterval) {
    lastCheckTime = millis();
    HTTPClient http;
    http.begin(serverUrl);  // Just attempt connection, no data yet
    http.addHeader("Content-Type", "application/octet-stream");
    int httpCode = http.POST((uint8_t *)"", 0);  // Empty POST to test server
    http.end();

    if (httpCode == 204) {
      if (!serverAvailable) {
        Serial.println("✅ Flask server is back online. Resuming audio stream...");
        scrollText = "Server online. Streaming...";
        scrollX = 0;
      }
      serverAvailable = true;
      shutdownRequested = false;  // <-- reset shutdown flag on server recovery
    } else {
      if (serverAvailable) {
        Serial.println("❌ Flask server down.");
        scrollText = "Server offline...";
        scrollX = 0;
      }
      serverAvailable = false;
    }
  }

  if (serverAvailable && !shutdownRequested) {
    // Read audio data
    size_t bytesRead;
    esp_err_t result = i2s_read(I2S_NUM_0, (void*)i2s_buffer, sizeof(i2s_buffer), &bytesRead, portMAX_DELAY);
    if (result == ESP_OK && bytesRead > 0) {
      HTTPClient http;
      http.begin(serverUrl);
      http.addHeader("Content-Type", "application/octet-stream");
      int httpCode = http.POST((uint8_t*)i2s_buffer, bytesRead);
      http.end();

      if (httpCode != 204) {
        Serial.printf("❗ HTTP Error: %d\n", httpCode);
        serverAvailable = false;  // Try again on next check
      }
    }
  }

  // OLED scroll
  if (millis() - lastScrollTime > scrollDelay) {
    displayScrollingText();
    lastScrollTime = millis();
  }
}

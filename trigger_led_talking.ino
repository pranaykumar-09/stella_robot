#include <MD_MAX72xx.h>
#include <SPI.h>

#define HARDWARE_TYPE MD_MAX72XX::FC16_HW
#define MAX_DEVICES 4
#define CS_PIN 5

MD_MAX72XX mx = MD_MAX72XX(HARDWARE_TYPE, CS_PIN, MAX_DEVICES);

const int rows = 8;
const int cols = MAX_DEVICES * 8;

unsigned long lastUpdate = 0;
int idleInterval = 300;
int activeInterval = 100;

int wave[cols];
const int triggerPin = 14; // Pin to detect speaking (HIGH = speaking)

void setup() {
  mx.begin();
  mx.control(MD_MAX72XX::INTENSITY, 5);
  mx.clear();

  pinMode(triggerPin, INPUT);

  // Initialize with a flat line
  for (int i = 0; i < cols; i++) {
    wave[i] = 3;
  }

  randomSeed(analogRead(0));
}

void loop() {
  bool isSpeaking = digitalRead(triggerPin) == HIGH;
  int interval = isSpeaking ? activeInterval : idleInterval;

  if (millis() - lastUpdate > interval) {
    lastUpdate = millis();
    mx.clear();

    if (isSpeaking) {
      // Generate animated wave
      wave[0] = random(2, 6);
      for (int i = 1; i < cols; i++) {
        int delta = random(-1, 2);
        wave[i] = constrain(wave[i - 1] + delta, 1, rows - 2);
      }
    } else {
      // Flat line immediately
      for (int i = 0; i < cols; i++) {
        wave[i] = 3;
      }
    }

    // Draw the current wave
    for (int x = 0; x < cols; x++) {
      mx.setPoint(rows - wave[x] - 1, x, true);  // Flip Y-axis
    }
  }
} 
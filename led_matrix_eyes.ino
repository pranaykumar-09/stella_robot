#include <MD_MAX72xx.h>
#include <SPI.h>

#define HARDWARE_TYPE MD_MAX72XX::FC16_HW
#define MAX_DEVICES 4
#define CS_PIN 5

MD_MAX72XX mx = MD_MAX72XX(HARDWARE_TYPE, CS_PIN, MAX_DEVICES);

const int rows = 8;
const int cols = MAX_DEVICES * 8;

bool isSpeaking = false;
unsigned long lastUpdate = 0;
int idleInterval = 300;
int activeInterval = 100;

int wave[cols];

void setup() {
  mx.begin();
  mx.control(MD_MAX72XX::INTENSITY, 5);
  mx.clear();
  randomSeed(analogRead(0));

  // Start with flatline
  for (int i = 0; i < cols; i++) {
    wave[i] = 3;
  }
}

void loop() {
  // Simulate speaking toggle (for demo)
  static unsigned long lastToggle = 0;
  if (millis() - lastToggle > 5000) {
    isSpeaking = !isSpeaking;
    lastToggle = millis();
  }

  int interval = isSpeaking ? activeInterval : idleInterval;

  if (millis() - lastUpdate > interval) {
    lastUpdate = millis();

    mx.clear();

    if (isSpeaking) {
      // Generate a new random but coherent wave
      wave[0] = random(2, 6);  // middle start
      for (int i = 1; i < cols; i++) {
        int delta = random(-1, 2);  // smooth change: -1, 0, 1
        wave[i] = constrain(wave[i - 1] + delta, 1, rows - 2);
      }
    } else {
      for (int i = 0; i < cols; i++) {
        wave[i] = 3;
      }
    }

    // Draw the wave
    for (int x = 0; x < cols; x++) {
      mx.setPoint(wave[x], x, true);
    }
  }
}

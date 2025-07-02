# Stella_Home Assistant Robot

---

STELLA is a custom-built voice-controlled AI assistant designed to run on local hardware, integrating real-time speech recognition, natural language understanding, and home automation. This assistant is designed to be lightweight, responsive, and privacy-aware, making it ideal for personal projects, offline experimentation, and smart home control. It supports both voice and typed prompts, making it robust even under network limitations.

### Key Features

* Offline wake word detection using Porcupine
* Real-time voice-to-text conversion via Vosk or Whisper.cpp
* AI-generated responses using Gemini 1.5 Flash
* Speech playback through Edge TTS streamed to ESP32
* MQTT-based communication for data and control
* Home Assistant integration for smart device automation
* Type-to-prompt fallback via web interface

---

## Project Flow: End-to-End Explanation

### 1. Wake Word Detection

The interaction begins with the assistant listening for a specific wake word ("STELLA"). This is handled locally using the **Porcupine wake word engine**, which processes audio input in real-time using a microphone connected to the PC or Raspberry Pi. This keeps the system idle and resource-efficient until user attention is requested.

### 2. Activating Listening and Flask Server

Once the wake word is detected, STELLA greets the user and launches its core components:

* A Flask web server starts to listen for audio data.
* A background thread is activated to process incoming audio and perform speech recognition.

### 3. Audio Streaming and Speech-to-Text

Audio is captured from an **INMP441 microphone** connected to an **ESP32**, which streams raw PCM audio over HTTP to the Flask server running on a local machine. The server amplifies and buffers the audio, feeding it to the **Vosk STT engine** to convert speech to text in real time.

Recognized text is checked for specific commands. If keywords like "exit", "shutdown", or "goodbye" are detected, the system terminates gracefully. Otherwise, the recognized text is forwarded as a prompt to Gemini.

### 4. Processing Prompt with Gemini AI

STELLA uses **Gemini Flash 1.5** from Google Generative AI to interpret and generate concise, conversational responses. Prompts are customized before sending to ensure responses are short, helpful, and polite. Gemini returns a text response, which is stored for playback and optionally sent via MQTT for display or logging.

### 5. Controlling Smart Devices via Home Assistant

For commands involving smart home devices, the system parses the user's intent (e.g., "turn on the light", "set brightness to 70") and sends HTTP POST requests to **Home Assistant**, which runs on a virtual machine (Oracle VirtualBox). Using a long-lived access token, the system interacts with specific entities such as a Wipro smart bulb. Actions like turning lights on/off or adjusting brightness are handled instantly.

### 6. Speech Response with Edge TTS

Once Gemini generates a reply, the Flask server uses **Edge TTS (Microsoft's text-to-speech API)** to convert the text response into an MP3 audio stream. The `/play` route on the Flask server serves this stream in chunks.

An **ESP32 with a MAX98357A DAC** fetches this audio stream and plays it through a connected speaker, allowing the user to hear STELLA’s spoken response.

Face Tracking Integration with OpenCV
To enhance user interaction and create a responsive robotic system, real-time face tracking was implemented using OpenCV and ESP32-CAM. This integration allows the robot to detect, track, and orient itself toward users, mimicking human-like engagement.
Functionality
1. Face Detection:
 Method: Haar cascade classifiers (pre-trained models like haarcascade_frontalface_default.xml) or lightweight DNN models (e.g., MobileNet-SSD) for face detection.
 Performance: Achieves ~15 FPS on a mid-range PC or Raspberry Pi 4, balancing accuracy and computational efficiency.
2. Tracking Mechanism:
 Coordinate Mapping: Detected face coordinates (x, y, width, height) are converted to servo angles using proportional control logic.
 Servo Control: ESP32 translates face position data into pan-tilt servo movements, ensuring smooth tracking.
Workflow
1. Image Capture:
 ESP32-CAM streams JPEG frames over Wi-Fi via HTTP (e.g., http://<IP>/cam-hi.jpg).
 Resolution: Optimized to 800×600 pixels for speed and clarity.
2. Face Detection & Processing (Python/OpenCV):
 Frame Fetching: Python script periodically retrieves frames from the ESP32-CAM.
 Preprocessing: Converts JPEG to grayscale for Haar cascades.
 Detection: OpenCV identifies faces and outputs bounding box coordinates.


---

Unlike commercial assistants, STELLA is modular, locally hosted, and customizable. It gives complete control to the user over audio processing, AI generation, smart home actions, and data routing — all without relying on closed-source ecosystems. It also serves as a hands-on showcase of integrating multiple protocols and tools like MQTT, HTTP, Flask, Vosk, Gemini, and Home Assistant into a cohesive AI automation pipeline.

---



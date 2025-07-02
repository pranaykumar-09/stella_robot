import queue
import pyaudio
import numpy as np
import vosk
import json
import google.generativeai as genai
import requests
import sounddevice as sd
import struct
import pvporcupine
import os
import time
import threading
from flask import Flask, request
import paho.mqtt.client as mqtt
import asyncio
import edge_tts
from flask import Response

# === MQTT Setup ===
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "stella/audio/text"

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# === Audio Setup ===
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
GAIN = 4.0

audio_queue = queue.Queue()
exit_event = threading.Event()
stream = None

# === Flask App Setup ===
app = Flask(__name__)
server_thread = None

# === Gemini Setup ===
genai.configure(api_key="AIzaSyAAR-fME5GteEQFuD3vt3FbqpceHMny_LA")
gemini_model = genai.GenerativeModel("gemini-1.5-flash")
last_gemini_text = ""
# === Vosk STT Setup ===
model = vosk.Model("vosk-model-small-en-us-0.15")
recognizer = vosk.KaldiRecognizer(model, RATE)
play_triggered = False


HOME_ASSISTANT_URL = "http://192.168.111.213:8123"  # Replace with your HA IP
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1MWU1NjUyYWFjMDc0MzA1OWQ2YTQ1NzQ3YWE5ZTczMiIsImlhdCI6MTc0OTE1NTg2MSwiZXhwIjoyMDY0NTE1ODYxfQ.9pkvfB5cr1xpDuU1xiTknaaY2ymi5zj6ooUyKLuHR7s"
ENTITY_ID = "light.wipro_rgbcw_9w_bulb"  # Replace with actual entity ID

HEADERS = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json"
}

def control_bulb(action, brightness=None):
    url = f"{HOME_ASSISTANT_URL}/api/services/light/turn_{action}"
    data = {"entity_id": ENTITY_ID}

    if action == "on" and brightness is not None:
        data["brightness"] = int(brightness * 2.55)  # 0–255 scale

    response = requests.post(url, headers=HEADERS, json=data)
    if response.status_code == 200:
        print(f"✅ Bulb turned {action} successfully.")
        return f"Bulb turned {action}"
    else:
        print(f"❌ Failed: {response.text}")
        return "Failed to control the bulb"


def greet_user():
    global last_gemini_text, play_triggered
    greeting_prompt = "Say a short, friendly assistant-style greeting like 'Hi, what can I do for you?'"
    try:
        response = gemini_model.generate_content(greeting_prompt, generation_config={"max_output_tokens": 50})
        last_gemini_text = response.text.strip()
        play_triggered = True
        mqtt_client.publish("stella/play", "play")
        print(f"👋 Greeting: {last_gemini_text}")
    except Exception as e:
        print(f"[Greeting Error] {e}")

def say_goodbye():
    global last_gemini_text, play_triggered
    goodbye_text = "Goodbye! Have a great day!"  # You can customize this or use Gemini

    # Optional: Use Gemini for dynamic goodbye
    # response = gemini_model.generate_content("Say a short friendly goodbye.")
    # goodbye_text = response.text.strip()

    last_gemini_text = goodbye_text
    play_triggered = True
    mqtt_client.publish("stella/play", "play")
    print(f"👋 Goodbye: {last_gemini_text}")




# === Gemini Function ===
def send_to_gemini(prompt):
    global last_gemini_text, play_triggered

    # Handle local intent first
    if "on" in prompt.lower():
        result = control_bulb("on")
        last_gemini_text = result
        play_triggered = True
        mqtt_client.publish("stella/play", "play")
        return result

    elif "oh" in prompt.lower():
        result = control_bulb("off")
        last_gemini_text = result
        play_triggered = True
        mqtt_client.publish("stella/play", "play")
        return result

    elif "brightness" in prompt.lower():
        import re
        match = re.search(r"(\d+)", prompt)
        if match:
            brightness = int(match.group(1))
            result = control_bulb("on", brightness)
            last_gemini_text = f"Brightness set to {brightness}%"
            play_triggered = True
            mqtt_client.publish("stella/play", "play")
            return last_gemini_text

    # Modify prompt for short & kind response
    gemini_prompt = f"Answer this briefly and kindly, in 1-2 sentences max: {prompt}"

    try:
        response = gemini_model.generate_content(
            gemini_prompt,
            generation_config={
                "max_output_tokens": 60,
                "temperature": 0.7
            }
        )
        last_gemini_text = response.text.strip()
        play_triggered = True
        mqtt_client.publish("stella/play", "play")
        return last_gemini_text
    except Exception as e:
        print(f"[Gemini Error] {e}")
        return "[Error getting response from Gemini]"




# === Flask Shutdown Handler ===
def shutdown_server():
    try:
        requests.post("http://127.0.0.1:5000/shutdown")
    except Exception as e:
        print(f"[Shutdown Error] {e}")

# === Audio Player and STT ===
def audio_player_and_stt():
    global stream
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    output=True, frames_per_buffer=CHUNK)

    while not exit_event.is_set():
        data = audio_queue.get()
        if data is None:
            break
        try:
            samples = np.frombuffer(data, dtype=np.int16)
            amplified = np.clip(samples * GAIN, -32768, 32767).astype(np.int16)
            stream.write(amplified.tobytes())

            if recognizer.AcceptWaveform(amplified.tobytes()):
                result = json.loads(recognizer.Result())
                recognized_text = result.get("text", "").strip()
                if recognized_text:
                    print(f"🗣️ Recognized: {recognized_text}")

                    if recognized_text.lower() in ["exit", "bye","goodbye", "shutdown"]:
                        print("👋 Exit command detected. Shutting down...")
                        say_goodbye()
                        time.sleep(2)
                        mqtt_client.publish(MQTT_TOPIC, "SHUTDOWN")
                        exit_event.set()
                        shutdown_server()
                        break

                    ai_response = send_to_gemini(recognized_text)
                    print(f"🤖 Gemini: {ai_response}")
                    mqtt_client.publish(MQTT_TOPIC, f"Q: {recognized_text} | A: {ai_response}")
        except Exception as e:
            print(f"[Audio Error] {e}")

    stream.stop_stream()
    stream.close()

# === Flask Routes ===
@app.route('/audio', methods=['POST'])
def audio():
    data = request.data
    if data:
        audio_queue.put(data)
    return ('', 204)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    print("🛑 Flask shutting down...")
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    return "Server shutting down...", 200

@app.route('/play', methods=['GET'])
def play_audio():
    global play_triggered

    if not play_triggered or not last_gemini_text:
        print("⏸️ No new TTS content to stream.")
        return Response(status=204)

    play_triggered = False  # ✅ Reset the trigger

    async def tts_stream():
        try:
            communicate = edge_tts.Communicate(text=last_gemini_text, voice="en-US-JennyNeural")
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except Exception as e:
            print(f"[TTS Error] {e}")
            yield b""

    def generator():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async_gen = tts_stream()
            while True:
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    return Response(generator(), mimetype="audio/mpeg")




# === Wake Word Detection ===
def detect_wake_word():
    q = queue.Queue()
    porcupine = pvporcupine.create(
        access_key="L6UM2BOy64ZJBGeXNu8z/p3tFqxzfJ+tM1N+APM0TEx9k063BeQLfw==",
        keyword_paths=["stella_wakeword.ppn"]
    )

    def audio_callback(indata, frames, time, status):
        if status:
            print(f"[Audio Callback Error] {status}")
        q.put(bytes(indata))

    try:
        with sd.RawInputStream(samplerate=16000, blocksize=512, dtype="int16",
                               channels=1, callback=audio_callback):
            print("🔎 Waiting for wake word...")
            while True:
                pcm = q.get()
                if not pcm:
                    continue
                pcm_int16 = struct.unpack_from("h" * (len(pcm) // 2), pcm)
                keyword_index = porcupine.process(pcm_int16)
                if keyword_index >= 0:
                    print("🟢 Wake word detected!")
                    porcupine.delete()
                    greet_user()  # ✅ Send greeting
                    return


    except Exception as e:
        print(f"[Wakeword Error] {e}")
        porcupine.delete()

# === Flask Server Starter ===
def start_flask_server():
    global server_thread
    server_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True)
    server_thread.start()

# === Main Loop ===
def main_loop():
    while True:
        detect_wake_word()
        exit_event.clear()
        print("🚀 Starting Flask + STT + Gemini")
        threading.Thread(target=audio_player_and_stt, daemon=True).start()
        start_flask_server()
        while not exit_event.is_set():
            time.sleep(1)
        print("🔁 Restarting wake word detection...")

# === Run Program ===
if __name__ == '__main__':
    main_loop()

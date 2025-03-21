import os
import cv2
import queue
import json
import struct
import sounddevice as sd
import vosk
import multiprocessing
import pvporcupine
import google.generativeai as genai

# === CONFIGURE KEYS & MODELS ===
ACCESS_KEY = ""  # Replace with your Porcupine key
WAKEWORD_MODEL = "stella_wakeword.ppn"  # Path to wake word model
VOSK_MODEL_PATH = "vosk-model-small-en-us-0.15"  # Path to Vosk model
GEMINI_API_KEY = ""  # Replace with your Gemini API Key

# === LOAD MODELS ===
genai.configure(api_key=GEMINI_API_KEY)
vosk_model = vosk.Model(VOSK_MODEL_PATH)

# Load Face Detection Model
prototxt_path = "deploy.prototxt"
caffemodel_path = "res10_300x300_ssd_iter_140000.caffemodel"
face_net = cv2.dnn.readNetFromCaffe(prototxt_path, caffemodel_path)

# Queue for Vosk speech recognition
q = queue.Queue()
recognizer = vosk.KaldiRecognizer(vosk_model, 16000)

# === MEMORY BUFFER FOR GEMINI ===
conversation_history = []  # Stores past interactions
MEMORY_LIMIT = 5 # Max number of exchanges before clearing memory

# === SYSTEM PROMPT FOR GEMINI PERSONALITY ===
system_prompt = """
You are Stella, a friendly AI assistant. 
- Speak casually but clearly.
- Use sarcasm and jokes when appropriate.
- Keep responses short and engaging.
- Remember past interactions to make conversations more natural.
"""


# === CALLBACK FUNCTION FOR AUDIO STREAM ===
def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    q.put(bytes(indata))


# === FACE TRACKING FUNCTION ===
def face_tracking():
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0))
        face_net.setInput(blob)
        detections = face_net.forward()

        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:  # Confidence threshold
                box = detections[0, 0, i, 3:7] * [w, h, w, h]
                (x, y, x1, y1) = box.astype("int")
                cv2.rectangle(frame, (x, y), (x1, y1), (0, 255, 0), 2)

        cv2.imshow("Face Tracking", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # Press 'ESC' to exit
            break

    cap.release()
    cv2.destroyAllWindows()


# === FUNCTION TO COMMUNICATE WITH GEMINI & REMEMBER CONVERSATION ===
def chat_with_gemini(user_input):
    global conversation_history

    # Add user input in the correct format
    conversation_history.append({"role": "user", "parts": [{"text": user_input}]})

    # Keep history within limits
    if len(conversation_history) > MEMORY_LIMIT:
        conversation_history = conversation_history[-MEMORY_LIMIT:]

    # Generate AI response
    model = genai.GenerativeModel("gemini-1.5-flash")  # Fastest Gemini model
    response = model.generate_content(conversation_history,generation_config={"max_output_tokens": 150})

    # Store the assistant's response
    conversation_history.append({"role": "assistant", "parts": [{"text": response.text}]})

    return response.text



# === SPEECH RECOGNITION FUNCTION ===
def speech_recognition():
    with sd.RawInputStream(device=1, samplerate=16000, blocksize=8192, dtype="int16",
                           channels=1, callback=audio_callback):
        print("🎤 Listening for speech...")
        while True:
            data = q.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                recognized_text = result["text"]
                print("Recognized:", recognized_text)

                if recognized_text:
                    # Send recognized speech to Gemini with memory
                    response = chat_with_gemini(recognized_text)
                    print("💬 AI Response:", response)
            else:
                partial_result = json.loads(recognizer.PartialResult())
                print("Partial:", partial_result["partial"])


# === PORCUPINE WAKE WORD DETECTION FUNCTION ===
def wake_word_detection():
    porcupine = pvporcupine.create(access_key=ACCESS_KEY, keyword_paths=[WAKEWORD_MODEL])

    with sd.RawInputStream(samplerate=porcupine.sample_rate, blocksize=porcupine.frame_length,
                           dtype="int16", channels=1) as stream:
        print("🔍 Waiting for wake word...")

        while True:
            pcm = stream.read(porcupine.frame_length)[0]
            pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)

            keyword_index = porcupine.process(pcm_unpacked)
            if keyword_index >= 0:
                print("🚀 Wake Word Detected! Starting face tracking and speech recognition...")

                # Run face tracking and STT simultaneously
                face_proc = multiprocessing.Process(target=face_tracking)
                speech_proc = multiprocessing.Process(target=speech_recognition)

                face_proc.start()
                speech_proc.start()

                face_proc.join()
                speech_proc.join()


# === MAIN EXECUTION ===
if __name__ == "__main__":
    wake_word_detection()

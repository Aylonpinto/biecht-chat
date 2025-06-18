import os
import tempfile
import sounddevice as sd
from scipy.io.wavfile import write
from pynput import keyboard
import openai
import re
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load your OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai

# Audio settings
samplerate = 44100
channels = 1
recording = []
is_recording = False


def start_recording():
    global recording
    print("🎙️  Opname gestart. Houd de toets ingedrukt...")
    recording = []

    def callback(indata, frames, time, status):
        if status:
            print(status)
        recording.append(indata.copy())

    global stream
    stream = sd.InputStream(samplerate=samplerate, channels=channels, callback=callback)
    stream.start()


def stop_recording_and_save():
    global stream
    print("🛑 Opname gestopt.")
    stream.stop()
    stream.close()

    audio_data = b"".join([chunk.tobytes() for chunk in recording])
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        audio_data = np.concatenate(recording, axis=0)
        write(f.name, samplerate, audio_data)
        return f.name


def transcribe_audio(filename):
    print("📤 Versturen naar Whisper...")
    with open(filename, "rb") as f:
        transcript = client.audio.transcriptions.create(model="whisper-1", file=f)
    print(f"📄 Transcript: {transcript.text}")
    return transcript.text


def ask_chatgpt(prompt):
    print("🤖 Versturen naar ChatGPT...")
    messages = [
        {
            "role": "system",
            "content": "Je bent een rijke zakenman waar alles draait om geld en succes. Sluit elk antwoord af met een stem in dit formaat: [voice:nova|shimmer|echo|fable|onyx|alloy]. Kies een stem die past bij de toon.",
        },
        {"role": "user", "content": prompt},
    ]
    response = client.chat.completions.create(model="gpt-4", messages=messages)
    return response.choices[0].message.content


def extract_voice_and_clean_text(text):
    match = re.search(r"\[voice:(\w+)\]", text)
    voice = match.group(1) if match else "nova"
    cleaned = re.sub(r"\[voice:\w+\]", "", text).strip()
    return voice, cleaned


def speak(text, voice="nova"):
    print(f"🔊 Voorlezen met stem: {voice}")
    response = client.audio.speech.create(model="tts-1", voice=voice, input=text)
    with open("response.mp3", "wb") as f:
        f.write(response.content)

    # Mac: afplay | Linux/RPi: mpg123 of ffplay
    os.system("afplay response.mp3")  # <- pas aan indien nodig


def on_press(key):
    global is_recording
    if key == keyboard.Key.space and not is_recording:
        is_recording = True
        start_recording()


def on_release(key):
    global is_recording
    if key == keyboard.Key.space and is_recording:
        is_recording = False
        filename = stop_recording_and_save()
        transcript = transcribe_audio(filename)
        answer_with_tag = ask_chatgpt(transcript)
        voice, answer = extract_voice_and_clean_text(answer_with_tag)
        print(f"\n🤖 Antwoord: {answer} [{voice}]")
        speak(answer, voice=voice)


# Start listener
print("Druk op spatie om te spreken (loslaten = verzenden). Ctrl+C om te stoppen.")
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

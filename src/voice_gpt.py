import os
import tempfile
import sounddevice as sd
from scipy.io.wavfile import write
import evdev
from evdev import InputDevice, categorize, ecodes
import openai
import re
import numpy as np
from dotenv import load_dotenv
import threading
import time
import subprocess
import math
import pygame
import select
import csv
import datetime
from conversation_manager import ConversationManager

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
stop_elevator = False
speaker_keepalive_minutes = 4

# Initialize pygame mixer
pygame.mixer.init()


PROMPT = "Je bent een licht aangeschoten italiaan die de persoon die de vraagt stelt stiekem probeert te versieren."

# Initialize conversation manager
conversation_manager = ConversationManager()


def start_recording():
    global recording
    print("🎙️  Opname gestart. Houd de toets ingedrukt...")
    recording = []

    def callback(indata, frames, time, status):
        if status:
            print(status)
        recording.append(indata.copy())

    global stream
    stream = sd.InputStream(
        device=1, samplerate=samplerate, channels=channels, 
        callback=callback
    )
    stream.start()


def stop_recording_and_save():
    global stream
    print("🛑 Opname gestopt.")
    stream.stop()
    stream.close()

    if not recording:
        print("⚠️  Geen audio opgenomen!")
        return None

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        audio_data = np.concatenate(recording, axis=0)
        write(f.name, samplerate, audio_data)
        return f.name


def transcribe_audio(filename):
    print("📤 Versturen naar Whisper...")
    with open(filename, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", file=f
        )
    print(f"📄 Transcript: {transcript.text}")
    return transcript.text


def ask_chatgpt(prompt):
    print("🤖 Versturen naar ChatGPT...")
    
    if conversation_manager.is_conversation_expired():
        conversation_manager.start_new_conversation()
    
    conversation_manager.log_interaction("user", prompt)
    
    system_prompt = f"{PROMPT}Sluit elk antwoord af met een stem in dit formaat: [voice:nova|shimmer|echo|fable|onyx|alloy]. Kies een stem die past bij de toon."
    messages = conversation_manager.get_conversation_for_openai(system_prompt)
    
    response = client.chat.completions.create(model="gpt-4", messages=messages)
    answer = response.choices[0].message.content
    
    conversation_manager.log_interaction("assistant", answer)
    
    return answer


def extract_voice_and_clean_text(text):
    match = re.search(r"\[voice:(\w+)\]", text)
    voice = match.group(1) if match else "nova"
    cleaned = re.sub(r"\[voice:\w+\]", "", text).strip()
    return voice, cleaned


def speak(text, voice="nova"):
    print(f"🔊 Voorlezen met stem: {voice}")
    response = client.audio.speech.create(
        model="tts-1", voice=voice, input=text, response_format="mp3"
    )
    with open("response.mp3", "wb") as f:
        f.write(response.content)

    # Stop elevator music and immediately start response
    print("🎵 Playing response...")
    stop_elevator_music()
    pygame.mixer.music.load("response.mp3")
    pygame.mixer.music.play()

    # Wait for playback to finish
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    print("✅ Playback completed")


def play_elevator_music():
    """Play continuous elevator music in background"""
    global stop_elevator
    stop_elevator = False

    if os.path.exists("elevator.mp3"):

        def play_loop():
            global stop_elevator
            elevator_sound = pygame.mixer.Sound("elevator.mp3")
            while not stop_elevator:
                elevator_sound.play()
                # Wait for the sound to finish or stop signal
                duration = elevator_sound.get_length()
                start_time = time.time()
                while time.time() - start_time < duration and not stop_elevator:
                    time.sleep(0.1)

        # Start playing in a thread
        music_thread = threading.Thread(target=play_loop)
        music_thread.daemon = True
        music_thread.start()


def stop_elevator_music():
    global stop_elevator
    stop_elevator = True
    pygame.mixer.stop()


def keep_speaker_alive():
    try:
        silent_audio = np.zeros((int(samplerate * 0.1), 1))
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            write(f.name, samplerate, silent_audio.astype(np.int16))
            
            pygame.mixer.music.load(f.name)
            pygame.mixer.music.set_volume(0.01)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.01)
            
            pygame.mixer.music.set_volume(1.0)
            os.unlink(f.name)
    except Exception as e:
        print(f"Keep-alive error: {e}")


def start_speaker_keepalive():
    def keepalive_loop():
        while True:
            time.sleep(speaker_keepalive_minutes * 60)
            keep_speaker_alive()
    
    keepalive_thread = threading.Thread(target=keepalive_loop)
    keepalive_thread.daemon = True
    keepalive_thread.start()
    print(f"🔊 Speaker keep-alive started (every {speaker_keepalive_minutes} minutes)")


def play_waiting_sequence():
    """Play elevator music"""
    # Start elevator music immediately without thread delay
    play_elevator_music()


def find_keyboard_device():
    """Find the keyboard device that responds to spacebar"""
    devices = [InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        # Look for devices that support the spacebar key (KEY_SPACE = 57)
        if ecodes.KEY_SPACE in device.capabilities().get(ecodes.EV_KEY, []):
            print(f"Found keyboard device: {device.path} - {device.name}")
            return device
    return None

def handle_events():
    """Handle keyboard events using evdev"""
    global is_recording
    
    device = find_keyboard_device()
    if not device:
        print("❌ No keyboard device found!")
        return
    
    print(f"🎹 Listening for spacebar on: {device.name}")
    print("Druk op spatie om te spreken (loslaten = verzenden). Ctrl+C om te stoppen.")
    
    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY:
                # Spacebar keycode is 57 (0x39)
                if event.code == ecodes.KEY_SPACE:
                    if event.value == 1:  # Key press
                        if not is_recording:
                            is_recording = True
                            start_recording()
                    elif event.value == 0:  # Key release
                        if is_recording:
                            is_recording = False
                            filename = stop_recording_and_save()

                            if filename is None:
                                continue

                            # Start elevator music immediately after recording stops
                            play_waiting_sequence()

                            transcript = transcribe_audio(filename)
                            answer_with_tag = ask_chatgpt(transcript)
                            voice, answer = extract_voice_and_clean_text(answer_with_tag)

                            print(f"\n🤖 Antwoord: {answer} [{voice}]")
                            speak(answer, voice=voice)
                            
                            # Clean up temp file
                            os.unlink(filename)
                            
    except KeyboardInterrupt:
        print("\n👋 Programma gestopt.")
    except Exception as e:
        print(f"❌ Error: {e}")

# Start speaker keep-alive and event handler
start_speaker_keepalive()
handle_events()

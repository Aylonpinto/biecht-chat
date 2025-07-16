import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import subprocess
import evdev
from evdev import InputDevice, ecodes

samplerate = 44100
channels = 1
recording = []
is_recording = False

def start_recording():
    global recording, stream
    print("🎙️ Recording keep-alive message...")
    recording = []

    def callback(indata, frames, time, status):
        if status:
            print(status)
        recording.append(indata.copy())

    stream = sd.InputStream(
        device=1, samplerate=samplerate, channels=channels, 
        callback=callback
    )
    stream.start()

def stop_recording_and_save():
    global stream
    print("🛑 Recording stopped.")
    stream.stop()
    stream.close()

    if recording:
        audio_data = np.concatenate(recording, axis=0)
        write("keepalive.wav", samplerate, audio_data)
        print("✅ Converting to MP3...")
        
        subprocess.run([
            "ffmpeg", "-y", "-i", "keepalive.wav", 
            "-codec:a", "mp3", "-b:a", "128k", "keepalive.mp3"
        ])
        
        print("✅ Keep-alive message saved to keepalive.mp3")
    else:
        print("⚠️ No audio recorded")

def record_keepalive():
    global is_recording
    
    device = InputDevice('/dev/input/event1')
    print(f"🎹 Press and hold SPACEBAR to record keep-alive message. Ctrl+C to exit.")
    
    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY:
                if event.code == ecodes.KEY_SPACE:
                    if event.value == 1:
                        if not is_recording:
                            is_recording = True
                            start_recording()
                    elif event.value == 0:
                        if is_recording:
                            is_recording = False
                            stop_recording_and_save()
                            return
    except KeyboardInterrupt:
        print("\n👋 Exiting...")

if __name__ == "__main__":
    record_keepalive()
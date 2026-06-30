import time
import threading
import numpy as np
import sounddevice as sd
from pynput import keyboard as kb

SAMPLE_RATE = 16000
CHANNELS = 1
PTT_KEY = kb.Key.f5


def record_ptt(on_press_callback=None):
    """
    Wait for F5 press, record while held, return raw PCM int16 bytes on release.
    Calls on_press_callback() the instant F5 is pressed — use this to stop TTS.
    Returns None if no audio was captured.
    """
    frames = []
    state = {"pressing": False, "done": False}

    def on_press(key):
        if key == PTT_KEY and not state["pressing"]:
            state["pressing"] = True
            if on_press_callback:
                on_press_callback()

    def on_release(key):
        if key == PTT_KEY:
            state["pressing"] = False
            state["done"] = True

    print("\n[Hold F5 to speak]", flush=True)

    listener = kb.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # Wait for F5 to go down
    while not state["pressing"] and not state["done"]:
        time.sleep(0.01)

    if state["done"] and not state["pressing"]:
        listener.stop()
        return None

    print("[Recording...]", flush=True)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
        while state["pressing"]:
            data, _ = stream.read(512)
            frames.append(data.copy())

    # Wait for the release event to register
    while not state["done"]:
        time.sleep(0.01)

    listener.stop()
    print("[Processing...]", flush=True)

    if not frames:
        return None

    return np.concatenate(frames, axis=0).tobytes()

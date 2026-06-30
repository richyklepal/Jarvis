import os
import threading
import numpy as np
import sounddevice as sd
from elevenlabs.client import ElevenLabs

SAMPLE_RATE = 22050
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Adam

_client = None
_stop_event = threading.Event()
_playback_thread = None


def _get_client():
    global _client
    if _client is None:
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise RuntimeError("ELEVENLABS_API_KEY not set — add it to your .env file.")
        _client = ElevenLabs(api_key=key)
    return _client


def speak(text):
    """Synthesize text and play it. Interruptible — call stop() to cut it short."""
    _stop_event.clear()
    client = _get_client()
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)

    audio_chunks = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_turbo_v2_5",
        output_format="pcm_22050",
    )
    audio_bytes = b"".join(audio_chunks)

    if not audio_bytes or _stop_event.is_set():
        return

    audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    chunk_size = 2048
    with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as out:
        for i in range(0, len(audio_array), chunk_size):
            if _stop_event.is_set():
                break
            out.write(audio_array[i : i + chunk_size])


def speak_async(text):
    """Speak in a background thread so the voice loop can continue. Returns the thread."""
    global _playback_thread
    _playback_thread = threading.Thread(target=speak, args=(text,), daemon=True)
    _playback_thread.start()
    return _playback_thread


def stop():
    """Stop current playback immediately."""
    _stop_event.set()
    if _playback_thread and _playback_thread.is_alive():
        _playback_thread.join(timeout=1.0)

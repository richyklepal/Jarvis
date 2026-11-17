"""
Text-to-speech with swappable providers. Pick one with TTS_PROVIDER in .env:

  voicestudio  local VoiceStudio server (OpenAI-compatible /v1/audio/speech, streamed PCM)
  elevenlabs   ElevenLabs cloud (needs ELEVENLABS_API_KEY) — the original provider

Default: elevenlabs (unchanged behaviour). Playback is interruptible via stop().
"""
import json
import os
import threading
import urllib.request

import numpy as np
import sounddevice as sd

DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # ElevenLabs "Adam"
VOICESTUDIO_RATE = 24000  # VoiceStudio pcm = 24 kHz 16-bit LE mono
ELEVENLABS_RATE = 22050

_client = None
_stop_event = threading.Event()
_playback_thread = None


def provider():
    return os.environ.get("TTS_PROVIDER", "elevenlabs").strip().lower()


def _play_chunks(chunks, rate):
    """Play an iterable of raw int16 PCM byte chunks as they arrive."""
    leftover = b""
    with sd.OutputStream(samplerate=rate, channels=1, dtype="float32") as out:
        for chunk in chunks:
            if _stop_event.is_set():
                break
            data = leftover + chunk
            usable = len(data) - (len(data) % 2)
            leftover = data[usable:]
            if usable:
                out.write(np.frombuffer(data[:usable], dtype=np.int16).astype(np.float32) / 32768.0)


# ---------------------------------------------------------------- elevenlabs

def _elevenlabs_chunks(text):
    global _client
    from elevenlabs.client import ElevenLabs

    if _client is None:
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise RuntimeError("ELEVENLABS_API_KEY not set — add it to your .env file.")
        _client = ElevenLabs(api_key=key)
    return _client.text_to_speech.convert(
        voice_id=os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID),
        text=text,
        model_id="eleven_turbo_v2_5",
        output_format="pcm_22050",
    )


# ---------------------------------------------------------------- voicestudio

def _voicestudio_chunks(text):
    from audio.stt import voicestudio_url, voicestudio_headers

    payload = {
        "model": os.environ.get("VOICESTUDIO_TTS_MODEL", "omnivoice"),
        "input": text[:4096],
        "voice": os.environ.get("VOICESTUDIO_VOICE", "default"),
        "response_format": "pcm",
        "stream_format": "audio",
    }
    req = urllib.request.Request(
        voicestudio_url() + "/v1/audio/speech",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **voicestudio_headers()},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=120)
    except urllib.error.URLError as e:
        raise RuntimeError(f"VoiceStudio not reachable at {voicestudio_url()} — is it running? ({e})")
    with resp:
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            yield chunk


# ---------------------------------------------------------------- public API

def speak(text):
    """Synthesize text and play it. Interruptible — call stop() to cut it short."""
    _stop_event.clear()
    try:
        if provider() == "voicestudio":
            _play_chunks(_voicestudio_chunks(text), VOICESTUDIO_RATE)
        else:
            _play_chunks(_elevenlabs_chunks(text), ELEVENLABS_RATE)
    except RuntimeError as e:
        print(f"\n[TTS error: {e}]")


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

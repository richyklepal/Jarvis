"""
Text-to-speech with swappable providers. Pick one with TTS_PROVIDER in .env:

  voicestudio  local VoiceStudio server (OpenAI-compatible /v1/audio/speech, streamed PCM)
  elevenlabs   ElevenLabs cloud (needs ELEVENLABS_API_KEY) — the original provider
  mac          free built-in Mac voice via `say` — default "Daniel", the British male voice

Default: elevenlabs if ELEVENLABS_API_KEY is set, otherwise mac on a Mac.
Playback is interruptible via stop().
"""
import json
import os
import re
import shutil
import subprocess
import sys
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


_say_proc = None
_mac_voice = None
MAC_VOICE_FALLBACKS = ["Daniel (Enhanced)", "Daniel (Premium)", "Daniel", "Oliver", "Arthur"]


def provider():
    name = os.environ.get("TTS_PROVIDER", "").strip().lower()
    if name:
        return name
    if os.environ.get("ELEVENLABS_API_KEY", "").strip() not in ("", "your_key_here"):
        return "elevenlabs"
    return "mac" if sys.platform == "darwin" else "elevenlabs"


def clean_for_speech(text):
    """Strip Markdown so the voice doesn't read out asterisks, pound signs and links."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "a link", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.M)
    text = re.sub(r"[*_`|>#]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- mac (free)

def _pick_mac_voice():
    global _mac_voice
    if _mac_voice is None:
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        installed = {m.group(1).strip() for m in re.finditer(r"^(.+?)\s{2,}[a-z]{2}[_-][A-Za-z]{2}", out, re.M)}
        wanted = os.environ.get("MAC_VOICE", "").strip()
        _mac_voice = next((v for v in ([wanted] if wanted else []) + MAC_VOICE_FALLBACKS if v in installed), "")
        if wanted and _mac_voice != wanted:
            print(f"[Voice] '{wanted}' isn't installed; using '{_mac_voice or 'system default'}'. Add voices in "
                  "System Settings → Accessibility → Spoken Content → System Voice → Manage Voices.")
    return _mac_voice


def _speak_mac(text):
    global _say_proc
    if sys.platform != "darwin" or not shutil.which("say"):
        raise RuntimeError("TTS_PROVIDER=mac only works on a Mac.")
    cmd = ["say", "-r", os.environ.get("MAC_VOICE_RATE", "180")]
    voice = _pick_mac_voice()
    if voice:
        cmd += ["-v", voice]
    _say_proc = subprocess.Popen(cmd + [text])
    while _say_proc.poll() is None:
        if _stop_event.wait(0.05):
            _say_proc.terminate()
            break


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
    text = clean_for_speech(text)
    if not text:
        return
    try:
        if provider() == "mac":
            _speak_mac(text)
        elif provider() == "voicestudio":
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
    if _say_proc and _say_proc.poll() is None:
        _say_proc.terminate()
    if _playback_thread and _playback_thread.is_alive():
        _playback_thread.join(timeout=1.0)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    line = " ".join(sys.argv[1:]) or "Good evening. All systems are online, and I am at your service."
    print(f"[{provider()} voice{': ' + _pick_mac_voice() if provider() == 'mac' else ''}] {line}")
    speak(line)

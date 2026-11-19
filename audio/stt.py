"""
Speech-to-text with swappable providers. Pick one with STT_PROVIDER in .env:

  voicestudio  local VoiceStudio server (OpenAI-compatible /v1/audio/transcriptions)
  whisper      local faster-whisper, in-process (pip install faster-whisper)
  deepgram     Deepgram cloud (needs DEEPGRAM_API_KEY) — the original provider

Default: deepgram if DEEPGRAM_API_KEY is set, otherwise local whisper (free). Every provider takes raw PCM int16 @16 kHz
mono bytes from audio/capture.py and returns the transcript string.
"""
import io
import json
import os
import uuid
import urllib.request
import wave

SAMPLE_RATE = 16000
CHANNELS = 1

_whisper_model = None


def _pcm_to_wav(pcm_bytes):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 = 2 bytes per sample
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    buf.seek(0)
    return buf.read()


def voicestudio_url():
    return os.environ.get("VOICESTUDIO_URL", "http://localhost:3900").rstrip("/")


def voicestudio_headers():
    key = os.environ.get("VOICESTUDIO_API_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


# ---------------------------------------------------------------- providers

def _deepgram(pcm_bytes):
    from deepgram import DeepgramClient, PrerecordedOptions

    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPGRAM_API_KEY not set — add it to your .env file.")
    client = DeepgramClient(api_key)
    options = PrerecordedOptions(model="nova-2", smart_format=True, language="en")
    response = client.listen.prerecorded.v("1").transcribe_raw(
        {"buffer": _pcm_to_wav(pcm_bytes), "mimetype": "audio/wav"},
        options,
    )
    return response.results.channels[0].alternatives[0].transcript


def _voicestudio(pcm_bytes):
    boundary = uuid.uuid4().hex
    fields = {"model": "whisper-1", "response_format": "json"}
    lang = os.environ.get("STT_LANGUAGE", "").strip()
    if lang:
        fields["language"] = lang
    body = b""
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\n'
        "Content-Type: audio/wav\r\n\r\n"
    ).encode() + _pcm_to_wav(pcm_bytes) + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        voicestudio_url() + "/v1/audio/transcriptions",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **voicestudio_headers()},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode()).get("text", "")
    except urllib.error.URLError as e:
        raise RuntimeError(f"VoiceStudio not reachable at {voicestudio_url()} — is it running? ({e})")


def _whisper(pcm_bytes):
    global _whisper_model
    import numpy as np
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("faster-whisper not installed — run: pip install faster-whisper")
    if _whisper_model is None:
        size = os.environ.get("WHISPER_MODEL", "base.en")
        device = os.environ.get("WHISPER_DEVICE", "auto")
        _whisper_model = WhisperModel(size, device=device, compute_type="int8" if device != "cuda" else "float16")
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    lang = os.environ.get("STT_LANGUAGE", "").strip() or None
    segments, _ = _whisper_model.transcribe(audio, language=lang, vad_filter=True)
    return " ".join(s.text for s in segments)


_PROVIDERS = {"deepgram": _deepgram, "voicestudio": _voicestudio, "whisper": _whisper}


def provider():
    name = os.environ.get("STT_PROVIDER", "").strip().lower()
    if name:
        return name
    key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    return "deepgram" if key and key != "your_key_here" else "whisper"


def transcribe(pcm_bytes):
    """Transcribe raw PCM int16 audio with the configured provider. Returns the transcript."""
    name = provider()
    fn = _PROVIDERS.get(name)
    if not fn:
        raise RuntimeError(f"Unknown STT_PROVIDER '{name}'. Use one of: {', '.join(_PROVIDERS)}")
    return (fn(pcm_bytes) or "").strip()

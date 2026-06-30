import io
import os
import wave

from deepgram import DeepgramClient, PrerecordedOptions

SAMPLE_RATE = 16000
CHANNELS = 1


def _pcm_to_wav(pcm_bytes):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 = 2 bytes per sample
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    buf.seek(0)
    return buf.read()


def transcribe(pcm_bytes):
    """Transcribe raw PCM int16 audio using Deepgram. Returns the transcript string."""
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPGRAM_API_KEY not set — add it to your .env file.")

    client = DeepgramClient(api_key)
    wav_bytes = _pcm_to_wav(pcm_bytes)

    options = PrerecordedOptions(model="nova-2", smart_format=True, language="en")
    response = client.listen.prerecorded.v("1").transcribe_raw(
        {"buffer": wav_bytes, "mimetype": "audio/wav"},
        options,
    )

    transcript = response.results.channels[0].alternatives[0].transcript
    return transcript.strip()

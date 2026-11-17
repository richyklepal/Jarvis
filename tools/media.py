"""
Image & video generation via MuAPI — the engine behind Open-Generative-AI
(Anil-matcha/Open-Generative-AI), used as the Higgsfield replacement.

MuAPI is a PAID cloud service: every generation spends credits. Per AGENT.md's
hard confirmation gate, the tools refuse to run unless `confirmed` is true, and
Jarvis must only set it after the user explicitly says yes to that generation.

Results are downloaded into the Obsidian vault (Jarvis/Media/) and logged, so
every generated asset is kept with its prompt.

API (from Open-Generative-AI src/lib/muapi.js + generationLifecycle.js):
  POST {base}/api/v1/{endpoint}  header x-api-key  → {request_id}
  GET  {base}/api/v1/predictions/{request_id}/result → {status, outputs:[url]}
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

from tools import obsidian

_SUCCESS = {"completed", "succeeded", "success"}
_FAILURE = {"failed", "error", "cancelled", "canceled"}

DEFAULT_IMAGE_MODEL = "flux-dev-image"
DEFAULT_VIDEO_MODEL = "kling-v3-turbo-standard-text-to-video"
DEFAULT_I2V_MODEL = "kling-v3-turbo-standard-image-to-video"


def _base():
    return os.environ.get("MUAPI_BASE_URL", "https://api.muapi.ai").rstrip("/")


def _key():
    key = os.environ.get("MUAPI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MUAPI_API_KEY not set — get one at muapi.ai and add it to .env.")
    return key


def _request(method, path, payload=None):
    req = urllib.request.Request(
        _base() + path,
        method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json", "x-api-key": _key(), "User-Agent": "jarvis-assistant"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:200]
        hint = {401: "bad API key", 403: "bad API key", 402: "out of credits"}.get(e.code, "")
        raise RuntimeError(f"MuAPI {e.code} {hint}: {detail}")


def _run(endpoint, payload, timeout_s):
    submit = _request("POST", f"/api/v1/{endpoint}", payload)
    rid = submit.get("request_id") or submit.get("id")
    if not rid:
        raise RuntimeError(f"MuAPI returned no request_id: {str(submit)[:200]}")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(3)
        try:
            result = _request("GET", f"/api/v1/predictions/{rid}/result")
        except RuntimeError as e:
            if " 5" in str(e)[:12]:
                continue  # transient server error — keep polling
            raise
        status = str(result.get("status", "")).lower()
        if status in _SUCCESS:
            url = (result.get("outputs") or [None])[0] or result.get("url") or (result.get("output") or {}).get("url")
            if not url:
                raise RuntimeError(f"Completed but no output URL (request {rid}).")
            return rid, url
        if status in _FAILURE:
            raise RuntimeError(f"Generation {status}: {result.get('error') or result} (request {rid})")
    raise RuntimeError(f"Timed out after {timeout_s}s — request {rid} may still finish on MuAPI.")


def _save(kind, url, prompt, model, rid):
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    ext = os.path.splitext(url.split("?")[0])[1] or (".png" if kind == "image" else ".mp4")
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower())[:40].strip("-") or kind
    fname = f"{stamp}_{slug}{ext}"
    media_dir = obsidian.jarvis_root() / "Media"
    media_dir.mkdir(parents=True, exist_ok=True)
    saved = None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "jarvis-assistant"}), timeout=120) as r:
            (media_dir / fname).write_bytes(r.read())
        saved = f"Jarvis/Media/{fname}"
    except Exception as e:
        print(f"\n[media download failed, keeping URL only: {e}]")
    embed = f"![[{fname}]]" if saved else f"![]({url})"
    obsidian.vault_write(
        "Jarvis/Media/Generations.md",
        f"## {stamp} — {kind} · `{model}`\n**Prompt:** {prompt}\n\n{embed}\n\nSource: {url} · request `{rid}`\n",
    )
    return saved, url


def _gate(confirmed, what):
    if not confirmed:
        return (
            f"NOT RUN — {what} costs MuAPI credits. Ask the user to confirm this exact generation "
            "(prompt + model), then call again with confirmed=true."
        )
    return None


def generate_image(prompt, model=DEFAULT_IMAGE_MODEL, aspect_ratio="1:1", image_url="", confirmed=False):
    blocked = _gate(confirmed, "image generation")
    if blocked:
        return blocked
    payload = {"prompt": prompt, "aspect_ratio": aspect_ratio}
    if image_url:
        payload["image_url"] = image_url
    rid, url = _run(model, payload, timeout_s=300)
    saved, url = _save("image", url, prompt, model, rid)
    return f"Image ready ({model}). Saved to vault: {saved or 'not saved'}. URL: {url}"


def generate_video(prompt, model="", aspect_ratio="16:9", image_url="", duration=5, confirmed=False):
    blocked = _gate(confirmed, "video generation")
    if blocked:
        return blocked
    model = model or (DEFAULT_I2V_MODEL if image_url else DEFAULT_VIDEO_MODEL)
    payload = {"prompt": prompt, "aspect_ratio": aspect_ratio, "duration": duration}
    if image_url:
        payload["image_url"] = image_url
    rid, url = _run(model, payload, timeout_s=1800)
    saved, url = _save("video", url, prompt, model, rid)
    return f"Video ready ({model}). Saved to vault: {saved or 'not saved'}. URL: {url}"


def register_media_tools(registry):
    common = {
        "prompt": {"type": "string", "description": "What to generate."},
        "aspect_ratio": {"type": "string", "description": "e.g. 1:1, 16:9, 9:16 (TikTok/Shorts)."},
        "image_url": {"type": "string", "description": "Optional reference/start image URL (image-to-image / image-to-video)."},
        "confirmed": {
            "type": "boolean",
            "description": "Spends money. Only true after the user explicitly confirmed THIS generation.",
        },
    }
    registry.register(
        name="generate_image",
        description=(
            "Generate an image with MuAPI (Higgsfield replacement; 70+ models e.g. flux-dev-image, "
            "nano-banana-2, bytedance-seedream-5.0-pro-layer). PAID: first describe prompt+model and "
            "get the user's yes, then call with confirmed=true. Result is saved into Obsidian."
        ),
        input_schema={
            "type": "object",
            "properties": {**common, "model": {"type": "string", "description": f"MuAPI endpoint. Default {DEFAULT_IMAGE_MODEL}."}},
            "required": ["prompt"],
        },
        fn=generate_image,
    )
    registry.register(
        name="generate_video",
        description=(
            "Generate a video with MuAPI (Higgsfield replacement; Kling v3, Seedance 2, Hailuo 2.3, Veo, "
            "Wan…). Text-to-video, or image-to-video when image_url is given. PAID: get the user's explicit "
            "yes first, then call with confirmed=true. Can take minutes. Result is saved into Obsidian."
        ),
        input_schema={
            "type": "object",
            "properties": {
                **common,
                "model": {"type": "string", "description": f"MuAPI endpoint. Default {DEFAULT_VIDEO_MODEL} (or {DEFAULT_I2V_MODEL} with image_url)."},
                "duration": {"type": "integer", "description": "Seconds, if the model supports it. Default 5."},
            },
            "required": ["prompt"],
        },
        fn=generate_video,
    )

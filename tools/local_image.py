"""
Local image generation with stable-diffusion.cpp (`sd-cli`) — free, private, offline.
Metal GPU on Apple Silicon, CUDA on NVIDIA, CPU otherwise.

Setup once: scripts/setup_local_images.sh  (builds sd-cli + downloads a model)

Model catalog + CLI arguments mirror Open-Generative-AI's tested local engine
(electron/lib/modelCatalog.js, electron/lib/localInference.js), checked against
stable-diffusion.cpp's argument parser.
"""
import os
import random
import subprocess
import time
from pathlib import Path

AUX = {
    "llm": {"file": "Qwen3-4B-Instruct-2507-UD-Q4_K_XL.gguf",
            "url": "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-UD-Q4_K_XL.gguf"},
    "vae": {"file": "ae.safetensors",
            "url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors"},
}

CATALOG = {
    "z-image-turbo": {
        "type": "z-image", "about": "Fast 8-step, high quality, 1024px. Best default.",
        "file": "z_image_turbo-Q4_K.gguf",
        "url": "https://huggingface.co/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q4_K.gguf",
        "steps": 8, "cfg": 1.0, "sampler": "euler", "scheduler": "simple",
    },
    "dreamshaper-8": {
        "type": "sd1", "about": "Versatile SD1.5 — portraits, landscapes, art. 512px, light on RAM.",
        "file": "DreamShaper_8_pruned.safetensors",
        "url": "https://huggingface.co/Lykon/DreamShaper/resolve/main/DreamShaper_8_pruned.safetensors",
        "steps": 20, "cfg": 7.5, "sampler": "euler_a",
    },
    "realistic-vision-v51": {
        "type": "sd1", "about": "Photorealistic people and scenes (SD1.5).",
        "file": "realisticVisionV51_v51VAE.safetensors",
        "url": "https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE/resolve/main/Realistic_Vision_V5.1_fp16-no-ema.safetensors",
        "steps": 25, "cfg": 7.0, "sampler": "euler_a",
    },
    "anything-v5": {
        "type": "sd1", "about": "Anime / illustration (SD1.5).",
        "file": "Anything-v5.0-PRT.safetensors",
        "url": "https://huggingface.co/Yntec/AnythingV5/resolve/main/Anything-v5.0-PRT.safetensors",
        "steps": 20, "cfg": 7.0, "sampler": "euler_a",
    },
    "sdxl-base": {
        "type": "sdxl", "about": "SDXL 1.0 — 1024px, needs ~16 GB RAM.",
        "file": "sd_xl_base_1.0.safetensors",
        "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
        "steps": 30, "cfg": 7.5, "sampler": "dpm++2m",
    },
}


def local_dir() -> Path:
    return Path(os.environ.get("JARVIS_LOCAL_AI_DIR", "~/.jarvis/local-ai")).expanduser()


def binary() -> Path:
    override = os.environ.get("SD_CLI_PATH", "").strip()
    return Path(override).expanduser() if override else local_dir() / "bin" / "sd-cli"


def default_model() -> str:
    return os.environ.get("LOCAL_IMAGE_MODEL", "z-image-turbo")


def installed_models() -> list[str]:
    mdir = local_dir() / "models"
    out = []
    for name, m in CATALOG.items():
        need = [m["file"]] + ([AUX["llm"]["file"], AUX["vae"]["file"]] if m["type"] == "z-image" else [])
        if all((mdir / f).exists() for f in need):
            out.append(name)
    return out


def is_ready() -> bool:
    return binary().exists() and bool(installed_models())


def _dims(aspect_ratio: str, mtype: str):
    base = 1024 if mtype in ("sdxl", "z-image") else 512
    r = lambda x: round(x / 64) * 64  # noqa: E731
    return {
        "1:1": (base, base),
        "16:9": (r(base * 16 / 9), base), "9:16": (base, r(base * 16 / 9)),
        "4:3": (r(base * 4 / 3), base), "3:4": (base, r(base * 4 / 3)),
    }.get(aspect_ratio, (base, base))


def build_args(prompt, model, out_path, aspect_ratio="1:1", negative_prompt="", seed=None, steps=None):
    m = CATALOG[model]
    mdir = local_dir() / "models"
    width, height = _dims(aspect_ratio, m["type"])
    # z-image/flux GGUFs are standalone diffusion transformers → --diffusion-model, not -m
    flag = "--diffusion-model" if m["type"] in ("z-image", "flux") else "-m"
    args = [
        str(binary()), flag, str(mdir / m["file"]),
        "-p", prompt, "-o", str(out_path),
        "--steps", str(steps or m["steps"]),
        "-W", str(width), "-H", str(height),
        "--cfg-scale", str(m["cfg"]),
        "--seed", str(seed if seed is not None else random.randint(0, 2_147_483_647)),
        "--sampling-method", m["sampler"],
    ]
    if negative_prompt:
        args += ["-n", negative_prompt]
    if m["type"] == "z-image":
        args += ["--llm", str(mdir / AUX["llm"]["file"]), "--vae", str(mdir / AUX["vae"]["file"])]
        if m.get("scheduler"):
            args += ["--scheduler", m["scheduler"]]
    return args


def generate(prompt, out_path, model="", aspect_ratio="1:1", negative_prompt="", seed=None, timeout_s=1800):
    """Run sd-cli. Returns (out_path, model, seconds). Raises RuntimeError with a helpful hint."""
    model = model or default_model()
    if model not in CATALOG:
        raise RuntimeError(f"Unknown local model '{model}'. Options: {', '.join(CATALOG)}")
    if not binary().exists():
        raise RuntimeError("Local engine not installed — run scripts/setup_local_images.sh")
    if model not in installed_models():
        raise RuntimeError(f"Model '{model}' not downloaded — run scripts/setup_local_images.sh {model}")

    args = build_args(prompt, model, out_path, aspect_ratio, negative_prompt, seed)
    env = dict(os.environ)
    libdir = str(binary().parent)  # shared libs sit next to sd-cli
    env["DYLD_LIBRARY_PATH"] = libdir + os.pathsep + env.get("DYLD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = libdir + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    t = time.time()
    print(f"\n  [local image: {model}, generating…]", flush=True)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s, env=env)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Local generation timed out after {timeout_s}s.")
    if proc.returncode != 0 or not Path(out_path).exists():
        tail = "\n".join((proc.stderr or proc.stdout).strip().splitlines()[-8:])
        hint = " (killed — likely out of memory; try dreamshaper-8)" if proc.returncode in (-9, 137) else ""
        raise RuntimeError(f"sd-cli failed (exit {proc.returncode}){hint}:\n{tail}")
    return str(out_path), model, round(time.time() - t)


def list_local_models():
    have = set(installed_models())
    lines = [f"Engine: {'installed' if binary().exists() else 'NOT installed (scripts/setup_local_images.sh)'}"]
    for name, m in CATALOG.items():
        mark = "✓" if name in have else "·"
        lines.append(f"{mark} {name} — {m['about']}" + ("" if name in have else f"  (get: scripts/setup_local_images.sh {name})"))
    return "\n".join(lines)

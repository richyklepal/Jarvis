#!/usr/bin/env bash
# One-time setup for LOCAL image generation (free, private, no API key).
# Builds stable-diffusion.cpp's `sd-cli` from source — with Metal GPU on Apple Silicon,
# CUDA if nvcc is present — then downloads a model.
#
#   scripts/setup_local_images.sh                 engine + Z-Image Turbo (default, ~5.2 GB)
#   scripts/setup_local_images.sh dreamshaper-8   engine + a specific model
#   scripts/setup_local_images.sh --engine-only
#
# Needs: git, cmake, a C++ compiler (Mac: `xcode-select --install` and `brew install cmake`).
# Files go to $JARVIS_LOCAL_AI_DIR (default ~/.jarvis/local-ai).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="${JARVIS_LOCAL_AI_DIR:-$HOME/.jarvis/local-ai}"
SRC="$DIR/src/stable-diffusion.cpp"
MODEL="${1:-z-image-turbo}"
mkdir -p "$DIR/bin" "$DIR/models"

for tool in git cmake; do
  command -v "$tool" >/dev/null || { echo "Missing '$tool'. Mac: brew install $tool"; exit 1; }
done

# ---- engine ---------------------------------------------------------------
if [[ -x "$DIR/bin/sd-cli" ]]; then
  echo "✓ sd-cli already built ($DIR/bin/sd-cli) — delete it to rebuild"
else
  if [[ -d "$SRC/.git" ]]; then git -C "$SRC" pull -q --ff-only; else
    git clone -q --depth 1 https://github.com/leejet/stable-diffusion.cpp.git "$SRC"; fi
  # only ggml is needed (skip the large CUDA cutlass + webp/webm submodules)
  git -C "$SRC" submodule update -q --init --depth 1 ggml

  FLAGS=(-DCMAKE_BUILD_TYPE=Release -DSD_WEBP=OFF -DSD_WEBM=OFF)
  if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
    FLAGS+=(-DSD_METAL=ON); echo "→ building with Metal (Apple Silicon GPU)"
  elif command -v nvcc >/dev/null; then
    FLAGS+=(-DSD_CUDA=ON);  echo "→ building with CUDA"
  else
    echo "→ building CPU-only (slow, but works)"
  fi
  cmake -S "$SRC" -B "$SRC/build" "${FLAGS[@]}" >/dev/null
  JOBS="$(sysctl -n hw.ncpu 2>/dev/null || nproc)"
  cmake --build "$SRC/build" --config Release --target sd-cli -j "$JOBS"
  cp "$SRC/build/bin/sd-cli" "$DIR/bin/sd-cli"
  # keep any shared libs next to the binary
  find "$SRC/build/bin" -maxdepth 1 \( -name '*.dylib' -o -name '*.so*' -o -name '*.metal' \) -exec cp {} "$DIR/bin/" \; 2>/dev/null || true
  echo "✓ engine → $DIR/bin/sd-cli"
fi

[[ "$MODEL" == "--engine-only" ]] && exit 0

# ---- model ----------------------------------------------------------------
ROOT_DIR="$ROOT" python3 - "$MODEL" "$DIR/models" <<'PY'
import sys, urllib.request, os
sys.path.insert(0, os.environ.get("ROOT_DIR", "."))
from tools.local_image import CATALOG, AUX
name, dest = sys.argv[1], sys.argv[2]
m = CATALOG.get(name)
if not m:
    sys.exit(f"Unknown model '{name}'. Options: {', '.join(CATALOG)}")
files = [(m["file"], m["url"])] + ([(AUX[k]["file"], AUX[k]["url"]) for k in ("llm", "vae")] if m["type"] == "z-image" else [])
for fname, url in files:
    path = os.path.join(dest, fname)
    if os.path.exists(path):
        print(f"✓ {fname} already downloaded"); continue
    print(f"↓ {fname}")
    def hook(n, bs, total):
        if total > 0 and n % 200 == 0:
            print(f"\r  {min(100, n * bs * 100 // total)}%", end="", flush=True)
    urllib.request.urlretrieve(url, path + ".part", hook)
    os.replace(path + ".part", path); print("\r  done   ")
print(f"✓ model '{name}' ready")
PY
echo
echo "Done. In .env set:  IMAGE_PROVIDER=local   LOCAL_IMAGE_MODEL=$MODEL"

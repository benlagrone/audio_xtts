#!/bin/sh
set -eu

MODEL_NAME="${MODEL_NAME:-tts_models/multilingual/multi-dataset/xtts_v2}"
TTS_PORT="${TTS_PORT:-5002}"
USE_CUDA="${USE_CUDA:-0}"

EVAL_OUTPUT=$(python - <<'PY'
import os
import sys
import io
import contextlib
from pathlib import Path
from TTS.utils.manage import ModelManager

model_name = os.environ.get("MODEL_NAME")
if not model_name:
    sys.exit("MODEL_NAME environment variable must be set")

manager = ModelManager()
with contextlib.redirect_stdout(io.StringIO()):
    result = manager.download_model(model_name)

if isinstance(result, (list, tuple)):
    parts = list(result) + [None, None]
    model_path, config_path = parts[0], parts[1]
else:
    model_path, config_path = result, None

if not model_path:
    sys.exit(f"Unable to download checkpoint for model {model_name}")

model_path = Path(model_path)
search_dirs = []
if model_path.is_file():
    search_dirs.append(model_path.parent)
else:
    search_dirs.append(model_path)

output_path = getattr(manager, "output_path", None)
if isinstance(output_path, (str, Path)):
    output_dir = Path(output_path)
    if output_dir.exists():
        search_dirs.append(output_dir)

if not config_path:
    preferred_names = (
        "config.json",
        "model_config.json",
        "config.yaml",
        "config.yml",
    )
    candidates = []
    for directory in search_dirs:
        if not directory or not directory.exists():
            continue
        for item in directory.iterdir():
            if item.name in preferred_names and item.is_file():
                candidates.append(item)
        if candidates:
            break

    if not candidates:
        for directory in search_dirs:
            if not directory or not directory.exists():
                continue
            for item in directory.rglob("config.*"):
                if item.suffix.lower() in {".json", ".yaml", ".yml"} and item.is_file():
                    candidates.append(item)
                    break
            if candidates:
                break

    if candidates:
        config_path = str(candidates[0])

if not config_path:
    sys.exit(f"Unable to locate config for model {model_name}. Upgrade the TTS package or specify --config_path manually.")

print(f"MODEL_PATH={model_path}")
print(f"CONFIG_PATH={config_path}")
PY
)

# shellcheck disable=SC2086
eval "$EVAL_OUTPUT"

echo "Using model: ${MODEL_PATH}" >&2
echo "Using model config: ${CONFIG_PATH}" >&2

export COQUI_TOS_AGREED="${COQUI_TOS_AGREED:-0}"

exec python /usr/local/bin/xtts-entry.py \
  --model_path "${MODEL_PATH}" \
  --config_path "${CONFIG_PATH}" \
  --port "${TTS_PORT}" \
  --use_cuda "${USE_CUDA}"

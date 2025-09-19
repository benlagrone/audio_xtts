#!/bin/sh
set -eu

MODEL_NAME="${MODEL_NAME:-tts_models/multilingual/multi-dataset/xtts_v2}"
TTS_PORT="${TTS_PORT:-5002}"
USE_CUDA="${USE_CUDA:-0}"

CONFIG_PATH=$(python - <<'PY'
import os
import sys
from pathlib import Path
from TTS.utils.manage import ModelManager

model_name = os.environ.get("MODEL_NAME")
if not model_name:
    sys.exit("MODEL_NAME environment variable must be set")

manager = ModelManager()
model_path, config_path, *_ = manager.download_model(model_name)

if not config_path and model_path:
    model_path = Path(model_path)
    search_order = [
        model_path.with_suffix('.json'),
        model_path.with_name('config.json'),
        model_path.with_name('model_config.json'),
        model_path.with_name('config.yaml'),
        model_path.with_name('config.yml'),
    ]
    for candidate in search_order:
        if candidate and candidate.is_file():
            config_path = str(candidate)
            break
    if not config_path:
        for ext in ('.json', '.yaml', '.yml'):
            matches = sorted(model_path.parent.glob(f'*{ext}'))
            if matches:
                config_path = str(matches[0])
                break

if not config_path:
    sys.exit(f"Unable to locate config for model {model_name}. Upgrade the TTS package or specify --config_path manually.")

print(config_path, end="")
PY
)

export COQUI_TOS_AGREED="${COQUI_TOS_AGREED:-0}"

exec tts-server \
  --model_name "${MODEL_NAME}" \
  --config_path "${CONFIG_PATH}" \
  --port "${TTS_PORT}" \
  --use_cuda "${USE_CUDA}"

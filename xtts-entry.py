#!/usr/bin/env python3
import base64
import json
import os
import sys
from pathlib import Path
from torch.serialization import add_safe_globals
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
from TTS.config.shared_configs import BaseDatasetConfig

add_safe_globals([XttsConfig, XttsAudioConfig, XttsArgs, BaseDatasetConfig])

from TTS.server import server as tts_server
from flask import abort, g, jsonify, request

_original_tts_handler = tts_server.app.view_functions.get("tts")
_app_logger = getattr(tts_server.app, "logger", None)


def _log_debug(message, data):
    if _app_logger:
        _app_logger.debug("%s %s", message, data)


def _builtin_voice_ids():
    manager = getattr(tts_server.synthesizer, "speaker_manager", None)
    candidates: list[str] = []
    if manager:
        for attr in ("speaker_names", "speaker_ids", "speakers", "speaker_id_to_idx"):
            value = getattr(manager, attr, None)
            if not value:
                continue
            if callable(value):
                try:
                    value = value()
                except TypeError:
                    continue
            if isinstance(value, dict):
                candidates.extend(map(str, value.keys()))
            elif isinstance(value, (list, tuple, set)):
                candidates.extend(map(str, value))
    if candidates:
        return list(dict.fromkeys(candidates))

    return _speaker_ids_from_files()


def _speaker_ids_from_files():
    directories = []

    model_path = os.environ.get("MODEL_PATH")
    if model_path:
        directories.append(Path(model_path).parent)

    config_path = os.environ.get("CONFIG_PATH")
    if config_path:
        directories.append(Path(config_path).parent)

    candidates: list[str] = []
    seen: set[str] = set()
    filename_hints = {
        "speakers.json",
        "speaker_ids.json",
        "speaker_mapping.json",
        "speakers.pth",
        "speaker_ids.pth",
        "speakers.pickle",
    }

    for directory in directories:
        if not directory.exists():
            continue
        paths = list(directory.glob("*.json")) + list(directory.glob("*.pth")) + list(directory.glob("*.pickle"))
        for path in paths:
            if filename_hints and path.name not in filename_hints and path.suffix not in {".json", ".pth", ".pickle"}:
                continue
            if str(path) in seen:
                continue
            seen.add(str(path))
            try:
                if path.suffix == ".json":
                    data = json.loads(path.read_text())
                else:
                    import torch

                    data = torch.load(path, map_location="cpu")
            except Exception:  # noqa: BLE001
                continue

            if isinstance(data, dict):
                # look for dict[str, int] or nested structure
                if all(isinstance(k, str) for k in data.keys()):
                    candidates.extend(map(str, data.keys()))
                elif "speakers" in data and isinstance(data["speakers"], dict):
                    candidates.extend(map(str, data["speakers"].keys()))
            elif isinstance(data, list):
                candidates.extend(map(str, data))

    return list(dict.fromkeys(candidates))


def _available_voice_files():
    if not VOICES_ROOT.exists():
        return {}
    voices = {}
    for path in VOICES_ROOT.glob("*"):
        if path.suffix.lower() not in {".wav", ".mp3", ".flac", ".ogg"}:
            continue
        voices[path.stem] = path
    return voices


def _encode_voice_file(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    return base64.b64encode(data).decode("ascii")


def _ensure_voice_reference(payload: dict) -> None:
    if not isinstance(payload, dict):
        return
    if payload.get("speaker_wav") or payload.get("speaker_wav_files"):
        return

    builtin = sorted(_builtin_voice_ids())
    file_voices = _available_voice_files()

    requested = (
        payload.get("voice")
        or payload.get("speaker_id")
        or payload.get("speaker")
        or payload.get("speaker_idx")
    )

    if requested:
        if requested in builtin:
            payload["speaker_id"] = requested
            payload["voice"] = requested
            return
        if requested in file_voices:
            encoded = _encode_voice_file(file_voices[requested])
            if encoded:
                payload["speaker_wav"] = encoded
                payload["voice"] = requested
            return
        available = builtin + sorted(file_voices.keys())
        abort(404, description=f"Voice '{requested}' not found. Available voices: {available}")

    if builtin:
        default_voice = DEFAULT_VOICE if DEFAULT_VOICE in builtin else builtin[0]
        payload["speaker_id"] = default_voice
        payload["voice"] = default_voice
        return

    if file_voices:
        voice_id, voice_path = sorted(file_voices.items())[0]
        encoded = _encode_voice_file(voice_path)
        if encoded:
            payload["speaker_wav"] = encoded
            payload["voice"] = voice_id
        return

    abort(
        400,
        description=(
            "No speaker reference available. Provide 'speaker_wav' or install a model with built-in voices."
        ),
    )


VOICES_ROOT = Path(os.environ.get("VOICES_PATH", "/voices"))
DEFAULT_VOICE = os.environ.get("DEFAULT_VOICE")
DEFAULT_LANGUAGE = "en"


def _normalize_payload(payload):
    if not payload:
        return payload
    normalized = dict(payload)
    text = normalized.get("text")
    if isinstance(text, list):
        collapsed = [t for t in (s.strip() if isinstance(s, str) else s for s in text) if t]
        if collapsed:
            normalized["text"] = collapsed[0] if len(collapsed) == 1 else collapsed
        else:
            normalized["text"] = None
    elif isinstance(text, str):
        stripped = text.strip()
        normalized["text"] = stripped if stripped else None
    speaker_wav = normalized.get("speaker_wav")
    if isinstance(speaker_wav, str) and not speaker_wav.strip():
        normalized.pop("speaker_wav", None)
    language = normalized.get("language") or normalized.get("language_id")
    if not language:
        normalized["language"] = DEFAULT_LANGUAGE
    voice = (
        normalized.get("voice")
        or normalized.get("speaker_idx")
        or normalized.get("speaker")
        or normalized.get("speaker_id")
    )
    if voice:
        normalized["voice"] = voice
    style_wav = normalized.get("style_wav")
    if isinstance(style_wav, str) and not style_wav.strip():
        normalized.pop("style_wav", None)
    return normalized


def _normalized_tts_handler(*args, **kwargs):
    payload = request.get_json(silent=True)
    if payload is None and request.args:
        payload = {key: value for key, value in request.args.items()}
    normalized = _normalize_payload(payload)
    if normalized is None:
        g.__tts_payload__ = None
        return _original_tts_handler(*args, **kwargs)
    _ensure_voice_reference(normalized)
    g.__tts_payload__ = normalized
    _log_debug("[normalized payload]", normalized)
    return _original_tts_handler(*args, **kwargs)


if _original_tts_handler is not None:
    tts_server.app.view_functions["tts"] = _normalized_tts_handler

from TTS.server.server import main, app

synthesizer = tts_server.synthesizer
_original_synth_tts = synthesizer.tts


def _coalesce_argument(args_list, kwargs, name, position, value):
    if not value:
        return
    if kwargs.get(name):
        return
    if len(args_list) > position:
        if args_list[position]:
            return
        args_list[position] = value
    else:
        kwargs[name] = value


def _patched_synth_tts(*args, **kwargs):
    payload = getattr(g, "__tts_payload__", None) or {}
    args_list = list(args)

    text_override = payload.get("text")
    if text_override:
        if len(args_list) > 0:
            if not args_list[0]:
                args_list[0] = text_override
        else:
            args_list.append(text_override)

    speaker_override = (
        payload.get("speaker_id")
        or payload.get("voice")
        or payload.get("speaker")
        or payload.get("speaker_idx")
    )
    _coalesce_argument(args_list, kwargs, "speaker_name", 1, speaker_override)

    language_override = payload.get("language") or payload.get("language_name")
    _coalesce_argument(args_list, kwargs, "language_name", 3, language_override)

    return _original_synth_tts(*tuple(args_list), **kwargs)


synthesizer.tts = _patched_synth_tts


@app.route("/__health", methods=["GET"])
def health_check():
    return {"status": "ok"}


@app.route("/api/voices", methods=["GET"])
def list_voices():
    builtin = sorted(_builtin_voice_ids())
    file_based = sorted(_available_voice_files().keys())
    return jsonify(
        {
            "builtin": builtin,
            "cloned": file_based,
            "voices": sorted({*builtin, *file_based}),
        }
    )


if __name__ == "__main__":
    sys.exit(main())

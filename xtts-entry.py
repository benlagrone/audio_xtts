#!/usr/bin/env python3
import sys
from torch.serialization import add_safe_globals
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
from TTS.config.shared_configs import BaseDatasetConfig

add_safe_globals([XttsConfig, XttsAudioConfig, XttsArgs, BaseDatasetConfig])

from TTS.server import server as tts_server
from flask import request, g

_original_tts_handler = tts_server.app.view_functions.get("tts")
_app_logger = getattr(tts_server.app, "logger", None)


def _log_debug(message, data):
    if _app_logger:
        _app_logger.debug("%s %s", message, data)


DEFAULT_SPEAKER = "female-en-5"
DEFAULT_LANGUAGE = "en"


def _normalize_payload(payload):
    if not payload:
        return payload
    normalized = dict(payload)
    text = normalized.get("text")
    if isinstance(text, list):
        normalized["text"] = [t for t in (s.strip() if isinstance(s, str) else s for s in text) if t]
        if not normalized["text"]:
            normalized["text"] = None
    elif isinstance(text, str):
        stripped = text.strip()
        normalized["text"] = [stripped] if stripped else None
    speaker_wav = normalized.get("speaker_wav")
    if isinstance(speaker_wav, str) and not speaker_wav.strip():
        normalized.pop("speaker_wav", None)
    language = normalized.get("language") or normalized.get("language_id")
    if not language:
        normalized["language"] = DEFAULT_LANGUAGE
    speaker = normalized.get("speaker_idx") or normalized.get("speaker") or normalized.get("speaker_id")
    if not speaker:
        normalized["speaker"] = DEFAULT_SPEAKER
    style_wav = normalized.get("style_wav")
    if isinstance(style_wav, str) and not style_wav.strip():
        normalized.pop("style_wav", None)
    return normalized


def _normalized_tts_handler(*args, **kwargs):
    payload = request.get_json(silent=True)
    if payload is None and request.args:
        payload = {key: value for key, value in request.args.items()}
    normalized = _normalize_payload(payload)
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

    speaker_override = payload.get("speaker") or payload.get("speaker_idx")
    _coalesce_argument(args_list, kwargs, "speaker_name", 1, speaker_override)

    language_override = payload.get("language") or payload.get("language_name")
    _coalesce_argument(args_list, kwargs, "language_name", 3, language_override)

    return _original_synth_tts(*tuple(args_list), **kwargs)


synthesizer.tts = _patched_synth_tts


@app.route("/__health", methods=["GET"])
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    sys.exit(main())

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


def _patched_synth_tts(*args, **kwargs):
    payload = getattr(g, "__tts_payload__", {}) or {}
    text_arg = kwargs.get("text")
    if (text_arg is None or text_arg == "" or text_arg == []) and payload:
        text = payload.get("text")
        if text:
            kwargs["text"] = text
    if not kwargs.get("speaker_name") and payload:
        speaker = payload.get("speaker") or payload.get("speaker_idx")
        if speaker:
            kwargs["speaker_name"] = speaker
    if not kwargs.get("language_name") and payload:
        language = payload.get("language") or payload.get("language_name")
        if language:
            kwargs["language_name"] = language
    return _original_synth_tts(*args, **kwargs)


synthesizer.tts = _patched_synth_tts


@app.route("/__health", methods=["GET"])
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    sys.exit(main())

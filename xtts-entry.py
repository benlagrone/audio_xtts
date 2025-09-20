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
    style_wav = normalized.get("style_wav")
    if isinstance(style_wav, str) and not style_wav.strip():
        normalized.pop("style_wav", None)
    return normalized


def _normalized_tts_handler(*args, **kwargs):
    payload = request.get_json(silent=True)
    normalized = _normalize_payload(payload)
    g.__tts_payload__ = normalized
    tts_server.logger.info("[debug] normalized payload: %s", normalized)
    return _original_tts_handler(*args, **kwargs)


if _original_tts_handler is not None:
    tts_server.app.view_functions["tts"] = _normalized_tts_handler

from TTS.server.server import main, app

synthesizer = tts_server.synthesizer
_original_synth_tts = synthesizer.tts


def _patched_synth_tts(*args, **kwargs):
    payload = getattr(g, "__tts_payload__", None)
    text_arg = kwargs.get("text")
    if (text_arg is None or text_arg == "" or text_arg == []) and payload:
        text = payload.get("text")
        if text:
            kwargs["text"] = text
    return _original_synth_tts(*args, **kwargs)


synthesizer.tts = _patched_synth_tts


@app.route("/__health", methods=["GET"])
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    sys.exit(main())

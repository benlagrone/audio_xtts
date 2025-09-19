#!/usr/bin/env python3
import sys
from torch.serialization import add_safe_globals
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsAudioConfig

add_safe_globals([XttsConfig, XttsAudioConfig])

from TTS.server.server import main

if __name__ == "__main__":
    sys.exit(main())

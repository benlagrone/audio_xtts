FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential ffmpeg git cargo \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir TTS==0.22.0

ENV MODEL_NAME=tts_models/multilingual/multi-dataset/xtts_v2
ENV TTS_PORT=5002
ENV COQUI_TOS_AGREED=1

COPY start-xtts.sh /usr/local/bin/start-xtts.sh
COPY xtts-entry.py /usr/local/bin/xtts-entry.py
RUN chmod +x /usr/local/bin/start-xtts.sh /usr/local/bin/xtts-entry.py

EXPOSE ${TTS_PORT}

ENTRYPOINT ["/usr/local/bin/start-xtts.sh"]

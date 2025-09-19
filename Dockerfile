FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg git \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir TTS==0.22.0

ENV MODEL_NAME=tts_models/multilingual/multi-dataset/xtts_v2
ENV TTS_PORT=5002
ENV COQUI_TOS_AGREED=1

EXPOSE ${TTS_PORT}

CMD ["/bin/sh", "-c", "tts-server --model_name \"$MODEL_NAME\" --port $TTS_PORT --use_cuda 0"]

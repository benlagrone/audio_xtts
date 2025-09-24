FROM python:3.11-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential ffmpeg git curl espeak-ng \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal \
 && echo 'source /root/.cargo/env' >> /etc/profile.d/cargo.sh

ENV PATH="/root/.cargo/bin:${PATH}"

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir TTS==0.22.0

ENV TTS_PORT=5002
ENV COQUI_TOS_AGREED=1

COPY start-xtts.sh /usr/local/bin/start-xtts.sh
COPY xtts-entry.py /usr/local/bin/xtts-entry.py
RUN chmod +x /usr/local/bin/start-xtts.sh /usr/local/bin/xtts-entry.py

EXPOSE ${TTS_PORT}

ENTRYPOINT ["/usr/local/bin/start-xtts.sh"]

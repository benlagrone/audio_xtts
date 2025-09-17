
### 1. Scaffold a new project

```bash
mkdir -p ~/Projects/xtts-service
cd ~/Projects/xtts-service
```

Create `Dockerfile`:

```Dockerfile
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg git \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir TTS==0.22.0

ENV MODEL_NAME=tts_models/multilingual/multi-dataset/xtts_v2
ENV TTS_PORT=5002

EXPOSE ${TTS_PORT}

CMD ["tts-server", "--model_name", "${MODEL_NAME}", "--port", "${TTS_PORT}", "--use_cuda", "0", "--host", "0.0.0.0"]
```

Create `docker-compose.yml`:

```yaml
version: "3.9"
services:
  xtts:
    build: .
    image: local-xtts:latest
    container_name: xtts
    environment:
      - MODEL_NAME=${MODEL_NAME:-tts_models/multilingual/multi-dataset/xtts_v2}
      - TTS_PORT=${TTS_PORT:-5002}
    volumes:
      - ./cache:/root/.local/share/tts
    networks:
      - fortress-phronesis-net
    restart: unless-stopped
    ports:
      - "5002:5002"

networks:
  fortress-phronesis-net:
    external: true
```

First boot downloads the model into `./cache`, so keep that directory around for subsequent runs.

### 2. Launch xTTS

```bash
docker compose up -d --build
```

Once healthy, the API lives at `http://192.168.86.23:5002/api/tts` (adjust the host/port if you expose it differently).

### 3. Point the render stack at xTTS

Back in your render project directory:

```bash
echo "XTTS_API_URL=http://xtts:5002" >> .env
# optional overrides
echo "XTTS_LANGUAGE=en" >> .env
```

Redeploy the render stack so it reads the updated `.env`:

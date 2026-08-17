# NoiR Code imaging sidecar: the FastAPI wrapper around the encode/decode core.
# OpenCV (opencv-python) needs libGL + glib at runtime, hence the apt libs.
FROM python:3.14-slim AS prod

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[api]"

ENV NOIRCODE_API_HOST=0.0.0.0 \
    NOIRCODE_API_PORT=8001
EXPOSE 8001
CMD ["noir-api"]

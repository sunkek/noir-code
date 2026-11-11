# NoiR Code imaging sidecar: the FastAPI wrapper around the encode/decode core.
# OpenCV (opencv-python) needs libGL + glib at runtime, hence the apt libs.
FROM python:3.15-slim AS prod

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[api]"

# OPENCV_IO_MAX_IMAGE_PIXELS is a backstop to noircode.upload's header check: OpenCV
# reads it once at load, so it has to come from the environment, not the app.
ENV NOIRCODE_API_HOST=0.0.0.0 \
    NOIRCODE_API_PORT=8001 \
    OPENCV_IO_MAX_IMAGE_PIXELS=50000000

# Untrusted images are parsed here; do it without root.
RUN useradd --system --no-create-home --uid 10001 app
USER app
EXPOSE 8001
CMD ["noir-api"]

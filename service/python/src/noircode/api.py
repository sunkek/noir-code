"""Imaging sidecar: a thin HTTP wrapper around the NoiR Code encode/decode core.

The Go gateway (``service/backend``) owns the public API, rate-limiting and CORS; it
proxies the actual image work here because decode needs the OpenCV pipeline that lives
in this reference implementation. Endpoints:

* ``POST /encode``  JSON ``{text, style, hatch_data, adaptive}`` -> ``image/png`` bytes.
* ``POST /decode``  multipart file ``image`` -> JSON decode result.
* ``GET  /health``  liveness probe.

Run with ``noir-api`` (installs the ``api`` extra) or ``uvicorn noircode.api:app``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os

import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from noircode.config import Config
from noircode.decode.decoder import DecodeResult
from noircode.decode.decoder import decode as decode_panel
from noircode.ecc import EccError
from noircode.encode.encoder import encode as encode_text
from noircode.payload import FrameError
from noircode.upload import ImageRejected, decode_upload

app = FastAPI(title="NoiR Code imaging sidecar", version="0.1.0")

# Decodes run off the event loop (so /health still answers during one) but at most
# this many at once: each holds a full image buffer plus the pipeline's working
# copies, and this bound is what makes the container's memory limit predictable.
_DECODE_SLOTS = asyncio.Semaphore(int(os.environ.get("NOIRCODE_DECODE_CONCURRENCY", "2")))

# Permissive CORS by default for local dev (the Go gateway also fronts this in prod and
# does not need it). Lock down with NOIRCODE_API_CORS_ORIGINS="https://a,https://b".
# Branding caption stamped under generated panels (outside the decode region). Set
# empty to disable.
DEFAULT_CAPTION = os.environ.get("NOIRCODE_CAPTION", "noir-code.suncake.xyz")

_origins = os.environ.get("NOIRCODE_API_CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class EncodeRequest(BaseModel):
    """Encode parameters mirroring the CLI flags."""

    text: str = Field(..., description="UTF-8 text payload to encode.")
    style: bool = Field(False, description="Apply the noir styling + halftone artwork.")
    hatch_data: bool = Field(False, description="Hatch the data cells (engraving look).")
    adaptive: bool = Field(True, description="Shrink the grid to the smallest fitting size.")
    caption: str | None = Field(
        None, description="Caption stamped under the panel; null uses the server default."
    )


class DecodeResponse(BaseModel):
    """Structured decode outcome (mirrors ``decode.decoder.DecodeResult``)."""

    ok: bool
    text: str | None
    confidence: float
    rotation: int | None
    grid_erasures: int
    motif_erasures: int
    cross_check: bool | None
    failed_stage: str | None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/encode",
    responses={200: {"content": {"image/png": {}}}},
    response_class=Response,
)
def encode(req: EncodeRequest) -> Response:
    """Encode text to a PNG panel."""
    cfg = dataclasses.replace(Config(), hatched_data=req.hatch_data)
    caption = DEFAULT_CAPTION if req.caption is None else req.caption
    try:
        panel = encode_text(
            req.text, cfg, style=req.style, adaptive=req.adaptive, caption=caption or None
        )
    except EccError:
        limit = cfg.rs_data_bytes - 7
        raise HTTPException(
            status_code=422,
            detail=f"text too long: {len(req.text.encode())} bytes; capacity is {limit} bytes",
        ) from None
    ok, buf = cv2.imencode(".png", panel)
    if not ok:
        raise HTTPException(status_code=500, detail="failed to encode PNG")
    return Response(content=buf.tobytes(), media_type="image/png")


@app.post("/decode", response_model=DecodeResponse)
async def decode(image: UploadFile = File(...)) -> DecodeResponse:
    """Decode an uploaded panel image to text + diagnostics."""
    raw = await image.read()
    async with _DECODE_SLOTS:
        try:
            res = await run_in_threadpool(_decode_bytes, raw)
        except ImageRejected as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except (EccError, FrameError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"decode error: {exc}") from None
    return DecodeResponse(
        ok=res.ok,
        text=res.text,
        confidence=res.confidence,
        rotation=res.rotation,
        grid_erasures=res.grid_erasures,
        motif_erasures=res.motif_erasures,
        cross_check=res.cross_check,
        failed_stage=res.failed_stage,
    )


def _decode_bytes(raw: bytes) -> DecodeResult:
    return decode_panel(decode_upload(raw), Config())


class _JsonFormatter(logging.Formatter):
    """One JSON object per line, so the log pipeline parses fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry)


class _DropHealthProbes(logging.Filter):
    """The Docker health check hits /health every 10 s; it was nearly every line."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()


# uvicorn's own loggers, every handler on stdout and JSON. Replaces uvicorn's
# default config (plain text, access log on stdout, errors on stderr).
LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": f"{__name__}._JsonFormatter"}},
    "filters": {"no_health": {"()": f"{__name__}._DropHealthProbes"}},
    "handlers": {
        "stdout": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout", "formatter": "json"},
    },
    "loggers": {
        "uvicorn": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["stdout"], "level": "INFO", "propagate": False, "filters": ["no_health"]},
    },
}


def main() -> None:
    """Console-script entry point: run uvicorn from env (NOIRCODE_API_HOST/PORT)."""
    import uvicorn

    host = os.environ.get("NOIRCODE_API_HOST", "0.0.0.0")
    port = int(os.environ.get("NOIRCODE_API_PORT", "8001"))
    uvicorn.run(app, host=host, port=port, log_config=LOG_CONFIG)

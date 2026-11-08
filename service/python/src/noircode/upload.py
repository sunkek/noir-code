"""Turning untrusted uploaded bytes into a grayscale image, safely.

``cv2.imdecode`` allocates the full pixel buffer the file header asks for. Its own
ceiling is 2**30 pixels, so a ~1 MB PNG of a 30000x30000 blank canvas costs ~1.7 GB of
RAM before any decoding logic runs — an unauthenticated memory bomb.

So the dimensions are read from the header first, without decoding, and anything over
``MAX_PIXELS`` is refused. Only PNG, JPEG and WebP are accepted: the formats browsers
and phones actually produce, and every other codec stays unreachable from the internet.

OpenCV's own limit (``OPENCV_IO_MAX_IMAGE_PIXELS``) is read once when the library
loads, so it cannot be set from here; the container sets it as a backstop instead.
"""

from __future__ import annotations

import struct

import cv2
import numpy as np

# ~50 MP covers a 48 MP phone photo; a grayscale buffer of that size is ~50 MB.
MAX_PIXELS = 50_000_000


class ImageRejected(ValueError):
    """The upload is empty, not a supported image, malformed, or too large."""


def image_size(raw: bytes) -> tuple[int, int]:
    """Return ``(width, height)`` from a PNG, JPEG or WebP header without decoding.

    Raises ``ImageRejected`` for any other format or a truncated header.
    """
    try:
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            if raw[12:16] != b"IHDR":
                raise ImageRejected("malformed PNG header")
            width, height = struct.unpack(">II", raw[16:24])
            return width, height
        if raw.startswith(b"\xff\xd8"):
            return _jpeg_size(raw)
        if raw[0:4] == b"RIFF" and raw[8:12] == b"WEBP":
            return _webp_size(raw)
    except (struct.error, IndexError):
        raise ImageRejected("truncated image header") from None
    raise ImageRejected("unsupported image format; use PNG, JPEG or WebP")


# Start-of-frame markers carry the frame dimensions. C4 (DHT), C8 (JPG) and CC (DAC)
# share the range but are not frames.
_JPEG_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def _jpeg_size(raw: bytes) -> tuple[int, int]:
    i = 2
    while i < len(raw):
        if raw[i] != 0xFF:
            raise ImageRejected("malformed JPEG")
        while raw[i] == 0xFF:  # fill bytes may pad a marker
            i += 1
        marker = raw[i]
        i += 1
        if marker == 0x01 or 0xD0 <= marker <= 0xD9:  # standalone markers, no length
            continue
        (length,) = struct.unpack(">H", raw[i : i + 2])
        if marker in _JPEG_SOF:
            height, width = struct.unpack(">HH", raw[i + 3 : i + 7])
            return width, height
        i += length
    raise ImageRejected("JPEG has no frame header")


def _webp_size(raw: bytes) -> tuple[int, int]:
    chunk = raw[12:16]
    if chunk == b"VP8 ":  # lossy: 14-bit dimensions after the frame tag + start code
        width, height = struct.unpack("<HH", raw[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L":  # lossless: 14 bits each, packed after the 0x2F signature
        b = raw[21:25]
        if len(b) < 4:
            raise IndexError
        width = 1 + (b[0] | (b[1] & 0x3F) << 8)
        height = 1 + (b[1] >> 6 | b[2] << 2 | (b[3] & 0x0F) << 10)
        return width, height
    if chunk == b"VP8X":  # extended: 24-bit (dimension - 1) little-endian
        b = raw[24:30]
        if len(b) < 6:
            raise IndexError
        width = 1 + int.from_bytes(b[0:3], "little")
        height = 1 + int.from_bytes(b[3:6], "little")
        return width, height
    raise ImageRejected("malformed WebP")


def decode_upload(raw: bytes, max_pixels: int = MAX_PIXELS) -> np.ndarray:
    """Decode uploaded bytes to a grayscale image, refusing anything unsafe."""
    if not raw:
        raise ImageRejected("empty image upload")
    width, height = image_size(raw)
    if width == 0 or height == 0:
        raise ImageRejected("image has no pixels")
    if width * height > max_pixels:
        raise ImageRejected(
            f"image is {width}x{height}; the limit is {max_pixels // 1_000_000} megapixels"
        )
    try:
        img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    except cv2.error:  # OpenCV's own size check (the container backstop) or a bad stream
        raise ImageRejected("cannot decode image bytes") from None
    if img is None:
        raise ImageRejected("cannot decode image bytes")
    return img

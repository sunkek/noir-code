"""Turning untrusted uploaded bytes into a grayscale image, safely.

``cv2.imdecode`` allocates whatever the file header asks for. Its own ceiling is 2**30
pixels, so a ~1 MB PNG of a 30000x30000 blank canvas costs ~1.7 GB of RAM before any
decoding logic runs — an unauthenticated memory bomb.

So the header is read first, without decoding, and two limits apply:

* ``MAX_PIXELS`` — the decode pipeline's own working memory grows with pixel count.
* ``MAX_DECODE_BYTES`` — what the codec allocates differs a lot by format, so pixels
  alone do not bound it. Measured at 50 MP, decoding to grayscale: PNG and baseline
  JPEG ~2 bytes/pixel; lossy WebP ~4 (a 92 KiB file cost 191 MiB); progressive JPEG
  keeps every component's coefficients, 1 + 2 bytes per component-pixel (a 744 KiB
  4:4:4 file cost 334 MiB). ``decode_cost`` estimates this from the header.

Only PNG, JPEG and WebP are accepted: the formats browsers and phones actually
produce, and every other codec stays unreachable from the internet.

OpenCV's own limit (``OPENCV_IO_MAX_IMAGE_PIXELS``) is read once when the library
loads, so it cannot be set from here; the container sets it as a backstop instead.
"""

from __future__ import annotations

import struct

import cv2
import numpy as np

# ~50 MP covers a 48 MP phone photo; a grayscale buffer of that size is ~50 MB.
MAX_PIXELS = 50_000_000
# Admits any 50 MP PNG or baseline JPEG; caps WebP at ~25 MP and progressive JPEG at
# ~11-25 MP depending on components and subsampling.
MAX_DECODE_BYTES = 100_000_000


class ImageRejected(ValueError):
    """The upload is empty, not a supported image, malformed, or too large."""


def image_size(raw: bytes) -> tuple[int, int]:
    """Return ``(width, height)`` from a PNG, JPEG or WebP header without decoding.

    Raises ``ImageRejected`` for any other format or a truncated header.
    """
    width, height, _ = _header(raw)
    return width, height


def decode_cost(raw: bytes) -> int:
    """Estimate the bytes the codec allocates to decode ``raw`` to grayscale."""
    width, height, bytes_per_pixel = _header(raw)
    return int(width * height * bytes_per_pixel)


def _header(raw: bytes) -> tuple[int, int, float]:
    """``(width, height, estimated decode bytes per pixel)`` from the header."""
    try:
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            if raw[12:16] != b"IHDR":
                raise ImageRejected("malformed PNG header")
            width, height = struct.unpack(">II", raw[16:24])
            return width, height, 2.0
        if raw.startswith(b"\xff\xd8"):
            return _jpeg_header(raw)
        if raw[0:4] == b"RIFF" and raw[8:12] == b"WEBP":
            width, height = _webp_size(raw)
            return width, height, 4.0
    except (struct.error, IndexError):
        raise ImageRejected("truncated image header") from None
    raise ImageRejected("unsupported image format; use PNG, JPEG or WebP")


# Start-of-frame markers carry the frame dimensions. Only the variants browsers and
# cameras produce are accepted: baseline/extended sequential and progressive, Huffman
# or arithmetic coded. Lossless and hierarchical frames are refused.
_JPEG_SOF_ACCEPTED = {0xC0, 0xC1, 0xC2, 0xC9, 0xCA}
_JPEG_SOF_REFUSED = {0xC3, 0xC5, 0xC6, 0xC7, 0xCB, 0xCD, 0xCE, 0xCF}
_JPEG_PROGRESSIVE = {0xC2, 0xCA}
_JPEG_SOS = 0xDA


def _jpeg_header(raw: bytes) -> tuple[int, int, float]:
    """Walk the markers to the first scan; the frame and that scan set the cost.

    A single interleaved scan carrying every component streams through the decoder
    at ~2 bytes/pixel. Otherwise libjpeg buffers every component's DCT coefficients
    for the whole image: always for progressive, and also for a sequential image
    split into one scan per component (measured: same 50 MP image, 95 MiB
    interleaved vs 334 MiB split).
    """
    frame: tuple[int, int, int, list[int]] | None = None
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
        if marker in _JPEG_SOF_REFUSED:
            raise ImageRejected("unsupported JPEG variant (lossless or hierarchical)")
        if marker in _JPEG_SOF_ACCEPTED:
            if frame is not None:
                raise ImageRejected("malformed JPEG: more than one frame header")
            precision, height, width, ncomp = struct.unpack(">BHHB", raw[i + 2 : i + 8])
            if precision != 8:
                raise ImageRejected("unsupported JPEG precision; use 8-bit")
            sampling = [raw[i + 8 + 3 * c + 1] for c in range(ncomp)]
            if not sampling:
                raise ImageRejected("JPEG frame has no components")
            frame = (width, height, marker, sampling)
        if marker == _JPEG_SOS:
            if frame is None:
                raise ImageRejected("JPEG scan before frame header")
            width, height, sof, sampling = frame
            scan_components = raw[i + 2]
            if sof not in _JPEG_PROGRESSIVE and scan_components == len(sampling):
                return width, height, 2.0
            hmax = max(sf >> 4 for sf in sampling) or 1
            vmax = max(sf & 0x0F for sf in sampling) or 1
            # Fraction of full-resolution pixels each component stores.
            component_pixels = sum((sf >> 4) * (sf & 0x0F) / (hmax * vmax) for sf in sampling)
            return width, height, 1.0 + 2.0 * component_pixels
        i += length
    raise ImageRejected("JPEG has no scan")


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


def decode_upload(
    raw: bytes, max_pixels: int = MAX_PIXELS, max_decode_bytes: int = MAX_DECODE_BYTES
) -> np.ndarray:
    """Decode uploaded bytes to a grayscale image, refusing anything unsafe."""
    if not raw:
        raise ImageRejected("empty image upload")
    width, height, bytes_per_pixel = _header(raw)
    if width == 0 or height == 0:
        raise ImageRejected("image has no pixels")
    if width * height > max_pixels:
        raise ImageRejected(
            f"image is {width}x{height}; the limit is {max_pixels // 1_000_000} megapixels"
        )
    if width * height * bytes_per_pixel > max_decode_bytes:
        raise ImageRejected(
            f"image is {width}x{height} and too costly to decode in this format; "
            "re-save it smaller or as a baseline JPEG or PNG"
        )
    try:
        img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    except cv2.error:  # OpenCV's own size check (the container backstop) or a bad stream
        raise ImageRejected("cannot decode image bytes") from None
    if img is None:
        raise ImageRejected("cannot decode image bytes")
    return img

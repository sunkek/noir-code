"""Upload decoding refuses oversized and unsupported images before allocating pixels."""

import resource
import struct
import zlib

import cv2
import numpy as np
import pytest

from noircode.config import Config
from noircode.decode.decoder import decode
from noircode.encode.encoder import encode
from noircode.upload import MAX_PIXELS, ImageRejected, decode_upload, image_size


def _blank_png(width: int, height: int) -> bytes:
    """A valid grayscale PNG that compresses to almost nothing at any size."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + b"\xff" * width
    z = zlib.compressobj(9)
    idat = b"".join(z.compress(row) for _ in range(height)) + z.flush()
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    sig = b"\x89PNG\r\n\x1a\n"
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _encoded(ext: str, img: np.ndarray, params: list[int] | None = None) -> bytes:
    ok, buf = cv2.imencode(ext, img, params or [])
    assert ok
    return buf.tobytes()


IMG = np.random.default_rng(0).integers(0, 255, (123, 457), dtype=np.uint8)


@pytest.mark.parametrize(
    ("ext", "params"),
    [
        (".png", None),
        (".jpg", None),
        (".jpg", [cv2.IMWRITE_JPEG_PROGRESSIVE, 1]),
        (".webp", [cv2.IMWRITE_WEBP_QUALITY, 80]),  # lossy VP8
        (".webp", [cv2.IMWRITE_WEBP_QUALITY, 101]),  # lossless VP8L
    ],
)
def test_header_size_matches_real_files(ext: str, params: list[int] | None) -> None:
    assert image_size(_encoded(ext, IMG, params)) == (457, 123)


def test_webp_extended_header() -> None:
    vp8x = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"VP8X" + b"\x0a\x00\x00\x00" + b"\x00" * 4
    vp8x += (4999).to_bytes(3, "little") + (2999).to_bytes(3, "little")
    assert image_size(vp8x) == (5000, 3000)


def test_decompression_bomb_is_refused_without_allocating() -> None:
    bomb = _blank_png(30_000, 30_000)  # ~1 MB on the wire, ~900 MP decoded
    assert len(bomb) < 2_000_000
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with pytest.raises(ImageRejected, match="megapixels"):
        decode_upload(bomb)
    grown_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - before
    assert grown_kib < 100_000


def test_just_under_the_limit_is_accepted() -> None:
    side = int(MAX_PIXELS**0.5)
    assert decode_upload(_blank_png(side, 100)).shape == (100, side)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        _encoded(".bmp", IMG),
        _encoded(".tiff", IMG),
        b"GIF89a" + b"\x00" * 20,
        b"\x89PNG\r\n\x1a\n\x00\x00",  # truncated PNG
        b"\xff\xd8\xff\xe0\x00",  # truncated JPEG
        b"RIFF\x00\x00\x00\x00WEBPVP8L",  # truncated WebP
        b"not an image at all",
    ],
)
def test_rejects_empty_unsupported_and_truncated(raw: bytes) -> None:
    with pytest.raises(ImageRejected):
        decode_upload(raw)


def test_header_lies_about_content() -> None:
    # Valid PNG header, garbage body: header check passes, decoding fails cleanly.
    png = _blank_png(50, 50)
    with pytest.raises(ImageRejected, match="cannot decode"):
        decode_upload(png[:40] + b"\x00" * 30)


@pytest.mark.parametrize("ext", [".png", ".jpg", ".webp"])
def test_real_panel_still_decodes(ext: str) -> None:
    text = "https://noir-code.suncake.xyz"
    panel = encode(text, style=True, adaptive=True)
    params = [cv2.IMWRITE_WEBP_QUALITY, 101] if ext == ".webp" else None
    img = decode_upload(_encoded(ext, panel, params))
    assert decode(img, Config()).text == text

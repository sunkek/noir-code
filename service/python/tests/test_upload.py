"""Upload decoding refuses oversized and unsupported images before allocating pixels."""

import resource
import struct
import zlib
from pathlib import Path

import cv2
import numpy as np
import pytest

from noircode.config import Config
from noircode.decode.decoder import decode
from noircode.encode.encoder import encode
from noircode.upload import (
    MAX_DECODE_BYTES,
    MAX_PIXELS,
    ImageRejected,
    decode_cost,
    decode_upload,
    image_size,
)


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


RGB = np.dstack([IMG, IMG[::-1], np.full_like(IMG, 128)])


@pytest.mark.parametrize(
    ("ext", "img", "params", "bytes_per_pixel"),
    [
        (".png", IMG, None, 2.0),
        (".jpg", RGB, None, 2.0),  # baseline
        (".webp", RGB, [cv2.IMWRITE_WEBP_QUALITY, 80], 4.0),
        # Progressive keeps every component's coefficients: 1 + 2 x component-pixels.
        (".jpg", IMG, [cv2.IMWRITE_JPEG_PROGRESSIVE, 1], 3.0),
        (
            ".jpg",
            RGB,
            [
                cv2.IMWRITE_JPEG_PROGRESSIVE,
                1,
                cv2.IMWRITE_JPEG_SAMPLING_FACTOR,
                cv2.IMWRITE_JPEG_SAMPLING_FACTOR_420,
            ],
            4.0,
        ),
        (
            ".jpg",
            RGB,
            [
                cv2.IMWRITE_JPEG_PROGRESSIVE,
                1,
                cv2.IMWRITE_JPEG_SAMPLING_FACTOR,
                cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444,
            ],
            7.0,
        ),
    ],
)
def test_decode_cost_by_format(
    ext: str, img: np.ndarray, params: list[int] | None, bytes_per_pixel: float
) -> None:
    raw = _encoded(ext, img, params)
    assert decode_cost(raw) == int(457 * 123 * bytes_per_pixel)


def test_costly_format_refused_where_cheap_one_is_not() -> None:
    # Same pixels, same budget: baseline fits, progressive 4:4:4 does not. At full
    # size this is a 744 KiB file that cost 334 MiB to decode.
    budget = 457 * 123 * 3
    baseline = _encoded(".jpg", RGB)
    progressive = _encoded(
        ".jpg",
        RGB,
        [
            cv2.IMWRITE_JPEG_PROGRESSIVE,
            1,
            cv2.IMWRITE_JPEG_SAMPLING_FACTOR,
            cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444,
        ],
    )
    assert decode_upload(baseline, max_decode_bytes=budget).shape == (123, 457)
    with pytest.raises(ImageRejected, match="too costly"):
        decode_upload(progressive, max_decode_bytes=budget)


def test_default_budget_admits_a_50mp_baseline_photo() -> None:
    # 8160x6120 (a 50 MP phone frame) as PNG/baseline JPEG costs 2 bytes/pixel.
    assert MAX_DECODE_BYTES >= 8160 * 6120 * 2
    assert MAX_PIXELS >= 8160 * 6120


FIXTURES = Path(__file__).parent / "fixtures"


def test_sequential_jpeg_split_into_one_scan_per_component_is_charged_as_buffered() -> None:
    # Made with `jpegtran -scans` from a baseline 4:4:4 image: still a baseline
    # (SOF0) frame, but each component in its own scan, so libjpeg buffers the
    # whole image's coefficients. At 50 MP this cost 334 MiB, like progressive.
    raw = (FIXTURES / "noninterleaved_444.jpg").read_bytes()
    assert b"\xff\xc0" in raw and b"\xff\xc2" not in raw  # baseline, not progressive
    assert raw.count(b"\xff\xda") == 3  # three scans, one per component
    assert decode_cost(raw) == int(457 * 123 * 7.0)
    assert decode_upload(raw).shape == (123, 457)


def _jpeg_with_frame(marker: int, precision: int = 8) -> bytes:
    frame = struct.pack(">HBHHB", 11, precision, 64, 64, 1) + bytes([1, 0x11, 0])
    scan = struct.pack(">HB", 8, 1) + bytes([1, 0, 0, 63, 0])
    return b"\xff\xd8" + bytes([0xFF, marker]) + frame + b"\xff\xda" + scan + b"\x00" * 16


@pytest.mark.parametrize(
    ("marker", "precision", "message"),
    [
        (0xC0, 12, "precision"),  # 12-bit baseline
        (0xC3, 8, "lossless"),
        (0xC7, 8, "hierarchical"),
        (0xCB, 8, "lossless"),
    ],
)
def test_rare_jpeg_variants_are_refused(marker: int, precision: int, message: str) -> None:
    with pytest.raises(ImageRejected, match=message):
        decode_upload(_jpeg_with_frame(marker, precision))


def test_hand_built_header_parses_as_baseline() -> None:
    assert decode_cost(_jpeg_with_frame(0xC0)) == 64 * 64 * 2

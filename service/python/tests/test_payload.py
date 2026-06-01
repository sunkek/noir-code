"""Frame build/parse + CRC, including malformed input (Stage 1)."""

import zlib

import pytest

from noircode.config import HEADER_BYTES, MAGIC_VALUE
from noircode.payload import FrameError, build_frame, parse_frame


@pytest.mark.parametrize("payload", [b"", b"x", b"hello world", b"\x00\xff" * 50])
def test_roundtrip(payload: bytes) -> None:
    assert parse_frame(build_frame(payload)) == payload


def test_trailing_bytes_ignored() -> None:
    frame = build_frame(b"abc")
    assert parse_frame(frame + b"\x00" * 32) == b"abc"


def test_bad_magic() -> None:
    frame = bytearray(build_frame(b"abc"))
    frame[0] ^= 0xFF
    with pytest.raises(FrameError, match="bad magic"):
        parse_frame(bytes(frame))


def test_crc_mismatch() -> None:
    frame = bytearray(build_frame(b"abc"))
    frame[HEADER_BYTES] ^= 0x01  # corrupt a payload byte
    with pytest.raises(FrameError, match="CRC mismatch"):
        parse_frame(bytes(frame))


def test_truncated() -> None:
    frame = build_frame(b"abcdef")
    with pytest.raises(FrameError, match="truncated"):
        parse_frame(frame[:-2])


def test_too_short() -> None:
    with pytest.raises(FrameError, match="too short"):
        parse_frame(b"\x00")


def test_crc_is_over_payload_only() -> None:
    payload = b"noir"
    frame = build_frame(payload)
    crc = int.from_bytes(frame[-4:], "big")
    assert crc == zlib.crc32(payload) & 0xFFFFFFFF
    assert frame[0] == MAGIC_VALUE

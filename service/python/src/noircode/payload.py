"""Frame build/parse and CRC32.

Frame (before ECC):
    +--------+---------+--------------+-------------+
    | MAGIC  |  LEN    |   PAYLOAD    | PAYLOAD_CRC |
    | 1 byte | 2 bytes |  LEN bytes   |   4 bytes   |
    +--------+---------+--------------+-------------+

LEN and CRC are big-endian. CRC32 is computed over PAYLOAD only.
"""

from __future__ import annotations

import zlib

from noircode.config import (
    CRC_BYTES,
    FRAME_OVERHEAD_BYTES,
    HEADER_BYTES,
    LEN_BYTES,
    MAGIC_BYTES,
    MAGIC_VALUE,
    MAX_PAYLOAD_LEN,
)


class FrameError(ValueError):
    """Raised when a byte string is not a well-formed noir-code frame."""


def build_frame(payload: bytes) -> bytes:
    """Wrap ``payload`` in a MAGIC/LEN/PAYLOAD/CRC frame."""
    if len(payload) > MAX_PAYLOAD_LEN:
        raise FrameError(f"payload too long: {len(payload)} > {MAX_PAYLOAD_LEN}")
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    return b"".join(
        [
            MAGIC_VALUE.to_bytes(MAGIC_BYTES, "big"),
            len(payload).to_bytes(LEN_BYTES, "big"),
            payload,
            crc.to_bytes(CRC_BYTES, "big"),
        ]
    )


def parse_frame(frame: bytes) -> bytes:
    """Validate a frame and return its payload, or raise :class:`FrameError`.

    Trailing bytes after the declared frame (e.g. grid padding) are ignored.
    """
    if len(frame) < FRAME_OVERHEAD_BYTES:
        raise FrameError(f"frame too short: {len(frame)} < {FRAME_OVERHEAD_BYTES}")

    magic = int.from_bytes(frame[:MAGIC_BYTES], "big")
    if magic != MAGIC_VALUE:
        raise FrameError(f"bad magic: 0x{magic:02X} != 0x{MAGIC_VALUE:02X}")

    length = int.from_bytes(frame[MAGIC_BYTES:HEADER_BYTES], "big")
    payload_end = HEADER_BYTES + length
    crc_end = payload_end + CRC_BYTES
    if len(frame) < crc_end:
        raise FrameError(f"truncated: need {crc_end} bytes for LEN={length}, have {len(frame)}")

    payload = frame[HEADER_BYTES:payload_end]
    stored_crc = int.from_bytes(frame[payload_end:crc_end], "big")
    actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
    if stored_crc != actual_crc:
        raise FrameError(f"CRC mismatch: 0x{stored_crc:08X} != 0x{actual_crc:08X}")
    return payload

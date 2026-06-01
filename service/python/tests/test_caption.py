"""A caption band is branding only: rendered outside the frame/quiet zone, it must
not affect detection or decoding."""

from noircode.config import Config
from noircode.decode.decoder import decode
from noircode.encode.encoder import encode


def test_caption_does_not_break_decode() -> None:
    text = "https://noir-code.suncake.xyz"
    plain = encode(text, style=True, adaptive=True)
    captioned = encode(text, style=True, adaptive=True, caption="noir-code.suncake.xyz")
    # Footer adds rows below the panel, same width.
    assert captioned.shape[0] > plain.shape[0]
    assert captioned.shape[1] == plain.shape[1]
    assert decode(captioned, Config()).text == text

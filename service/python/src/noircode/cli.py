"""``noir`` command-line interface: encode / decode / eval."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Annotated

import cv2
import typer

from noircode.config import Config
from noircode.decode.decoder import decode as decode_image
from noircode.ecc import EccError
from noircode.encode.encoder import encode as encode_text
from noircode.eval import default_sweep, format_report

app = typer.Typer(add_completion=False, help="NoiR Code: encode/decode data as a noir panel.")


@app.command()
def encode(
    text: Annotated[str, typer.Argument(help="Text payload to encode.")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output PNG path.")],
    style: Annotated[bool, typer.Option(help="Apply the noir styling pass.")] = False,
    hatch_data: Annotated[
        bool,
        typer.Option(
            "--hatch-data",
            help="Render data cells as line hatching (engraving look) instead of flat "
            "gray. Halftone mode only (needs --style).",
        ),
    ] = False,
    adaptive: Annotated[
        bool,
        typer.Option(
            "--adaptive/--no-adaptive",
            help="Shrink the grid to the smallest size that fits the text (smaller panel "
            "for short payloads). Decoded automatically. On by default; "
            "--no-adaptive forces the full fixed grid.",
        ),
    ] = True,
) -> None:
    """Encode TEXT into a noir-code panel PNG."""
    cfg = dataclasses.replace(Config(), hatched_data=hatch_data)
    try:
        panel = encode_text(text, cfg, style=style, adaptive=adaptive)
    except EccError:
        limit = cfg.rs_data_bytes - 7
        typer.echo(
            f"text too long: {len(text.encode('utf-8'))} bytes; capacity is {limit} bytes. "
            f"Shorten it, lower rs_parity_ratio, or grow the grid.",
            err=True,
        )
        raise typer.Exit(code=1) from None
    if not cv2.imwrite(str(out), panel):
        raise typer.Exit(code=1)
    typer.echo(f"wrote {out} ({panel.shape[1]}x{panel.shape[0]})")


@app.command()
def decode(
    path: Annotated[Path, typer.Argument(help="Panel image to decode.")],
) -> None:
    """Decode a panel image and print a structured result."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        typer.echo(f"cannot read image: {path}", err=True)
        raise typer.Exit(code=1)

    res = decode_image(img, Config())
    typer.echo(f"text:         {res.text!r}")
    typer.echo(f"confidence:   {res.confidence:.2%}")
    typer.echo(f"rotation:     {res.rotation}")
    typer.echo(f"grid_erasure: {res.grid_erasures}")
    typer.echo(f"motif_erasur: {res.motif_erasures}")
    typer.echo(f"cross_check:  {res.cross_check}")
    typer.echo(f"failed_stage: {res.failed_stage}")
    if not res.ok:
        raise typer.Exit(code=2)


@app.command()
def eval(
    trials: Annotated[int, typer.Option(help="Trials per sweep point.")] = 12,
) -> None:
    """Run the robustness sweep and print the report."""
    typer.echo(format_report(default_sweep(trials=trials)))


if __name__ == "__main__":
    app()

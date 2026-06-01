"""Stage 6: CLI encode -> decode round-trip."""

from pathlib import Path

from typer.testing import CliRunner

from noircode.cli import app

runner = CliRunner()


def test_cli_encode_decode_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "panel.png"
    enc = runner.invoke(app, ["encode", "cli noir", "--out", str(out)])
    assert enc.exit_code == 0, enc.output
    assert out.exists()

    dec = runner.invoke(app, ["decode", str(out)])
    assert dec.exit_code == 0, dec.output
    assert "'cli noir'" in dec.output


def test_cli_encode_styled(tmp_path: Path) -> None:
    out = tmp_path / "styled.png"
    enc = runner.invoke(app, ["encode", "styled", "--out", str(out), "--style"])
    assert enc.exit_code == 0
    dec = runner.invoke(app, ["decode", str(out)])
    assert dec.exit_code == 0 and "'styled'" in dec.output


def test_cli_encode_hatched_data(tmp_path: Path) -> None:
    out = tmp_path / "hatched.png"
    enc = runner.invoke(app, ["encode", "hatched", "--out", str(out), "--style", "--hatch-data"])
    assert enc.exit_code == 0, enc.output
    dec = runner.invoke(app, ["decode", str(out)])
    assert dec.exit_code == 0 and "'hatched'" in dec.output


def test_cli_decode_missing_file(tmp_path: Path) -> None:
    dec = runner.invoke(app, ["decode", str(tmp_path / "nope.png")])
    assert dec.exit_code == 1

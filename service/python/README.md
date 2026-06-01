# NoiR Code — `noircode` (Python reference implementation)

Reference encoder/decoder for NoiR Code: a QR-like scheme where the code **is** a noir
comic panel. This is the deterministic, byte-stable core (format, channel split, ECC
tuning, CV pipeline) plus the CLI and the FastAPI imaging sidecar.

## Develop

```
uv sync                 # install deps + dev group
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy             # type check (strict)
uv run pytest           # tests
```

## CLI

```
noir encode "text payload" --out panel.png [--style]
noir decode panel.png            # text + confidence + diagnostics
noir eval [--trials N]           # robustness sweep report
```

## Capacity vs robustness (from `noir eval`)

Sweep of decode success rate over synthetic warp + occlusion of **hatched, fully
styled** panels (40x40 grid). "cap" is max payload bytes; "cover" is fraction of the
grid occluded. Codeword bytes are interleaved across the grid, so localized occlusion
spreads across the per-block Reed-Solomon codes instead of destroying one block.

| tonal levels | RS parity | payload cap | 0% | 10% | 20% | 30% |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 4 | 0.25 | 286 | 100% | 8% | 0% | 0% |
| 4 | 0.40 | 226 | 100% | 92% | 0% | 0% |
| 4 | **0.55** | **173** | 100% | 100% | 67% | 0% |
| 8 | 0.55 | 256 | 100% | 100% | 67% | 0% |

**Defaults** (`Config`): 40x40 grid, tonal_levels=4, rs_parity_ratio=0.55 → **173 byte**
payload. Data cells are drawn as **ink hatching** (the noir "shadow density" look),
which costs robustness; ~55% parity buys it back, decoding cleanly through ~10% grid
loss. The codeword spans multiple 255-symbol RS blocks (one per ~200 bytes). This is
the art<->capacity<->robustness trade made explicit: lower parity or raise tonal levels
for more capacity at the cost of damage tolerance or tonal margin.

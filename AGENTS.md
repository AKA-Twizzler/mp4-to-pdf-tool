# MP4 to PDF Tool

## OVERVIEW
Extract frames from MP4 video via ffmpeg, assemble into PDF. 5 selection modes, 4 quality profiles, strict config validation.

## STRUCTURE
```text
tools/
├── mp4_to_pdf.py               # CLI entry (argparse)
├── run_integration_matrix.py   # Determinism matrix runner
└── mp4_to_pdf_lib/             # 11-module pipeline
    ├── orchestrator.py          # parse -> select -> extract -> assemble -> verify
    ├── schema.py                # ALLOWED_KEYS, MODE_TO_SELECTOR_KEY, QUALITY_PROFILES
    ├── options_parser.py        # key:value txt/md parser with alias resolution
    ├── selection.py             # frame index computation (5 strategies)
    ├── extract.py               # ffmpeg subprocess frame extraction
    ├── assemble.py              # img2pdf assembly
    ├── verify.py                # gs + pdfinfo integrity check
    ├── quality.py               # profile -> ffmpeg arg mapping
    ├── preflight.py             # dependency checks
    ├── benchmark.py             # timing harness
    └── errors.py                # code -> message mapping
recipes/                         # Options templates + schema docs
```

## WHERE TO LOOK
| Task | File |
| --- | --- |
| Pipeline flow | `tools/mp4_to_pdf_lib/orchestrator.py` |
| Add selection mode | `selection.py` + `schema.py` (MODE_TO_SELECTOR_KEY) |
| Add quality profile | `quality.py` + `schema.py` (QUALITY_PROFILES) |
| Options parsing | `options_parser.py` (alias resolution, markdown stripping) |
| Error codes | `schema.py` (E_CONFIG_*) + `errors.py` |
| Recipe examples | `recipes/mp4-to-pdf-recipes.md` |

## CONVENTIONS
- Job contract: `jobs/<id>/input.mp4` + `options.txt|md` -> `output.pdf`.
- Options are `key: value` text. Aliases map shorthand to canonical keys (e.g. `fps` -> `selector_fps`).
- Exactly one selector key active per job, must match `mode` value.
- Selection modes: `every_frame`, `fps`, `every_nth`, `keyframes`, `time_range`.
- Quality profiles: `jpeg_fast`, `jpeg_balanced`, `jpeg_small`, `png_lossless`.
- `--pdf-nodate` strips mutable metadata for byte-identical determinism testing.
- No venv here, uses system ffmpeg/img2pdf/ghostscript. PDF tool's venv for pytest.

## ANTI-PATTERNS
- Never set alias and canonical selector together (raises `E_CONFIG_ALIAS_AMBIGUITY`).
- Never enable multiple selector keys (raises `E_CONFIG_MODE_CONFLICT`).
- Never combine `--job-dir` with `--parse-options`.
- Never add config keys without updating `ALLOWED_KEYS` in schema.py.
- Never skip verify step, it catches corrupt or truncated PDFs.

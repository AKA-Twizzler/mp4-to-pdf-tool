# MP4 to PDF Conversion Pipeline
Convert MP4 video frames to PDF locally, faster than browser-based tools.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Guide](#usage-guide)
- [Frame Selection Modes](#frame-selection-modes)
- [Quality Profiles](#quality-profiles)
- [Options File Reference](#options-file-reference)
- [Recipe Profiles](#recipe-profiles)
- [CLI Reference](#cli-reference)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)

## Features
- Local, scriptable MP4-to-PDF conversion with no web upload.
- Deterministic job contract using `jobs/<job-id>/` and `options.txt` or `options.md`.
- Five frame selection modes, including frame rate, every Nth frame, keyframes, and time range.
- Four output quality profiles, from fast JPEG preview to lossless PNG.
- Batch execution for many jobs in one command.
- Built-in verification, benchmarking, schema checks, and config introspection flags.

## Prerequisites
- Python `3.12+`
- `ffmpeg`
- `img2pdf` Python package
- For PDF verification: `ghostscript` (`gs`) and `poppler` (`pdfinfo`)

> **Tip:** Run preflight before your first conversion to validate tools and Python dependencies.

```bash
python3 tools/mp4_to_pdf.py --preflight --strict
```

## Installation
Ubuntu or Debian:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg ghostscript poppler-utils python3-pip
python3 -m pip install img2pdf
```

macOS (Homebrew):

```bash
brew install ffmpeg ghostscript poppler
python3 -m pip install img2pdf
```

## Quick Start
1) Install dependencies and run preflight.

```bash
python3 tools/mp4_to_pdf.py --preflight --strict
```

2) Create a job folder and `options.txt`.

```bash
mkdir -p jobs/my-video
cat > jobs/my-video/options.txt <<'EOF'
mode: fps
quality_profile: jpeg_balanced
input_mp4: jobs/my-video/input.mp4
output_pdf: jobs/my-video/output.pdf
selector_fps: 2
EOF
```

3) Run the job.

```bash
python3 tools/mp4_to_pdf.py --job-dir jobs/my-video
```

## Usage Guide
### Job folder structure
Each job must follow this contract:

```text
jobs/<job-id>/
  input.mp4
  options.txt or options.md
  output.pdf
```

`--job-dir` points at `jobs/<job-id>/`.

### Create an options file
Use either `options.txt` or `options.md`. Both use `key: value` pairs.

Minimal valid config:

```text
mode: fps
quality_profile: jpeg_balanced
input_mp4: jobs/my-video/input.mp4
output_pdf: jobs/my-video/output.pdf
selector_fps: 2
```

Required keys:
- `mode`
- `quality_profile`
- `input_mp4`
- `output_pdf`

### Run a single job

```bash
python3 tools/mp4_to_pdf.py --job-dir jobs/my-video
```

Use `--pdf-nodate` for stable output metadata in reproducible workflows:

```bash
python3 tools/mp4_to_pdf.py --job-dir jobs/my-video --pdf-nodate
```

### Verify output

```bash
python3 tools/mp4_to_pdf.py --verify --job-dir jobs/my-video
```

### Run batch mode

```bash
python3 tools/mp4_to_pdf.py --jobs-root jobs --batch
```

Strict batch mode, stop on first invalid job:

```bash
python3 tools/mp4_to_pdf.py --jobs-root jobs --batch --strict
```

### Real-world workflow example
For a 33.7-minute 1080p video at `fps: 2`, a typical run produced:
- `4,047` pages
- `511 MB` PDF
- `jpeg_balanced` quality profile

Example command:

```bash
python3 tools/mp4_to_pdf.py --job-dir jobs/lecture-33min --pdf-nodate
```

> **Warning:** High page count PDFs can be large and slow to open in lightweight viewers.

### Benchmarking
Run repeated conversion timing with JSON output:

```bash
python3 tools/mp4_to_pdf.py --job-dir jobs/my-video --benchmark-runs 3 --report-json jobs/my-video/benchmark.json
```

## Frame Selection Modes
Use exactly one selector mode per job.

| Mode | What it does | Required selector key |
|---|---|---|
| `every_frame` | Every single frame | `selector_every_frame: true` |
| `fps` | N frames per second | `selector_fps: 2` |
| `every_nth` | Every Nth frame | `selector_every_nth: 10` |
| `keyframes` | Only I-frames or scene-change keyframes | `selector_keyframes: true` |
| `time_range` | Frames inside a time window in seconds | `selector_time_range: 5-15` |

## Quality Profiles
`jpeg_balanced` is the default profile.

| Profile | ffmpeg settings | Use case |
|---|---|---|
| `jpeg_fast` | `-c:v mjpeg -q:v 3` | Fastest output generation |
| `jpeg_balanced` | `-c:v mjpeg -q:v 5` | Default and recommended baseline |
| `jpeg_small` | `-c:v mjpeg -q:v 8` | Smaller output files |
| `png_lossless` | `-c:v png -pix_fmt rgb24` | Maximum visual fidelity |

## Options File Reference
### Full key list
Allowed keys:
- `mode`
- `quality_profile`
- `input_mp4`
- `output_pdf`
- `selector_every_frame`
- `selector_fps`
- `selector_every_nth`
- `selector_keyframes`
- `selector_time_range`

### Alias mapping
Alias keys map to canonical selector keys:

| Alias | Canonical key |
|---|---|
| `every_frame` | `selector_every_frame` |
| `fps` | `selector_fps` |
| `every_nth` | `selector_every_nth` |
| `keyframes` | `selector_keyframes` |
| `time_range` | `selector_time_range` |

> **Warning:** Do not set both alias and canonical versions for the same selector. That fails with `E_CONFIG_ALIAS_AMBIGUITY`.

### Parsing rules
- Lines with no `:` are ignored.
- Empty lines are ignored.
- Lines starting with `#` or `//` are comments.
- Markdown list prefixes `- ` and `* ` are stripped before parsing.
- Keys are normalized to lowercase with `_` separators.

### Complete example

```text
mode: fps
quality_profile: jpeg_balanced
input_mp4: jobs/demo/input.mp4
output_pdf: jobs/demo/output.pdf
selector_fps: 2
```

## Recipe Profiles
Ready-to-use options templates.

### 1) Fast preview
```text
mode: every_nth
quality_profile: jpeg_fast
input_mp4: jobs/fast-preview/input.mp4
output_pdf: jobs/fast-preview/output.pdf
selector_every_nth: 10
```

### 2) Balanced
```text
mode: fps
quality_profile: jpeg_balanced
input_mp4: jobs/balanced/input.mp4
output_pdf: jobs/balanced/output.pdf
selector_fps: 2
```

### 3) Smallest
```text
mode: fps
quality_profile: jpeg_small
input_mp4: jobs/smallest/input.mp4
output_pdf: jobs/smallest/output.pdf
selector_fps: 1
```

### 4) Max quality
```text
mode: every_frame
quality_profile: png_lossless
input_mp4: jobs/max-quality/input.mp4
output_pdf: jobs/max-quality/output.pdf
selector_every_frame: true
```

## CLI Reference
Command:

```bash
python3 tools/mp4_to_pdf.py [flags]
```

### Info and introspection
- `--print-schema`
- `--print-error-map`
- `--print-profile-map`

### Config validation and preparation
- `--schema-lint`
- `--preflight`
- `--strict`
- `--quality-profile QUALITY_PROFILE`
- `--job-dir JOB_DIR`
- `--jobs-root JOBS_ROOT`
- `--parse-options PARSE_OPTIONS`
- `--print-config-json`

### Execution
- `--batch`
- `--temp-dir TEMP_DIR`
- `--keep-temp`
- `--pdf-nodate`

### Selection dry-run and simulation inputs
- `--selection-dry-run`
- `--selection-frame-count SELECTION_FRAME_COUNT`
- `--selection-source-fps SELECTION_SOURCE_FPS`
- `--selection-duration-seconds SELECTION_DURATION_SECONDS`
- `--selection-keyframe-indices SELECTION_KEYFRAME_INDICES`
- `--selection-report-path SELECTION_REPORT_PATH`

### Verification
- `--verify`

### Benchmark and reports
- `--benchmark-runs BENCHMARK_RUNS`
- `--report-json REPORT_JSON`

## Troubleshooting
Error codes from the runbook, with common cause and fix.

| Error code | Typical cause | Fix |
|---|---|---|
| `E_DEP_MISSING` | Missing binary or Python module during preflight | Install the missing dependency shown in the message, rerun `--preflight --strict` |
| `E_CONFIG_UNKNOWN_KEY` | Unsupported key in options, for example `selector_interval` | Replace with a supported key, for example `selector_every_nth`, `selector_fps`, `selector_time_range`, `selector_keyframes`, `selector_every_frame` |
| `E_CONFIG_ALIAS_AMBIGUITY` | Both alias and canonical selector key used for the same field | Keep one form only, for example `fps` or `selector_fps`, not both |
| `E_CONFIG_MODE_CONFLICT` | Multiple selector keys enabled, or `mode` does not match active selector | Keep exactly one selector key enabled and align it with `mode` |
| `E_CONFIG_MISSING_REQUIRED` | Required key missing or empty, or required selection inputs missing in dry-run | Add required keys: `mode`, `quality_profile`, `input_mp4`, `output_pdf` and required selector values |
| `E_CONFIG_DUPLICATE_KEY` | Same key repeated in options file | Keep one unique entry per key |
| `E_CONFIG_BAD_MODE` | `mode` is not one of `fps`, `every_frame`, `every_nth`, `keyframes`, `time_range` | Set `mode` to a supported value |
| `E_CONFIG_BAD_QUALITY_PROFILE` | Unsupported quality profile | Use one of `jpeg_fast`, `jpeg_balanced`, `jpeg_small`, `png_lossless` |
| `E_CONFIG_BAD_INPUT_FORMAT` | `input_mp4` does not use `.mp4` extension in v1 | Point `input_mp4` to an `.mp4` path, absolute or job-dir-relative |
| `E_CONFIG_INVALID_BENCHMARK_RUNS` | `--benchmark-runs` is zero or negative | Use a positive integer, for example `--benchmark-runs 3` |
| `E_NO_FRAMES_SELECTED` | Selection rule chooses zero frames | Relax the selector, widen time range, or lower `every_nth` |
| `E_EXTRACT_BINARY_MISSING` | Configured `ffmpeg` binary path is missing | Install `ffmpeg` or fix `MP4_TO_PDF_FFMPEG_BIN` to a valid executable |
| `E_EXTRACT_FAILED` | `ffmpeg` extraction command failed | Check source MP4 path and ffmpeg availability, inspect command output in error text |
| `E_NO_FRAMES_EXTRACTED` | Extraction finished but no `frame_*.png` files were produced | Verify input has frames and selection and extraction settings are valid |
| `E_ASSEMBLY_INPUT_MISSING` | Manifest missing, empty, or points to missing frame files | Regenerate extraction workspace, ensure manifest and frame paths exist |
| `E_ASSEMBLY_FAILED` | `img2pdf` command failed | Verify `img2pdf` installation and manifest entries, rerun after fixing source inputs |
| `E_JOB_INVALID` | Job folder invalid, for example missing options file or missing input MP4 | Keep one options file, `options.txt` or `options.md`, ensure `input_mp4` exists |
| `E_PDF_VALIDATE` | PDF verification failed, `pdfinfo`, `gs`, or page or manifest mismatch | Recreate output PDF, confirm verify tools are installed, confirm manifest matches selected frames |
| `E_UNEXPECTED` | Unmapped runtime failure | Rerun with the same command, capture stderr, then fix underlying tool or input issue |

## Project Structure
Paths are relative to repository root.

```text
.
├── tools/
│   └── mp4_to_pdf.py
├── recipes/
│   ├── mp4-to-pdf-recipes.md
│   └── options-schema.md
├── jobs/
│   └── <job-id>/
│       ├── input.mp4
│       ├── options.txt or options.md
│       └── output.pdf
└── fixtures/
    └── ...
```

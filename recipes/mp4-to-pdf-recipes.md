# MP4 to PDF Recipes and Operator Runbook

This runbook documents supported commands and options for `tools/mp4_to_pdf.py`.
It stays within the current v1 schema and error behavior.

## Recipe Profiles

These four profiles are reusable starting points.

### 1) Fast preview

Use this for the quickest visual check.

```text
mode: every_nth
quality_profile: jpeg_fast
input_mp4: fixtures/cfr10_3s.mp4
output_pdf: fixtures/job_examples/fast_preview/output.pdf
selector_every_nth: 10
```

### 2) Balanced

Use this when you want readable output with moderate size.

```text
mode: fps
quality_profile: jpeg_balanced
input_mp4: fixtures/cfr10_3s.mp4
output_pdf: fixtures/job_examples/balanced/output.pdf
selector_fps: 2
```

### 3) Smallest

Use this when output size matters most.

```text
mode: fps
quality_profile: jpeg_small
input_mp4: fixtures/cfr10_3s.mp4
output_pdf: fixtures/job_examples/smallest/output.pdf
selector_fps: 1
```

### 4) Max quality

Use this when visual fidelity is the top priority.

```text
mode: every_frame
quality_profile: png_lossless
input_mp4: fixtures/cfr10_3s.mp4
output_pdf: fixtures/job_examples/max_quality/output.pdf
selector_every_frame: true
```

## Operator Flow

Run these steps in order.

### 1) Install dependencies

Ubuntu/Debian:

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

### 2) Preflight check

```bash
python3 tools/mp4_to_pdf.py --preflight --strict
```

### 3) Parse options before execution (optional, recommended)

```bash
python3 tools/mp4_to_pdf.py --parse-options fixtures/job_examples/balanced/options.md --print-config-json
```

### 4) Run one job

```bash
python3 tools/mp4_to_pdf.py --job-dir fixtures/job_examples/balanced --pdf-nodate
```

### 5) Verify one job output

```bash
python3 tools/mp4_to_pdf.py --verify --job-dir fixtures/job_examples/balanced
```

### 6) Run batch mode

```bash
python3 tools/mp4_to_pdf.py --jobs-root fixtures/job_examples --batch --pdf-nodate
```

Strict batch mode (stop on first invalid job):

```bash
python3 tools/mp4_to_pdf.py --jobs-root fixtures/job_examples --batch --strict --pdf-nodate
```

### 7) Local shim mode for deterministic QA in this repo

Use this only in environments that do not have real `ffmpeg`, `img2pdf`, `gs`, or `pdfinfo`.

```bash
PATH="$(pwd)/.sisyphus/evidence/fake_bin:$PATH" MP4_TO_PDF_FFMPEG_BIN="$(pwd)/.sisyphus/evidence/fake_ffmpeg_ok.py" python3 tools/mp4_to_pdf.py --job-dir fixtures/job_examples/balanced --pdf-nodate
```

## Sample Jobs in `fixtures/job_examples/`

- `fixtures/job_examples/fast_preview/options.txt`
- `fixtures/job_examples/balanced/options.md`
- `fixtures/job_examples/smallest/options.txt`
- `fixtures/job_examples/max_quality/options.md`
- `fixtures/job_examples/stale_key/options.txt` (intentional failure sample)

## Troubleshooting by Error Code

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
| `E_CONFIG_BAD_INPUT_FORMAT` | `input_mp4` does not use `.mp4` extension in v1 | Point `input_mp4` to an `.mp4` path (absolute or job-dir-relative) |
| `E_CONFIG_INVALID_BENCHMARK_RUNS` | `--benchmark-runs` is zero or negative | Use a positive integer, for example `--benchmark-runs 3` |
| `E_NO_FRAMES_SELECTED` | Selection rule chooses zero frames | Relax the selector, widen time range, or lower `every_nth` |
| `E_EXTRACT_BINARY_MISSING` | Configured `ffmpeg` binary path is missing | Install `ffmpeg` or fix `MP4_TO_PDF_FFMPEG_BIN` to a valid executable |
| `E_EXTRACT_FAILED` | `ffmpeg` extraction command failed | Check source MP4 path and ffmpeg availability, inspect command output in error text |
| `E_NO_FRAMES_EXTRACTED` | Extraction finished but no `frame_*.png` files were produced | Verify input has frames and selection/extraction settings are valid |
| `E_ASSEMBLY_INPUT_MISSING` | Manifest missing, empty, or points to missing frame files | Regenerate extraction workspace, ensure manifest and frame paths exist |
| `E_ASSEMBLY_FAILED` | `img2pdf` command failed | Verify `img2pdf` installation and manifest entries, rerun after fixing source inputs |
| `E_JOB_INVALID` | Job folder invalid, for example missing options file or missing input MP4 | Keep one options file (`options.txt` or `options.md`), ensure `input_mp4` exists |
| `E_PDF_VALIDATE` | PDF verification failed (`pdfinfo`, `gs`, or page/manifest mismatch) | Recreate output PDF, confirm verify tools are installed, confirm manifest matches selected frames |
| `E_UNEXPECTED` | Unmapped runtime failure | Rerun with the same command, capture stderr, then fix underlying tool or input issue |

## Stale Key Failure Example and Fix

Intentional failure command:

```bash
python3 tools/mp4_to_pdf.py --parse-options fixtures/job_examples/stale_key/options.txt
```

Expected result:

- non-zero exit
- `E_CONFIG_UNKNOWN_KEY: Unknown key 'selector_interval'`

Fix:

Replace stale key `selector_interval` with supported key `selector_every_nth`.

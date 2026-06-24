# MP4 to PDF Library

## OVERVIEW
Pipeline library for MP4 to PDF conversion, 11 modules, orchestrator drives parse -> select -> extract -> assemble -> verify.

## MODULE MAP
| Module | Role | Key Exports |
| --- | --- | --- |
| orchestrator.py | Pipeline coordinator | run_orchestrated_job, run_batch_jobs, verify_existing_job_output, JobInvalidError |
| schema.py | Config validation + constants | schema_lint, SchemaError, E_CONFIG_*, MODE_TO_SELECTOR_KEY, QUALITY_PROFILES, ALLOWED_KEYS, KEY_ALIASES |
| options_parser.py | Options file parsing | parse_options_path |
| selection.py | Frame index computation | select_frame_indices, default_report_path |
| extract.py | ffmpeg frame extraction | extract_frames_with_manifest |
| assemble.py | img2pdf PDF assembly | assemble_manifest_to_pdf |
| verify.py | PDF output validation | verify_pdf_output |
| quality.py | Profile -> ffmpeg args | ffmpeg_args_for_profile, profile_map_payload |
| preflight.py | Dependency checks | run_preflight |
| benchmark.py | Timing harness | run_benchmark_job |
| errors.py | Error mapping | map_error_code, format_mapped_error, error_map_payload |

## DATA FLOW
```text
options.txt/md -> options_parser.parse_options_path() -> config dict
  -> schema validation (ALLOWED_KEYS, mode/selector match)
  -> selection.select_frame_indices() -> frame index list
  -> extract.extract_frames_with_manifest() -> temp frames + manifest
  -> assemble.assemble_manifest_to_pdf() -> output.pdf
  -> verify.verify_pdf_output() -> page count + integrity check
```

## CONVENTIONS
- Options files are key:value text (txt or md), markdown list prefixes stripped, comments via # or //.
- Alias resolution maps shorthand keys (fps, every_nth, etc.) to canonical selector_* keys.
- Exactly one selector key must be active, matching the `mode` value.
- Frame extraction uses ffmpeg subprocess, assembly uses img2pdf.
- Verification uses ghostscript (`gs`) and poppler (`pdfinfo`).
- Temp workspace is created per job, cleaned unless `--keep-temp`.
- Error pattern uses `@dataclass(frozen=True)` exceptions with `.code` + `.message`.
- Error hierarchy: SchemaError -> JobInvalidError -> E_UNEXPECTED.

## ANTI-PATTERNS
- Never set both alias and canonical for same selector (`E_CONFIG_ALIAS_AMBIGUITY`).
- Never enable multiple selector keys (`E_CONFIG_MODE_CONFLICT`).
- Never add keys without updating ALLOWED_KEYS in `schema.py`.
- Never skip verify step after assembly, it catches corrupt or truncated PDFs.

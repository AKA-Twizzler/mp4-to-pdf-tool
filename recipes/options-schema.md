# MP4 to PDF v1 options schema

## Folder contract

Each job uses this exact v1 layout:

`jobs/<job-id>/input.mp4`
`jobs/<job-id>/options.txt` or `jobs/<job-id>/options.md`
`jobs/<job-id>/output.pdf`

## Shared key parsing

`options.txt` and `options.md` both use the same `key: value` format.

Rules:
- Lines with no `:` are ignored.
- Empty lines are ignored.
- Lines starting with `#` or `//` are ignored.
- Markdown list prefixes `- ` and `* ` are stripped before parsing.
- Keys are normalized to lowercase with `_` separators.

## Required keys

Required keys for every job:
- `mode`
- `quality_profile`
- `input_mp4`
- `output_pdf`

## Allowed keys

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

Alias keys map to selector keys:
- `every_frame` -> `selector_every_frame`
- `fps` -> `selector_fps`
- `every_nth` -> `selector_every_nth`
- `keyframes` -> `selector_keyframes`
- `time_range` -> `selector_time_range`

## Error policy

- Unknown key fails with `E_CONFIG_UNKNOWN_KEY`.
- Alias + canonical for the same selector fails with `E_CONFIG_ALIAS_AMBIGUITY`.
- Multiple selectors at once fails with `E_CONFIG_MODE_CONFLICT`.
- `mode` must match the single configured selector or fail with `E_CONFIG_MODE_CONFLICT`.

## Example valid options

```text
mode: fps
quality_profile: jpeg_balanced
input_mp4: jobs/demo/input.mp4
output_pdf: jobs/demo/output.pdf
selector_fps: 2
```

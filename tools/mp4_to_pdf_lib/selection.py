from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Mapping

from mp4_to_pdf_lib.schema import E_CONFIG_MISSING_REQUIRED
from mp4_to_pdf_lib.schema import E_NO_FRAMES_SELECTED
from mp4_to_pdf_lib.schema import SchemaError


@dataclass(frozen=True)
class SelectionResult:
    mode: str
    selected_indices: list[int]
    frame_count: int
    source_fps: str
    duration_seconds: str


def _parse_fraction(value: str, *, field_name: str) -> Fraction:
    raw = value.strip()
    if not raw:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, f"Missing required value for '{field_name}'")
    try:
        number = Fraction(raw)
    except Exception as exc:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, f"Invalid numeric value for '{field_name}': {value}") from exc
    if number <= 0:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, f"'{field_name}' must be > 0")
    return number


def _parse_positive_int(value: str, *, field_name: str) -> int:
    raw = value.strip()
    if not raw:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, f"Missing required value for '{field_name}'")
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, f"Invalid integer for '{field_name}': {value}") from exc
    if parsed <= 0:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, f"'{field_name}' must be > 0")
    return parsed


def _parse_time_range(value: str) -> tuple[Fraction, Fraction]:
    cleaned = value.strip()
    if not cleaned:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, "Missing required value for 'selector_time_range'")

    parts: list[str]
    if "," in cleaned:
        parts = [piece.strip() for piece in cleaned.split(",", 1)]
    elif "-" in cleaned:
        parts = [piece.strip() for piece in cleaned.split("-", 1)]
    else:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, "selector_time_range must look like 'start-end'")

    if len(parts) != 2:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, "selector_time_range must define exactly start and end")

    start = _parse_fraction(parts[0], field_name="selector_time_range.start")
    end = _parse_fraction(parts[1], field_name="selector_time_range.end")
    if end <= start:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, "selector_time_range end must be greater than start")
    return start, end


def _parse_index_list(value: str) -> list[int]:
    cleaned = value.strip()
    if not cleaned:
        return []
    items = [item.strip() for item in cleaned.split(",")]
    indices: list[int] = []
    for item in items:
        if not item:
            continue
        try:
            parsed = int(item)
        except ValueError as exc:
            raise SchemaError(E_CONFIG_MISSING_REQUIRED, f"Invalid keyframe index '{item}'") from exc
        if parsed < 0:
            raise SchemaError(E_CONFIG_MISSING_REQUIRED, "Keyframe indices must be >= 0")
        indices.append(parsed)
    return indices


def _fps_selected_indices(frame_count: int, source_fps: Fraction, target_fps: Fraction) -> list[int]:
    selected: list[int] = []
    previous_bucket: int | None = None

    for index in range(frame_count):
        bucket = (index * source_fps.denominator * target_fps.numerator) // (
            source_fps.numerator * target_fps.denominator
        )
        if previous_bucket is None or bucket != previous_bucket:
            selected.append(index)
            previous_bucket = bucket
    return selected


def _ensure_non_empty(indices: Iterable[int], *, mode: str) -> list[int]:
    values = list(indices)
    if not values:
        raise SchemaError(E_NO_FRAMES_SELECTED, f"mode='{mode}' produced zero selected frames")
    return values


def ffmpeg_preselection_args(config: Mapping[str, str], *, source_fps: str) -> tuple[str, ...]:
    """Return ffmpeg args that can safely preselect frames before extraction.

    The pipeline normally extracts all input frames and then selects from that
    manifest. For long videos, low-rate fps selections are much faster if ffmpeg
    performs the downsampling while decoding. Only return args when the ffmpeg
    filter preserves the same selected-frame semantics.
    """
    mode = str(config.get("mode", "")).strip()
    if mode != "fps":
        return ()

    selector_fps_raw = str(config.get("selector_fps", "")).strip()
    target_fps = _parse_fraction(selector_fps_raw, field_name="selector_fps")
    source_fps_fraction = _parse_fraction(source_fps, field_name="source_fps")
    if target_fps >= source_fps_fraction:
        return ()

    return ("-vf", f"fps={target_fps}")


def select_frame_indices(
    config: Mapping[str, str],
    *,
    frame_count: int,
    source_fps: str,
    duration_seconds: str | None = None,
    keyframe_indices_override: str | None = None,
) -> SelectionResult:
    if frame_count <= 0:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, "frame_count must be > 0")

    mode = str(config.get("mode", "")).strip()
    if not mode:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, "Missing required value for 'mode'")

    source_fps_fraction = _parse_fraction(source_fps, field_name="source_fps")
    duration_fraction = (
        _parse_fraction(duration_seconds, field_name="duration_seconds")
        if duration_seconds is not None
        else Fraction(frame_count, 1) / source_fps_fraction
    )

    selected: list[int]
    if mode == "every_frame":
        selected = list(range(frame_count))
    elif mode == "every_nth":
        every_nth_raw = str(config.get("selector_every_nth", "")).strip()
        every_nth = _parse_positive_int(every_nth_raw, field_name="selector_every_nth")
        selected = [index for index in range(frame_count) if index % every_nth == 0]
    elif mode == "fps":
        selector_fps_raw = str(config.get("selector_fps", "")).strip()
        target_fps = _parse_fraction(selector_fps_raw, field_name="selector_fps")
        selected = _fps_selected_indices(frame_count, source_fps_fraction, target_fps)
    elif mode == "keyframes":
        keyframe_value = keyframe_indices_override
        if keyframe_value is None:
            keyframe_value = str(config.get("selector_keyframes", "")).strip()
        if not keyframe_value:
            raise SchemaError(
                E_CONFIG_MISSING_REQUIRED,
                "mode='keyframes' requires --selection-keyframe-indices or selector_keyframes",
            )
        selected = sorted({index for index in _parse_index_list(keyframe_value) if index < frame_count})
    elif mode == "time_range":
        raw_range = str(config.get("selector_time_range", "")).strip()
        start, end = _parse_time_range(raw_range)
        selected = [
            index
            for index in range(frame_count)
            if start <= Fraction(index * source_fps_fraction.denominator, source_fps_fraction.numerator) < end
        ]
    else:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, f"Unsupported mode '{mode}'")

    selected = _ensure_non_empty(selected, mode=mode)
    return SelectionResult(
        mode=mode,
        selected_indices=selected,
        frame_count=frame_count,
        source_fps=str(source_fps_fraction),
        duration_seconds=str(duration_fraction),
    )


def default_report_path(output_pdf: str) -> Path:
    output_path = Path(output_pdf)
    return output_path.with_suffix(output_path.suffix + ".run_report.json")

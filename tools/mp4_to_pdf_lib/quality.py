from __future__ import annotations

from typing import Dict, Mapping

from mp4_to_pdf_lib.schema import E_CONFIG_BAD_QUALITY_PROFILE
from mp4_to_pdf_lib.schema import SchemaError


DEFAULT_QUALITY_PROFILE = "jpeg_balanced"

QUALITY_PROFILE_TO_FFMPEG_ARGS: Mapping[str, tuple[str, ...]] = {
    "jpeg_fast": ("-c:v", "mjpeg", "-q:v", "3"),
    "jpeg_balanced": ("-c:v", "mjpeg", "-q:v", "5"),
    "jpeg_small": ("-c:v", "mjpeg", "-q:v", "8"),
    "png_lossless": ("-c:v", "png", "-pix_fmt", "rgb24"),
}


def resolve_quality_profile(profile: str | None) -> str:
    candidate = (profile or "").strip()
    if not candidate:
        return DEFAULT_QUALITY_PROFILE
    if candidate not in QUALITY_PROFILE_TO_FFMPEG_ARGS:
        raise SchemaError(E_CONFIG_BAD_QUALITY_PROFILE, f"Unsupported quality profile '{candidate}'")
    return candidate


def ffmpeg_args_for_profile(profile: str | None) -> tuple[str, ...]:
    resolved = resolve_quality_profile(profile)
    return QUALITY_PROFILE_TO_FFMPEG_ARGS[resolved]


def profile_map_payload(profile: str | None = None) -> Dict[str, object]:
    resolved = resolve_quality_profile(profile)
    return {
        "default_profile": DEFAULT_QUALITY_PROFILE,
        "requested_profile": profile,
        "resolved_profile": resolved,
        "profile_ffmpeg_args": {
            key: list(value)
            for key, value in QUALITY_PROFILE_TO_FFMPEG_ARGS.items()
        },
        "resolved_ffmpeg_args": list(ffmpeg_args_for_profile(profile)),
    }

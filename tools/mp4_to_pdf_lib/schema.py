from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping


E_CONFIG_UNKNOWN_KEY = "E_CONFIG_UNKNOWN_KEY"
E_CONFIG_ALIAS_AMBIGUITY = "E_CONFIG_ALIAS_AMBIGUITY"
E_CONFIG_MODE_CONFLICT = "E_CONFIG_MODE_CONFLICT"
E_CONFIG_MISSING_REQUIRED = "E_CONFIG_MISSING_REQUIRED"
E_CONFIG_DUPLICATE_KEY = "E_CONFIG_DUPLICATE_KEY"
E_CONFIG_BAD_MODE = "E_CONFIG_BAD_MODE"
E_CONFIG_BAD_QUALITY_PROFILE = "E_CONFIG_BAD_QUALITY_PROFILE"
E_CONFIG_BAD_INPUT_FORMAT = "E_CONFIG_BAD_INPUT_FORMAT"
E_CONFIG_INVALID_BENCHMARK_RUNS = "E_CONFIG_INVALID_BENCHMARK_RUNS"
E_NO_FRAMES_SELECTED = "E_NO_FRAMES_SELECTED"

V1_JOB_ROOT_TEMPLATE = "jobs/<job-id>"
V1_INPUT_TEMPLATE = "jobs/<job-id>/input.mp4"
V1_OPTIONS_TEMPLATE = "jobs/<job-id>/options.(txt|md)"
V1_OUTPUT_TEMPLATE = "jobs/<job-id>/output.pdf"

MODE_TO_SELECTOR_KEY = {
    "every_frame": "selector_every_frame",
    "fps": "selector_fps",
    "every_nth": "selector_every_nth",
    "keyframes": "selector_keyframes",
    "time_range": "selector_time_range",
}

QUALITY_PROFILES = (
    "jpeg_fast",
    "jpeg_balanced",
    "jpeg_small",
    "png_lossless",
)

REQUIRED_KEYS = (
    "mode",
    "quality_profile",
    "input_mp4",
    "output_pdf",
)

OPTIONAL_KEYS = tuple(MODE_TO_SELECTOR_KEY.values())
ALLOWED_KEYS = REQUIRED_KEYS + OPTIONAL_KEYS

KEY_ALIASES = {
    "every_frame": "selector_every_frame",
    "fps": "selector_fps",
    "every_nth": "selector_every_nth",
    "keyframes": "selector_keyframes",
    "time_range": "selector_time_range",
}


@dataclass(frozen=True)
class SchemaError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _normalize_key(raw_key: str) -> str:
    return raw_key.strip().lower().replace("-", "_")


def _is_enabled(value: str) -> bool:
    return value.strip().lower() not in {"", "0", "false", "no", "off", "none", "null"}


def parse_key_value_text(text: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    source_key_by_canonical: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("//"):
            continue
        if line.startswith("- ") or line.startswith("* "):
            line = line[2:].strip()
        if ":" not in line:
            continue

        raw_key, raw_value = line.split(":", 1)
        key = _normalize_key(raw_key)
        value = raw_value.strip()
        canonical_key = KEY_ALIASES.get(key, key)

        if key not in ALLOWED_KEYS and key not in KEY_ALIASES:
            raise SchemaError(E_CONFIG_UNKNOWN_KEY, f"Unknown key '{key}'")

        if canonical_key in source_key_by_canonical:
            previous_source = source_key_by_canonical[canonical_key]
            if previous_source != key:
                raise SchemaError(
                    E_CONFIG_ALIAS_AMBIGUITY,
                    f"Alias ambiguity for '{canonical_key}' via '{previous_source}' and '{key}'",
                )
            raise SchemaError(E_CONFIG_DUPLICATE_KEY, f"Duplicate key '{key}'")

        source_key_by_canonical[canonical_key] = key
        parsed[canonical_key] = value

    validate_config(parsed)
    return parsed


def validate_config(config: Mapping[str, str]) -> None:
    missing = [key for key in REQUIRED_KEYS if key not in config or not str(config[key]).strip()]
    if missing:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, f"Missing required keys: {', '.join(missing)}")

    mode = str(config["mode"]).strip()
    if mode not in MODE_TO_SELECTOR_KEY:
        raise SchemaError(E_CONFIG_BAD_MODE, f"Unsupported mode '{mode}'")

    quality_profile = str(config["quality_profile"]).strip()
    if quality_profile not in QUALITY_PROFILES:
        raise SchemaError(E_CONFIG_BAD_QUALITY_PROFILE, f"Unsupported quality profile '{quality_profile}'")

    selector_keys_present = [
        key
        for key in MODE_TO_SELECTOR_KEY.values()
        if key in config and _is_enabled(str(config[key]))
    ]
    if len(selector_keys_present) > 1:
        raise SchemaError(
            E_CONFIG_MODE_CONFLICT,
            f"Multiple selectors set: {', '.join(selector_keys_present)}",
        )

    if len(selector_keys_present) == 1:
        expected_selector = MODE_TO_SELECTOR_KEY[mode]
        if selector_keys_present[0] != expected_selector:
            raise SchemaError(
                E_CONFIG_MODE_CONFLICT,
                f"mode='{mode}' conflicts with selector '{selector_keys_present[0]}'",
            )


def load_options_file(path: Path) -> Dict[str, str]:
    if path.suffix.lower() not in {".txt", ".md"}:
        raise SchemaError(E_CONFIG_UNKNOWN_KEY, "Options file must use .txt or .md")
    return parse_key_value_text(path.read_text(encoding="utf-8"))


def schema_payload() -> Dict[str, object]:
    return {
        "contract": {
            "job_root": V1_JOB_ROOT_TEMPLATE,
            "input_mp4": V1_INPUT_TEMPLATE,
            "options": V1_OPTIONS_TEMPLATE,
            "output_pdf": V1_OUTPUT_TEMPLATE,
        },
        "required_keys": list(REQUIRED_KEYS),
        "allowed_keys": list(ALLOWED_KEYS),
        "key_aliases": dict(KEY_ALIASES),
        "modes": list(MODE_TO_SELECTOR_KEY.keys()),
        "mode_selector_map": dict(MODE_TO_SELECTOR_KEY),
        "quality_profiles": list(QUALITY_PROFILES),
        "conflict_policy": {
            "mixed_selector_error": E_CONFIG_MODE_CONFLICT,
            "unknown_key_error": E_CONFIG_UNKNOWN_KEY,
            "alias_ambiguity_error": E_CONFIG_ALIAS_AMBIGUITY,
            "duplicate_key_error": E_CONFIG_DUPLICATE_KEY,
            "duplicate_key_rule": "reject duplicates deterministically",
        },
    }


def schema_lint() -> Iterable[str]:
    errors = []
    if any(key not in ALLOWED_KEYS for key in REQUIRED_KEYS):
        errors.append("required keys must be part of allowed keys")
    if set(KEY_ALIASES.values()) - set(ALLOWED_KEYS):
        errors.append("all alias targets must be allowed keys")
    if set(MODE_TO_SELECTOR_KEY.values()) - set(ALLOWED_KEYS):
        errors.append("all mode selectors must be allowed keys")
    if "mode" not in REQUIRED_KEYS:
        errors.append("required key 'mode' is missing")
    if "quality_profile" not in REQUIRED_KEYS:
        errors.append("required key 'quality_profile' is missing")
    if "input_mp4" not in REQUIRED_KEYS:
        errors.append("required key 'input_mp4' is missing")
    if "output_pdf" not in REQUIRED_KEYS:
        errors.append("required key 'output_pdf' is missing")
    if len(set(MODE_TO_SELECTOR_KEY.values())) != len(MODE_TO_SELECTOR_KEY):
        errors.append("selector targets must be unique")
    return errors

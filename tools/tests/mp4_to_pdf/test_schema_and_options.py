from __future__ import annotations

import pytest

from mp4_to_pdf_lib.schema import (
    E_CONFIG_ALIAS_AMBIGUITY,
    E_CONFIG_BAD_MODE,
    E_CONFIG_BAD_QUALITY_PROFILE,
    E_CONFIG_DUPLICATE_KEY,
    E_CONFIG_MISSING_REQUIRED,
    E_CONFIG_MODE_CONFLICT,
    E_CONFIG_UNKNOWN_KEY,
    SchemaError,
    parse_key_value_text,
    schema_lint,
    validate_config,
)


# ---------------------------------------------------------------------------
# schema_lint
# ---------------------------------------------------------------------------


def test_schema_lint_passes() -> None:
    errors = list(schema_lint())
    assert errors == []


# ---------------------------------------------------------------------------
# parse_key_value_text — valid inputs
# ---------------------------------------------------------------------------


def test_parse_minimal_fps_config() -> None:
    text = (
        "mode: fps\n"
        "quality_profile: jpeg_balanced\n"
        "input_mp4: jobs/test/input.mp4\n"
        "output_pdf: jobs/test/output.pdf\n"
        "selector_fps: 2\n"
    )
    config = parse_key_value_text(text)
    assert config["mode"] == "fps"
    assert config["quality_profile"] == "jpeg_balanced"
    assert config["selector_fps"] == "2"


def test_parse_alias_fps_resolves_to_canonical() -> None:
    text = (
        "mode: fps\n"
        "quality_profile: jpeg_balanced\n"
        "input_mp4: jobs/test/input.mp4\n"
        "output_pdf: jobs/test/output.pdf\n"
        "fps: 3\n"  # alias for selector_fps
    )
    config = parse_key_value_text(text)
    assert "selector_fps" in config
    assert config["selector_fps"] == "3"
    assert "fps" not in config


def test_parse_skips_comments_and_blank_lines() -> None:
    text = (
        "# this is a comment\n"
        "// another comment\n"
        "\n"
        "mode: every_frame\n"
        "quality_profile: png_lossless\n"
        "input_mp4: jobs/test/input.mp4\n"
        "output_pdf: jobs/test/output.pdf\n"
        "selector_every_frame: true\n"
    )
    config = parse_key_value_text(text)
    assert config["mode"] == "every_frame"


def test_parse_strips_markdown_list_prefix() -> None:
    text = (
        "- mode: every_nth\n"
        "* quality_profile: jpeg_fast\n"
        "- input_mp4: jobs/test/input.mp4\n"
        "- output_pdf: jobs/test/output.pdf\n"
        "- selector_every_nth: 5\n"
    )
    config = parse_key_value_text(text)
    assert config["mode"] == "every_nth"
    assert config["selector_every_nth"] == "5"


def test_parse_ignores_lines_without_colon() -> None:
    text = (
        "this line has no colon\n"
        "mode: fps\n"
        "quality_profile: jpeg_balanced\n"
        "input_mp4: jobs/test/input.mp4\n"
        "output_pdf: jobs/test/output.pdf\n"
        "selector_fps: 1\n"
    )
    config = parse_key_value_text(text)
    assert config["mode"] == "fps"


# ---------------------------------------------------------------------------
# parse_key_value_text — error cases
# ---------------------------------------------------------------------------


def test_unknown_key_raises_error_code() -> None:
    text = (
        "mode: fps\n"
        "quality_profile: jpeg_balanced\n"
        "input_mp4: jobs/test/input.mp4\n"
        "output_pdf: jobs/test/output.pdf\n"
        "selector_fps: 2\n"
        "selector_interval: 5\n"  # unknown key
    )
    with pytest.raises(SchemaError) as exc_info:
        parse_key_value_text(text)
    assert exc_info.value.code == E_CONFIG_UNKNOWN_KEY


def test_alias_ambiguity_raises_error_code() -> None:
    # Both alias 'fps' and canonical 'selector_fps' set
    text = (
        "mode: fps\n"
        "quality_profile: jpeg_balanced\n"
        "input_mp4: jobs/test/input.mp4\n"
        "output_pdf: jobs/test/output.pdf\n"
        "fps: 2\n"
        "selector_fps: 3\n"
    )
    with pytest.raises(SchemaError) as exc_info:
        parse_key_value_text(text)
    assert exc_info.value.code == E_CONFIG_ALIAS_AMBIGUITY


def test_duplicate_key_raises_error_code() -> None:
    text = (
        "mode: fps\n"
        "quality_profile: jpeg_balanced\n"
        "input_mp4: jobs/test/input.mp4\n"
        "output_pdf: jobs/test/output.pdf\n"
        "selector_fps: 2\n"
        "selector_fps: 3\n"  # duplicate
    )
    with pytest.raises(SchemaError) as exc_info:
        parse_key_value_text(text)
    assert exc_info.value.code == E_CONFIG_DUPLICATE_KEY


# ---------------------------------------------------------------------------
# validate_config — error cases
# ---------------------------------------------------------------------------


def test_missing_required_key_raises_error_code() -> None:
    config = {
        "mode": "fps",
        # quality_profile missing
        "input_mp4": "jobs/test/input.mp4",
        "output_pdf": "jobs/test/output.pdf",
    }
    with pytest.raises(SchemaError) as exc_info:
        validate_config(config)
    assert exc_info.value.code == E_CONFIG_MISSING_REQUIRED


def test_bad_mode_raises_error_code() -> None:
    config = {
        "mode": "unsupported_mode",
        "quality_profile": "jpeg_balanced",
        "input_mp4": "jobs/test/input.mp4",
        "output_pdf": "jobs/test/output.pdf",
    }
    with pytest.raises(SchemaError) as exc_info:
        validate_config(config)
    assert exc_info.value.code == E_CONFIG_BAD_MODE


def test_bad_quality_profile_raises_error_code() -> None:
    config = {
        "mode": "fps",
        "quality_profile": "super_hd",
        "input_mp4": "jobs/test/input.mp4",
        "output_pdf": "jobs/test/output.pdf",
    }
    with pytest.raises(SchemaError) as exc_info:
        validate_config(config)
    assert exc_info.value.code == E_CONFIG_BAD_QUALITY_PROFILE


def test_mode_selector_mismatch_raises_mode_conflict() -> None:
    # mode=fps but selector_every_nth is set
    config = {
        "mode": "fps",
        "quality_profile": "jpeg_balanced",
        "input_mp4": "jobs/test/input.mp4",
        "output_pdf": "jobs/test/output.pdf",
        "selector_every_nth": "5",
    }
    with pytest.raises(SchemaError) as exc_info:
        validate_config(config)
    assert exc_info.value.code == E_CONFIG_MODE_CONFLICT


def test_multiple_selectors_raises_mode_conflict() -> None:
    config = {
        "mode": "fps",
        "quality_profile": "jpeg_balanced",
        "input_mp4": "jobs/test/input.mp4",
        "output_pdf": "jobs/test/output.pdf",
        "selector_fps": "2",
        "selector_every_nth": "5",
    }
    with pytest.raises(SchemaError) as exc_info:
        validate_config(config)
    assert exc_info.value.code == E_CONFIG_MODE_CONFLICT


# ---------------------------------------------------------------------------
# Fixture-based: load known bad options files
# ---------------------------------------------------------------------------


def test_stale_key_fixture_raises_unknown_key(tmp_path: pytest.TempPathFactory) -> None:
    from conftest import job_examples_root
    from mp4_to_pdf_lib.options_parser import parse_options_path

    stale_key_options = job_examples_root() / "stale_key" / "options.txt"
    assert stale_key_options.exists(), f"Fixture missing: {stale_key_options}"
    with pytest.raises(SchemaError) as exc_info:
        parse_options_path(stale_key_options)
    assert exc_info.value.code == E_CONFIG_UNKNOWN_KEY


def test_conflict_selectors_fixture_raises_mode_conflict() -> None:
    from conftest import fixtures_root
    from mp4_to_pdf_lib.options_parser import parse_options_path

    conflict_options = fixtures_root() / "job_conflict_selectors" / "options.txt"
    assert conflict_options.exists(), f"Fixture missing: {conflict_options}"
    with pytest.raises(SchemaError) as exc_info:
        parse_options_path(conflict_options)
    assert exc_info.value.code == E_CONFIG_MODE_CONFLICT

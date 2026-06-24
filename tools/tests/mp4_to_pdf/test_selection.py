from __future__ import annotations

import pytest

from mp4_to_pdf_lib.schema import E_CONFIG_MISSING_REQUIRED, E_NO_FRAMES_SELECTED, SchemaError
from mp4_to_pdf_lib.selection import ffmpeg_preselection_args, select_frame_indices


def _base_config(**overrides: str) -> dict[str, str]:
    base = {
        "mode": "every_frame",
        "quality_profile": "jpeg_balanced",
        "input_mp4": "jobs/test/input.mp4",
        "output_pdf": "jobs/test/output.pdf",
        "selector_every_frame": "true",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# every_frame mode
# ---------------------------------------------------------------------------


def test_every_frame_selects_all_frames() -> None:
    config = _base_config(mode="every_frame", selector_every_frame="true")
    result = select_frame_indices(config, frame_count=10, source_fps="30")
    assert result.selected_indices == list(range(10))
    assert result.frame_count == 10
    assert result.mode == "every_frame"


# ---------------------------------------------------------------------------
# every_nth mode
# ---------------------------------------------------------------------------


def test_every_nth_selects_correct_indices() -> None:
    config = _base_config(mode="every_nth", selector_every_nth="3")
    del config["selector_every_frame"]
    result = select_frame_indices(config, frame_count=10, source_fps="30")
    assert result.selected_indices == [0, 3, 6, 9]


def test_every_nth_one_selects_all() -> None:
    config = _base_config(mode="every_nth", selector_every_nth="1")
    del config["selector_every_frame"]
    result = select_frame_indices(config, frame_count=5, source_fps="30")
    assert result.selected_indices == [0, 1, 2, 3, 4]


def test_every_nth_larger_than_frame_count_selects_first_only() -> None:
    config = _base_config(mode="every_nth", selector_every_nth="100")
    del config["selector_every_frame"]
    result = select_frame_indices(config, frame_count=5, source_fps="30")
    assert result.selected_indices == [0]


# ---------------------------------------------------------------------------
# fps mode
# ---------------------------------------------------------------------------


def test_fps_mode_selects_at_target_rate() -> None:
    # 30fps source, target 1fps, 30 frames → ~1 frame selected
    config = _base_config(mode="fps", selector_fps="1")
    del config["selector_every_frame"]
    result = select_frame_indices(config, frame_count=30, source_fps="30")
    assert len(result.selected_indices) >= 1


def test_fps_mode_target_higher_than_source_selects_all() -> None:
    # 10fps source, target 30fps (higher) → all 10 frames
    config = _base_config(mode="fps", selector_fps="30")
    del config["selector_every_frame"]
    result = select_frame_indices(config, frame_count=10, source_fps="10")
    assert result.selected_indices == list(range(10))


def test_fps_mode_lower_than_source_can_preselect_in_ffmpeg() -> None:
    config = _base_config(mode="fps", selector_fps="1/5")
    del config["selector_every_frame"]
    assert ffmpeg_preselection_args(config, source_fps="25") == ("-vf", "fps=1/5")


def test_fps_mode_higher_than_source_does_not_preselect_in_ffmpeg() -> None:
    config = _base_config(mode="fps", selector_fps="30")
    del config["selector_every_frame"]
    assert ffmpeg_preselection_args(config, source_fps="10") == ()


def test_every_frame_mode_does_not_preselect_in_ffmpeg() -> None:
    config = _base_config(mode="every_frame", selector_every_frame="true")
    assert ffmpeg_preselection_args(config, source_fps="25") == ()


# ---------------------------------------------------------------------------
# time_range mode
# ---------------------------------------------------------------------------


def test_time_range_selects_frames_in_window() -> None:
    # 10fps source, 20 frames = 2 seconds total, select 0.5-1.5s
    config = _base_config(mode="time_range", selector_time_range="0.5-1.5")
    del config["selector_every_frame"]
    result = select_frame_indices(
        config, frame_count=20, source_fps="10", duration_seconds="2"
    )
    # frames in 0.5-1.5s at 10fps → indices 5-14
    assert len(result.selected_indices) > 0
    assert all(5 <= idx <= 15 for idx in result.selected_indices)


def test_time_range_comma_separator() -> None:
    config = _base_config(mode="time_range", selector_time_range="0.5,1.5")
    del config["selector_every_frame"]
    result = select_frame_indices(
        config, frame_count=20, source_fps="10", duration_seconds="2"
    )
    assert len(result.selected_indices) > 0


# ---------------------------------------------------------------------------
# keyframes mode
# ---------------------------------------------------------------------------


def test_keyframes_mode_with_index_override() -> None:
    config = _base_config(mode="keyframes", selector_keyframes="")
    del config["selector_every_frame"]
    result = select_frame_indices(
        config,
        frame_count=10,
        source_fps="30",
        keyframe_indices_override="0,3,7",
    )
    assert result.selected_indices == [0, 3, 7]


def test_keyframes_filters_out_of_range_indices() -> None:
    config = _base_config(mode="keyframes", selector_keyframes="")
    del config["selector_every_frame"]
    result = select_frame_indices(
        config,
        frame_count=5,
        source_fps="30",
        keyframe_indices_override="0,3,99",  # 99 is out of range
    )
    assert 99 not in result.selected_indices
    assert 0 in result.selected_indices
    assert 3 in result.selected_indices


# ---------------------------------------------------------------------------
# error cases
# ---------------------------------------------------------------------------


def test_zero_frame_count_raises_missing_required() -> None:
    config = _base_config()
    with pytest.raises(SchemaError) as exc_info:
        select_frame_indices(config, frame_count=0, source_fps="30")
    assert exc_info.value.code == E_CONFIG_MISSING_REQUIRED


def test_keyframes_missing_value_raises_missing_required() -> None:
    config = _base_config(mode="keyframes", selector_keyframes="")
    del config["selector_every_frame"]
    with pytest.raises(SchemaError) as exc_info:
        select_frame_indices(config, frame_count=10, source_fps="30")
    assert exc_info.value.code == E_CONFIG_MISSING_REQUIRED


def test_fps_missing_selector_value_raises_missing_required() -> None:
    config = _base_config(mode="fps", selector_fps="")
    del config["selector_every_frame"]
    with pytest.raises(SchemaError) as exc_info:
        select_frame_indices(config, frame_count=10, source_fps="30")
    assert exc_info.value.code == E_CONFIG_MISSING_REQUIRED

from __future__ import annotations

from pathlib import Path
from typing import Dict

from mp4_to_pdf_lib.schema import E_CONFIG_UNKNOWN_KEY
from mp4_to_pdf_lib.schema import SchemaError
from mp4_to_pdf_lib.schema import parse_key_value_text


SUPPORTED_EXTENSIONS = {".txt", ".md"}


def parse_options_text(text: str) -> Dict[str, str]:
    return parse_key_value_text(text)


def parse_options_path(path: Path) -> Dict[str, str]:
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise SchemaError(E_CONFIG_UNKNOWN_KEY, "Options file must use .txt or .md")
    return parse_options_text(path.read_text(encoding="utf-8"))

from __future__ import annotations

from typing import Mapping


E_PDF_VALIDATE = "E_PDF_VALIDATE"
E_UNEXPECTED = "E_UNEXPECTED"
_USE_EXCEPTION_CODE = "__USE_EXCEPTION_CODE__"

ERROR_CODE_MAP: Mapping[str, str] = {
    "SchemaError": _USE_EXCEPTION_CODE,
    "PreflightError": _USE_EXCEPTION_CODE,
    "ExtractionError": _USE_EXCEPTION_CODE,
    "AssemblyError": _USE_EXCEPTION_CODE,
    "JobInvalidError": _USE_EXCEPTION_CODE,
    "VerificationError": _USE_EXCEPTION_CODE,
}


def error_map_payload() -> dict[str, object]:
    return {
        "declared_failure_classes": sorted(ERROR_CODE_MAP.keys()),
        "error_code_map": dict(ERROR_CODE_MAP),
        "fallback_error_code": E_UNEXPECTED,
    }


def map_error_code(error: BaseException) -> str:
    class_name = error.__class__.__name__
    mapped = ERROR_CODE_MAP.get(class_name)
    if mapped == _USE_EXCEPTION_CODE:
        code = getattr(error, "code", "")
        if isinstance(code, str) and code.strip():
            return code.strip()
    elif isinstance(mapped, str) and mapped.strip():
        return mapped.strip()

    fallback_code = getattr(error, "code", "")
    if isinstance(fallback_code, str) and fallback_code.strip():
        return fallback_code.strip()
    return E_UNEXPECTED


def error_message(error: BaseException) -> str:
    message = getattr(error, "message", "")
    if isinstance(message, str) and message.strip():
        return message.strip()
    rendered = str(error).strip()
    if rendered:
        return rendered
    return error.__class__.__name__


def format_mapped_error(error: BaseException) -> str:
    code = map_error_code(error)
    rendered = str(error).strip()
    if rendered.startswith(f"{code}:"):
        return rendered
    return f"{code}: {error_message(error)}"

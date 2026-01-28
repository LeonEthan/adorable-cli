from __future__ import annotations

from adorable_cli.ui import interactive


def test_looks_like_mcp_jsonrpc_error_direct_message() -> None:
    exc = RuntimeError("Failed to parse JSONRPC message from server")
    assert interactive._looks_like_mcp_jsonrpc_error(exc) is True  # noqa: SLF001


def test_looks_like_mcp_jsonrpc_error_nested() -> None:
    inner = ValueError(
        "Invalid JSON: EOF while parsing a value at line 1 column 0 "
        "[type=json_invalid, input_value='', input_type=str] "
        "JSONRPCMessage"
    )
    outer = RuntimeError("wrapped")
    outer.__cause__ = inner
    assert interactive._looks_like_mcp_jsonrpc_error(outer) is True  # noqa: SLF001


def test_looks_like_mcp_jsonrpc_error_negative() -> None:
    exc = RuntimeError("something else")
    assert interactive._looks_like_mcp_jsonrpc_error(exc) is False  # noqa: SLF001

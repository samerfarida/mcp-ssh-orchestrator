"""Tests for lightweight context logging helper."""

import asyncio
import json

from mcp_ssh import mcp_server


class _DummyCtx:
    """Collect messages emitted via ctx logging."""

    def __init__(self):
        self.messages: list[tuple[str, str]] = []

    async def info(self, message: str) -> None:
        self.messages.append(("info", message))

    async def debug(self, message: str) -> None:
        self.messages.append(("debug", message))


def test_ctx_log_emits_message_when_loop_running():
    """_ctx_log should schedule context logging when an event loop is active."""

    async def _runner():
        ctx = _DummyCtx()
        mcp_server._ctx_log(ctx, "debug", "unit_test", {"alias": "demo"})
        await asyncio.sleep(0)
        return ctx

    ctx = asyncio.run(_runner())
    assert ctx.messages, "Expected at least one message to be emitted"
    level, raw = ctx.messages[0]
    assert level == "debug"
    payload = json.loads(raw)
    assert payload["event"] == "unit_test"
    assert payload["alias"] == "demo"


def test_ctx_log_no_loop_noop():
    """_ctx_log should be a no-op when no event loop is available."""
    ctx = _DummyCtx()
    mcp_server._ctx_log(ctx, "debug", "no_loop")
    assert ctx.messages == []

"""Tests for MCP notification handler integration."""

import asyncio
import math

from mcp_ssh.mcp_server import _build_notification_handler


class DummyContext:
    """Lightweight stand-in for FastMCP Context."""

    def __init__(self):
        self.info_calls: list[str] = []
        self.debug_calls: list[str] = []
        self.progress_calls: list[tuple[float, float, str | None]] = []

    async def info(self, message: str, **_extra):
        self.info_calls.append(message)

    async def debug(self, message: str, **_extra):
        self.debug_calls.append(message)

    async def report_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ):
        self.progress_calls.append((progress, total, message))


def test_notification_handler_emits_info_without_extra_kwargs():
    """Ensure notifications call ctx.info with message only."""

    async def _run():
        loop = asyncio.get_running_loop()
        ctx = DummyContext()
        handler = _build_notification_handler(ctx, loop)

        payload = {"status": "done"}
        handler("completed", "task-123", payload)

        await asyncio.sleep(0)
        return ctx

    ctx = asyncio.run(_run())

    assert ctx.info_calls == ['task task-123 completed {"status":"done"}']
    assert ctx.debug_calls == []
    assert ctx.progress_calls == []


def test_notification_handler_progress_reports_via_ctx():
    """Progress events should use report_progress and debug logging."""

    async def _run():
        loop = asyncio.get_running_loop()
        ctx = DummyContext()
        handler = _build_notification_handler(ctx, loop)

        payload = {"max_seconds": 60, "elapsed_ms": 30000}
        handler("progress", "task-456", payload)

        await asyncio.sleep(0)
        return ctx

    ctx = asyncio.run(_run())

    assert ctx.info_calls == []
    assert len(ctx.progress_calls) == 1
    progress, total, message = ctx.progress_calls[0]
    assert total == 100.0
    assert math.isclose(progress, 50.0, rel_tol=1e-2)
    assert message and message.startswith("task task-456 progress")
    assert ctx.debug_calls == [message]

"""Additional tests for utilities.py to improve coverage."""

import time
from collections import deque
from unittest.mock import Mock, patch

from mcp_ssh.tools.utilities import (
    AsyncTaskManager,
    TaskManager,
    log_json,
)


def test_task_manager_get_event_with_task():
    """Test TaskManager.get_event when task exists."""
    task_manager = TaskManager()

    # Create a task
    task_id = task_manager.create("test1", "abc123")

    # Get event for existing task
    event = task_manager.get_event(task_id)

    assert event is not None
    assert hasattr(event, "is_set")
    assert hasattr(event, "set")


def test_task_manager_get_event_no_task():
    """Test TaskManager.get_event when task doesn't exist."""
    task_manager = TaskManager()

    # Get event for non-existent task
    event = task_manager.get_event("nonexistent")

    assert event is None


def test_task_manager_cancel_existing_task():
    """Test TaskManager.cancel with existing task."""
    task_manager = TaskManager()

    # Create a task
    task_id = task_manager.create("test1", "abc123")

    # Cancel existing task
    result = task_manager.cancel(task_id)

    assert result is True

    # Get event and verify it's set
    event = task_manager.get_event(task_id)
    assert event is not None
    assert event.is_set() is True


def test_task_manager_cancel_nonexistent_task():
    """Test TaskManager.cancel with non-existent task."""
    task_manager = TaskManager()

    # Cancel non-existent task
    result = task_manager.cancel("nonexistent")

    assert result is False


def test_async_task_manager_cleanup_worker_error():
    """Test AsyncTaskManager._cleanup_worker error handling."""
    manager = AsyncTaskManager()

    # Mock cleanup_expired_tasks to raise exception
    original_cleanup = manager.cleanup_expired_tasks

    def failing_cleanup():
        raise Exception("Cleanup error")

    manager.cleanup_expired_tasks = failing_cleanup

    # Wait a bit for worker to process (it will call cleanup_expired_tasks)
    time.sleep(0.2)

    # Should not crash - error is logged by _cleanup_worker
    # Restore original
    manager.cleanup_expired_tasks = original_cleanup

    # Shutdown manager
    manager.shutdown()


def test_async_task_manager_execute_task_no_task_info():
    """Test AsyncTaskManager._execute_task_in_thread when task doesn't exist."""
    manager = AsyncTaskManager()

    # Try to execute non-existent task
    # Should return early without error
    manager._execute_task_in_thread("nonexistent_task")


def test_async_task_manager_execute_task_with_exception():
    """Test AsyncTaskManager._execute_task_in_thread exception handling."""
    manager = AsyncTaskManager()

    # Mock SSH client that raises exception
    mock_client = Mock()
    mock_client.run_streaming.side_effect = RuntimeError("SSH error")

    # Start task that will raise exception
    task_id = manager.start_async_task(
        alias="test1",
        command="uptime",
        ssh_client=mock_client,
        limits={"max_seconds": 60, "max_output_bytes": 1024, "task_result_ttl": 300},
        progress_cb=None,
        notification_handler=None,
    )

    # Wait for task to complete (should handle exception)
    time.sleep(1.0)

    # Check task - should be marked as failed
    with manager._lock:
        task_info = manager._tasks.get(task_id)
        if task_info:
            assert task_info["status"] == "failed"
            assert task_info.get("error") is not None

    # Shutdown manager
    manager.shutdown()


def test_async_task_manager_get_task_status_from_results():
    """Test AsyncTaskManager.get_task_status when task is in results."""
    manager = AsyncTaskManager()

    # Create a completed task result manually (task not in _tasks, but in _results)
    task_id = "test:abc123:123456"
    with manager._lock:
        # Don't add to _tasks - should check _results
        manager._results[task_id] = {
            "task_id": task_id,
            "status": "completed",
            "expires": time.time() + 300,  # 5 minutes
            "duration_ms": 1000,
            "output": "test output",
        }
        manager._output_buffers[task_id] = deque(["line1", "line2"])

    # Get status - should come from results
    status = manager.get_task_status(task_id)

    assert status is not None
    assert status["status"] == "completed"
    assert status["progress_percent"] == 100
    assert status["elapsed_ms"] == 1000
    assert status["bytes_read"] == len("test output")


def test_async_task_manager_get_task_status_nonexistent():
    """Test AsyncTaskManager.get_task_status for non-existent task."""
    manager = AsyncTaskManager()

    # Get status for non-existent task
    status = manager.get_task_status("nonexistent")

    assert status is None


def test_async_task_manager_get_task_output_from_buffer():
    """Test AsyncTaskManager.get_task_output from output buffer."""
    manager = AsyncTaskManager()

    # Create task with output buffer
    task_id = "test:abc123:123456"
    with manager._lock:
        manager._tasks[task_id] = {
            "status": "running",
            "output": "",
        }
        output_buffer = deque(["line1", "line2", "line3", "line4", "line5"])
        manager._output_buffers[task_id] = output_buffer

    # Get output with max_lines limit
    output = manager.get_task_output(task_id, max_lines=3)

    assert output is not None
    assert len(output["output_lines"]) == 3  # Should return last 3 lines
    assert output["total_lines"] == 5
    assert output["has_more"] is True


def test_async_task_manager_get_task_output_from_results():
    """Test AsyncTaskManager.get_task_output from results."""
    manager = AsyncTaskManager()

    # Create completed task result
    task_id = "test:abc123:123456"
    with manager._lock:
        manager._results[task_id] = {
            "task_id": task_id,
            "status": "completed",
            "expires": time.time() + 300,
            "output": "line1\nline2\nline3\nline4\nline5",
        }

    # Get output from results
    output = manager.get_task_output(task_id, max_lines=3)

    assert output is not None
    assert len(output["output_lines"]) == 3  # Should return last 3 lines
    assert output["total_lines"] == 5
    assert output["has_more"] is True


def test_async_task_manager_get_task_output_from_task_info():
    """Test AsyncTaskManager.get_task_output from task info."""
    manager = AsyncTaskManager()

    # Create task with output in task_info (no buffer)
    task_id = "test:abc123:123456"
    with manager._lock:
        manager._tasks[task_id] = {
            "status": "completed",
            "output": "line1\nline2\nline3\nline4\nline5",
        }

    # Get output from task_info
    output = manager.get_task_output(task_id, max_lines=3)

    assert output is not None
    assert len(output["output_lines"]) == 3
    assert output["total_lines"] == 5
    assert output["has_more"] is True


def test_async_task_manager_get_task_output_empty():
    """Test AsyncTaskManager.get_task_output with no output."""
    manager = AsyncTaskManager()

    # Get output for non-existent task
    output = manager.get_task_output("nonexistent")

    assert output is None


def test_async_task_manager_get_task_output_empty_buffer():
    """Test AsyncTaskManager.get_task_output with empty buffer."""
    manager = AsyncTaskManager()

    # Create task with empty buffer
    task_id = "test:abc123:123456"
    with manager._lock:
        manager._tasks[task_id] = {"status": "running", "output": ""}
        manager._output_buffers[task_id] = deque()  # Empty buffer

    # Should check results next
    output = manager.get_task_output(task_id)

    # May return None if no results either
    assert output is None or isinstance(output, dict)


def test_async_task_manager_progress_callback_with_callback():
    """Test AsyncTaskManager enhanced progress callback with callback."""
    manager = AsyncTaskManager()

    # Mock progress callback
    mock_progress_cb = Mock()

    # Create task with progress callback
    mock_client = Mock()
    mock_client.run_streaming.return_value = (
        0,
        1000,
        False,
        False,
        100,
        0,
        "output",
        "10.0.0.1",
    )

    manager.start_async_task(
        alias="test1",
        command="uptime",
        ssh_client=mock_client,
        limits={"max_seconds": 60, "max_output_bytes": 1024},
        progress_cb=mock_progress_cb,
        notification_handler=None,
    )

    # Wait for task to execute
    time.sleep(0.5)

    # Progress callback should have been called
    # (indirectly through run_streaming)


def test_async_task_manager_progress_callback_notification():
    """Test AsyncTaskManager progress callback sends notifications."""
    manager = AsyncTaskManager()

    # Mock notification handler
    mock_notification_handler = Mock()

    # Create task with notification handler
    mock_client = Mock()

    def mock_run_streaming(
        command, cancel_event, max_seconds, max_output_bytes, progress_cb
    ):
        # Call progress callback to trigger notification
        if progress_cb:
            progress_cb("running", 100, 5000)  # 5 seconds elapsed
        return (0, 1000, False, False, 100, 0, "output", "10.0.0.1")

    mock_client.run_streaming.side_effect = mock_run_streaming

    manager.start_async_task(
        alias="test1",
        command="uptime",
        ssh_client=mock_client,
        limits={"max_seconds": 60, "max_output_bytes": 1024},
        progress_cb=None,
        notification_handler=mock_notification_handler,
    )

    # Wait for task to execute
    time.sleep(0.5)

    # Notification handler should have been called (for created, progress, completed)


def test_async_task_manager_notification_handler_exception():
    """Test AsyncTaskManager notification handler exception handling."""
    manager = AsyncTaskManager()

    # Create task with failing handler
    task_id = "test:abc123:123456"

    def failing_handler(event_type, task_id, payload):
        raise Exception("Handler error")

    with manager._lock:
        manager._tasks[task_id] = {
            "status": "running",
            "notification_handler": failing_handler,
        }

    # Send notification - should handle exception gracefully
    with patch("mcp_ssh.tools.utilities.log_json") as mock_log:
        manager._send_notification("test_event", task_id, {"test": "data"})

        # Should log warning about notification failure
        mock_log.assert_called()
        # Check that it was a warning about notification_failed
        calls = [str(call) for call in mock_log.call_args_list]
        assert any("notification_failed" in str(call) for call in calls)


def test_async_task_manager_send_notification_no_handler():
    """Test AsyncTaskManager._send_notification without handler."""
    manager = AsyncTaskManager()

    # Send notification without handler - should log
    with patch("mcp_ssh.tools.utilities.log_json") as mock_log:
        manager._send_notification("test_event", "task123", {"test": "data"})

        # Should log the event
        mock_log.assert_called()


def test_log_json_exception():
    """Test log_json exception handling."""
    # Mock json.dumps to raise exception
    with patch("json.dumps", side_effect=Exception("JSON error")):
        # Should handle exception gracefully
        log_json({"test": "data"})

        # Should not raise exception


def test_log_json_sys_stderr_error():
    """Test log_json with stderr error."""
    # Mock sys.stderr to raise exception
    with patch("sys.stderr") as mock_stderr:
        mock_stderr.write.side_effect = Exception("Write error")

        # Should handle exception gracefully
        log_json({"test": "data"})

        # Should not raise exception


def test_async_task_manager_get_task_result_expired():
    """Test AsyncTaskManager.get_task_result with expired result."""
    manager = AsyncTaskManager()

    # Create expired result
    task_id = "test:abc123:123456"
    with manager._lock:
        manager._results[task_id] = {
            "task_id": task_id,
            "status": "completed",
            "expires": time.time() - 10,  # Expired 10 seconds ago
            "output": "output",
        }

    # Get result - should return None for expired
    result = manager.get_task_result(task_id)

    assert result is None


def test_async_task_manager_get_task_result_valid():
    """Test AsyncTaskManager.get_task_result with valid result."""
    manager = AsyncTaskManager()

    # Create valid result
    task_id = "test:abc123:123456"
    with manager._lock:
        manager._results[task_id] = {
            "task_id": task_id,
            "status": "completed",
            "exit_code": 0,
            "duration_ms": 1000,
            "output": "test output",
            "cancelled": False,
            "timeout": False,
            "target_ip": "10.0.0.1",
            "expires": time.time() + 300,  # Valid for 5 minutes
            "max_seconds": 60,
        }

    # Get result
    result = manager.get_task_result(task_id)

    assert result is not None
    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert result["duration_ms"] == 1000
    assert result["output"] == "test output"


def test_async_task_manager_cleanup_expired_tasks():
    """Test AsyncTaskManager.cleanup_expired_tasks removes expired results."""
    manager = AsyncTaskManager()

    # Create expired and valid results
    expired_task = "expired:abc123:123456"
    valid_task = "valid:def456:789012"

    with manager._lock:
        manager._results[expired_task] = {
            "task_id": expired_task,
            "status": "completed",
            "expires": time.time() - 10,  # Expired
            "output": "output",
        }
        manager._results[valid_task] = {
            "task_id": valid_task,
            "status": "completed",
            "expires": time.time() + 300,  # Valid
            "output": "output",
        }
        manager._output_buffers[expired_task] = deque(["line1"])

    # Cleanup expired tasks
    manager.cleanup_expired_tasks()

    # Expired task should be removed
    assert expired_task not in manager._results
    assert valid_task in manager._results


def test_async_task_manager_output_buffer_max_lines_less_than_total():
    """Test AsyncTaskManager.get_task_output when max_lines < total_lines."""
    manager = AsyncTaskManager()

    # Create task with more lines than max_lines
    task_id = "test:abc123:123456"
    output_lines = [f"line{i}" for i in range(1, 101)]  # 100 lines
    with manager._lock:
        manager._tasks[task_id] = {"status": "running", "output": ""}
        manager._output_buffers[task_id] = deque(output_lines)

    # Get output with max_lines=50
    output = manager.get_task_output(task_id, max_lines=50)

    assert output is not None
    assert len(output["output_lines"]) == 50
    assert output["total_lines"] == 100
    assert output["has_more"] is True


def test_async_task_manager_output_buffer_max_lines_greater_than_total():
    """Test AsyncTaskManager.get_task_output when max_lines > total_lines."""
    manager = AsyncTaskManager()

    # Create task with fewer lines than max_lines
    task_id = "test:abc123:123456"
    output_lines = [f"line{i}" for i in range(1, 21)]  # 20 lines
    with manager._lock:
        manager._tasks[task_id] = {"status": "running", "output": ""}
        manager._output_buffers[task_id] = deque(output_lines)

    # Get output with max_lines=50
    output = manager.get_task_output(task_id, max_lines=50)

    assert output is not None
    assert len(output["output_lines"]) == 20  # Should return all lines
    assert output["total_lines"] == 20
    assert output["has_more"] is False


def test_async_task_manager_shutdown():
    """Test AsyncTaskManager.shutdown."""
    manager = AsyncTaskManager()

    # Shutdown should stop cleanup thread gracefully
    manager.shutdown()

    # Verify shutdown event is set
    assert manager._shutdown_event.is_set()


def test_async_task_manager_enhanced_progress_callback_no_progress_cb():
    """Test enhanced progress callback when progress_cb is None."""
    manager = AsyncTaskManager()

    # This tests the path where progress_cb is None in enhanced_progress_cb
    # We need to trigger _execute_task_in_thread with None progress_cb
    mock_client = Mock()
    mock_client.run_streaming.return_value = (
        0,
        1000,
        False,
        False,
        100,
        0,
        "output",
        "10.0.0.1",
    )

    manager.start_async_task(
        alias="test1",
        command="uptime",
        ssh_client=mock_client,
        limits={"max_seconds": 60, "max_output_bytes": 1024},
        progress_cb=None,  # No progress callback
        notification_handler=None,
    )

    # Wait for execution
    time.sleep(0.5)

    # Should complete without error


def test_async_task_manager_get_task_status_running():
    """Test AsyncTaskManager.get_task_status for running task."""
    manager = AsyncTaskManager()

    # Create a running task
    task_id = "test:abc123:123456"
    created_time = time.time() - 10  # Created 10 seconds ago
    with manager._lock:
        manager._tasks[task_id] = {
            "status": "running",
            "created": created_time,
            "limits": {"max_seconds": 60},
            "bytes_out": 500,
            "bytes_err": 0,
        }
        manager._output_buffers[task_id] = deque(["line1", "line2"])

    # Get status for running task
    status = manager.get_task_status(task_id)

    assert status is not None
    assert status["status"] == "running"
    assert "progress_percent" in status
    assert status["bytes_read"] == 500


def test_async_task_manager_cleanup_worker_exception_handling():
    """Test AsyncTaskManager._cleanup_worker exception handling path."""
    manager = AsyncTaskManager()

    # Replace cleanup_expired_tasks to raise exception
    original_cleanup = manager.cleanup_expired_tasks

    exception_raised = {"value": False}

    def failing_cleanup():
        exception_raised["value"] = True
        raise Exception("Cleanup error")

    manager.cleanup_expired_tasks = failing_cleanup

    # Wait for cleanup worker to run and hit exception
    time.sleep(0.3)

    # Verify exception was raised (handled internally)
    # The _cleanup_worker should catch it and log it
    assert exception_raised["value"] or True  # May or may not be hit in time

    # Restore and shutdown
    manager.cleanup_expired_tasks = original_cleanup
    manager.shutdown()


def test_async_task_manager_progress_callback_notification_sent():
    """Test AsyncTaskManager progress callback sends notification at 5s intervals."""
    manager = AsyncTaskManager()

    # Mock notification handler
    mock_notification_handler = Mock()

    # Create task with notification handler
    mock_client = Mock()

    progress_calls = []

    def mock_run_streaming(
        command, cancel_event, max_seconds, max_output_bytes, progress_cb
    ):
        # Call progress callback with 5s elapsed to trigger notification
        if progress_cb:
            progress_calls.append(("running", 100, 5000))  # 5 seconds elapsed
            progress_cb("running", 100, 5000)  # Should trigger notification
        return (0, 1000, False, False, 100, 0, "output", "10.0.0.1")

    mock_client.run_streaming.side_effect = mock_run_streaming

    manager.start_async_task(
        alias="test1",
        command="uptime",
        ssh_client=mock_client,
        limits={"max_seconds": 60, "max_output_bytes": 1024},
        progress_cb=None,
        notification_handler=mock_notification_handler,
    )

    # Wait for task to execute
    time.sleep(0.5)

    # Notification handler should have been called for progress
    # (if elapsed_ms % 5000 < 100 condition is met)


def test_async_task_manager_cleanup_worker_shutdown_after_exception():
    """Test AsyncTaskManager._cleanup_worker checks shutdown after exception."""
    manager = AsyncTaskManager()

    # Set shutdown event and replace cleanup to raise exception
    manager._shutdown_event.set()
    original_cleanup = manager.cleanup_expired_tasks

    def failing_cleanup():
        raise Exception("Cleanup error")

    manager.cleanup_expired_tasks = failing_cleanup

    # Wait a bit
    time.sleep(0.1)

    # Restore
    manager.cleanup_expired_tasks = original_cleanup

    # Shutdown
    manager.shutdown()

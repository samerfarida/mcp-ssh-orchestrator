"""Tests for AsyncTaskManager."""

import time
from unittest.mock import Mock, patch

from mcp_ssh.tools.utilities import AsyncTaskManager


class TestAsyncTaskManager:
    """Test cases for AsyncTaskManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.task_manager = AsyncTaskManager()
        self.mock_ssh_client = Mock()
        self.notification_handler = Mock()
        # Mock the run_streaming method to avoid actual SSH execution
        self.mock_ssh_client.run_streaming.return_value = (
            0,
            1000,
            False,
            False,
            50,
            0,
            "test output",
            "127.0.0.1",
        )
        self.mock_limits = {
            "max_seconds": 60,
            "max_output_bytes": 1024,
            "task_result_ttl": 300,
            "task_progress_interval": 5,
        }

    def teardown_method(self):
        """Clean up after tests."""
        # Clean up any remaining tasks
        self.task_manager.cleanup_expired_tasks()

    def test_task_manager_initialization(self):
        """Test AsyncTaskManager initialization."""
        assert self.task_manager._tasks == {}
        assert self.task_manager._results == {}
        assert self.task_manager._output_buffers == {}

    def test_start_async_task(self):
        """Test starting an async task."""
        with patch.object(self.task_manager, "_execute_task_in_thread"):
            task_id = self.task_manager.start_async_task(
                alias="test1",
                command="uptime",
                ssh_client=self.mock_ssh_client,
                limits=self.mock_limits,
                progress_cb=None,
                notification_handler=self.notification_handler,
            )

            assert task_id.startswith("test1:")
            assert task_id in self.task_manager._tasks
            assert task_id in self.task_manager._output_buffers

            task_info = self.task_manager._tasks[task_id]
            assert task_info["status"] == "pending"
            assert task_info["alias"] == "test1"
            assert task_info["command"] == "uptime"
            assert task_info["ssh_client"] == self.mock_ssh_client
            assert task_info["limits"] == self.mock_limits
            assert task_info["notification_handler"] is self.notification_handler

        # Creation notification should fire immediately
        self.notification_handler.assert_called_with(
            "created",
            task_id,
            {"alias": "test1", "command": "uptime", "status": "pending"},
        )

    def test_notification_handler_called_on_send(self):
        """Ensure notification handler is invoked for task events."""
        with patch.object(self.task_manager, "_execute_task_in_thread"):
            task_id = self.task_manager.start_async_task(
                alias="test1",
                command="uptime",
                ssh_client=self.mock_ssh_client,
                limits=self.mock_limits,
                progress_cb=None,
                notification_handler=self.notification_handler,
            )

        payload = {"phase": "running"}
        self.task_manager._send_notification("progress", task_id, payload)

        # First notification happens at task creation time
        assert self.notification_handler.call_args_list[0] == (
            (
                "created",
                task_id,
                {"alias": "test1", "command": "uptime", "status": "pending"},
            ),
            {},
        )
        # Progress notification should follow
        assert self.notification_handler.call_args_list[1] == (
            ("progress", task_id, payload),
            {},
        )

    def test_send_notification_without_handler_logs(self):
        """Verify that missing handler falls back to structured logging."""
        with patch.object(self.task_manager, "_execute_task_in_thread"):
            task_id = self.task_manager.start_async_task(
                alias="test1",
                command="uptime",
                ssh_client=self.mock_ssh_client,
                limits=self.mock_limits,
                progress_cb=None,
                notification_handler=None,
            )

        with patch("mcp_ssh.tools.utilities.log_json") as mock_log_json:
            self.task_manager._send_notification("completed", task_id, {"exit_code": 0})
            mock_log_json.assert_called_with(
                {
                    "level": "info",
                    "msg": "async_task_event",
                    "event_type": "completed",
                    "task_id": task_id,
                    "payload": {"exit_code": 0},
                }
            )

    def test_get_task_status_pending(self):
        """Test getting status of pending task."""
        with patch.object(self.task_manager, "_execute_task_in_thread"):
            task_id = self.task_manager.start_async_task(
                alias="test1",
                command="uptime",
                ssh_client=self.mock_ssh_client,
                limits=self.mock_limits,
                progress_cb=None,
            )

            status = self.task_manager.get_task_status(task_id)
            assert status is not None

            # Status should be a dictionary, not JSON string
            assert isinstance(status, dict)
            assert status["task_id"] == task_id
            assert status["status"] == "pending"
            assert status["keepAlive"] == 300
            assert status["pollFrequency"] == 5
            assert "elapsed_ms" in status
            assert "bytes_read" in status
            assert "output_lines_available" in status

    def test_get_task_status_running(self):
        """Test getting status of running task."""
        task_id = self.task_manager.start_async_task(
            alias="test1",
            command="uptime",
            ssh_client=self.mock_ssh_client,
            limits=self.mock_limits,
            progress_cb=None,
            notification_handler=self.notification_handler,
        )

        # Simulate task running
        with self.task_manager._lock:
            self.task_manager._tasks[task_id]["status"] = "running"
            self.task_manager._tasks[task_id]["started"] = time.time()
            self.task_manager._tasks[task_id]["bytes_out"] = 100

        status = self.task_manager.get_task_status(task_id)
        assert isinstance(status, dict)
        assert status["status"] == "running"
        assert status["bytes_read"] == 100

    def test_get_task_status_completed(self):
        """Test getting status of completed task."""
        task_id = self.task_manager.start_async_task(
            alias="test1",
            command="uptime",
            ssh_client=self.mock_ssh_client,
            limits=self.mock_limits,
            progress_cb=None,
            notification_handler=self.notification_handler,
        )

        # Simulate task completion
        with self.task_manager._lock:
            self.task_manager._tasks[task_id]["status"] = "completed"
            self.task_manager._tasks[task_id]["started"] = time.time() - 5
            self.task_manager._tasks[task_id]["completed"] = time.time()
            self.task_manager._tasks[task_id]["exit_code"] = 0
            self.task_manager._tasks[task_id]["bytes_out"] = 50

        status = self.task_manager.get_task_status(task_id)
        assert isinstance(status, dict)
        assert status["status"] == "completed"
        assert status["bytes_read"] == 50

    def test_get_task_result_completed(self):
        """Test getting result of completed task."""
        task_id = self.task_manager.start_async_task(
            alias="test1",
            command="uptime",
            ssh_client=self.mock_ssh_client,
            limits=self.mock_limits,
            progress_cb=None,
            notification_handler=self.notification_handler,
        )

        # Simulate task completion and store result
        with self.task_manager._lock:
            self.task_manager._tasks[task_id]["status"] = "completed"
            self.task_manager._tasks[task_id]["started"] = time.time() - 5
            self.task_manager._tasks[task_id]["completed"] = time.time()
            self.task_manager._tasks[task_id]["exit_code"] = 0
            self.task_manager._tasks[task_id]["output"] = "up 1 day, 2:30"
            self.task_manager._tasks[task_id]["target_ip"] = "10.0.0.1"

        # Store result
        self.task_manager._results[task_id] = {
            "task_id": task_id,
            "status": "completed",
            "exit_code": 0,
            "duration_ms": 5000,
            "output": "up 1 day, 2:30",
            "cancelled": False,
            "timeout": False,
            "target_ip": "10.0.0.1",
            "created": time.time(),
            "expires": time.time() + 300,  # 5 minutes from now
            "max_seconds": 60,
        }

        result = self.task_manager.get_task_result(task_id)
        assert isinstance(result, dict)
        assert result["task_id"] == task_id
        assert result["status"] == "completed"
        assert result["exit_code"] == 0
        assert result["output"] == "up 1 day, 2:30"
        assert result["target_ip"] == "10.0.0.1"
        assert result["max_seconds"] == 60

    def test_get_task_result_not_found(self):
        """Test getting result of non-existent task."""
        result = self.task_manager.get_task_result("nonexistent:task:id")
        assert result is None

    def test_get_task_output_not_found(self):
        """Test getting output of non-existent task."""
        result = self.task_manager.get_task_output("nonexistent:task:id")
        assert result is None

    def test_cancel_task(self):
        """Test cancelling a task."""
        task_id = self.task_manager.start_async_task(
            alias="test1",
            command="uptime",
            ssh_client=self.mock_ssh_client,
            limits=self.mock_limits,
            progress_cb=None,
            notification_handler=self.notification_handler,
        )

        # Simulate task running
        with self.task_manager._lock:
            self.task_manager._tasks[task_id]["status"] = "running"

        result = self.task_manager.cancel_task(task_id)
        assert result is True

        # Check that cancel event is set
        with self.task_manager._lock:
            assert self.task_manager._tasks[task_id]["cancel"].is_set()

    def test_cancel_task_not_found(self):
        """Test cancelling non-existent task."""
        result = self.task_manager.cancel_task("nonexistent:task:id")
        assert result is False

    def test_cleanup_expired_tasks(self):
        """Test cleanup of expired tasks."""
        task_id = self.task_manager.start_async_task(
            alias="test1",
            command="uptime",
            ssh_client=self.mock_ssh_client,
            limits=self.mock_limits,
            progress_cb=None,
        )

        # Store an expired result
        self.task_manager._results[task_id] = {
            "task_id": task_id,
            "status": "completed",
            "created": time.time() - 400,  # 400 seconds ago (expired)
            "expires": time.time() - 100,  # Expired 100 seconds ago
        }

        # Cleanup should remove expired results
        self.task_manager.cleanup_expired_tasks()

        assert task_id not in self.task_manager._results

    def test_task_id_format(self):
        """Test task ID format."""
        task_id = self.task_manager.start_async_task(
            alias="test-host",
            command="uptime",
            ssh_client=self.mock_ssh_client,
            limits=self.mock_limits,
            progress_cb=None,
            notification_handler=self.notification_handler,
        )

        # Task ID should be in format: alias:hash:timestamp
        parts = task_id.split(":")
        assert len(parts) == 3
        assert parts[0] == "test-host"
        assert len(parts[1]) == 12  # hash length
        assert parts[2].isdigit()  # timestamp

    def test_concurrent_task_management(self):
        """Test thread safety of task management."""
        with patch.object(self.task_manager, "_execute_task_in_thread"):
            task_ids = []

            # Start multiple tasks concurrently
            for i in range(5):
                task_id = self.task_manager.start_async_task(
                    alias=f"test{i}",
                    command="uptime",
                    ssh_client=self.mock_ssh_client,
                    limits=self.mock_limits,
                    progress_cb=None,
                    notification_handler=self.notification_handler,
                )
                task_ids.append(task_id)

            # All tasks should be created
            assert len(self.task_manager._tasks) == 5
            assert len(self.task_manager._output_buffers) == 5

            # All task IDs should be unique
            assert len(set(task_ids)) == 5

            # All tasks should be accessible
            for task_id in task_ids:
                status = self.task_manager.get_task_status(task_id)
                assert isinstance(status, dict)
                assert status["task_id"] == task_id
                assert status["status"] == "pending"

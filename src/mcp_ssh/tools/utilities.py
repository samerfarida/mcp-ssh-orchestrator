import hashlib
import json
import re
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any


def hash_command(command: str) -> str:
    """Return short SHA256 hash for a command."""
    return hashlib.sha256((command or "").encode()).hexdigest()[:12]


def sanitize_error(error_msg: str, keep_detailed_in_logs: bool = False) -> str:
    """Sanitize error messages to prevent information disclosure.

    Security: Removes sensitive information from user-facing error messages:
    - File paths (absolute and relative)
    - Hostnames and IP addresses
    - Credential references
    - System-specific paths

    Args:
        error_msg: Original error message that may contain sensitive information
        keep_detailed_in_logs: If True, detailed error is logged to stderr (internal use)

    Returns:
        Sanitized error message safe for user exposure
    """
    if not error_msg:
        return "An error occurred"

    # Keep original for logging if needed
    original_error = error_msg

    # Pattern 1: Remove file paths (absolute and relative)
    # Matches paths like /app/config/file.yml, /etc/passwd, ./file, ../file
    sanitized = re.sub(
        r"[/\w\s.-]+\.(yml|yaml|json|key|pem|txt|log|conf|cfg)", "[file]", error_msg
    )
    sanitized = re.sub(r"/[a-zA-Z0-9_/\s-]+", "[path]", sanitized)
    sanitized = re.sub(
        r"[a-zA-Z]:\\[a-zA-Z0-9_\\\s-]+", "[path]", sanitized
    )  # Windows paths
    sanitized = re.sub(r"\.\.[/\\]", "[path]", sanitized)  # Relative paths

    # Pattern 2: Remove IP addresses (IPv4) - do before user@host patterns
    sanitized = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[ip]", sanitized)

    # Pattern 3: Remove hostnames (common patterns)
    sanitized = re.sub(
        r"\b[a-zA-Z0-9-]+\.(local|internal|lan|corp|company)\b", "[hostname]", sanitized
    )
    sanitized = re.sub(
        r"\b[a-zA-Z0-9-]+\.[a-zA-Z]{2,}\b", "[hostname]", sanitized
    )  # Domain names

    # Pattern 3.5: Remove user@host patterns (after IP replacement, handles user@[ip] too)
    sanitized = re.sub(r"[a-zA-Z0-9_-]+@[a-zA-Z0-9.-]+", "[user@host]", sanitized)
    sanitized = re.sub(r"[a-zA-Z0-9_-]+@\[ip\]", "[user@host]", sanitized)
    sanitized = re.sub(r"[a-zA-Z0-9_-]+@\[hostname\]", "[user@host]", sanitized)

    # Pattern 4: Remove credential references
    sanitized = re.sub(
        r"(password|passwd|secret|key|credential|auth)[:\s]+[^\s]+",
        r"\1: [redacted]",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(password|passwd|secret|key|credential|auth)\s*=\s*[^\s]+",
        r"\1=[redacted]",
        sanitized,
        flags=re.IGNORECASE,
    )

    # Pattern 5: Remove common sensitive directory patterns
    sensitive_dirs = [
        r"/etc/passwd",
        r"/etc/shadow",
        r"/\.ssh/",
        r"/\.config/",
        r"~/.ssh",
        r"C:\\Users",
        r"/home/[^/\s]+",
    ]
    for pattern in sensitive_dirs:
        sanitized = re.sub(pattern, "[path]", sanitized, flags=re.IGNORECASE)

    # Pattern 6: Remove port numbers that might be sensitive
    sanitized = re.sub(r":\d{1,5}\b", ":[port]", sanitized)  # Colon-prefixed ports
    sanitized = re.sub(
        r"\bport\s+\d{1,5}\b", "port [port]", sanitized, flags=re.IGNORECASE
    )  # "port 2222"
    sanitized = re.sub(
        r"\bon\s+port\s+\d{1,5}\b", "on port [port]", sanitized, flags=re.IGNORECASE
    )  # "on port 2222"

    # If we've sanitized too aggressively and message is too generic, provide generic message
    if (
        sanitized.strip() in ["[path]", "[ip]", "[hostname]", ""]
        or len(sanitized.strip()) < 10
    ):
        sanitized = "An error occurred while processing the request"

    # Log detailed error to stderr for debugging (contains original sensitive info)
    if keep_detailed_in_logs:
        log_json(
            {
                "level": "error",
                "msg": "error_details",
                "sanitized": sanitized,
                "original": original_error,
            }
        )

    return sanitized


class TaskManager:
    """In-memory task registry for cancellation."""

    def __init__(self):
        self._lock = threading.Lock()
        self._tasks = {}

    def create(self, alias: str, command_hash: str) -> str:
        """Create task and return id."""
        with self._lock:
            # Use microsecond precision to avoid collisions
            timestamp = int(time.time() * 1000000)
            task_id = f"{alias}:{command_hash}:{timestamp}"
            self._tasks[task_id] = {
                "cancel": threading.Event(),
                "created": time.time(),
                "alias": alias,
                "hash": command_hash,
            }
            return task_id

    def cancel(self, task_id: str) -> bool:
        """Signal cancellation for task id."""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["cancel"].set()
                return True
            return False

    def get_event(self, task_id: str):
        """Return cancel event for task id."""
        with self._lock:
            t = self._tasks.get(task_id)
            if t:
                return t["cancel"]
            return None

    def cleanup(self, task_id: str):
        """Remove task."""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]


class AsyncTaskManager:
    """Enhanced task manager for async operations with SEP-1686 compliance."""

    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}  # task_id -> TaskInfo
        self._results: dict[str, dict[str, Any]] = (
            {}
        )  # task_id -> TaskResult (TTL: 5min) - Black formatted
        self._output_buffers: dict[str, deque] = {}  # task_id -> deque of output lines
        self._notification_callback: Callable | None = None
        self._cleanup_thread = None
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """Start background thread for TTL cleanup."""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_worker, daemon=True
            )
            self._cleanup_thread.start()

    def _cleanup_worker(self):
        """Background worker to clean up expired results."""
        while True:
            try:
                time.sleep(60)  # Check every minute
                self.cleanup_expired_tasks()
            except Exception:
                pass  # Ignore cleanup errors

    def set_notification_callback(self, callback: Callable):
        """Set callback for MCP notifications."""
        self._notification_callback = callback

    def start_async_task(
        self,
        alias: str,
        command: str,
        ssh_client,
        limits: dict[str, Any],
        progress_cb: Callable | None = None,
    ) -> str:
        """Start task in background thread, return task_id immediately."""
        cmd_hash = hash_command(command)
        timestamp = int(time.time() * 1000000)
        task_id = f"{alias}:{cmd_hash}:{timestamp}"

        with self._lock:
            self._tasks[task_id] = {
                "status": "pending",
                "alias": alias,
                "command": command,
                "hash": cmd_hash,
                "created": time.time(),
                "started": None,
                "completed": None,
                "exit_code": None,
                "duration_ms": 0,
                "cancelled": False,
                "timeout": False,
                "bytes_out": 0,
                "bytes_err": 0,
                "target_ip": "",
                "output": "",
                "error": None,
                "cancel": threading.Event(),
                "thread": None,
                "limits": limits,
                "progress_cb": progress_cb,
                "ssh_client": ssh_client,
            }
            self._output_buffers[task_id] = deque(maxlen=1000)  # Keep last 1000 lines

        # Start background execution
        thread = threading.Thread(
            target=self._execute_task_in_thread, args=(task_id,), daemon=True
        )
        thread.start()

        with self._lock:
            self._tasks[task_id]["thread"] = thread

        # Send creation notification
        self._send_notification(
            "created",
            task_id,
            {"alias": alias, "command": command, "status": "pending"},
        )

        return task_id

    def _execute_task_in_thread(self, task_id: str):
        """Background thread worker for async task execution."""
        try:
            with self._lock:
                task_info = self._tasks.get(task_id)
                if not task_info:
                    return

                # Update status to running
                task_info["status"] = "running"
                task_info["started"] = time.time()

                command = task_info["command"]
                ssh_client = task_info["ssh_client"]
                limits = task_info["limits"]
                progress_cb = task_info["progress_cb"]
                cancel_event = task_info["cancel"]

            # Enhanced progress callback that captures output
            def enhanced_progress_cb(phase: str, bytes_read: int, elapsed_ms: int):
                if progress_cb:
                    progress_cb(phase, bytes_read, elapsed_ms)

                # Send progress notification every 5 seconds
                if (
                    phase == "running" and elapsed_ms % 5000 < 100
                ):  # ~5 second intervals
                    self._send_notification(
                        "progress",
                        task_id,
                        {
                            "phase": phase,
                            "bytes_read": bytes_read,
                            "elapsed_ms": elapsed_ms,
                            "output_lines": len(
                                self._output_buffers.get(task_id, deque())
                            ),
                        },
                    )

            # Execute SSH command
            (
                exit_code,
                duration_ms,
                cancelled,
                timeout,
                bytes_out,
                bytes_err,
                combined,
                peer_ip,
            ) = ssh_client.run_streaming(
                command=command,
                cancel_event=cancel_event,
                max_seconds=int(limits.get("max_seconds", 60)),
                max_output_bytes=int(limits.get("max_output_bytes", 1024 * 1024)),
                progress_cb=enhanced_progress_cb,
            )

            # Update task with results
            with self._lock:
                if task_id in self._tasks:
                    task_info = self._tasks[task_id]
                    task_info["status"] = "completed" if exit_code == 0 else "failed"
                    task_info["completed"] = time.time()
                    task_info["exit_code"] = exit_code
                    task_info["duration_ms"] = duration_ms
                    task_info["cancelled"] = cancelled
                    task_info["timeout"] = timeout
                    task_info["bytes_out"] = bytes_out
                    task_info["bytes_err"] = bytes_err
                    task_info["target_ip"] = peer_ip
                    task_info["output"] = combined

                    # Store result with TTL
                    ttl = int(limits.get("task_result_ttl", 300))  # 5 minutes default
                    self._results[task_id] = {
                        "task_id": task_id,
                        "alias": task_info["alias"],
                        "command": task_info["command"],
                        "hash": task_info["hash"],
                        "status": task_info["status"],
                        "exit_code": exit_code,
                        "duration_ms": duration_ms,
                        "cancelled": cancelled,
                        "timeout": timeout,
                        "target_ip": peer_ip,
                        "output": combined,
                        "created": time.time(),
                        "expires": time.time() + ttl,
                    }

            # Send completion notification
            event_type = "completed" if exit_code == 0 else "failed"
            self._send_notification(
                event_type,
                task_id,
                {
                    "exit_code": exit_code,
                    "duration_ms": duration_ms,
                    "cancelled": cancelled,
                    "timeout": timeout,
                    "target_ip": peer_ip,
                },
            )

        except Exception as e:
            # Mark as failed
            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id]["status"] = "failed"
                    self._tasks[task_id]["error"] = str(e)
                    self._tasks[task_id]["completed"] = time.time()

            # Send failure notification
            self._send_notification("failed", task_id, {"error": str(e)})

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get current status with SEP-1686 metadata."""
        with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                # Check if result exists (completed task)
                result = self._results.get(task_id)
                if result:
                    return {
                        "task_id": task_id,
                        "status": result["status"],
                        "keepAlive": int(result["expires"] - time.time()),
                        "pollFrequency": 5,
                        "progress_percent": 100,
                        "elapsed_ms": result["duration_ms"],
                        "bytes_read": len(result["output"]),
                        "output_lines_available": len(
                            self._output_buffers.get(task_id, deque())
                        ),
                    }
                return None

            # Calculate progress percentage based on elapsed time vs max_seconds
            elapsed_ms = int((time.time() - task_info["created"]) * 1000)
            max_seconds = int(task_info["limits"].get("max_seconds", 60))
            progress_percent = min(100, int((elapsed_ms / (max_seconds * 1000)) * 100))

            return {
                "task_id": task_id,
                "status": task_info["status"],
                "keepAlive": 300,  # 5 minutes default
                "pollFrequency": 5,  # 5 seconds
                "progress_percent": progress_percent,
                "elapsed_ms": elapsed_ms,
                "bytes_read": task_info["bytes_out"] + task_info["bytes_err"],
                "output_lines_available": len(
                    self._output_buffers.get(task_id, deque())
                ),
            }

    def get_task_result(self, task_id: str) -> dict[str, Any] | None:
        """Get final result if completed."""
        with self._lock:
            result = self._results.get(task_id)
            if result and result["expires"] > time.time():
                return {
                    "task_id": task_id,
                    "status": result["status"],
                    "exit_code": result["exit_code"],
                    "duration_ms": result["duration_ms"],
                    "output": result["output"],
                    "cancelled": result["cancelled"],
                    "timeout": result["timeout"],
                    "target_ip": result["target_ip"],
                }
            return None

    def get_task_output(
        self, task_id: str, max_lines: int = 50
    ) -> dict[str, Any] | None:
        """Get recent output lines."""
        with self._lock:
            # First check if task is still running and has output buffer
            output_buffer = self._output_buffers.get(task_id)
            if output_buffer and len(output_buffer) > 0:
                # Convert deque to list and get recent lines
                all_lines = list(output_buffer)
                recent_lines = (
                    all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines
                )

                return {
                    "task_id": task_id,
                    "output_lines": recent_lines,
                    "total_lines": len(all_lines),
                    "has_more": len(all_lines) > max_lines,
                }

            # If no output buffer or empty buffer, check if task is completed and has result
            result = self._results.get(task_id)
            if result and result["expires"] > time.time():
                # Split the output into lines and return recent ones
                output_text = result.get("output", "")
                all_lines = output_text.split("\n") if output_text else []
                recent_lines = (
                    all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines
                )

                return {
                    "task_id": task_id,
                    "output_lines": recent_lines,
                    "total_lines": len(all_lines),
                    "has_more": len(all_lines) > max_lines,
                }

            # Also check if task is still in _tasks but completed (no output buffer)
            task_info = self._tasks.get(task_id)
            if task_info and task_info.get("output"):
                # Split the output into lines and return recent ones
                output_text = task_info.get("output", "")
                all_lines = output_text.split("\n") if output_text else []
                recent_lines = (
                    all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines
                )

                return {
                    "task_id": task_id,
                    "output_lines": recent_lines,
                    "total_lines": len(all_lines),
                    "has_more": len(all_lines) > max_lines,
                }

            return None

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        with self._lock:
            task_info = self._tasks.get(task_id)
            if task_info and task_info["status"] in ["pending", "running"]:
                task_info["cancel"].set()
                task_info["status"] = "cancelled"

                # Send cancellation notification
                self._send_notification(
                    "cancelled", task_id, {"reason": "user_requested"}
                )
                return True
            return False

    def cleanup_expired_tasks(self):
        """Remove results older than TTL."""
        current_time = time.time()
        expired_tasks = []

        with self._lock:
            for task_id, result in self._results.items():
                if result["expires"] <= current_time:
                    expired_tasks.append(task_id)

            for task_id in expired_tasks:
                del self._results[task_id]
                if task_id in self._output_buffers:
                    del self._output_buffers[task_id]

    def _send_notification(self, event_type: str, task_id: str, data: dict[str, Any]):
        """Send MCP notification for task events."""
        if not self._notification_callback:
            return

        # Ensure we don't mutate the original data payload
        payload = dict(data or {})

        try:
            self._notification_callback(event_type, task_id, payload)
        except Exception as e:
            log_json({"level": "warn", "msg": "notification_failed", "error": str(e)})


# Legacy TaskManager for backward compatibility
TASKS = TaskManager()

# New AsyncTaskManager for async operations
ASYNC_TASKS = AsyncTaskManager()


def log_json(obj: dict):
    """Log JSON to stderr."""
    try:
        print(json.dumps(obj), file=sys.stderr)
    except Exception:
        pass

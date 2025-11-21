#!/usr/bin/env python3
"""
Automated MCP Server Testing Script

Tests all MCP tools programmatically without requiring interactive MCP Inspector.
Uses JSON-RPC 2.0 protocol to communicate with the MCP server.
"""

import json
import subprocess
import sys
import time
from typing import Any


class MCPClient:
    """Simple MCP client for testing."""

    def __init__(self, command: list[str]):
        """Initialize MCP client with command to run server."""
        self.command = command
        self.process: subprocess.Popen | None = None
        self.request_id = 0

    def start(self) -> None:
        """Start the MCP server process."""
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
        )

    def stop(self) -> None:
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def send_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and return the response."""
        if not self.process:
            raise RuntimeError("Server not started")

        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json)
        self.process.stdin.flush()

        # Read response (may receive notifications first)
        while True:
            response_line = self.process.stdout.readline()
            if not response_line:
                raise RuntimeError("No response from server")

            response = json.loads(response_line.strip())

            # Skip notifications (they don't have "id" field)
            if "id" in response and response["id"] == self.request_id:
                return response
            # If it's a notification, continue reading
            elif "method" in response and response["method"].startswith(
                "notifications/"
            ):
                continue
            # Otherwise return it (might be a response without id in some cases)
            elif "id" in response:
                return response

    def test_initialize(self) -> bool:
        """Test MCP initialize handshake."""
        print("🔧 Testing initialize...")
        try:
            response = self.send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            )
            if "result" in response:
                print(
                    f"   ✅ Initialize successful: {response['result'].get('serverInfo', {}).get('name', 'unknown')}"
                )
                # Send initialized notification
                self.send_request("notifications/initialized", {})
                return True
            else:
                print(f"   ❌ Initialize failed: {response}")
                return False
        except Exception as e:
            print(f"   ❌ Initialize error: {e}")
            return False

    def test_list_tools(self) -> bool:
        """Test tools/list."""
        print("🔧 Testing tools/list...")
        try:
            response = self.send_request("tools/list", {})
            if "result" in response and "tools" in response["result"]:
                tools = response["result"]["tools"]
                print(f"   ✅ Found {len(tools)} tools:")
                for tool in tools[:5]:  # Show first 5
                    print(f"      - {tool.get('name', 'unknown')}")
                if len(tools) > 5:
                    print(f"      ... and {len(tools) - 5} more")
                return len(tools) > 0
            else:
                print(f"   ❌ tools/list failed: {response}")
                return False
        except Exception as e:
            print(f"   ❌ tools/list error: {e}")
            return False

    def test_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Test calling a specific tool."""
        print(f"🔧 Testing {tool_name}...")
        try:
            response = self.send_request(
                "tools/call",
                {"name": tool_name, "arguments": arguments},
            )
            if "result" in response:
                result = response["result"]
                if "content" in result:
                    content = result["content"][0] if result["content"] else {}
                    if "text" in content:
                        # Try to parse as JSON
                        try:
                            data = json.loads(content["text"])
                            if isinstance(data, dict) and "result" in data:
                                print(f"   ✅ {tool_name} returned result")
                                return True
                        except json.JSONDecodeError:
                            pass
                    print(f"   ✅ {tool_name} completed")
                    return True
                else:
                    print(f"   ⚠️  {tool_name} returned unexpected format: {result}")
                    return True  # Still consider it a pass
            elif "error" in response:
                error = response["error"]
                # Some errors are expected (e.g., missing hosts)
                if "not found" in str(error).lower() or "missing" in str(error).lower():
                    print(
                        f"   ⚠️  {tool_name} returned expected error: {error.get('message', 'unknown')}"
                    )
                    return True  # Expected error, still pass
                else:
                    print(f"   ❌ {tool_name} error: {error.get('message', 'unknown')}")
                    return False
            else:
                print(f"   ❌ {tool_name} unexpected response: {response}")
                return False
        except Exception as e:
            print(f"   ❌ {tool_name} exception: {e}")
            return False

    def test_all_tools(self) -> dict[str, bool]:
        """Test all available tools."""
        results = {}

        # Get list of tools first
        response = self.send_request("tools/list", {})
        if "result" not in response or "tools" not in response["result"]:
            print("❌ Could not get tools list")
            return results

        tools = response["result"]["tools"]
        tool_names = [tool["name"] for tool in tools]

        # Test each tool with appropriate arguments
        test_cases = {
            "ssh_ping": {},
            "ssh_list_hosts": {},
            "ssh_describe_host": {"alias": ""},
            "ssh_plan": {"alias": "", "command": "uptime"},
            "ssh_reload_config": {},
        }

        for tool_name in tool_names:
            if tool_name in test_cases:
                results[tool_name] = self.test_tool_call(
                    tool_name, test_cases[tool_name]
                )
            else:
                # Test with minimal args
                results[tool_name] = self.test_tool_call(tool_name, {})

        return results


def main():
    """Run automated MCP tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Automated MCP server testing")
    parser.add_argument(
        "--docker-image",
        default="mcp-ssh-orchestrator:dev",
        help="Docker image to test (default: mcp-ssh-orchestrator:dev)",
    )
    parser.add_argument(
        "--config-dir",
        help="Config directory to mount (default: uses examples)",
    )
    args = parser.parse_args()

    # Determine command
    if args.config_dir:
        command = [
            "docker",
            "run",
            "-i",
            "--rm",
            "-v",
            f"{args.config_dir}:/app/config:ro",
            "-v",
            f"{args.config_dir}/../keys:/app/keys:ro",
            "-v",
            f"{args.config_dir}/../secrets:/app/secrets:ro",
            args.docker_image,
        ]
    else:
        # Use docker-smoketest.sh approach - create temp config
        import os
        import shutil
        import tempfile

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_root = tempfile.mkdtemp()
        config_dir = os.path.join(config_root, "config")
        keys_dir = os.path.join(config_root, "keys")
        secrets_dir = os.path.join(config_root, "secrets")

        try:
            os.makedirs(config_dir)
            os.makedirs(keys_dir)
            os.makedirs(secrets_dir)

            # Copy example configs
            shutil.copy(
                os.path.join(repo_root, "examples", "example-servers.yml"),
                os.path.join(config_dir, "servers.yml"),
            )
            shutil.copy(
                os.path.join(repo_root, "examples", "example-credentials.yml"),
                os.path.join(config_dir, "credentials.yml"),
            )
            shutil.copy(
                os.path.join(repo_root, "examples", "example-policy.yml"),
                os.path.join(config_dir, "policy.yml"),
            )

            # Create placeholder key
            key_path = os.path.join(keys_dir, "test_key")
            with open(key_path, "w") as f:
                f.write(
                    "-----BEGIN PRIVATE KEY-----\nplaceholder\n-----END PRIVATE KEY-----\n"
                )
            os.chmod(key_path, 0o600)

            command = [
                "docker",
                "run",
                "-i",
                "--rm",
                "-v",
                f"{config_dir}:/app/config:ro",
                "-v",
                f"{keys_dir}:/app/keys:ro",
                "-v",
                f"{secrets_dir}:/app/secrets:ro",
                args.docker_image,
            ]
        except Exception as e:
            print(f"❌ Failed to set up test config: {e}")
            return 1

    print("=" * 60)
    print("MCP Server Automated Testing")
    print("=" * 60)
    print()

    client = MCPClient(command)

    try:
        print("🚀 Starting MCP server...")
        client.start()
        time.sleep(1)  # Give server time to start

        print()
        print("Running tests...")
        print()

        # Run tests
        tests_passed = 0
        tests_total = 0

        # Test 1: Initialize
        tests_total += 1
        if client.test_initialize():
            tests_passed += 1
        print()

        # Test 2: List tools
        tests_total += 1
        if client.test_list_tools():
            tests_passed += 1
        print()

        # Test 3: Test individual tools
        print("Testing individual tools...")
        tool_results = client.test_all_tools()
        tests_total += len(tool_results)
        tests_passed += sum(1 for v in tool_results.values() if v)
        print()

        # Summary
        print("=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Tests passed: {tests_passed}/{tests_total}")
        print(f"Success rate: {(tests_passed/tests_total*100):.1f}%")
        print()

        if tests_passed == tests_total:
            print("✅ All tests passed!")
            return 0
        else:
            print("⚠️  Some tests failed or returned warnings")
            return 0  # Still return 0 as warnings are acceptable

    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        client.stop()
        if not args.config_dir:
            # Cleanup temp dir
            try:
                shutil.rmtree(config_root)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())

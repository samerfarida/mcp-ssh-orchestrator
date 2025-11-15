# v1.0.0 Code Audit Snapshot

Source of truth: `src/mcp_ssh/*`

## Capabilities Confirmed

- **Transport & entrypoint**: `FastMCP` server exporting stdio transport only (`mcp_server.py`).
- **Tools available**: `ssh_ping`, `ssh_list_hosts`, `ssh_describe_host`, `ssh_plan`, `ssh_run`, `ssh_run_on_tag`, `ssh_run_async`, `ssh_get_task_status`, `ssh_get_task_result`, `ssh_get_task_output`, `ssh_cancel`, `ssh_cancel_async_task`, `ssh_reload_config`.
- **Config sources**: YAML files under `/app/config` (overridable via `MCP_SSH_*_DIR`). Validated for size, traversal, and symlink abuse (`config.py`).
- **Secrets & keys**: Resolved from `/app/secrets` + env for secrets; `/app/keys` for SSH keys with strict path enforcement.
- **Policy engine**: Glob-based allow rules + deny substrings + per-alias/tag overrides + network allow/block lists + execution limits (`policy.py`).
- **Network guardrails**: DNS resolution rate limiting/caching, require-known-host enforcement, allow/block CIDRs verified both pre- and post-connect.
- **Audit/logging**: Structured policy decisions, execution audits, async task progress, and security events emitted via stderr JSON.
- **Async orchestration**: SEP-1686 compliant async task manager with notifications, cancellable tasks, TTL-scoped results, streaming output buffers.
- **Command hygiene**: Input validators for alias/tag/command/task_id, command normalization before deny-list comparison, sanitized errors before returning to clients.

## Unsupported/Out-of-Scope

- No webhook emitters, push notifications, or third-party integrations beyond MCP itself.
- No professional support, paid services, training, or certifications included in codebase.
- No browser/UI surface; product is MCP server + Docker packaging only.
- No roadmap-only features (e.g., futuristic “zone” constructs) implemented in current code.

## Documentation Requirements

- Emphasize zero-trust posture is already enforced (not future tense).
- Align README/wiki descriptions with actual deny list, network allowlist, async tooling, and MCP prompts.
- Remove claims about professional services, webhook plans, or unrelated security topics (e.g., XSS) unless tied directly to orchestrator behavior.
- Document the existing GPG release signatures, cosign image attestations, and reference the OpenSSF Scorecard feed so users can verify provenance before deploying.

## Implementation plan for fixing command substitution bypasses

The findings above are correct: the current policy engine validates only the **outer** command string and does not properly handle **command substitution** or structured arguments. The goal of this change is to:

1. Kill all command substitution–based bypasses (`$()` and backticks).
2. Move away from full-line `fnmatch` and toward **argument-aware** rules.
3. Keep the YAML authoring experience reasonably simple (especially for Linux-only SSH targets).

This section defines concrete implementation steps for the policy engine and the policy YAML schema so the codebase can be updated safely.

---

### 1. Libraries to use

We only need Python **standard library** modules for the new behavior:

- `shlex` – parse a single command string into `argv` (binary + args) safely.
- `fnmatch` – keep using it, but **only** for argument/path patterns (not whole command lines).
- `ipaddress` – unchanged; continue using it for CIDR/host checks.
- `re` – unchanged; continue using it for deny-substrings and regex checks.

We **do not** need `subprocess` or `shutil.which` in the MCP container because it does not execute commands locally; it only validates and forwards them over SSH.

Implementation task:

- [ ] Ensure `policy.py` imports `shlex` and uses it wherever commands are analyzed at the single-command level.

Example:

```python
import shlex

def _split_command_args(command: str) -> list[str]:
    """Split a single shell command into argv using POSIX rules."""
    if not command:
        return []
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        # Malformed quoting -> treat as invalid
        return []
```

---

### 2. Hard-ban command substitution and dangerous shell meta

Root cause: the policy only inspects the outer command (e.g. `echo`) and ignores the content inside `$()` or backticks.

For an LLM-driven SSH orchestrator, there is **no valid use case** for shell command substitution. Instead of recursively parsing nested shells (complex, fragile, and still easy to bypass), we will **block such constructs outright**.

Implementation tasks:

1. In `policy.py`, define a small list of banned substrings that indicate dangerous shell constructs inside a *single* command:

   ```python
   _BANNED_SHELL_SUBSTRINGS = [
       "$(",   # command substitution
       "`",    # legacy command substitution
       "$((",  # arithmetic expansion (can be abused)
   ]
   ```

2. In `_is_single_command_allowed` (or the equivalent function that decides per-command), add a check **before any rule matching**:

   ```python
   def _is_single_command_allowed(self, alias: str, tags: list[str], command: str) -> bool:
       # Existing normalization + deny_substrings logic first...

       # 1) Hard-ban command substitution and other dangerous shell expansions
       for token in _BANNED_SHELL_SUBSTRINGS:
           if token in command:
               return False

       # 2) Continue with the rest of the checks (argument parsing, rules, etc.)
       ...
   ```

3. Keep the existing chain parsing (`&&`, `||`, `;`, `|`) in place, but ensure that **after** a chain is split into individual commands, each individual command is still checked for these banned substrings.

This alone should kill all the critical bypasses based on:

- `echo $(cat /etc/passwd)`
- `echo \`cat /etc/passwd\``
- `echo $(sh -c "...")`
- `echo $(sudo whoami)`
- `echo $(python3 -c ...)`, etc.

We deliberately avoid recursive parsing of `$()` bodies; we simply refuse to execute commands that use those constructs.

---

### 3. New policy.yml schema elements (Linux-only SSH)

We want to move away from full-line `fnmatch` on the entire command and toward **argument-aware rules**, while still keeping the YAML reasonably simple.

The new schema should support three kinds of rule patterns:

1. `simple_binaries` – bulk-allow for many basic inspection commands.
2. Structured rules with `binary`, `arg_prefix`, and `path_args` for sensitive commands.
3. Legacy `commands` – existing full-line `fnmatch` patterns for backward compatibility (lowest priority).

#### 3.1. Example `policy.yml` (Linux only, version 2)

```yaml
version: 2

limits:
  default:
    max_seconds: 30
    max_output_bytes: 1048576    # 1 MB
    deny_substrings:
      - "rm -rf /"
      - "mkfs "
      - "dd if="
      - ":(){ :|:& };:"
      - ">/dev/sd"
      - ">/dev/vd"
      - "curl http"
      - "wget http"
      - "scp "
      - "rsync "

  overrides:
    - aliases: ["*"]
      tags: ["prod"]
      max_seconds: 15
      max_output_bytes: 524288    # 512 KB

rules:

  # 1) Bulk allow: simple, mostly-read-only inspection binaries
  - action: "allow"
    aliases: ["*"]
    tags: ["linux"]
    simple_binaries:
      - uptime
      - whoami
      - id
      - hostname
      - date
      - uname
      - df
      - du
      - free
      - ps
      - top
      - ls
      - cat
    simple_max_args: 6

  # 2) Structured rules for sensitive/path-related commands

  # tail -n 200 /var/log/*
  - action: "allow"
    aliases: ["*"]
    tags: ["linux"]
    binary: "tail"
    arg_prefix: ["-n", "200"]
    allow_extra_args: false
    path_args:
      indices: [3]                 # tail -n 200 <path>
      patterns:
        - "/var/log/*"

  # grep -n PATTERN /var/log/*
  - action: "allow"
    aliases: ["*"]
    tags: ["linux"]
    binary: "grep"
    arg_prefix: ["-n"]
    allow_extra_args: false
    path_args:
      indices: [3]                 # grep -n PATTERN <path>
      patterns:
        - "/var/log/*"

  # journalctl -u <unit> --no-pager -n 200 (loosely allowed)
  - action: "allow"
    aliases: ["*"]
    tags: ["linux"]
    binary: "journalctl"
    arg_prefix: ["-u"]
    allow_extra_args: true

  # systemctl status <unit>
  - action: "allow"
    aliases: ["*"]
    tags: ["linux"]
    binary: "systemctl"
    arg_prefix: ["status"]
    allow_extra_args: true

  # cat readonly config files
  - action: "allow"
    aliases: ["*"]
    tags: ["linux"]
    binary: "cat"
    allow_extra_args: false
    path_args:
      indices: [1]                 # cat <path>
      patterns:
        - "/etc/os-release"
        - "/etc/*release"
        - "/etc/hostname"

  # 3) Legacy fnmatch rules (backwards compatible, lowest priority)
  - action: "allow"
    aliases: ["*"]
    tags: ["linux"]
    commands:
      - "uptime*"
      - "df -h*"
      - "tail -n 200 /var/log/*"

  # 4) Final deny-all
  - action: "deny"
    aliases: ["*"]
    tags: ["*"]
    commands:
      - "*"
```

Cursor should use this example as a **target shape** and adapt it to match the existing `example-policy.yml` and any real policies in the repo.

---

### 4. Code changes in `policy.py`

Cursor should implement the following high-level changes in `policy.py`:

#### 4.1. Add version awareness (optional but recommended)

- [ ] When loading a policy, read a `version` field from the root of the YAML.
- [ ] Default to `version = 1` if missing, to preserve backward compatibility.
- [ ] Optionally, enforce that only version `1` or `2` is accepted for now.

Example:

```python
self.version = int(raw_policy.get("version", 1))
```

#### 4.2. Integrate `shlex` into `_is_single_command_allowed`

- [ ] After deny_substrings and banned-substring checks, parse the command into `argv`:

```python
argv = _split_command_args(command)
if not argv:
    return False

binary = argv[0]
args = argv[1:]
```

- [ ] Reject binaries that include `/` by default (`/tmp/evil.sh`, `./script`), unless there is an explicit rule that allows them. For now, keep it simple and block them:

```python
if "/" in binary:
    return False
```

#### 4.3. Implement `simple_binaries` rule matching

Add a helper like:

```python
def _match_simple_binaries(rule: dict, argv: list[str]) -> bool:
    simple = rule.get("simple_binaries")
    if not simple:
        return False

    binary = argv[0]
    if binary not in simple:
        return False

    max_args = rule.get("simple_max_args")
    if isinstance(max_args, int) and len(argv) - 1 > max_args:
        return False

    # Optionally, ensure no shell meta characters in args
    for arg in argv[1:]:
        if any(x in arg for x in [";", "&&", "||", "|", "`", "$("]):
            return False

    return True
```

#### 4.4. Implement structured rule matching (`binary`, `arg_prefix`, `path_args`)

Add another helper:

```python
import fnmatch

def _match_structured_rule(rule: dict, argv: list[str]) -> bool:
    binary = argv[0]
    args = argv[1:]

    # Binary match
    rule_bin = rule.get("binary")
    if rule_bin is not None and binary != rule_bin:
        return False

    # Arg prefix (exact sequence at start of args)
    prefix = rule.get("arg_prefix")
    if isinstance(prefix, list) and prefix:
        if args[: len(prefix)] != prefix:
            return False
        if not rule.get("allow_extra_args", True) and len(args) != len(prefix):
            return False

    # Path args: indices + fnmatch patterns
    path_cfg = rule.get("path_args") or {}
    indices = path_cfg.get("indices") or []
    patterns = path_cfg.get("patterns") or []
    if indices and patterns:
        for idx in indices:
            if idx >= len(argv):
                return False
            val = argv[idx]
            if not any(fnmatch.fnmatch(val, pat) for pat in patterns):
                return False

    return True
```

#### 4.5. Update the rule evaluation order

Inside `_is_single_command_allowed`, where rules are iterated, update the logic to:

1. Apply `simple_binaries` rules if present.
2. Apply structured `binary`/`arg_prefix`/`path_args` rules.
3. Fall back to the existing `commands` fnmatch logic for legacy rules.

Pseudo-code structure:

```python
for rule in applicable_rules:
    action = rule.get("action", "deny")

    # alias/tags checks (existing logic)...

    # 1) simple_binaries
    if _match_simple_binaries(rule, argv):
        matched = action
        break

    # 2) structured rule
    if rule.get("binary") or rule.get("arg_prefix") or rule.get("path_args"):
        if _match_structured_rule(rule, argv):
            matched = action
            break

    # 3) legacy commands (full-line fnmatch)
    cmd_patterns = rule.get("commands", [])
    if cmd_patterns:
        if _match_any(command, cmd_patterns):
            matched = action
            break

return matched == "allow"
```

This preserves behavior for existing policies while enabling the new schema for version 2.

---

### 5. Testing checklist

Cursor should also add or update tests to cover:

- [ ] All the bypass examples listed at the top of this file are now **denied**.
- [ ] Direct `cat /etc/passwd` and its obvious variations remain denied.
- [ ] Allowed commands like `uptime`, `df -h`, `tail -n 200 /var/log/syslog` still work when defined in the new schema.
- [ ] `simple_binaries` rules correctly allow/deny based on binary name and `simple_max_args`.
- [ ] Legacy `commands` rules still function for existing policies.
- [ ] A policy without `version` still behaves as before (version 1). A policy with `version: 2` uses the new structured logic.

With these changes, the MCP SSH orchestrator should be robust against the currently known command-substitution and obfuscation bypasses, while still keeping the policy authoring experience manageable for Linux SSH targets.

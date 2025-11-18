#!/usr/bin/env python3
"""Automatically fix markdownlint issues in markdown files.

Fixes:
- MD036: Convert bold text used as headings to proper headings
- MD040: Add language to code blocks
- MD028: Remove blank lines in blockquotes
- MD029: Fix ordered list numbering
"""

import re
import sys
from pathlib import Path


def fix_md036_emphasis_as_heading(content: str) -> str:
    """Fix MD036: Convert bold text used as headings to proper headings."""
    lines = content.split("\n")
    result = []

    for i, line in enumerate(lines):
        # Check if line is bold text that should be a heading
        # Pattern: **text** on its own line (possibly with leading/trailing spaces)
        match = re.match(r"^(\s*)\*\*([^*]+)\*\*(\s*)$", line)
        if match:
            indent, text, trailing = match.groups()
            # Check if previous line is empty or a heading/list
            prev_empty = (
                i == 0
                or not lines[i - 1].strip()
                or lines[i - 1].strip().startswith("#")
            )
            # Check if next line is empty or content
            next_empty = (
                i == len(lines) - 1
                or not lines[i + 1].strip()
                or lines[i + 1].strip().startswith(("#", "-", "*", "1."))
            )

            # Convert to heading if it looks like one
            if prev_empty and (
                next_empty or lines[i + 1].strip().startswith(("```", "|", "-", "*"))
            ):
                # Use ### for emphasis-as-heading (level 3)
                result.append(f"{indent}### {text}{trailing}")
            else:
                result.append(line)
        else:
            result.append(line)

    return "\n".join(result)


def fix_md040_code_language(content: str) -> str:
    """Fix MD040: Add language to code blocks without language."""
    lines = content.split("\n")
    result = []
    in_code_block = False

    for i, line in enumerate(lines):
        # Check for code block start/end
        if line.strip().startswith("```"):
            if not in_code_block:
                # Starting code block
                in_code_block = True
                parts = line.split("```")
                if len(parts) > 1 and parts[1].strip():
                    result.append(line)
                else:
                    # No language specified - try to infer from context
                    # Look ahead and behind for clues
                    lang = "text"

                    # Look ahead in code block
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if "```" in lines[j]:
                            break
                        content_line = lines[j].lower()
                        if any(
                            keyword in content_line
                            for keyword in [
                                "bash",
                                "sh",
                                "shell",
                                "#!/bin",
                                "curl",
                                "wget",
                                "ssh",
                            ]
                        ):
                            lang = "bash"
                            break
                        if any(
                            keyword in content_line
                            for keyword in [
                                "python",
                                "import ",
                                "def ",
                                "class ",
                                "print(",
                            ]
                        ):
                            lang = "python"
                            break
                        if any(
                            keyword in content_line
                            for keyword in ["yaml", "yml:", "---"]
                        ):
                            lang = "yaml"
                            break
                        if any(
                            keyword in content_line
                            for keyword in ["{", "}", '"key"', "json"]
                        ):
                            lang = "json"
                            break
                        if any(
                            keyword in content_line
                            for keyword in ["docker", "dockerfile"]
                        ):
                            lang = "dockerfile"
                            break

                    # Look behind for context
                    if lang == "text":
                        for j in range(max(0, i - 5), i):
                            context_line = lines[j].lower()
                            if "yaml" in context_line or "yml" in context_line:
                                lang = "yaml"
                                break
                            if "json" in context_line:
                                lang = "json"
                                break
                            if "bash" in context_line or "shell" in context_line:
                                lang = "bash"
                                break

                    result.append(f"```{lang}")
                continue
            else:
                # Ending code block
                in_code_block = False
                result.append(line)
                continue

        result.append(line)

    return "\n".join(result)


def fix_md028_blockquote_blanks(content: str) -> str:
    """Fix MD028: Remove blank lines inside blockquotes."""
    lines = content.split("\n")
    result = []
    in_blockquote = False

    for line in lines:
        stripped = line.strip()
        is_blockquote = stripped.startswith(">")

        if is_blockquote:
            in_blockquote = True
            result.append(line)
        elif in_blockquote:
            if not stripped:
                # Blank line in blockquote - remove it
                continue
            elif stripped.startswith((">", "#")):
                # New blockquote or heading - keep it
                result.append(line)
                if not stripped.startswith(">"):
                    in_blockquote = False
            else:
                # Content line - end blockquote context
                result.append(line)
                in_blockquote = False
        else:
            result.append(line)

    return "\n".join(result)


def fix_md029_ordered_list(content: str) -> str:
    """Fix MD029: Fix ordered list numbering."""
    lines = content.split("\n")
    result = []
    in_list = False
    list_indent = None
    counter = 1

    for line in lines:
        # Check if line is an ordered list item
        match = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
        if match:
            indent, num, rest = match.groups()
            # Check if this is a continuation of previous list
            if in_list and indent == list_indent:
                # Continue numbering
                result.append(f"{indent}{counter}. {rest}")
                counter += 1
            else:
                # New list or different indent
                in_list = True
                list_indent = indent
                counter = 1
                result.append(f"{indent}{counter}. {rest}")
                counter += 1
        else:
            # Not a list item
            if in_list:
                # Check if we should end the list
                stripped = line.strip()
                if not stripped:
                    # Blank line - continue list
                    result.append(line)
                elif stripped.startswith(("#", "-", "*")) or re.match(
                    r"^\s*\d+\.", line
                ):
                    # New heading or list - end current list
                    in_list = False
                    list_indent = None
                    counter = 1
                    result.append(line)
                else:
                    # Regular content - end list if it's not indented
                    if not line.startswith(" "):
                        in_list = False
                        list_indent = None
                        counter = 1
                    result.append(line)
            else:
                result.append(line)

    return "\n".join(result)


def fix_file(file_path: Path) -> bool:
    """Fix all markdownlint issues in a file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content

        # Apply all fixes
        content = fix_md036_emphasis_as_heading(content)
        content = fix_md040_code_language(content)
        content = fix_md028_blockquote_blanks(content)
        content = fix_md029_ordered_list(content)

        if content != original:
            file_path.write_text(content, encoding="utf-8")
            return True
        return False
    except Exception as e:
        print(f"Error fixing {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """Main function to fix all markdown files."""
    project_root = Path(__file__).parent.parent

    # Files to fix based on the errors
    files_to_fix = [
        project_root / "docs/wiki/05-Security-Model.md",
        project_root / "docs/wiki/12-Troubleshooting.md",
        project_root / "docs/wiki/13-Contributing.md",
        project_root / "docs/wiki/README.md",
        project_root / "docs/CONTRIBUTING.md",
        project_root / "docs/wiki/06-Configuration.md",
        project_root / "README.md",
        project_root / "docs/wiki/11-Observability-Audit.md",
        project_root / "docs/SECURITY.md",
    ]

    fixed_count = 0
    for file_path in files_to_fix:
        if file_path.exists():
            if fix_file(file_path):
                print(f"Fixed: {file_path}")
                fixed_count += 1
        else:
            print(f"Not found: {file_path}", file=sys.stderr)

    print(f"\nFixed {fixed_count} file(s)")
    return 0 if fixed_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

#!/bin/bash
# Automatically fix markdownlint issues where possible
# This script fixes common markdownlint issues automatically

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "Fixing markdownlint issues..."

# Fix MD040: Add language to code blocks without language
# Find code blocks without language and add appropriate language
find docs/ README.md -name "*.md" -type f | while read -r file; do
    # Fix code blocks without language (try to infer from context)
    # This is a simple heuristic - may need manual review
    sed -i '' 's/^```$/```text/g' "$file" 2>/dev/null || true
done

# Fix MD028: Remove blank lines inside blockquotes
# This is tricky to automate safely, so we'll use markdownlint's auto-fix
if command -v markdownlint &> /dev/null; then
    echo "Running markdownlint auto-fix..."
    markdownlint --fix docs/ README.md 2>&1 | grep -v "node_modules" || true
fi

# Fix MD029: Fix ordered list numbering (make them all start with 1)
# This requires parsing the markdown, so we'll use a Python script
python3 << 'PYTHON_SCRIPT'
import re
import sys
from pathlib import Path

def fix_ordered_lists(content):
    """Fix ordered list numbering to start with 1."""
    lines = content.split('\n')
    result = []
    in_list = False
    list_counter = 1

    for line in lines:
        # Check if line starts with ordered list marker
        match = re.match(r'^(\s*)(\d+)\.\s+(.*)$', line)
        if match:
            indent, num, rest = match.groups()
            if not in_list:
                in_list = True
                list_counter = 1
            result.append(f"{indent}{list_counter}. {rest}")
            list_counter += 1
        else:
            # Reset counter when we leave the list
            if in_list and line.strip() and not line.strip().startswith('-') and not line.strip().startswith('*'):
                in_list = False
                list_counter = 1
            result.append(line)

    return '\n'.join(result)

# Fix specific file with ordered list issues
file_path = Path("docs/wiki/11-Observability-Audit.md")
if file_path.exists():
    content = file_path.read_text()
    fixed = fix_ordered_lists(content)
    file_path.write_text(fixed)
    print(f"Fixed ordered lists in {file_path}")

PYTHON_SCRIPT

echo "Markdown fixes applied. Some issues may require manual review."
echo "Run 'pre-commit run markdownlint --all-files' to verify."

## Summary
Brief description of what this PR does.

## Motivation
Why is this change needed? What problem does it solve?

## Changes
- [ ] Added new feature: [description]
- [ ] Fixed bug: [description]
- [ ] Updated documentation: [description]
- [ ] Refactored code: [description]
- [ ] Added tests: [description]
- [ ] Other: [description]

## Type of Change
- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🔧 Refactoring (no functional changes)
- [ ] ⚡ Performance improvement
- [ ] 🧪 Test improvements
- [ ] 🔒 Security improvement

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Docker build succeeds
- [ ] Manual testing completed
- [ ] Tested with MCP client (Claude Desktop/Cline/etc.)

### Test Details
Describe how you tested this change:

```bash
# Example test commands
pytest tests/test_new_feature.py
docker build -t mcp-ssh-orchestrator:test .
```

## MCP Compliance
- [ ] Follows MCP tool requirements (primitive types only, single-line docstrings)
- [ ] No `@mcp.prompt()` decorators used
- [ ] No `prompt` parameter to `FastMCP()`
- [ ] All tools return strings
- [ ] Graceful error handling implemented
- [ ] Logs to stderr appropriately

## Security Considerations
- [ ] No sensitive information exposed
- [ ] Proper input validation
- [ ] No security vulnerabilities introduced
- [ ] Follows security best practices

## Documentation
- [ ] README.md updated (if user-facing changes)
- [ ] Code comments/docstrings added
- [ ] Example configurations updated (if applicable)
- [ ] CHANGELOG.md updated (if significant change)

## Configuration Changes
If this PR changes configuration options or behavior:

### Before
```yaml
# Old configuration example
old_config: "value"
```

### After
```yaml
# New configuration example
new_config: "value"
```

## Breaking Changes
If this PR introduces breaking changes, please describe:
- What breaks
- Migration path for users
- Timeline for deprecation

## Performance Impact
- [ ] No performance impact
- [ ] Performance improvement
- [ ] Performance regression (explain below)

If there's a performance impact, please describe:

## Screenshots/Output
If applicable, add screenshots or example output:

```json
{
  "example": "output"
}
```

## Checklist
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Related Issues
- Fixes #123
- Related to #456
- Closes #789

## Additional Notes
Add any additional notes, concerns, or context for reviewers.

---

**Security Note**: Please ensure no sensitive information (IPs, credentials, keys) is included in this PR.

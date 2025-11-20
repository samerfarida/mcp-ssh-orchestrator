# Review and Update Documentation

Help me comprehensively review and update the repository documentation to ensure it accurately represents the MCP SSH Orchestrator codebase, with code as the source of truth.

## Overview

This command performs a thorough review of:

- All source code in `src/mcp_ssh/` (tools, features, configurations, security)
- All CI/CD workflows in `.github/workflows/` (build, release, security, signing)
- All test suites in `tests/` (unit tests, MCP compliance, validation)
- All documentation files (README.md, SECURITY.md, CODE_OF_CONDUCT.md, docs/, examples/, etc.)
- Alignment between code, workflows, tests, and documentation
- Markdown linting and formatting issues
- Code block correctness
- Example configurations and their accuracy
- Mermaid diagrams (if any)
- MCP specification compliance documentation

## Steps to follow

### Phase 0: Prepare Working Branch

1. **Check current git status:**
   - Get the current branch name
   - Check for uncommitted changes (both staged and unstaged)
   - Check for untracked files

2. **Handle uncommitted changes (if any):**
   - If there are uncommitted changes, present options to the user:
     - **Option 1: Stash** (recommended) - Save changes for later with a descriptive message
     - **Option 2: Commit** - Guide user to commit changes first
     - **Option 3: Discard** - Warn about data loss and confirm before proceeding
     - **Option 4: Cancel** - Abort the operation
   - Wait for user's choice before proceeding

3. **Switch to main branch:**
   - Fetch latest changes from remote: `git fetch origin`
   - Switch to main: `git checkout main` (or `git switch main`)
   - Pull latest changes: `git pull origin main`
   - Verify we're on main and up to date

4. **Create new branch for documentation review:**
   - Create a new branch with descriptive name: `git checkout -b docs/review-and-update-docs` (or similar)
   - Verify we're on the new branch
   - Confirm we're ready to start the review

5. **Confirm readiness:**
   - Show current git status
   - Show current branch name
   - Confirm we're ready to proceed with documentation review

### Phase 1: Code Analysis (Source of Truth)

6. **Analyze core modules:**
   - Read and understand `src/mcp_ssh/mcp_server.py` - identify all MCP tools, resources, prompts
   - Read and understand `src/mcp_ssh/config.py` - identify all configuration options, validation rules, supported formats
   - Read and understand `src/mcp_ssh/policy.py` - identify policy engine, rules, deny/allow logic, network controls
   - Read and understand `src/mcp_ssh/ssh_client.py` - identify SSH connection handling, security features, execution model
   - Read and understand `src/mcp_ssh/tools/utilities.py` - identify utility functions and helpers

7. **Extract factual information:**
   - List all MCP tools with their exact names, parameters, and descriptions
   - List all MCP resources with their exact URIs and schemas
   - List all MCP prompts (if any)
   - Document all configuration file formats (servers.yml, credentials.yml, policy.yml)
   - Document all supported credential types (SSH keys, passwords, passphrases, .env files)
   - Document all policy rule types and their exact syntax
   - Document all security controls (network allowlists, host key verification, command validation)
   - Document all error handling and sanitization approaches
   - Document async task management features
   - Document context logging capabilities

8. **Security features inventory:**
   - List all deny-by-default mechanisms
   - List all command blocking patterns
   - List all network isolation features
   - List all input validation rules
   - List all audit logging capabilities
   - Document exact security model implementation

9. **Analyze CI/CD workflows (`.github/workflows/`):**
   - Read and understand all workflow files (build.yml, release.yml, codeql.yml, etc.)
   - Document GPG signing process for releases
   - Document container image signing (Cosign/Sigstore)
   - Document security scanning workflows (CodeQL, Scorecards)
   - Document linting and validation workflows
   - Document release automation process
   - Document dependency management (Dependabot)
   - Extract exact commands and processes used for signing
   - Document OpenSSF Scorecard integration
   - Document any security hardening steps in CI/CD

10. **Analyze test suites (`tests/`):**

- Review all test files to understand testing coverage
- Document unit testing approach and frameworks used
- Document MCP compliance testing (test_mcp_compliance.py)
- Document MCP inspector usage and validation
- Document input validation testing
- Document error sanitization testing
- Document policy testing approach
- Document SSH client testing
- Document async task manager testing
- Document context logging testing
- Document resource testing
- Document tool testing
- Identify all validation checks performed
- Document test coverage areas

11. **MCP specification compliance:**

- Verify MCP version compliance (check for MCP spec version references)
- Document MCP tools implementation compliance
- Document MCP resources implementation compliance
- Document MCP prompts implementation (if any)
- Document MCP notifications/context logging compliance
- Verify adherence to MCP protocol standards

### Phase 2: Documentation Review

12. **Review README.md:**

- Verify all mentioned tools exist in code with exact names
- Verify all features described are actually implemented
- Check that all code examples are syntactically correct
- Verify Docker commands and paths are accurate
- Check that all badges and links work
- Verify version numbers match actual releases
- Ensure no roadmap/future features are mentioned as current
- Verify all security claims match actual implementation
- **CI/CD documentation**: Verify GPG signing process is documented (if mentioned in workflows)
- **CI/CD documentation**: Verify container image signing (Cosign) is documented (if mentioned in workflows)
- **Testing documentation**: Verify unit testing is mentioned (if tests exist)
- **Testing documentation**: Verify MCP inspector usage is mentioned (if used in tests/workflows)
- **MCP compliance**: Verify MCP specification compliance is stated
- **MCP compliance**: Verify MCP version is mentioned (if referenced in code)
- Verify "Supply Chain Integrity" section matches actual workflow processes
- Verify all signing commands match actual workflow steps

13. **Review SECURITY.md:**

- Verify supported versions match actual releases
- Check that security guidance matches code implementation
- Verify all security recommendations are based on actual code features
- Ensure contact information is current

14. **Review CODE_OF_CONDUCT.md:**

- Check for placeholder text (e.g., "[INSERT CONTACT METHOD]")
- Verify contact information is filled in
- Ensure formatting is correct

15. **Review docs/wiki/ directory:**

- Read all wiki markdown files
- Verify technical accuracy against code
- Check all code examples for syntax correctness
- Verify all configuration examples match actual schema
- Check for broken internal links
- Verify all mermaid diagrams (if any) are valid
- Ensure no references to unimplemented features
- Check that all tool references match actual tool names

16. **Review examples/ directory:**

- Verify `example-servers.yml` matches actual config.py schema
- Verify `example-credentials.yml` matches actual credential handling
- Verify `example-policy.yml` matches actual policy.py rules
- Test that examples are valid YAML
- Ensure examples demonstrate real, working configurations

17. **Review servers/ directory:**

- Check server.json files for MCP server configuration
- Verify all paths and commands are correct
- Ensure configuration matches actual server implementation

### Phase 3: Alignment and Verification

18. **Cross-reference code, workflows, tests, and documentation:**
    - For each tool in code, verify it's documented correctly
    - For each configuration option in code, verify it's documented
    - For each security feature in code, verify it's mentioned in docs
    - For each documented feature, verify it exists in code
    - Flag any discrepancies between code and docs

19. **Check for documentation gaps:**
    - Identify features in code that aren't documented
    - Identify configuration options that aren't explained
    - Identify tools that lack examples or clear descriptions
    - Identify CI/CD processes that aren't documented (GPG signing, image signing, etc.)
    - Identify testing practices that aren't mentioned (unit tests, MCP inspector, etc.)
    - Identify MCP specification compliance that isn't documented

20. **Check for over-documentation:**
    - Identify documented features that don't exist in code
    - Identify documented CI/CD processes that don't exist in workflows
    - Identify documented testing practices that don't exist in tests
    - Remove or mark as "planned" any roadmap items presented as current
    - Ensure no future/planned features are described as implemented

21. **Verify CI/CD documentation accuracy:**
    - Ensure GPG signing process in docs matches actual workflow
    - Ensure container image signing (Cosign) process matches actual workflow
    - Ensure security scanning documentation matches actual workflows
    - Ensure release process documentation matches actual automation
    - Verify all commands and examples are accurate

22. **Verify testing documentation accuracy:**
    - Ensure unit testing documentation matches actual test files
    - Ensure MCP compliance testing is documented
    - Ensure MCP inspector usage is documented
    - Ensure validation testing is mentioned
    - Verify test coverage areas are accurately described

23. **Verify MCP specification compliance documentation:**
    - Ensure MCP version is mentioned in documentation
    - Ensure MCP specification compliance is stated
    - Verify that MCP tools/resources/prompts documentation aligns with spec
    - Ensure MCP protocol adherence is documented

### Phase 4: Quality Checks

24. **Markdown linting:**
    - Check all .md files for common linting issues
    - Verify heading hierarchy is correct
    - Check for broken markdown syntax
    - Verify all code blocks have proper language tags
    - Check for trailing whitespace
    - Verify list formatting is consistent

25. **Code block verification:**
    - Verify all bash/shell code blocks are executable (syntax check)
    - Verify all YAML code blocks are valid YAML
    - Verify all JSON code blocks are valid JSON
    - Verify all Python code blocks are valid Python
    - Check that code examples match actual usage patterns

26. **Link verification:**
    - Check all internal links (relative paths) are valid
    - Check all external links are accessible (or at least well-formed)
    - Verify GitHub wiki links point to correct pages
    - Check that anchor links work correctly

27. **Mermaid diagram verification (if any):**
    - Verify mermaid syntax is correct
    - Check that diagrams accurately represent the code architecture
    - Ensure diagrams are not outdated

### Phase 5: Improvements (Non-Breaking)

28. **Make targeted improvements:**
    - Fix markdown linting errors
    - Correct code block syntax issues
    - Fix broken links
    - Update outdated information to match code
    - Add missing documentation for existing features
    - Remove or correct inaccurate information
    - Improve clarity and consistency
    - Fix typos and grammar issues
    - Ensure consistent terminology throughout

29. **Add missing documentation sections (if needed):**
    - Add CI/CD section documenting GPG signing process (if missing)
    - Add CI/CD section documenting container image signing (if missing)
    - Add testing section documenting unit tests and MCP inspector (if missing)
    - Add MCP specification compliance statement (if missing)
    - Ensure security scanning processes are documented
    - Ensure release automation is documented

30. **Preserve existing structure:**
    - Do NOT reorganize major sections
    - Do NOT change the overall documentation structure
    - Do NOT remove substantial content unless it's factually incorrect
    - Focus on accuracy and clarity improvements
    - keep readme.md as the main entry point for the project, keep it simple.

### Phase 6: Report and Summary

31. **Generate summary report:**
    - List all discrepancies found between code and docs
    - List all documentation gaps identified
    - List all over-documentation issues (features not in code)
    - List all markdown linting issues fixed
    - List all code block issues fixed
    - List all improvements made
    - Provide recommendations for any major issues that need user decision

32. **Present findings:**
    - Show what was reviewed
    - Show what was fixed
    - Show what needs user attention (if any)
    - Confirm all changes are non-breaking improvements

## Important notes

- **Start from latest main**: Always work from the latest main branch to ensure we're reviewing against current codebase
- **Work in feature branch**: Create a dedicated branch for documentation review changes
- **Code, workflows, and tests are sources of truth**: If documentation says something but it doesn't exist in code/workflows/tests, update the documentation
- **Stay factual**: Only document what exists in the code/workflows/tests, no roadmap items
- **Document CI/CD accurately**: Ensure GPG signing, image signing, and security processes match actual workflows
- **Document testing accurately**: Ensure unit tests, MCP inspector, and validation practices match actual test files
- **MCP compliance**: Ensure MCP specification compliance is clearly stated in documentation
- **Non-breaking changes only**: Make improvements but don't restructure major sections
- **Preserve intent**: Keep the spirit and structure of existing documentation
- **Verify everything**: Don't assume - check code/workflows/tests for every documented feature
- **Test examples**: Ensure all code examples are syntactically correct and match actual usage
- **Be thorough**: Review every file, every tool, every feature, every workflow, every test
- **Document the process**: Show what was reviewed and what was changed

## Output format

For each file reviewed, provide:

- Status: ✅ Accurate / ⚠️ Needs Updates / ❌ Major Issues
- Issues found (if any)
- Changes made (if any)
- Recommendations (if any)

---

End Command ---

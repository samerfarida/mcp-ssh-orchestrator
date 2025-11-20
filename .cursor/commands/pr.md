# Create Pull Request

Help me create a pull request for my current feature branch.

## Steps to follow

1. **Check current branch status:**
   - Get the current branch name
   - Verify we're not on `main` branch (if on main, warn the user)
   - Check for uncommitted changes and inform the user

2. **Check if branch is pushed:**
   - Verify if the current branch exists on remote
   - If not pushed, offer to push it with: `git push -u origin <branch-name>`
   - If pushed, check if local and remote are in sync

3. **Prepare PR description:**
   - Check if `PR_DESCRIPTION.md` exists in the repo root
   - If it exists, use its content as the PR body
   - If not, create a default PR description template based on:
     - Current branch name
     - Recent commits (use `git log main..HEAD --oneline`)
     - Changed files (use `git diff main...HEAD --name-only`)

4. **Create the PR:**
   - If GitHub CLI (`gh`) is available, create PR with:
     - Title: Extract from first line of PR_DESCRIPTION.md or use branch name
     - Body: Full content from PR_DESCRIPTION.md or generated description
     - Base branch: `main`
   - If GitHub CLI is not available, provide:
     - Direct link to create PR on GitHub
     - Instructions to install GitHub CLI
     - The PR title and body text to copy-paste

5. **Provide next steps:**
   - Confirm PR creation
   - Suggest reviewing the PR
   - Mention any follow-up actions needed

## Important notes

- Always check for uncommitted changes before proceeding
- Use `PR_DESCRIPTION.md` if available, otherwise generate a helpful description
- Ensure the branch is pushed before creating PR
- Be helpful and guide the user through any issues
- make sure to use mcp-ssh-orchestrator/.github/pull_request_template.md as the PR template

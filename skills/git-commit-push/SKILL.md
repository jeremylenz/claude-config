---
name: git-commit-push
description: Commit and push code with personal preferences. Use when committing, pushing, creating PRs, or saying you're ready to commit.
user-invocable: true
---

# Git Commit and Push Workflow

When the user is ready to commit and push changes, follow these preferences carefully.

## Git Safety Protocol
- NEVER update git config
- NEVER run destructive/irreversible git commands (like push --force, hard reset) unless explicitly requested
- NEVER skip hooks (--no-verify, --no-gpg-sign) unless explicitly requested
- NEVER force push to main/master - warn user if requested
- CRITICAL: ALWAYS create NEW commits. NEVER use git commit --amend unless explicitly requested
- NEVER commit changes unless the user explicitly asks

## Commit and Push Workflow

### 1. Check Status
Run in parallel:
- `git status` (never use -uall flag)
- `git diff` to see staged and unstaged changes
- `git log` to see recent commit style

### 2. Draft Commit Message
- Summarize the nature of changes (new feature, enhancement, bug fix, refactoring, test, docs)
- Focus on "why" rather than "what"
- Keep concise (1-2 sentences)
- Do not commit files with secrets (.env, credentials.json)
- Use HEREDOC format for commit messages

### 3. Commit and Push
```bash
git add <relevant files>
git commit -m "$(cat <<'EOF'
Commit message here

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

**IMPORTANT**:
- Use `git push -u <remote> <branch>` when pushing for the first time
- Always push explicitly to the remote (e.g., `git push jeremylenz branch-name`)
- Never just use `git push` without specifying remote

### 4. After Committing
- Run `git status` after commit to verify success
- If pre-commit hook fails, fix the issue and create a NEW commit
- Check current directory - may need to `cd` back to plugin directory after running tests

## Pull Request Creation

When creating PRs:

### 1. Understand Current State
Run in parallel:
- `git status` (never use -uall flag)
- `git diff` for staged/unstaged changes
- Check if branch tracks remote and is up to date
- `git log` and `git diff [base-branch]...HEAD` to see ALL commits in the PR

### 2. Draft PR Summary
Analyze ALL changes (not just latest commit) and create summary.

### 3. Create PR
```bash
# Create branch if needed
# Push with -u if needed
git push -u jeremylenz <branch>

# Create PR
gh pr create --title "Title" --body "$(cat <<'EOF'
## Summary
<1-3 bullet points>

## Test plan
[Bulleted markdown checklist]

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**IMPORTANT**:
- Create PRs against personal fork, NEVER against upstream or origin
- When creating the pull request description, find and follow PULL_REQUEST_TEMPLATE.md if it exists
- PR description should outline manual testing steps that the PR reviewer can follow
- Keep the description concise and focused on user impact
- Return PR URL when done

## Project-Specific Preferences

### Foreman Plugin Development
- **Don't restart the Foreman server** - ask user to test instead
- If **Ruby code changed**: remind user to restart Foreman server for testing
- If **only JS code changed**: no server restart needed
- After running tests/lint from `/home/vagrant/foreman`, may need to `cd /home/vagrant/foreman_rh_cloud` to see branch changes

### Commands
All rake/rails commands must be run from Foreman directory (`/home/vagrant/foreman`) with `bundle exec` prefix.

## Do NOT Use
- TodoWrite or Task tools
- Additional code exploration commands
- Time estimates

## Always Include
- Co-Authored-By tag in commit messages
- Clear commit messages following repo style
- Explicit remote name when pushing

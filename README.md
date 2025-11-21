# Claude Code Configuration

This repository contains my portable Claude Code configuration for consistency across multiple machines.

## What's Included

- `CLAUDE.md` - Global instructions and preferences for Claude
- `settings.json` - General Claude Code settings
- `settings.local.json` - Bash command permissions whitelist
- `agents/` - Custom agent definitions

## Setup on a New Machine

1. **Install Claude Code** (if not already installed)

2. **Clone this repository** to your home directory:
   ```bash
   cd ~
   git clone https://github.com/jeremylenz/claude-config .claude
   ```

3. **Add your credentials** (not in version control):
   - Create `.credentials.json` in `~/.claude/` with your API credentials
   - This file is gitignored for security

4. **Verify the setup**:
   ```bash
   ls -la ~/.claude
   ```
   You should see the configuration files along with runtime directories that will be created as you use Claude Code.

## If .claude Directory Already Exists

If you already have a `.claude` directory on the new machine, you have several options:

### Option 1: Backup and Replace (Recommended)

This is the cleanest approach and preserves your credentials:

```bash
cd ~
mv .claude .claude.backup
git clone git@github.com:jeremylenz/claude-config.git .claude
# Copy credentials from backup
cp .claude.backup/.credentials.json .claude/
```

### Option 2: Initialize Git in Existing Directory

If you want to preserve local files and merge with the remote:

```bash
cd ~/.claude
git init
git remote add origin git@github.com:jeremylenz/claude-config.git
git fetch
git checkout -b main
git branch --set-upstream-to=origin/main main
git pull --rebase
```

Note: This may require resolving conflicts if your local files differ from the repository.

### Option 3: Clone to Temporary Location

If you want to manually review and copy files:

```bash
cd ~
git clone git@github.com:jeremylenz/claude-config.git claude-config-temp
# Manually copy desired files from claude-config-temp/ to .claude/
# Then delete the temporary directory
rm -rf claude-config-temp
```

## What's NOT Included

The following files/directories are excluded via `.gitignore` as they contain runtime data, session state, or sensitive information:

- `.credentials.json` - API credentials (must be added manually)
- `debug/`, `file-history/`, `history.jsonl` - Logs and history
- `plans/`, `projects/`, `todos/` - Session-specific data
- `session-env/`, `shell-snapshots/` - Runtime state
- `.update.lock` - Lock file

## Customization

Feel free to modify any configuration files to suit your workflow:

- Edit `CLAUDE.md` to add project-specific instructions
- Update `settings.json` for general preferences
- Modify `settings.local.json` to adjust bash command permissions
- Add custom agents in the `agents/` directory

## Syncing Changes

After making changes to configuration files:

```bash
cd ~/.claude
git add .
git commit -m "Update configuration"
git push
```

On other machines, pull the latest changes:

```bash
cd ~/.claude
git pull
```

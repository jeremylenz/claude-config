- Use push -u when it's the first time pushing to my remote
- Don't try to restart or start the foreman server; please just ask me to test instead
- Push explicitly to the remote. Don't just 'git push'.
- Our hot code reloading doesn't work well for Ruby. If you've changed Ruby code and want me to test in the browser, remind me to restart the Foreman server. If only JS code has changed, server restart is not needed.
- After running tests or lint, you may be in the Foreman directory, and you may need to switch back to the plugin directory in order to see our branch's changes.
- Don't use CVE as an abbreviation for content view environment(s). CVE always stands for Common Vulnerabilities and Exposures.
- Database schema is located in the Foreman directory, in db/structure.sql
- For code review replies: Be concise and conversational. Lead with a simple definition if introducing a concept. Focus on what happened (the narrative) rather than deep technical 
  details. Keep it to 2-4 sentences. Use simple explanations instead of listing specifics. Don't over-explain.

## Config repo sync

This ~/.claude directory is a git repo tracking git@github.com:jeremylenz/claude-config.git (main branch).

- The Vertex `env` block in settings.json is machine-specific and intentionally not committed. After cloning on a new machine, add it manually with the appropriate values for `CLAUDE_CODE_USE_VERTEX`, `CLOUD_ML_REGION`, and `ANTHROPIC_VERTEX_PROJECT_ID`.
- To sync local changes back to the repo: `git add . && git commit -m "description" && git push origin main` from ~/.claude
- settings.json will always show as locally modified (due to the env block). That's expected.
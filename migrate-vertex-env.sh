#!/usr/bin/env bash
set -euo pipefail

SETTINGS_FILE="$HOME/.claude/settings.json"
BASHRC="$HOME/.bashrc"
ENV_VARS=("CLAUDE_CODE_USE_VERTEX" "CLOUD_ML_REGION" "ANTHROPIC_VERTEX_PROJECT_ID")

if ! command -v jq &>/dev/null; then
  echo "Error: jq is required but not installed." >&2
  exit 1
fi

if [[ ! -f "$SETTINGS_FILE" ]]; then
  echo "No settings.json found at $SETTINGS_FILE — nothing to migrate."
  exit 0
fi

has_env_block=$(jq 'has("env")' "$SETTINGS_FILE")
if [[ "$has_env_block" != "true" ]]; then
  echo "No env block in settings.json — nothing to migrate."
  exit 0
fi

declare -A values
for var in "${ENV_VARS[@]}"; do
  val=$(jq -r --arg k "$var" '.env[$k] // empty' "$SETTINGS_FILE")
  if [[ -n "$val" ]]; then
    values[$var]="$val"
  fi
done

if [[ ${#values[@]} -eq 0 ]]; then
  echo "env block exists but contains no Vertex vars — nothing to migrate."
  exit 0
fi

echo "Found ${#values[@]} Vertex env var(s) in settings.json."

jq 'del(.env)' "$SETTINGS_FILE" > "$SETTINGS_FILE.tmp" && mv "$SETTINGS_FILE.tmp" "$SETTINGS_FILE"
echo "Removed env block from settings.json."

added=0
if ! grep -q "# Claude Code Vertex AI" "$BASHRC" 2>/dev/null; then
  {
    echo ""
    echo "# Claude Code Vertex AI"
    for var in "${ENV_VARS[@]}"; do
      if [[ -n "${values[$var]:-}" ]]; then
        echo "export ${var}=${values[$var]}"
      fi
    done
  } >> "$BASHRC"
  added=${#values[@]}
else
  for var in "${ENV_VARS[@]}"; do
    if [[ -n "${values[$var]:-}" ]] && ! grep -q "^export ${var}=" "$BASHRC" 2>/dev/null; then
      echo "export ${var}=${values[$var]}" >> "$BASHRC"
      ((added++))
    fi
  done
fi

if [[ $added -gt 0 ]]; then
  echo "Added $added export(s) to $BASHRC."
else
  echo "Exports already present in $BASHRC — no changes needed."
fi

echo ""
echo "Run 'source ~/.bashrc' or restart your shell to pick up the changes."

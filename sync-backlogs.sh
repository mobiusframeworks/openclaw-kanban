#!/bin/bash
# Sync Obsidian backlogs to GitHub for Kanban
# Run: ./sync-backlogs.sh

KANBAN_DIR="$HOME/Vaults/openclaw/bridge/kanban"
OBSIDIAN="$HOME/Vaults/openclaw/agents/memory"

echo "Syncing backlogs..."

cp "$OBSIDIAN/ceo/briefs/backlog.md" "$KANBAN_DIR/backlogs/bml-ceo.md" 2>/dev/null
cp "$OBSIDIAN/energyscout-ceo/backlog.md" "$KANBAN_DIR/backlogs/energyscout-ceo.md" 2>/dev/null
cp "$OBSIDIAN/realestate-ceo/backlog.md" "$KANBAN_DIR/backlogs/realestate-ceo.md" 2>/dev/null
cp "$OBSIDIAN/analytics/backlog.md" "$KANBAN_DIR/backlogs/analytics.md" 2>/dev/null
cp "$OBSIDIAN/assistant/backlog.md" "$KANBAN_DIR/backlogs/assistant.md" 2>/dev/null

cd "$KANBAN_DIR"
git add -A
git commit -m "Sync backlogs $(date '+%Y-%m-%d %H:%M')"
git push

echo "Done! Kanban will update in ~5 min (or click Refresh)"

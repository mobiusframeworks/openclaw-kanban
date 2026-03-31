---
tags: [kanban, tasks, index]
updated: $(date -Iseconds)
---

# 📋 Task Archive Index

This folder contains all tasks from the Cline Kanban board, synced to Obsidian for persistent history.

## Quick Stats
```dataview
TABLE 
    status as "Status",
    agent_name as "Agent",
    column as "Column"
FROM "bridge/kanban/tasks"
WHERE file.name != "index"
SORT updated DESC
LIMIT 20
```

## By Status
- [[#Backlog]] - Tasks waiting to be started
- [[#In Progress]] - Currently being worked on
- [[#Review]] - Needs review/blocked
- [[#Done]] - Completed tasks

## Recent Tasks
```dataview
LIST
FROM "bridge/kanban/tasks"
WHERE file.name != "index"
SORT updated DESC
LIMIT 10
```

## By Agent
```dataview
TABLE length(rows) as "Count"
FROM "bridge/kanban/tasks"
WHERE file.name != "index"
GROUP BY agent_name
```

---

## Sync Info
- **Source**: `~/.cline/kanban/workspaces/openclaw/board.json`
- **Sync Script**: `~/Vaults/openclaw/bridge/kanban/cline_sync.py`
- **Last Full Sync**: See individual task files

## How Tasks Flow
```
Backlog → In Progress → Review → Done/Trash
   ↑          ↓           ↓
   ←──────────←───────────←  (if blocked or needs rework)
```

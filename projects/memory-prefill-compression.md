# Memory Prefill Compression Problem

**Goal:** Reduce token costs and memory bloat by compressing agent context into routing keys.

## Backlog

- [ ] 1. Create SQLite router (`bridge/memory/router.db`)
  - Tables: tasks, routes, tools, embeddings
  - Index by task_id, agent, status

- [ ] 2. Create compress.py - key generator
  - Input: full task context
  - Output: ~100 token compressed key
  - Format: JSON with route hashes

- [ ] 3. Add key field to task structure
  - Update dashboard task model
  - Store key in localStorage + SQLite

- [ ] 4. Modify executor to pass keys
  - Replace full context with key
  - Add hydrate function for expansion

- [ ] 5. Create hydrate.py - key expander
  - Input: compressed key
  - Output: minimal context for agent
  - Query SQLite → load only needed files

- [ ] 6. Test with local LLM (Ollama)
  - Verify key routing works
  - Measure token reduction
  - Compare output quality

## Architecture

```
CLAUDE.md (Rules) → context.key (State) → SQLite Router → Obsidian Content
```

## Success Metrics
- 90%+ token reduction for routine tasks
- Same task completion rate
- Works with any LLM (local or cloud)

---
Created: 2026-03-29
Status: Backlog

---
doc_type: task
project: none
priority: 8
compression_level: L2-COOL
age_days: 5.4
tags: [task, L2-COOL]
spatial_x: 1774913886
spatial_y: 8.0
updated: 2026-04-05
---

# OpenClaw Command Center — Deep Design Critique

*March 30, 2026 — Benchmarked against Cline Kanban, KanVibe, Vibe Kanban, Linear, and emerging agentic AI UI patterns*

---

## Context

**What this is:** A single-page HTML dashboard ("OpenClaw Command Center") that orchestrates 5 autonomous AI agents via cron-scheduled jobs, manual task execution, and a human review loop. It combines a Kanban board, a timeline scheduler, a chat panel, and a CLI panel into one interface.

**Who it's for:** Alex — a solo operator managing multiple AI-powered businesses (BitcoinML, EnergyScout, Real Estate) through delegated AI agents running on a Mac Mini.

**The stated goals:** Timed agentic task management, delegation, transparency. The CLI is the command center.

**Stage:** Working prototype — functional but ready for a serious design pass.

---

## What the Competitors Are Doing (and What OpenClaw Should Steal)

### Cline Kanban

Cline's kanban board gives each task card its own dedicated terminal and ephemeral git worktree. The killer insight: **the card IS the terminal session**. You don't go to a separate panel to see what an agent is doing — you click the card and the terminal + diff viewer appear *inside* the card's detail view.

What Cline does that OpenClaw doesn't:

- **Hook-driven card updates**: As agents work, hooks push the latest message or tool call onto each card surface. You can monitor hundreds of agents at a glance without opening each one.
- **Inline diff review**: Click a card, see a GitHub-style diff of every change. Leave inline comments as if doing a PR review. The review loop is built into the board.
- **One card = one isolation context**: Each card gets its own worktree. In OpenClaw, the concept of isolation is weaker — tasks reference shared bot inboxes, not isolated environments.

**What to steal:** Surface the latest agent output directly ON the card. Don't hide it behind a click. The card should show a 2-line preview of what the agent last said or did.

### KanVibe

KanVibe uses a **5-stage flow** that's closer to what OpenClaw needs: TODO → PROGRESS → PENDING → REVIEW → DONE. The critical addition is **PENDING** — a liminal state between "the agent finished working" and "someone has looked at it." This maps perfectly to OpenClaw's cron jobs that complete overnight.

What KanVibe does differently:

- **Hook-driven auto-tracking**: Agent status transitions happen automatically via hooks, not manual drag. When a Claude Code session finishes, the card moves to REVIEW by itself.
- **Multiple terminal panes per card**: Each task's detail page supports configurable pane layouts (vim, htop, lazygit, test runner) — not just one terminal.
- **Automatic cleanup**: When a task moves to DONE, its branch, worktree, and terminal session are automatically deleted. The board stays clean.

**What to steal:** The PENDING state. OpenClaw's cron jobs finish and immediately appear in Review, but there's no signal about whether anyone has looked at them. Add a "Pending Review" state that auto-collects completed work, distinct from "Actively Being Reviewed."

### Linear

Linear's contribution isn't about agent management — it's about **visual polish and filtering power**.

- **Swimlanes**: Board views have optional swimlane rows (by team, assignee, cycle, initiative). OpenClaw's timeline has agent swimlanes, but the Kanban view doesn't. Adding swimlanes-by-agent to the Kanban would eliminate the need for the agent filter bar.
- **Collapsible lanes**: Swimlanes can be collapsed for visual clarity. Critical for a system with 5 agents.
- **Timeline redesign**: Linear's timeline shows Milestones as first-class objects with hover details and inline date adjustment. OpenClaw's timeline is time-slot-based, which works for a daily view but lacks the ability to zoom out to weekly/monthly.

**What to steal:** Swimlane rows in the Kanban view grouped by agent, with collapse/expand. This replaces the agent filter buttons with something more spatial and scannable.

### Vibe Kanban

Vibe Kanban has the cleanest separation of concerns: the **left panel is the board**, the **right panel is the agent workspace**. This split-screen pattern (documented as the emerging standard for agentic AI UIs) means you never lose context — you're always seeing both the "what" and the "how."

**What to steal:** The fixed split-screen layout. OpenClaw currently has the CLI/Chat as a collapsible bottom panel, which means the CLI competes with the board for vertical space. Making it a right-side panel (like Vibe Kanban) would give the CLI permanent visibility alongside the board.

### Emerging Agentic UI Patterns (Industry Consensus)

From Smashing Magazine, UXMatters, and Fuselab's 2026 research:

1. **Action Audit Log with Undo**: Every agent action should have a visible trace AND a prominent Undo button. This dramatically lowers the perceived risk of granting autonomy.

2. **Status Narration**: The interface must clearly narrate agent status ("Thinking…", "Searching the Web…", "Writing to outbox…") — not just show a spinner. OpenClaw's `execution-status` div does this partially, but it's buried inside the card.

3. **Behavioral Transparency Windows**: Clear windows into HOW an agent forms intentions, evaluates trade-offs, and selects actions. OpenClaw has none of this — the work log records outcomes, not reasoning.

4. **Progressive Delegation**: Start with low-autonomy tasks (review before execute) and let the user gradually increase trust per agent. OpenClaw's Eisenhower Matrix partially addresses this, but there's no per-agent trust level.

---

## The Core Problem: OpenClaw Is Three Apps Fighting for One Screen

The dashboard currently has:
1. A Kanban board (top, full width)
2. A Timeline scheduler (swappable with Kanban)
3. A Chat panel (bottom, fixed 280px)
4. A CLI panel (inside bottom panel, left side)

These four tools compete for viewport space, and the transitions between them are jarring. The Kanban and Timeline are mutually exclusive views. The Chat and CLI are jammed into a bottom drawer that steals 280px from the main content.

**The fix**: Adopt the split-screen pattern that Cline, Vibe Kanban, and the industry are converging on:

```
┌─────────────────────────────────────────────────────────┐
│  TOP NAV: Filters + Status + Actions                     │
├──────────────────────────┬──────────────────────────────┤
│                          │                              │
│   LEFT: Board / Timeline │   RIGHT: Agent Workspace     │
│   (the "What")           │   (the "How")                │
│                          │                              │
│   Kanban columns OR      │   CLI terminal output        │
│   Timeline swimlanes     │   Chat with selected agent   │
│                          │   Action trace / thought log  │
│                          │   Diff viewer for completed   │
│                          │                              │
├──────────────────────────┴──────────────────────────────┤
│  BOTTOM BAR: Mini status (collapsed by default)          │
└─────────────────────────────────────────────────────────┘
```

This layout means:
- **Board and CLI are always visible together** — "the CLI is the command center" becomes literally true
- **Clicking a task card updates the right panel** with that task's agent output, work log, and CLI session
- **No more view-switching** between Kanban and Timeline — Timeline becomes a sub-view within the left panel, or a layer on top of the Kanban (like Linear's board-to-timeline toggle)

---

## Detailed Findings

### 1. First Impression (2 seconds)

**What draws the eye:** The three filter bars at the top (nav, priority filter, agent filter) — that's 3 rows of navigation before any content. On a 1080p screen, these consume ~140px before you see a single task card.

**Emotional reaction:** Information-dense but directionless. There's a lot you CAN do, but no visual guidance about what you SHOULD do right now.

**Is the purpose clear?** Yes — it's obviously a task board. But the "command center" identity is buried. The CLI is hidden in a bottom drawer; the chat panel is collapsed by default. If the CLI is the command center, it should be the most prominent element, not the most hidden.

### 2. Usability

| Finding | Severity | Recommendation |
|---------|----------|----------------|
| **CLI is hidden in a collapsible bottom panel** — contradicts the goal of "CLI as command center" | 🔴 Critical | Move CLI to a permanent right-side panel (split-screen layout). Make it the default-open workspace when any task is selected. |
| **No live agent output on cards** — you have to click into a modal or check the CLI to see what an agent is doing. Cline and KanVibe both show the latest message on the card surface. | 🔴 Critical | Add a 2-line "last output" preview to each card in the Doing column. Use hooks or polling to keep it fresh. |
| **Three filter bars consume too much vertical space** — Priority filter, Agent filter, and Running dropdown are all separate bars | 🟡 Moderate | Combine into a single compact filter row: `[Priority: All Q1 Q2 Q3 Q4] [Agent: All BML ENE REA ANA ASS] [3 Running ▼]` |
| **Kanban and Timeline are mutually exclusive views** — but they represent different dimensions of the same data (what vs. when) | 🟡 Moderate | Make Timeline a layer within the Kanban, not a separate view. Or use Linear's approach: the board IS the kanban, with an optional timeline bar at the top showing today's schedule. |
| **No "what should I do right now?" signal** — the board shows everything equally | 🟡 Moderate | Add a "Next Up" highlight: the single highest-priority unblocked task should have a distinct visual treatment (glow, border, or pinned position). |
| **Modal-heavy interaction model** — editing a task, viewing details, adding tasks all require modals | 🟢 Minor | With a right-side panel, task details can appear inline without a modal. Modals should be reserved for destructive actions (delete, archive). |
| **No keyboard navigation** — everything requires mouse clicks | 🟢 Minor | Add j/k for up/down through cards, Enter to open detail, Esc to close. Arrow keys in timeline. This matters because "the CLI is the command center" implies a keyboard-first user. |

### 3. Visual Hierarchy

**What draws the eye first:** The green "+ Add Task" button in the top nav — correct for an empty board, wrong for a board with tasks. On a populated board, the eye should be drawn to **what's running right now**.

**Reading flow:** Top nav → Filter bars → Kanban columns left-to-right → (Bottom panel is below the fold on most screens). The left-to-right Kanban flow (Backlog → Doing → Review → Done) is the right reading order.

**What's missing:** There's no visual "now" indicator on the Kanban. The Timeline has a green "Now" column, but when you're on the Kanban view, you have no sense of time. For a system running cron jobs on a schedule, temporal context should be always-visible.

**Recommendation:** Add a persistent "Now" bar — a thin horizontal strip above the Kanban showing the current time, the next scheduled job, and what's currently executing. Like a TV guide "now and next" strip. Something like:

```
┌─────────────────────────────────────────────────────────┐
│ 3:37 PM  ● bml-content-pipeline running (2m)  │  Next: research-solar @ 3:00 PM  │  8/12 cron jobs done today │
└─────────────────────────────────────────────────────────┘
```

### 4. Consistency

| Element | Issue | Recommendation |
|---------|-------|----------------|
| **Column naming** | Review column maps to 3 internal statuses (blocked, ai-review, human-review) but has one header | Add sub-headers or section dividers within the Review column |
| **Card actions inconsistency** | Doing cards have "▶ Run" + "📅 Schedule". Review cards have "📋 Backlog" + "▶ Run Again" + "✓ Done" + "📝 Note". Different buttons in different columns with no visual consistency. | Standardize: every card gets the same action tray, but buttons are contextually shown/hidden. Use icons consistently. |
| **Cron job cards vs. manual task cards** | Cron jobs get `[CRON]` prefix and auto-assigned Q3 priority. Manual tasks look different. But both live in the same columns. | Give cron cards a distinct visual treatment — maybe a clock icon badge and a slightly different background tint — so they're instantly distinguishable from manual tasks. |
| **Agent filter vs. Bot status** | The agent filter bar shows BML/ENE/REA/ANA/ASS. The bot status shows ASS/BML/ENE/REA (different order, missing ANA). These are two representations of the same concept in two adjacent bars. | Merge them: each agent filter button should include its online/offline dot. |
| **Routing indicator missing** | The cron scheduler now routes between Claude and Ollama (force_cloud flag, task_router.py), and the execution log shows "ollama-completed:qwen2.5:7b" vs "started-claude". But the dashboard has zero visibility into which model executed a task. | Add a small model badge to completed task cards: "via Claude" or "via qwen2.5:7b". This is a transparency win. |

### 5. Accessibility

**Color contrast:** Muted text (#8b949e on #161b22) gives ~4.5:1 — barely AA for normal text, failing for the 10-11px sizes used on badges. The 9px text on `.progress-text` and `.priority-badge` is below minimum readable size.

**Touch targets:** Action buttons on cards (✓, ✎, ▶) are 24x24px — below the 44x44px WCAG recommendation. The timeline task controls (play/stop/review) are even smaller at ~20x20px.

**Text readability:** Line heights are adequate (1.4), but the truncation at 60 characters (`task.text.substring(0, 60)` in the parser) means many task names are cut mid-word.

**Keyboard navigation:** None. Tab doesn't move through cards. Arrow keys don't navigate the timeline. For a tool where "the CLI is the command center," the keyboard should be a first-class input.

### 6. The Routing/Transparency Gap

The system now has intelligent routing (task_router.py) that sends simple tasks to local Ollama models and complex ones to Claude. This is a major architectural feature that's completely invisible in the UI.

The execution log shows entries like:
```
test-routing-001 -> assistant: ollama-completed:qwen2.5:7b
test-routing-003 -> assistant: started-claude
```

But none of this surfaces in the dashboard. The user has no way to know:
- Which model ran a given task
- How long it took (latency_ms is in the outbox but not displayed)
- Whether the routing decision was correct
- The cost savings from local execution

**Recommendation:** Add a "Routing" badge or indicator to every completed task showing the model used, latency, and whether it was routed locally or to cloud. This is exactly the kind of transparency that builds trust in autonomous systems.

---

## What Works Well

- **The Eisenhower Matrix filter** is a smart prioritization layer that none of the competitors have. Cline, KanVibe, and Vibe Kanban are all flat priority systems.

- **The cron-to-review pipeline** (autoMovePastCronJobs) is genuinely novel. No other tool I researched auto-promotes completed scheduled work into a human review queue. This is the right pattern for autonomous agent oversight.

- **The chat-per-agent model** with the sidebar showing all bot sessions is well-designed. It's like having Telegram conversations with each agent inline.

- **The agent color system** is rock solid and consistent across every surface.

- **The detail modal with work log, artifacts, and review file generation** is sophisticated — it creates Obsidian-compatible markdown review files that link back to agent memory. This is a genuine workflow innovation.

- **The task_router integration** with Ollama fallback is architecturally excellent. Once surfaced in the UI, it'll be a differentiator.

---

## Priority Recommendations

### 1. Adopt the Split-Screen Layout — CLI as Right Panel

**Why:** This is the single highest-impact structural change. It makes "CLI as command center" literally true. Every competitor (Cline, Vibe Kanban, KanVibe) uses this pattern. The current bottom-drawer CLI is fighting the board for space.

**How:**
- Left 60%: Kanban board (or Timeline when toggled)
- Right 40%: Agent workspace (CLI output, chat, action trace, diff viewer)
- Clicking a card in the board updates the right panel to show that task's context
- The right panel tabs: Terminal | Chat | Action Log | Diff

### 2. Surface Agent Output on Card Faces

**Why:** Cline's hook-driven card updates are the gold standard. You should never need to click into a task to know what an agent is doing. The card surface should show the last line of output, current status narration ("Searching the web…", "Writing draft…"), and elapsed time.

**How:**
- Poll outbox every 5-10 seconds for executing tasks
- Show last 2 lines of output on the card face in monospace
- Add a "thinking…" / "writing…" / "searching…" status label
- Show elapsed time since execution started

### 3. Add the "Now Strip" — Temporal Context on Every View

**Why:** OpenClaw is fundamentally a time-based system (cron jobs run on schedule), but the Kanban view has zero temporal context. You don't know what's running, what just ran, or what's next without switching to the Timeline.

**How:** A persistent 40px strip below the filter bars showing: current time, currently executing tasks with elapsed time, next scheduled job, and today's cron completion rate (8/12 done). This strip is always visible regardless of Kanban/Timeline view.

### 4. Show the Routing Layer

**Why:** The Ollama/Claude routing is a differentiating feature and a trust-building transparency win. Users of autonomous systems want to know HOW their agents executed, not just that they did.

**How:** Add a small badge to completed cards showing the execution model (🟢 qwen2.5:7b local, ☁️ Claude cloud), latency, and whether force_cloud was set. Add a daily summary to the cron report: "12 jobs today: 5 local (avg 340ms), 7 cloud."

### 5. Collapse the Filter Bars

**Why:** 140px of navigation before any content is too much. The three rows (nav, priority, agent) can be one.

**How:** Merge priority pills and agent filters into a single row. Move the bot status indicators INTO the agent filter buttons (each button shows its online dot). Move "Running" count into the nav bar next to the executor status.

---

## Competitive Positioning

OpenClaw occupies a unique niche: it's not a coding agent orchestrator (like Cline/KanVibe/Vibe Kanban) — it's a **business operations orchestrator** for a solo entrepreneur running multiple AI-powered businesses. The competitors focus on code diffs and worktrees. OpenClaw focuses on content pipelines, lead generation, research scans, and daily briefings.

This means OpenClaw should lean into:
- **Business outcome visibility** (not code diffs) — show metrics, lead counts, content published
- **Daily rhythm** (the cron schedule as a first-class visual element, not a hidden tab)
- **Cross-agent coordination** (BML research feeding into EnergyScout content, analytics informing all CEOs)
- **The human review loop** as the primary interaction pattern (not "writing code alongside agents")

The Review column is where Alex lives. Make it the best column.

---

*Analysis based on: dashboard.html (current), jobs.json (15 jobs), cron_scheduler.py (with task_router), executor.py, execution.log, and competitive research of Cline Kanban, KanVibe, Vibe Kanban, Linear, and 2026 agentic UI design patterns.*

#!/usr/bin/env python3
"""
Priority Manager for OpenClaw Kanban

Manages task priorities and dependencies for the Cline Kanban board.
Provides CLI for setting priorities and viewing task relationships.

Usage:
    python priority_manager.py list                    # List all tasks with priorities
    python priority_manager.py set <task_id> <priority>  # Set task priority (high/med/low)
    python priority_manager.py deps <task_id>          # Show task dependencies
    python priority_manager.py block <task_id> <blocked_by>  # Add dependency
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

BOARD_PATH = Path.home() / ".cline/kanban/workspaces/openclaw/board.json"
PRIORITIES_PATH = Path.home() / "Vaults/openclaw/bridge/kanban/priorities.json"

PRIORITY_LEVELS = {
    'high': {'emoji': '🔴', 'weight': 3, 'keywords': ['urgent', 'critical', 'asap', 'blocker', '!']},
    'med': {'emoji': '🟡', 'weight': 2, 'keywords': ['next', 'soon', 'needed', 'should']},
    'low': {'emoji': '🟢', 'weight': 1, 'keywords': []},
}


def load_board():
    """Load the Cline kanban board."""
    if BOARD_PATH.exists():
        return json.loads(BOARD_PATH.read_text())
    return {"columns": [], "dependencies": []}


def save_board(board):
    """Save the Cline kanban board."""
    BOARD_PATH.write_text(json.dumps(board, indent=2))


def load_priorities():
    """Load priority overrides."""
    if PRIORITIES_PATH.exists():
        return json.loads(PRIORITIES_PATH.read_text())
    return {"priorities": {}, "dependencies": {}, "updated": None}


def save_priorities(data):
    """Save priority overrides."""
    data["updated"] = datetime.now().isoformat()
    PRIORITIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRIORITIES_PATH.write_text(json.dumps(data, indent=2))


def infer_priority(prompt):
    """Infer priority from task prompt keywords."""
    prompt_lower = prompt.lower()
    for level, config in PRIORITY_LEVELS.items():
        for kw in config['keywords']:
            if kw in prompt_lower:
                return level
    return 'low'


def get_task_priority(task_id, prompt, priority_overrides):
    """Get effective priority for a task (override > inferred)."""
    if task_id in priority_overrides:
        return priority_overrides[task_id]
    return infer_priority(prompt)


def list_tasks():
    """List all tasks with their priorities."""
    board = load_board()
    priorities_data = load_priorities()
    priority_overrides = priorities_data.get("priorities", {})
    dependencies = priorities_data.get("dependencies", {})

    print("=" * 70)
    print("OpenClaw Kanban - Task Priorities")
    print("=" * 70)

    for col in board.get("columns", []):
        col_id = col.get("id", "")
        if col_id == "trash":
            continue

        print(f"\n### {col.get('title', col_id)} ({len(col.get('cards', []))})")
        print("-" * 50)

        # Sort by priority weight
        cards = col.get("cards", [])
        sorted_cards = sorted(cards, key=lambda c: -PRIORITY_LEVELS.get(
            get_task_priority(c.get("id"), c.get("prompt", ""), priority_overrides),
            {"weight": 1}
        ).get("weight", 1))

        for card in sorted_cards[:15]:
            task_id = card.get("id", "???")
            short_id = task_id[:8] if len(task_id) > 8 else task_id
            prompt = card.get("prompt", "")[:50]

            priority = get_task_priority(task_id, card.get("prompt", ""), priority_overrides)
            emoji = PRIORITY_LEVELS[priority]["emoji"]

            # Check dependencies
            blocked_by = dependencies.get(task_id, [])
            dep_marker = f" [blocked by: {', '.join(blocked_by[:2])}]" if blocked_by else ""

            is_override = task_id in priority_overrides
            override_marker = " *" if is_override else ""

            print(f"{emoji} [{short_id}] {prompt}{override_marker}{dep_marker}")

        if len(cards) > 15:
            print(f"   ...and {len(cards) - 15} more")

    print("\n" + "=" * 70)
    print("* = manually set priority")
    print("Priorities: 🔴 HIGH  🟡 MED  🟢 LOW")


def set_priority(task_id, priority):
    """Set priority for a task."""
    if priority not in PRIORITY_LEVELS:
        print(f"Invalid priority: {priority}")
        print(f"Valid options: {', '.join(PRIORITY_LEVELS.keys())}")
        return False

    # Find the task
    board = load_board()
    found = False
    task_prompt = ""

    for col in board.get("columns", []):
        for card in col.get("cards", []):
            if card.get("id", "").startswith(task_id) or task_id in card.get("id", ""):
                found = True
                task_id = card.get("id")  # Use full ID
                task_prompt = card.get("prompt", "")[:40]
                break
        if found:
            break

    if not found:
        print(f"Task not found: {task_id}")
        return False

    # Save priority override
    priorities_data = load_priorities()
    priorities_data["priorities"][task_id] = priority
    save_priorities(priorities_data)

    emoji = PRIORITY_LEVELS[priority]["emoji"]
    print(f"Set priority: {emoji} {priority.upper()} for [{task_id[:8]}] {task_prompt}")
    return True


def show_dependencies(task_id):
    """Show dependencies for a task."""
    priorities_data = load_priorities()
    dependencies = priorities_data.get("dependencies", {})

    # Find tasks this one blocks
    blocks = []
    for tid, blocked_by in dependencies.items():
        if task_id in blocked_by or any(task_id in b for b in blocked_by):
            blocks.append(tid)

    # Find tasks that block this one
    blocked_by = []
    for tid, deps in dependencies.items():
        if task_id in tid or any(task_id in d for d in deps):
            blocked_by = deps
            break

    print(f"Dependencies for: {task_id}")
    print("-" * 40)

    if blocked_by:
        print(f"Blocked by: {', '.join(blocked_by)}")
    else:
        print("Blocked by: (none)")

    if blocks:
        print(f"Blocks: {', '.join(blocks)}")
    else:
        print("Blocks: (none)")


def add_dependency(task_id, blocked_by):
    """Add a dependency (task_id is blocked by blocked_by)."""
    priorities_data = load_priorities()

    if "dependencies" not in priorities_data:
        priorities_data["dependencies"] = {}

    # Find full task IDs
    board = load_board()
    full_task_id = None
    full_blocked_by = None

    for col in board.get("columns", []):
        for card in col.get("cards", []):
            cid = card.get("id", "")
            if task_id in cid:
                full_task_id = cid
            if blocked_by in cid:
                full_blocked_by = cid

    if not full_task_id:
        print(f"Task not found: {task_id}")
        return False
    if not full_blocked_by:
        print(f"Blocker task not found: {blocked_by}")
        return False

    if full_task_id not in priorities_data["dependencies"]:
        priorities_data["dependencies"][full_task_id] = []

    if full_blocked_by not in priorities_data["dependencies"][full_task_id]:
        priorities_data["dependencies"][full_task_id].append(full_blocked_by)

    save_priorities(priorities_data)
    print(f"Added dependency: [{full_task_id[:8]}] is blocked by [{full_blocked_by[:8]}]")
    return True


def main():
    parser = argparse.ArgumentParser(description='Manage kanban task priorities')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # List command
    subparsers.add_parser('list', help='List all tasks with priorities')

    # Set command
    set_parser = subparsers.add_parser('set', help='Set task priority')
    set_parser.add_argument('task_id', help='Task ID (or prefix)')
    set_parser.add_argument('priority', choices=['high', 'med', 'low'], help='Priority level')

    # Deps command
    deps_parser = subparsers.add_parser('deps', help='Show task dependencies')
    deps_parser.add_argument('task_id', help='Task ID (or prefix)')

    # Block command
    block_parser = subparsers.add_parser('block', help='Add dependency')
    block_parser.add_argument('task_id', help='Task that is blocked')
    block_parser.add_argument('blocked_by', help='Task that blocks it')

    args = parser.parse_args()

    if args.command == 'list' or args.command is None:
        list_tasks()
    elif args.command == 'set':
        set_priority(args.task_id, args.priority)
    elif args.command == 'deps':
        show_dependencies(args.task_id)
    elif args.command == 'block':
        add_dependency(args.task_id, args.blocked_by)


if __name__ == '__main__':
    main()

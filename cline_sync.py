#!/usr/bin/env python3
"""
Bidirectional Sync Service: Cline Kanban <-> OpenClaw Kanban

Syncs tasks between:
- Cline: ~/.cline/kanban/workspaces/openclaw/board.json
- OpenClaw: ~/Vaults/openclaw/bridge/kanban/tasks.json

Also pushes OpenClaw agent activity into Cline's hook system for real-time visibility.

Usage:
    python cline_sync.py              # Run sync service
    python cline_sync.py --once       # Run single sync and exit
    python cline_sync.py --status     # Show sync status
"""

import json
import subprocess
import time
import hashlib
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Configuration
CLINE_WORKSPACE = Path.home() / ".cline/kanban/workspaces/openclaw"
CLINE_BOARD = CLINE_WORKSPACE / "board.json"
CLINE_SESSIONS = CLINE_WORKSPACE / "sessions.json"
OPENCLAW_TASKS = Path.home() / "Vaults/openclaw/bridge/kanban/tasks.json"
OPENCLAW_API = "http://localhost:8765"
KANBAN_CLI = "/opt/homebrew/bin/kanban"
SYNC_STATE_FILE = Path(__file__).parent / "sync_state.json"
LOG_FILE = Path(__file__).parent / "sync.log"
OBSIDIAN_TASKS_DIR = Path.home() / "Vaults/openclaw/bridge/kanban/tasks"

# Polling intervals (seconds)
POLL_INTERVAL = 5
ACTIVITY_POLL_INTERVAL = 3

# Status mapping: OpenClaw -> Cline column
STATUS_TO_COLUMN = {
    'todo': 'backlog',
    'progress': 'in_progress',
    'executing': 'in_progress',
    'in_progress': 'in_progress',
    'blocked': 'review',
    'ai-review': 'review',
    'human-review': 'review',
    'done': 'trash',  # Completed tasks go to trash in Cline
}

# Reverse mapping: Cline column -> OpenClaw status
COLUMN_TO_STATUS = {
    'backlog': 'todo',
    'in_progress': 'progress',
    'review': 'blocked',
    'trash': 'done',
}

# Agent mapping: OpenClaw short codes to display names
AGENT_NAMES = {
    'bml': 'Bitcoin ML',
    'ene': 'EnergyScout',
    'rea': 'Real Estate',
    'ana': 'Analytics',
    'ass': 'Assistant',
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Obsidian sync configuration
STATUS_EMOJI = {'todo': '📋', 'progress': '🔄', 'blocked': '🚫', 'done': '✅', 'executing': '⚡', 'backlog': '📋'}


def save_task_to_obsidian(task: Dict, column_id: str) -> Optional[Path]:
    """Save a Cline task card to Obsidian as markdown for history tracking."""
    try:
        OBSIDIAN_TASKS_DIR.mkdir(parents=True, exist_ok=True)

        task_id = task.get('id', 'unknown')
        prompt = task.get('prompt', 'Untitled Task')
        openclaw = task.get('_openclaw', {})
        agent = openclaw.get('agent', 'ass')
        status = COLUMN_TO_STATUS.get(column_id, openclaw.get('status', 'todo'))

        # Parse agent from prompt prefix like "[Bitcoin ML]"
        if prompt.startswith('['):
            bracket_end = prompt.find(']')
            if bracket_end > 0:
                agent_hint = prompt[1:bracket_end].lower().replace(' ', '')
                if 'bitcoin' in agent_hint or 'bml' in agent_hint:
                    agent = 'bml'
                elif 'energy' in agent_hint:
                    agent = 'ene'
                elif 'real' in agent_hint:
                    agent = 'rea'
                elif 'analytics' in agent_hint:
                    agent = 'ana'
                elif 'assistant' in agent_hint:
                    agent = 'ass'

        created_ts = task.get('createdAt', 0)
        created = datetime.fromtimestamp(created_ts / 1000).isoformat() if created_ts else datetime.now().isoformat()

        md = f"""---
id: {task_id}
agent: {agent}
agent_name: {AGENT_NAMES.get(agent, 'Assistant')}
status: {status}
column: {column_id}
created: {created}
updated: {datetime.now().isoformat()}
source: cline_kanban
---

# {STATUS_EMOJI.get(status, '📋')} {prompt}

## Overview
| Field | Value |
|-------|-------|
| **Status** | {status.upper()} |
| **Column** | {column_id} |
| **Agent** | {AGENT_NAMES.get(agent, 'Assistant')} |
| **Base Ref** | {task.get('baseRef', 'main')} |
| **Auto Review** | {'✅' if task.get('autoReviewEnabled') else '❌'} |

## Task Details
- **Plan Mode**: {task.get('startInPlanMode', False)}
- **Auto Review Mode**: {task.get('autoReviewMode', 'commit')}

---
*Synced from Cline Kanban at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

        filepath = OBSIDIAN_TASKS_DIR / f"{task_id}.md"
        filepath.write_text(md)
        return filepath
    except Exception as e:
        logger.error(f"Failed to save task {task.get('id')} to Obsidian: {e}")
        return None


def sync_board_to_obsidian() -> int:
    """Sync all tasks from Cline board to Obsidian vault."""
    try:
        board = load_cline_board()
        synced = 0
        for column in board.get('columns', []):
            column_id = column.get('id', 'unknown')
            for card in column.get('cards', []):
                if save_task_to_obsidian(card, column_id):
                    synced += 1
        logger.info(f"Synced {synced} tasks to Obsidian")
        return synced
    except Exception as e:
        logger.error(f"Obsidian sync failed: {e}")
        return 0


class SyncState:
    """Tracks sync state to detect changes and avoid conflicts."""

    def __init__(self):
        self.cline_hash: str = ""
        self.openclaw_hash: str = ""
        self.last_sync: str = ""
        self.synced_ids: Dict[str, str] = {}  # openclaw_id -> cline_id
        self.load()

    def load(self):
        if SYNC_STATE_FILE.exists():
            try:
                data = json.loads(SYNC_STATE_FILE.read_text())
                self.cline_hash = data.get('cline_hash', '')
                self.openclaw_hash = data.get('openclaw_hash', '')
                self.last_sync = data.get('last_sync', '')
                self.synced_ids = data.get('synced_ids', {})
            except Exception as e:
                logger.warning(f"Failed to load sync state: {e}")

    def save(self):
        try:
            SYNC_STATE_FILE.write_text(json.dumps({
                'cline_hash': self.cline_hash,
                'openclaw_hash': self.openclaw_hash,
                'last_sync': datetime.now().isoformat(),
                'synced_ids': self.synced_ids,
            }, indent=2))
        except Exception as e:
            logger.error(f"Failed to save sync state: {e}")

    def compute_hash(self, data: Any) -> str:
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


def load_cline_board() -> Dict:
    """Load Cline kanban board."""
    if not CLINE_BOARD.exists():
        return {"columns": [
            {"id": "backlog", "title": "Backlog", "cards": []},
            {"id": "in_progress", "title": "In Progress", "cards": []},
            {"id": "review", "title": "Review", "cards": []},
            {"id": "trash", "title": "Trash", "cards": []},
        ], "dependencies": []}

    try:
        return json.loads(CLINE_BOARD.read_text())
    except Exception as e:
        logger.error(f"Failed to load Cline board: {e}")
        return {"columns": [], "dependencies": []}


def save_cline_board(board: Dict):
    """Save Cline kanban board."""
    try:
        CLINE_WORKSPACE.mkdir(parents=True, exist_ok=True)
        CLINE_BOARD.write_text(json.dumps(board, indent=2))
    except Exception as e:
        logger.error(f"Failed to save Cline board: {e}")


def load_openclaw_tasks() -> Dict:
    """Load OpenClaw tasks."""
    if not OPENCLAW_TASKS.exists():
        return {"tasks": []}

    try:
        return json.loads(OPENCLAW_TASKS.read_text())
    except Exception as e:
        logger.error(f"Failed to load OpenClaw tasks: {e}")
        return {"tasks": []}


def save_openclaw_tasks(tasks_data: Dict):
    """Save OpenClaw tasks."""
    try:
        tasks_data['updated'] = datetime.now().isoformat()
        OPENCLAW_TASKS.write_text(json.dumps(tasks_data, indent=2))
    except Exception as e:
        logger.error(f"Failed to save OpenClaw tasks: {e}")


def openclaw_to_cline_card(task: Dict) -> Dict:
    """Convert OpenClaw task to Cline card format."""
    agent = task.get('agent', 'ass')
    agent_name = AGENT_NAMES.get(agent, agent)

    # Build prompt from task text and agent info
    prompt = f"[{agent_name}] {task.get('text', 'Untitled')}"
    if task.get('notes'):
        prompt += f"\n\nNotes: {task['notes']}"

    card = {
        'id': task['id'],
        'prompt': prompt,
        'startInPlanMode': False,
        'autoReviewEnabled': False,
        'autoReviewMode': 'commit',
        'baseRef': 'main',
        'createdAt': int(datetime.fromisoformat(task.get('created', datetime.now().isoformat())).timestamp() * 1000) if task.get('created') else int(time.time() * 1000),
        'updatedAt': int(time.time() * 1000),
        # Store OpenClaw metadata
        '_openclaw': {
            'agent': agent,
            'quadrant': task.get('quadrant', 'q2'),
            'status': task.get('status', 'todo'),
            'scheduled': task.get('scheduled', False),
            'tags': task.get('tags', []),
        }
    }

    return card


def cline_card_to_openclaw(card: Dict, column: str) -> Dict:
    """Convert Cline card to OpenClaw task format."""
    # Extract agent from prompt if present
    prompt = card.get('prompt', '')
    agent = 'ass'  # Default
    text = prompt

    # Try to parse agent from [AgentName] prefix
    if prompt.startswith('['):
        end = prompt.find(']')
        if end > 0:
            agent_str = prompt[1:end]
            # Reverse lookup agent code
            for code, name in AGENT_NAMES.items():
                if name.lower() == agent_str.lower():
                    agent = code
                    break
            text = prompt[end+1:].strip()

    # Get existing metadata if present
    openclaw_meta = card.get('_openclaw', {})

    task = {
        'id': card['id'],
        'text': text,
        'agent': openclaw_meta.get('agent', agent),
        'quadrant': openclaw_meta.get('quadrant', 'q2'),
        'status': COLUMN_TO_STATUS.get(column, 'todo'),
        'scheduled': openclaw_meta.get('scheduled', False),
        'tags': openclaw_meta.get('tags', []),
        'created': datetime.fromtimestamp(card.get('createdAt', time.time() * 1000) / 1000).isoformat(),
    }

    # Extract notes from prompt if present
    if '\n\nNotes:' in prompt:
        notes_start = prompt.find('\n\nNotes:')
        task['notes'] = prompt[notes_start + 8:].strip()

    return task


def sync_openclaw_to_cline(state: SyncState):
    """Sync OpenClaw tasks to Cline board."""
    openclaw_data = load_openclaw_tasks()
    cline_board = load_cline_board()

    openclaw_tasks = openclaw_data.get('tasks', [])

    # Build index of existing Cline cards by ID
    cline_cards_by_id = {}
    for col in cline_board.get('columns', []):
        for card in col.get('cards', []):
            cline_cards_by_id[card['id']] = (card, col['id'])

    changes = 0

    for task in openclaw_tasks:
        task_id = task.get('id')
        if not task_id:
            continue

        # Skip cron jobs and internal tasks
        if task_id.startswith('cron-'):
            continue

        # Determine target column
        status = task.get('status', 'todo')
        target_column = STATUS_TO_COLUMN.get(status, 'backlog')

        if task_id in cline_cards_by_id:
            # Card exists - check if it needs to move columns
            existing_card, current_column = cline_cards_by_id[task_id]

            if current_column != target_column:
                # Move card to new column
                for col in cline_board['columns']:
                    if col['id'] == current_column:
                        col['cards'] = [c for c in col['cards'] if c['id'] != task_id]
                    if col['id'] == target_column:
                        # Update card data and add to new column
                        updated_card = openclaw_to_cline_card(task)
                        col['cards'].append(updated_card)
                        changes += 1
                        logger.info(f"Moved card {task_id} from {current_column} to {target_column}")
        else:
            # New card - add to appropriate column
            new_card = openclaw_to_cline_card(task)
            for col in cline_board['columns']:
                if col['id'] == target_column:
                    col['cards'].append(new_card)
                    changes += 1
                    logger.info(f"Added new card {task_id} to {target_column}")
                    break

            # Track sync mapping
            state.synced_ids[task_id] = task_id

    if changes > 0:
        save_cline_board(cline_board)
        logger.info(f"Synced {changes} changes from OpenClaw to Cline")

    return changes


def sync_cline_to_openclaw(state: SyncState):
    """Sync Cline board changes to OpenClaw."""
    cline_board = load_cline_board()
    openclaw_data = load_openclaw_tasks()

    openclaw_tasks = openclaw_data.get('tasks', [])
    openclaw_by_id = {t['id']: t for t in openclaw_tasks}

    changes = 0

    for col in cline_board.get('columns', []):
        column_id = col.get('id')
        for card in col.get('cards', []):
            card_id = card.get('id')
            if not card_id:
                continue

            # Skip internal Cline tasks (worktree IDs like 'bbe76')
            if len(card_id) <= 6 and card_id.isalnum():
                continue

            expected_status = COLUMN_TO_STATUS.get(column_id, 'todo')

            if card_id in openclaw_by_id:
                # Task exists - check if status changed
                existing_task = openclaw_by_id[card_id]
                current_status = existing_task.get('status', 'todo')

                # Map both to comparable values
                current_mapped = STATUS_TO_COLUMN.get(current_status, 'backlog')

                if current_mapped != column_id:
                    # Status changed in Cline - update OpenClaw
                    existing_task['status'] = expected_status
                    existing_task['updated'] = datetime.now().isoformat()

                    # Add work log entry
                    if 'workLog' not in existing_task:
                        existing_task['workLog'] = []
                    existing_task['workLog'].append({
                        'timestamp': datetime.now().strftime('%m/%d/%Y, %I:%M:%S %p'),
                        'content': f'Moved to {expected_status} via Cline sync',
                        'type': 'move'
                    })

                    changes += 1
                    logger.info(f"Updated task {card_id} status to {expected_status} from Cline")
            else:
                # New task from Cline - create in OpenClaw
                new_task = cline_card_to_openclaw(card, column_id)
                openclaw_tasks.append(new_task)
                changes += 1
                logger.info(f"Created new OpenClaw task {card_id} from Cline")

    if changes > 0:
        openclaw_data['tasks'] = openclaw_tasks
        save_openclaw_tasks(openclaw_data)
        logger.info(f"Synced {changes} changes from Cline to OpenClaw")

    return changes


def push_activity_to_cline(activity: Dict):
    """Push OpenClaw agent activity to Cline via hooks."""
    agents = activity.get('agents', {})

    for agent_name, agent_info in agents.items():
        if agent_info.get('status') in ['working', 'thinking']:
            activity_text = f"{AGENT_NAMES.get(agent_name, agent_name)}: {agent_info.get('status', 'active')}"

            # Get snippet of current output
            output = agent_info.get('current_output', '')
            if output:
                # Get last meaningful line
                lines = [l.strip() for l in output.strip().split('\n') if l.strip()]
                if lines:
                    last_line = lines[-1][:100]  # Limit length
                    activity_text = f"{AGENT_NAMES.get(agent_name, agent_name)}: {last_line}"

            try:
                # Use kanban CLI to push activity
                subprocess.run([
                    KANBAN_CLI, 'hooks', 'notify',
                    '--event', 'activity',
                    '--source', 'openclaw',
                    '--activity-text', activity_text,
                ], capture_output=True, timeout=5)
            except Exception as e:
                logger.debug(f"Failed to push activity: {e}")


def fetch_openclaw_activity() -> Optional[Dict]:
    """Fetch agent activity from OpenClaw API."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{OPENCLAW_API}/agent-activity", timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def run_sync_loop():
    """Main sync loop."""
    state = SyncState()
    logger.info("Starting Cline <-> OpenClaw sync service")
    logger.info(f"Cline board: {CLINE_BOARD}")
    logger.info(f"OpenClaw tasks: {OPENCLAW_TASKS}")

    last_activity_poll = 0

    while True:
        try:
            # Compute current hashes
            cline_board = load_cline_board()
            openclaw_data = load_openclaw_tasks()

            cline_hash = state.compute_hash(cline_board)
            openclaw_hash = state.compute_hash(openclaw_data)

            # Check for changes
            cline_changed = cline_hash != state.cline_hash
            openclaw_changed = openclaw_hash != state.openclaw_hash

            if cline_changed and not openclaw_changed:
                # Cline changed - sync to OpenClaw
                sync_cline_to_openclaw(state)
                state.cline_hash = cline_hash
                state.openclaw_hash = state.compute_hash(load_openclaw_tasks())
                state.save()

            elif openclaw_changed and not cline_changed:
                # OpenClaw changed - sync to Cline
                sync_openclaw_to_cline(state)
                state.openclaw_hash = openclaw_hash
                state.cline_hash = state.compute_hash(load_cline_board())
                state.save()

            elif cline_changed and openclaw_changed:
                # Both changed - last write wins (OpenClaw takes precedence)
                logger.warning("Both systems changed - OpenClaw takes precedence")
                sync_openclaw_to_cline(state)
                state.openclaw_hash = openclaw_hash
                state.cline_hash = state.compute_hash(load_cline_board())
                state.save()

            # Poll for agent activity less frequently
            now = time.time()
            if now - last_activity_poll > ACTIVITY_POLL_INTERVAL:
                activity = fetch_openclaw_activity()
                if activity:
                    push_activity_to_cline(activity)
                last_activity_poll = now

        except KeyboardInterrupt:
            logger.info("Shutting down sync service")
            state.save()
            break
        except Exception as e:
            logger.error(f"Sync error: {e}")

        time.sleep(POLL_INTERVAL)


def run_once():
    """Run a single sync cycle."""
    state = SyncState()
    logger.info("Running single sync cycle")

    # Sync both directions
    changes = sync_openclaw_to_cline(state)
    changes += sync_cline_to_openclaw(state)

    # Sync to Obsidian for history
    obsidian_synced = sync_board_to_obsidian()

    # Update state
    state.cline_hash = state.compute_hash(load_cline_board())
    state.openclaw_hash = state.compute_hash(load_openclaw_tasks())
    state.save()

    logger.info(f"Sync complete: {changes} changes, {obsidian_synced} tasks archived to Obsidian")
    return changes


def show_status():
    """Show current sync status."""
    state = SyncState()

    cline_board = load_cline_board()
    openclaw_data = load_openclaw_tasks()

    print("=" * 50)
    print("Cline <-> OpenClaw Sync Status")
    print("=" * 50)

    print(f"\nLast sync: {state.last_sync or 'Never'}")
    print(f"Synced IDs: {len(state.synced_ids)}")

    print(f"\nCline Board ({CLINE_BOARD}):")
    for col in cline_board.get('columns', []):
        print(f"  {col['title']}: {len(col.get('cards', []))} cards")

    print(f"\nOpenClaw Tasks ({OPENCLAW_TASKS}):")
    tasks = openclaw_data.get('tasks', [])
    by_status = {}
    for t in tasks:
        status = t.get('status', 'unknown')
        by_status[status] = by_status.get(status, 0) + 1
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count} tasks")

    # Check if executor is running
    try:
        import urllib.request
        with urllib.request.urlopen(f"{OPENCLAW_API}/status", timeout=2) as resp:
            print(f"\nOpenClaw Executor: Running")
    except Exception:
        print(f"\nOpenClaw Executor: Not running")

    print()


def main():
    parser = argparse.ArgumentParser(description='Bidirectional Cline <-> OpenClaw sync')
    parser.add_argument('--once', action='store_true', help='Run single sync and exit')
    parser.add_argument('--status', action='store_true', help='Show sync status')
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.once:
        run_once()
    else:
        run_sync_loop()


if __name__ == '__main__':
    main()

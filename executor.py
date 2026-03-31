#!/usr/bin/env python3
"""
Task Executor Server - Triggers autonomous actions from the dashboard.

Runs as a local server that the dashboard can call to:
1. Execute scheduled tasks
2. Write to bot inboxes (triggers tmux sessions)
3. Monitor results and update task status
4. Report back via JSON API

Usage: python executor.py
Runs on http://localhost:8765
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import subprocess
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import threading
import time

BRIDGE_DIR = Path(__file__).parent.parent
BOTS_DIR = BRIDGE_DIR / "bots"
JOBS_FILE = BRIDGE_DIR / "jobs.json"
TASKS_FILE = Path(__file__).parent / "tasks.json"

# Agent types with their preferred models and capabilities
AGENT_TYPES = {
    'general': {
        'name': 'General Assistant',
        'description': 'Versatile agent for most tasks',
        'local_model': 'qwen2.5:7b',
        'openrouter_model': 'nvidia/nemotron-3-super-120b-a12b:free',
        'claude_model': 'claude-sonnet',
        'color': '#58a6ff'
    },
    'code': {
        'name': 'Code Specialist',
        'description': 'Optimized for coding tasks',
        'local_model': 'qwen2.5-coder:7b',
        'openrouter_model': 'openai/gpt-oss-120b:free',
        'claude_model': 'claude-sonnet',
        'color': '#f0883e'
    },
    'research': {
        'name': 'Research Analyst',
        'description': 'Deep reasoning and analysis',
        'local_model': 'deepseek-r1:latest',
        'openrouter_model': 'qwen/qwen3-next-80b-a3b-instruct:free',
        'claude_model': 'claude-opus',
        'color': '#a371f7'
    },
    'fast': {
        'name': 'Quick Tasks',
        'description': 'Fast responses for simple tasks',
        'local_model': 'qwen2.5:3b',
        'openrouter_model': 'nvidia/nemotron-3-nano-30b-a3b:free',
        'claude_model': 'claude-haiku',
        'color': '#3fb950'
    }
}

# Track active parallel workers
ACTIVE_WORKERS = {}  # {worker_id: {task_id, agent_type, tmux_window, status, started_at}}

# Import task router for local model routing
try:
    from task_router import KanbanRouter
    ROUTER = KanbanRouter()
    ROUTER_AVAILABLE = ROUTER.check_ollama_health()
except ImportError:
    ROUTER = None
    ROUTER_AVAILABLE = False

class ExecutorHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self._send_json({})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/jobs':
            # Return all cron jobs
            jobs = load_jobs()
            self._send_json(jobs)

        elif path == '/tasks':
            # Return current task state
            tasks = load_tasks()
            self._send_json(tasks)

        elif path == '/status':
            # Check bot tmux sessions
            bots = ['assistant', 'bitcoinml', 'energyscout', 'realestate', 'analytics']
            status = {}
            for bot in bots:
                status[bot] = {
                    'tmux': check_tmux(bot),
                    'inbox': (BOTS_DIR / bot / 'inbox.md').exists(),
                    'outbox': read_outbox(bot)
                }
            # Also get all claude tmux sessions
            all_sessions = list_tmux_sessions()
            self._send_json({'bots': status, 'sessions': all_sessions, 'timestamp': datetime.now().isoformat()})

        elif path == '/agent-types':
            # Return available agent types
            self._send_json({'agent_types': AGENT_TYPES})

        elif path == '/workers':
            # List all active parallel workers
            result = list_workers()
            self._send_json(result)

        elif path == '/worker-output':
            # Get output from a specific worker
            params = parse_qs(parsed.query)
            worker_id = params.get('id', [''])[0]
            lines = int(params.get('lines', ['50'])[0])
            result = get_worker_output(worker_id, lines)
            self._send_json(result)

        elif path == '/outbox':
            # Get recent outbox messages
            params = parse_qs(parsed.query)
            bot = params.get('bot', ['assistant'])[0]
            content = read_outbox(bot)
            self._send_json({'bot': bot, 'content': content})

        elif path == '/inbox':
            # Get recent inbox messages (from Telegram, etc.)
            params = parse_qs(parsed.query)
            bot = params.get('bot', ['assistant'])[0]
            content = read_inbox(bot)
            self._send_json({'bot': bot, 'content': content})

        elif path == '/messages':
            # Get both inbox and outbox for full chat view
            params = parse_qs(parsed.query)
            bot = params.get('bot', ['assistant'])[0]
            inbox = read_inbox(bot)
            outbox = read_outbox(bot)
            self._send_json({'bot': bot, 'inbox': inbox, 'outbox': outbox})

        elif path == '/worktrees':
            # List git worktrees
            worktrees = list_worktrees()
            self._send_json({'worktrees': worktrees})

        elif path == '/daily-brief':
            # Return daily brief data for dashboard startup
            brief = get_daily_brief()
            self._send_json(brief)

        elif path == '/tmux-output':
            # Get real-time output from a bot's tmux session
            params = parse_qs(parsed.query)
            bot = params.get('bot', ['assistant'])[0]
            lines = int(params.get('lines', ['50'])[0])
            output = get_tmux_output(bot, lines)
            self._send_json({'bot': bot, 'output': output, 'timestamp': datetime.now().isoformat()})

        elif path == '/agent-activity':
            # Get detailed activity for all agents (for enhanced Doing view)
            activity = get_agent_activity()
            self._send_json(activity)

        elif path == '/job-status':
            # Get today's job completion status from cron.log
            status = get_job_status()
            self._send_json(status)

        elif path == '/routing-stats':
            # Get task routing statistics (local vs cloud)
            stats = get_routing_stats()
            self._send_json(stats)

        elif path == '/routing-check':
            # Check routing decision for a task without executing
            params = parse_qs(parsed.query)
            task_text = params.get('task', [''])[0]
            result = check_routing(task_text)
            self._send_json(result)

        else:
            self._send_json({'error': 'Unknown endpoint'}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        data = json.loads(body) if body else {}

        if path == '/execute':
            # Execute a task
            task_id = data.get('task_id')
            task_text = data.get('text', '')
            agent = data.get('agent', 'assistant')
            agent_type = data.get('agent_type', 'general')
            parallel = data.get('parallel', False)
            working_dir = data.get('working_dir')
            force_cloud = data.get('force_cloud', False)

            result = execute_task(task_id, task_text, agent, force_cloud, agent_type, parallel, working_dir)
            self._send_json(result)

        elif path == '/spawn-worker':
            # Spawn a parallel worker
            task_id = data.get('task_id')
            task_text = data.get('text', '')
            agent = data.get('agent', 'assistant')
            agent_type = data.get('agent_type', 'general')
            working_dir = data.get('working_dir')

            result = spawn_parallel_worker(task_id, task_text, agent, agent_type, working_dir)
            self._send_json(result)

        elif path == '/stop-worker':
            # Stop a parallel worker
            worker_id = data.get('worker_id')
            result = stop_worker(worker_id)
            self._send_json(result)

        elif path == '/run-job':
            # Run a cron job immediately
            job_name = data.get('job_name')
            result = run_job(job_name)
            self._send_json(result)

        elif path == '/update-task':
            # Update task status
            task_id = data.get('task_id')
            status = data.get('status')
            notes = data.get('notes', '')

            result = update_task(task_id, status, notes)
            self._send_json(result)

        elif path == '/save-tasks':
            # Save all tasks from dashboard
            tasks = data.get('tasks', [])
            save_tasks(tasks)
            self._send_json({'success': True, 'count': len(tasks)})

        elif path == '/create-task':
            # Create a new task (for agent delegation)
            result = create_task(data)
            self._send_json(result)

        elif path == '/update-worklog':
            # Add a work log entry to a task (for agent progress tracking)
            result = update_worklog(data)
            self._send_json(result)

        elif path == '/get-task':
            # Get a single task by ID (for agent context loading)
            task_id = data.get('task_id')
            result = get_task_by_id(task_id)
            self._send_json(result)

        elif path == '/save-to-vault':
            # Save file directly to Obsidian vault
            filename = data.get('filename')
            content = data.get('content')
            result = save_to_vault(filename, content)
            self._send_json(result)

        elif path == '/create-worktree':
            # Create a new git worktree for a task
            name = data.get('name')
            task = data.get('task', '')
            result = create_worktree(name, task)
            self._send_json(result)

        elif path == '/launch-agent':
            # Launch an agent in a worktree
            worktree = data.get('worktree')
            task_text = data.get('task', '')
            agent = data.get('agent', 'assistant')
            result = launch_agent_in_worktree(worktree, task_text, agent)
            self._send_json(result)

        elif path == '/launch-npx-kanban':
            # Launch npx kanban in a tmux session
            result = launch_npx_kanban()
            self._send_json(result)

        elif path == '/check-agent':
            # Have one agent check on another (cross-agent status check)
            checker = data.get('checker', 'assistant')  # The agent doing the checking
            target = data.get('target')  # The agent being checked on
            task_id = data.get('task_id')
            result = cross_agent_check(checker, target, task_id)
            self._send_json(result)

        elif path == '/tmux-send':
            # Send keys/command to a tmux session
            bot = data.get('bot', 'assistant')
            keys = data.get('keys', '')
            result = send_to_tmux(bot, keys)
            self._send_json(result)

        elif path == '/start-claude':
            # Start Claude with dangerous permissions for a specific bot/repo
            bot = data.get('bot', 'assistant')
            repo = data.get('repo', '')  # Optional custom repo path
            result = start_claude_session(bot, repo)
            self._send_json(result)

        elif path == '/save-cron-job':
            # Save or update a cron job
            job = data.get('job', {})
            result = save_cron_job(job)
            self._send_json(result)

        elif path == '/delete-cron-job':
            # Delete a cron job by name
            name = data.get('name', '')
            result = delete_cron_job(name)
            self._send_json(result)

        elif path == '/sync-from-cline':
            # Sync task from Cline kanban
            result = sync_from_cline(data)
            self._send_json(result)

        elif path == '/link-file':
            # Link a file or folder to a task
            result = link_file_to_task(data)
            self._send_json(result)

        else:
            self._send_json({'error': 'Unknown endpoint'}, 404)

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def load_jobs():
    """Load cron jobs."""
    if JOBS_FILE.exists():
        with open(JOBS_FILE) as f:
            return json.load(f)
    return {'jobs': []}


def load_tasks():
    """Load tasks from local storage."""
    if TASKS_FILE.exists():
        with open(TASKS_FILE) as f:
            return json.load(f)
    return {'tasks': []}


def save_tasks(tasks):
    """Save tasks to local storage."""
    with open(TASKS_FILE, 'w') as f:
        json.dump({'tasks': tasks, 'updated': datetime.now().isoformat()}, f, indent=2)


def create_task(data):
    """Create a new task from agent delegation.

    Expected data:
    - text: task description (required)
    - agent: 'bml', 'ene', 'rea', 'ana', 'ass' (default: 'ass')
    - status: 'todo', 'progress', 'blocked', 'done' (default: 'todo')
    - quadrant: 'q1', 'q2', 'q3', 'q4' (default: 'q2')
    - notes: additional notes
    - scheduledSlot: 0-8 for timeline placement (optional)
    """
    text = data.get('text', '').strip()
    if not text:
        return {'success': False, 'error': 'Task text is required'}

    # Agent mapping: full names to short codes
    agent_map = {
        'bitcoinml': 'bml', 'bml': 'bml',
        'energyscout': 'ene', 'ene': 'ene',
        'realestate': 'rea', 'rea': 'rea',
        'analytics': 'ana', 'ana': 'ana',
        'assistant': 'ass', 'ass': 'ass'
    }
    agent = agent_map.get(data.get('agent', 'assistant').lower(), 'ass')

    # Validate status
    valid_statuses = ['todo', 'progress', 'blocked', 'done']
    status = data.get('status', 'todo').lower()
    if status not in valid_statuses:
        status = 'todo'

    # Validate quadrant
    valid_quadrants = ['q1', 'q2', 'q3', 'q4']
    quadrant = data.get('quadrant', 'q2').lower()
    if quadrant not in valid_quadrants:
        quadrant = 'q2'

    # Create the task
    task = {
        'id': f'task-{int(datetime.now().timestamp() * 1000)}',
        'text': text,
        'agent': agent,
        'status': status,
        'quadrant': quadrant,
        'notes': data.get('notes', ''),
        'tags': data.get('tags', []),
        'created': datetime.now().isoformat(),
        'delegatedBy': data.get('delegatedBy', 'assistant'),
        'scheduled': data.get('scheduledSlot') is not None,
        'scheduledSlot': data.get('scheduledSlot', 4)  # Default to 'Today'
    }

    # Load existing tasks and append
    tasks_data = load_tasks()
    tasks_list = tasks_data.get('tasks', [])
    tasks_list.append(task)
    save_tasks(tasks_list)

    return {'success': True, 'task': task}


def update_worklog(data):
    """Add a work log entry to a task.

    Expected data:
    - task_id: ID of the task to update (required)
    - content: Log entry content (required)
    - type: Log type - 'progress', 'blocker', 'completed', 'note', 'files_modified', 'checkpoint' (default: 'progress')
    - files_modified: List of files that were modified (optional)
    - checkpoint: Summary of current state for resumption (optional)
    - next_steps: What should happen next (optional)
    """
    task_id = data.get('task_id')
    content = data.get('content', '').strip()

    if not task_id:
        return {'success': False, 'error': 'task_id is required'}
    if not content:
        return {'success': False, 'error': 'content is required'}

    tasks_data = load_tasks()
    tasks_list = tasks_data.get('tasks', [])

    task = next((t for t in tasks_list if t['id'] == task_id), None)
    if not task:
        return {'success': False, 'error': f'Task {task_id} not found'}

    # Initialize workLog if not present
    if 'workLog' not in task:
        task['workLog'] = []

    # Create the log entry with enhanced metadata
    log_entry = {
        'timestamp': datetime.now().strftime('%m/%d/%Y, %I:%M:%S %p'),
        'content': content,
        'type': data.get('type', 'progress')
    }

    # Add optional fields for AI resumption context
    if data.get('files_modified'):
        log_entry['filesModified'] = data['files_modified']
    if data.get('checkpoint'):
        log_entry['checkpoint'] = data['checkpoint']
    if data.get('next_steps'):
        log_entry['nextSteps'] = data['next_steps']
    if data.get('percent_complete') is not None:
        log_entry['percentComplete'] = data['percent_complete']

    task['workLog'].append(log_entry)

    # Update task status if specified
    if data.get('status'):
        task['status'] = data['status']

    # Update last checkpoint for easy resumption
    if data.get('checkpoint') or data.get('type') == 'checkpoint':
        task['lastCheckpoint'] = {
            'timestamp': log_entry['timestamp'],
            'summary': data.get('checkpoint', content),
            'nextSteps': data.get('next_steps', ''),
            'percentComplete': data.get('percent_complete', 0)
        }

    save_tasks(tasks_list)

    # Auto-save to Obsidian for persistence
    save_task_to_obsidian(task)

    return {'success': True, 'task_id': task_id, 'log_entry': log_entry}


def get_task_by_id(task_id):
    """Get a single task by ID with full context for AI resumption."""
    if not task_id:
        return {'success': False, 'error': 'task_id is required'}

    tasks_data = load_tasks()
    tasks_list = tasks_data.get('tasks', [])

    task = next((t for t in tasks_list if t['id'] == task_id), None)
    if not task:
        return {'success': False, 'error': f'Task {task_id} not found'}

    # Build resumption context
    resumption_context = None
    if task.get('lastCheckpoint'):
        resumption_context = task['lastCheckpoint']
    elif task.get('workLog') and len(task['workLog']) > 0:
        # Build context from recent work log entries
        recent_logs = task['workLog'][-5:]  # Last 5 entries
        resumption_context = {
            'recentActivity': [log['content'] for log in recent_logs],
            'lastUpdate': recent_logs[-1]['timestamp'] if recent_logs else None
        }

    return {
        'success': True,
        'task': task,
        'resumptionContext': resumption_context
    }


def save_task_to_obsidian(task):
    """Save task with full work log to Obsidian vault."""
    agent_names = {
        'bml': 'Bitcoin ML CEO', 'ene': 'EnergyScout CEO',
        'rea': 'Real Estate', 'ana': 'Analytics', 'ass': 'Assistant'
    }
    quadrant_names = {
        'q1': 'Urgent + Important', 'q2': 'Important (Strategic)',
        'q3': 'Urgent (Delegate)', 'q4': 'Low Priority'
    }
    status_emoji = {'todo': '📋', 'progress': '🔄', 'blocked': '🚫', 'done': '✅', 'executing': '⚡'}

    work_log_md = '_No work logged yet._'
    if task.get('workLog') and len(task['workLog']) > 0:
        work_log_md = '\n\n'.join([
            f"### {log.get('timestamp', 'Unknown time')}\n"
            f"**Type:** {log.get('type', 'note')}\n\n"
            f"{log.get('content', '')}\n"
            + (f"\n**Files Modified:** {', '.join(log['filesModified'])}" if log.get('filesModified') else '')
            + (f"\n**Checkpoint:** {log['checkpoint']}" if log.get('checkpoint') else '')
            + (f"\n**Next Steps:** {log['nextSteps']}" if log.get('nextSteps') else '')
            + (f"\n**Progress:** {log['percentComplete']}%" if log.get('percentComplete') is not None else '')
            for log in task['workLog']
        ])

    # Build resumption section
    resumption_md = '_No checkpoint saved._'
    if task.get('lastCheckpoint'):
        cp = task['lastCheckpoint']
        resumption_md = f"""**Last Checkpoint:** {cp.get('timestamp', 'Unknown')}
**Progress:** {cp.get('percentComplete', 0)}%

### Where We Left Off
{cp.get('summary', 'No summary')}

### Next Steps
{cp.get('nextSteps', 'No next steps defined')}"""

    md = f"""---
id: {task.get('id', 'unknown')}
agent: {task.get('agent', 'unknown')}
agent_name: {agent_names.get(task.get('agent'), task.get('agent', 'Unknown'))}
status: {task.get('status', 'unknown')}
quadrant: {task.get('quadrant', 'q2')}
tags: [{', '.join(task.get('tags', []))}]
created: {task.get('created', datetime.now().isoformat())}
updated: {datetime.now().isoformat()}
delegated_by: {task.get('delegatedBy', 'dashboard')}
vault_path: bridge/kanban/tasks/{task.get('id', 'unknown')}.md
---

# {status_emoji.get(task.get('status', 'todo'), '📋')} {task.get('text', 'Untitled Task')}

## Overview
| Field | Value |
|-------|-------|
| **Status** | {task.get('status', 'unknown').upper()} |
| **Agent** | {agent_names.get(task.get('agent'), task.get('agent', 'Unknown'))} |
| **Priority** | {quadrant_names.get(task.get('quadrant'), task.get('quadrant', 'Unknown'))} |
| **Created** | {task.get('created', 'Unknown')} |
| **Delegated By** | {task.get('delegatedBy', 'Dashboard')} |

## 🔄 Resumption Context (For AI Agents)
{resumption_md}

## Description & Notes
{task.get('notes', '_No notes yet._')}

## 📝 Work Log
{work_log_md}

## Related Files
{chr(10).join(['- [[' + f + ']]' for f in task.get('relatedFiles', [])]) or '_No related files linked._'}

## Artifacts & Links
{chr(10).join(['- [' + a.get('name', 'Link') + '](' + a.get('url', '#') + ')' for a in task.get('artifacts', [])]) or '_No artifacts attached._'}

---
*Last synced from OpenClaw Dashboard at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    filename = f"bridge/kanban/tasks/{task.get('id', 'unknown')}.md"
    save_to_vault(filename, md)


def check_tmux(bot_name):
    """Check if bot's tmux session is running."""
    session_name = f"claude-{bot_name}"
    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True
    )
    return result.returncode == 0


def list_tmux_sessions():
    """List all tmux sessions with claude in the name."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}:#{session_windows}:#{session_attached}"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return []

        sessions = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split(':')
            name = parts[0]
            sessions.append({
                'name': name,
                'windows': int(parts[1]) if len(parts) > 1 else 1,
                'attached': parts[2] == '1' if len(parts) > 2 else False,
                'is_claude': 'claude' in name.lower()
            })
        return sessions
    except Exception:
        return []


def read_outbox(bot_name):
    """Read bot's outbox."""
    outbox = BOTS_DIR / bot_name / 'outbox.md'
    if outbox.exists():
        content = outbox.read_text()
        # Get last 500 chars
        return content[-500:] if len(content) > 500 else content
    return ''


def read_inbox(bot_name):
    """Read bot's inbox (incoming messages from Telegram, etc.)."""
    inbox = BOTS_DIR / bot_name / 'inbox.md'
    if inbox.exists():
        content = inbox.read_text()
        # Get last 800 chars to capture recent messages
        return content[-800:] if len(content) > 800 else content
    return ''


def spawn_parallel_worker(task_id, task_text, agent, agent_type='general', working_dir=None):
    """Spawn a new parallel worker in a separate tmux window.

    Args:
        task_id: Task identifier
        task_text: Task description
        agent: Base bot name (assistant, bitcoinml, etc.)
        agent_type: Type of agent (general, code, research, fast)
        working_dir: Optional working directory for the worker

    Returns:
        dict with worker info
    """
    import uuid

    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    session_name = f"claude-{agent}"
    window_name = f"{agent_type}-{task_id[:8]}"

    # Get agent type config
    agent_config = AGENT_TYPES.get(agent_type, AGENT_TYPES['general'])

    # Create new tmux window in the agent's session
    try:
        # Check if session exists
        result = subprocess.run(
            ['tmux', 'has-session', '-t', session_name],
            capture_output=True
        )

        if result.returncode != 0:
            # Create session if it doesn't exist
            subprocess.run(
                ['tmux', 'new-session', '-d', '-s', session_name],
                capture_output=True
            )

        # Create new window
        cmd = ['tmux', 'new-window', '-t', session_name, '-n', window_name]
        if working_dir:
            cmd.extend(['-c', working_dir])
        subprocess.run(cmd, capture_output=True)

        # Start Claude in the new window with appropriate model hint
        model_hint = agent_config.get('claude_model', 'claude-sonnet')
        claude_cmd = f"claude --dangerously-skip-permissions"
        if working_dir:
            claude_cmd = f"cd {working_dir} && {claude_cmd}"

        subprocess.run([
            'tmux', 'send-keys', '-t', f"{session_name}:{window_name}",
            claude_cmd, 'Enter'
        ], capture_output=True)

        # Wait for Claude to start
        time.sleep(2)

        # Send the task
        subprocess.run([
            'tmux', 'send-keys', '-t', f"{session_name}:{window_name}",
            task_text, 'Enter'
        ], capture_output=True)

        # Track the worker
        ACTIVE_WORKERS[worker_id] = {
            'task_id': task_id,
            'agent': agent,
            'agent_type': agent_type,
            'session': session_name,
            'window': window_name,
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'working_dir': working_dir
        }

        return {
            'success': True,
            'worker_id': worker_id,
            'task_id': task_id,
            'agent_type': agent_type,
            'session': session_name,
            'window': window_name,
            'message': f'Spawned {agent_type} worker in {session_name}:{window_name}'
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_worker_output(worker_id, lines=50):
    """Get the current output from a parallel worker."""
    worker = ACTIVE_WORKERS.get(worker_id)
    if not worker:
        return {'success': False, 'error': 'Worker not found'}

    try:
        result = subprocess.run([
            'tmux', 'capture-pane', '-t', f"{worker['session']}:{worker['window']}",
            '-p', '-S', f'-{lines}'
        ], capture_output=True, text=True)

        return {
            'success': True,
            'worker_id': worker_id,
            'output': result.stdout,
            'status': worker['status']
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def stop_worker(worker_id):
    """Stop a parallel worker and close its window."""
    worker = ACTIVE_WORKERS.get(worker_id)
    if not worker:
        return {'success': False, 'error': 'Worker not found'}

    try:
        # Send Ctrl+C to stop current operation
        subprocess.run([
            'tmux', 'send-keys', '-t', f"{worker['session']}:{worker['window']}",
            'C-c'
        ], capture_output=True)

        time.sleep(0.5)

        # Close the window
        subprocess.run([
            'tmux', 'kill-window', '-t', f"{worker['session']}:{worker['window']}"
        ], capture_output=True)

        # Update tracking
        worker['status'] = 'stopped'
        del ACTIVE_WORKERS[worker_id]

        return {'success': True, 'message': f'Stopped worker {worker_id}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def list_workers():
    """List all active parallel workers."""
    workers = []
    for worker_id, info in ACTIVE_WORKERS.items():
        workers.append({
            'worker_id': worker_id,
            **info
        })
    return {'workers': workers, 'count': len(workers)}


def execute_task(task_id, task_text, agent, force_cloud=False, agent_type='general', parallel=False, working_dir=None):
    """Execute a task, routing to optimal model based on complexity.

    Routing tiers:
    1. Local Ollama (fastest, free, privacy-safe)
    2. OpenRouter Free (cloud, free tier models)
    3. Claude (most capable, for complex tasks via tmux)

    Args:
        task_id: Task identifier
        task_text: Task description/prompt
        agent: Bot name to execute on
        force_cloud: If True, skip local/openrouter and use Claude
        agent_type: Type of agent (general, code, research, fast)
        parallel: If True, spawn in a new tmux window for parallel execution
        working_dir: Optional working directory

    Returns:
        dict with execution result
    """
    # If parallel execution requested, spawn a new worker
    if parallel:
        return spawn_parallel_worker(task_id, task_text, agent, agent_type, working_dir)
    # Check routing decision
    if ROUTER_AVAILABLE and ROUTER and not force_cloud:
        routing = ROUTER.should_use_local(task_text, force_cloud=force_cloud)

        if routing.provider == "ollama":
            return _execute_ollama(task_id, task_text, agent, routing)
        elif routing.provider == "openrouter":
            return _execute_openrouter(task_id, task_text, agent, routing)

    # Fall through to Claude execution (complex tasks)
    return _execute_via_claude(task_id, task_text, agent)


def _execute_ollama(task_id, task_text, agent, routing):
    """Execute task on local Ollama model."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    system_prompt = """You are a helpful AI assistant. Complete the following task concisely and accurately.
Keep your response focused and under 500 words unless more detail is needed."""

    result = ROUTER.execute_local(task_text, routing.model, system_prompt)

    if not result.get('success'):
        log_execution(task_id, agent, f'ollama-failed:{routing.model}')
        return _execute_via_claude(task_id, task_text, agent)

    return _write_fast_result(task_id, task_text, agent, routing, result, "ollama")


def _execute_openrouter(task_id, task_text, agent, routing):
    """Execute task via OpenRouter free models."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    system_prompt = """You are a helpful AI assistant. Complete the following task concisely and accurately.
Keep your response focused and under 500 words unless more detail is needed."""

    result = ROUTER.execute_openrouter(task_text, routing.model, system_prompt)

    if not result.get('success'):
        log_execution(task_id, agent, f'openrouter-failed:{routing.model}')
        # Try Ollama fallback before Claude
        if ROUTER.check_ollama_health():
            fallback_routing = routing
            fallback_routing.model = "qwen2.5:7b"
            fallback_routing.provider = "ollama"
            return _execute_ollama(task_id, task_text, agent, fallback_routing)
        return _execute_via_claude(task_id, task_text, agent)

    return _write_fast_result(task_id, task_text, agent, routing, result, "openrouter")


def _write_fast_result(task_id, task_text, agent, routing, result, provider):
    """Write result from fast execution (Ollama or OpenRouter)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    outbox = BOTS_DIR / agent / 'outbox.md'
    if not outbox.parent.exists():
        outbox.parent.mkdir(parents=True, exist_ok=True)

    response_content = result.get('content', '')
    latency_ms = result.get('latency_ms', 0)
    model = routing.model

    # Short model name for display
    model_short = model.split('/')[-1].split(':')[0] if '/' in model else model.split(':')[0]

    outbox_message = f"""
---
**[{timestamp}]** From: {provider.upper()} ({model_short})
**Task ID:** `{task_id}`
**Latency:** {latency_ms}ms | **Complexity:** {routing.complexity:.2f}

{response_content}
"""

    try:
        existing = outbox.read_text() if outbox.exists() else ""
        outbox.write_text(existing + outbox_message)
    except Exception:
        pass

    update_worklog({
        'task_id': task_id,
        'content': f"Completed via {model_short} ({latency_ms}ms): {response_content[:200]}...",
        'type': 'completed',
        'status': 'done'
    })

    log_execution(task_id, agent, f'{provider}-completed:{model}')

    return {
        'success': True,
        'task_id': task_id,
        'agent': agent,
        'status': 'completed',
        'routed_to': provider,
        'model': model,
        'latency_ms': latency_ms,
        'complexity': routing.complexity,
        'reason': routing.reason,
        'message': f'Completed via {provider} model {model_short}'
    }


def _execute_via_claude(task_id, task_text, agent):
    """Execute task via Claude (tmux inbox method)."""
    inbox = BOTS_DIR / agent / 'inbox.md'

    if not inbox.parent.exists():
        inbox.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create execution prompt with progress logging instructions
    prompt = f"""
---
**[{timestamp}]** From: Dashboard Executor

## Task to Execute
**Task ID:** `{task_id}`
**Description:** {task_text}

## IMPORTANT: Log Your Progress in Real-Time!
As you work, call this API to log progress (the Obsidian file updates automatically):

```bash
# Log progress after each step:
curl -X POST http://localhost:8765/update-worklog -H 'Content-Type: application/json' -d '{{"task_id": "{task_id}", "content": "What you just did", "type": "progress", "files_modified": ["file1.js"], "percent_complete": 30}}'

# If blocked:
curl -X POST http://localhost:8765/update-worklog -H 'Content-Type: application/json' -d '{{"task_id": "{task_id}", "content": "Blocked: reason", "type": "blocker", "next_steps": "What needs to happen"}}'

# When complete:
curl -X POST http://localhost:8765/update-worklog -H 'Content-Type: application/json' -d '{{"task_id": "{task_id}", "content": "Completed: summary", "type": "completed", "percent_complete": 100, "status": "done"}}'
```

## Workflow
1. Log "Starting: [what you're about to do]" first
2. Execute each step, logging progress after each
3. If files are modified, include them in files_modified
4. If you stop before completing, log a checkpoint with next_steps
5. When done, log completion and write summary to outbox

Begin execution now.
"""

    try:
        existing = inbox.read_text() if inbox.exists() else ""
        inbox.write_text(existing + prompt)

        # Log execution
        log_execution(task_id, agent, 'started-claude')

        return {
            'success': True,
            'task_id': task_id,
            'agent': agent,
            'status': 'executing',
            'routed_to': 'claude',
            'model': 'claude',
            'message': f'Task sent to {agent} inbox'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def run_job(job_name):
    """Run a cron job immediately."""
    jobs = load_jobs()

    for job in jobs.get('jobs', []):
        if job['name'] == job_name:
            bot = job.get('bot', 'assistant')
            prompt = job.get('prompt', '')

            # Check if it's a script job
            if job.get('type') == 'script':
                try:
                    result = subprocess.run(
                        job['command'],
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=job.get('timeout', 300)
                    )
                    return {
                        'success': result.returncode == 0,
                        'output': result.stdout[:500],
                        'error': result.stderr[:200] if result.returncode != 0 else None
                    }
                except Exception as e:
                    return {'success': False, 'error': str(e)}

            # Regular Claude job
            inbox = BOTS_DIR / bot / 'inbox.md'
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            message = f"""
---
**[{timestamp}]** From: Dashboard (Manual: {job_name})

{prompt}
"""

            try:
                existing = inbox.read_text() if inbox.exists() else ""
                inbox.write_text(existing + message)
                return {'success': True, 'job': job_name, 'bot': bot}
            except Exception as e:
                return {'success': False, 'error': str(e)}

    return {'success': False, 'error': f'Job not found: {job_name}'}


def update_task(task_id, status, notes=''):
    """Update task status in local storage."""
    tasks_data = load_tasks()
    tasks = tasks_data.get('tasks', [])

    for task in tasks:
        if task.get('id') == task_id:
            task['status'] = status
            task['notes'] = notes
            task['updated'] = datetime.now().isoformat()
            break

    save_tasks(tasks)
    return {'success': True, 'task_id': task_id, 'status': status}


def log_execution(task_id, agent, status):
    """Log task execution."""
    log_file = Path(__file__).parent / 'execution.log'
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a') as f:
        f.write(f"[{timestamp}] {task_id} -> {agent}: {status}\n")


def save_to_vault(filename, content):
    """Save a file to the Obsidian vault."""
    if not filename or not content:
        return {'success': False, 'error': 'Missing filename or content'}

    # Security: prevent path traversal
    if '..' in filename or filename.startswith('/'):
        return {'success': False, 'error': 'Invalid filename'}

    # Vault is parent of bridge directory
    vault_dir = BRIDGE_DIR.parent
    file_path = vault_dir / filename

    try:
        # Create directory if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        file_path.write_text(content)

        return {
            'success': True,
            'path': str(file_path),
            'message': f'Saved to {filename}'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_daily_brief():
    """Get daily brief data for dashboard startup."""
    brief = {
        'timestamp': datetime.now().isoformat(),
        'bots': {},
        'cron_status': [],
        'backlog': []
    }

    # Get latest outbox from each bot
    bots = ['assistant', 'bitcoinml', 'energyscout', 'realestate', 'analytics']
    for bot in bots:
        content = read_outbox(bot)
        brief['bots'][bot] = {
            'outbox': content,
            'tmux': check_tmux(bot)
        }

    # Get recent cron activity
    cron_log = BRIDGE_DIR / 'cron.log'
    if cron_log.exists():
        lines = cron_log.read_text().split('\n')
        today = datetime.now().strftime('%Y-%m-%d')
        today_lines = [l for l in lines if today in l][-20:]  # Last 20 entries from today
        brief['cron_status'] = today_lines

    # Get backlog summary
    backlog_file = BRIDGE_DIR.parent / 'agents/memory/ceo/briefs/backlog.md'
    if backlog_file.exists():
        content = backlog_file.read_text()
        # Extract TODO items
        todos = [l.strip() for l in content.split('\n') if l.strip().startswith('- [ ]')]
        brief['backlog'] = todos[:10]  # Top 10 TODOs

    return brief


def list_worktrees():
    """List all git worktrees in the vault repo."""
    vault_dir = BRIDGE_DIR.parent
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=vault_dir
        )
        if result.returncode != 0:
            return []

        worktrees = []
        current_wt = {}
        for line in result.stdout.strip().split('\n'):
            if line.startswith('worktree '):
                if current_wt:
                    worktrees.append(current_wt)
                path = line.replace('worktree ', '')
                current_wt = {
                    'path': path,
                    'name': Path(path).name,
                    'active': False
                }
            elif line.startswith('branch '):
                current_wt['branch'] = line.replace('branch refs/heads/', '')
            elif line == 'bare':
                current_wt['bare'] = True

        if current_wt:
            worktrees.append(current_wt)

        # Check which is the current directory
        cwd_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=vault_dir
        )
        current_path = cwd_result.stdout.strip()
        for wt in worktrees:
            if wt['path'] == current_path:
                wt['active'] = True

        return worktrees
    except Exception as e:
        return []


def create_worktree(name, task_description=''):
    """Create a new git worktree for a task."""
    if not name:
        return {'success': False, 'error': 'Missing worktree name'}

    vault_dir = BRIDGE_DIR.parent
    worktree_path = vault_dir.parent / 'worktrees' / name

    try:
        # Create branch and worktree
        result = subprocess.run(
            ["git", "worktree", "add", "-b", name, str(worktree_path)],
            capture_output=True,
            text=True,
            cwd=vault_dir
        )

        if result.returncode != 0:
            return {'success': False, 'error': result.stderr}

        # Create a task file in the worktree
        if task_description:
            task_file = worktree_path / 'TASK.md'
            task_file.write_text(f"# {task_description}\n\nCreated: {datetime.now().isoformat()}\n")

        return {
            'success': True,
            'path': str(worktree_path),
            'branch': name
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def launch_agent_in_worktree(worktree, task_text, agent):
    """Launch a Claude agent in a specific worktree."""
    vault_dir = BRIDGE_DIR.parent
    worktree_path = vault_dir.parent / 'worktrees' / worktree

    if not worktree_path.exists():
        # Maybe it's a direct path
        if not Path(worktree).exists():
            return {'success': False, 'error': f'Worktree not found: {worktree}'}
        worktree_path = Path(worktree)

    try:
        # Create a tmux session for the agent
        session_name = f"agent-{worktree.replace('/', '-')}"

        # Check if session exists
        check = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True
        )

        if check.returncode == 0:
            return {'success': True, 'message': f'Agent already running in session {session_name}'}

        # Create new tmux session with claude
        cmd = f'cd {worktree_path} && claude "{task_text}"'
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "bash", "-c", cmd],
            capture_output=True
        )

        return {
            'success': True,
            'session': session_name,
            'path': str(worktree_path)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_tmux_output(bot_name, lines=50):
    """Get real-time output from a bot's tmux session."""
    session_name = f"claude-{bot_name}"
    try:
        # Capture pane content
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", f"-{lines}"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout
        return f"Session {session_name} not found or not accessible"
    except Exception as e:
        return f"Error: {str(e)}"


def get_job_status():
    """Parse cron.log to get today's job completion status."""
    cron_log = BRIDGE_DIR / 'cron.log'
    today = datetime.now().strftime('%Y-%m-%d')
    status = {}

    if cron_log.exists():
        try:
            lines = cron_log.read_text().split('\n')
            for line in lines:
                if today not in line:
                    continue
                # Parse lines like: [2026-03-30 07:00:28] Starting job: morning-briefing
                # or: [2026-03-30 07:00:28] Completed job: morning-briefing
                if 'Completed job:' in line:
                    job_name = line.split('Completed job:')[1].strip()
                    status[job_name] = {'completed': True, 'time': line.split(']')[0].strip('[')}
                elif 'Error' in line or 'Failed' in line or 'failed' in line:
                    # Try to extract job name
                    for part in line.split():
                        if '-' in part and part not in ['2026-03-30']:
                            status[part] = {'failed': True, 'time': line.split(']')[0].strip('[')}
                            break
        except Exception as e:
            pass

    return {'jobs': status, 'date': today, 'timestamp': datetime.now().isoformat()}


def get_agent_activity():
    """Get detailed activity status for all agents."""
    bots = ['assistant', 'bitcoinml', 'energyscout', 'realestate', 'analytics']
    activity = {}

    for bot in bots:
        agent_info = {
            'name': bot,
            'tmux_running': check_tmux(bot),
            'current_output': '',
            'last_outbox': read_outbox(bot),
            'status': 'idle'
        }

        # Get recent tmux output to determine what they're doing
        if agent_info['tmux_running']:
            output = get_tmux_output(bot, 20)
            agent_info['current_output'] = output

            # Determine status from output
            lower_output = output.lower()
            if 'thinking' in lower_output or 'processing' in lower_output or '...' in output:
                agent_info['status'] = 'thinking'
            elif 'error' in lower_output or 'failed' in lower_output:
                agent_info['status'] = 'error'
            elif 'done' in lower_output or 'completed' in lower_output:
                agent_info['status'] = 'completed'
            elif output.strip():
                agent_info['status'] = 'working'

        activity[bot] = agent_info

    return {'agents': activity, 'timestamp': datetime.now().isoformat()}


def send_to_tmux(bot_name, keys):
    """Send keys/commands to a bot's tmux session."""
    session_name = f"claude-{bot_name}"
    try:
        # Check if session exists
        check = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True
        )
        if check.returncode != 0:
            return {'success': False, 'error': f'Session {session_name} not found'}

        # Send the keys
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, keys],
            capture_output=True
        )
        return {'success': True, 'session': session_name, 'sent': keys}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def cross_agent_check(checker, target, task_id=None):
    """Have one agent check on another's progress without interrupting."""
    if not target:
        return {'success': False, 'error': 'Target agent required'}

    # Get target agent's current status
    target_running = check_tmux(target)
    target_output = get_tmux_output(target, 30) if target_running else "Not running"
    target_outbox = read_outbox(target)

    # Build a summary for the checker agent
    summary = f"""Status check on {target.upper()}:
- Session: {'Running' if target_running else 'Not running'}
- Recent activity: {target_output[-200:] if len(target_output) > 200 else target_output}
- Last outbox: {target_outbox[-200:] if len(target_outbox) > 200 else target_outbox}
"""

    # If checker is different from target, write summary to checker's chat
    if checker != target:
        inbox = BOTS_DIR / checker / 'inbox.md'
        if inbox.parent.exists():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"""
---
**[{timestamp}]** Status Check Request (Task: {task_id or 'N/A'})

Please review the status of {target.upper()} and provide a brief summary:

{summary}

Summarize: Is the task progressing? Any issues? ETA if possible.
"""
            try:
                existing = inbox.read_text() if inbox.exists() else ""
                inbox.write_text(existing + message)
            except:
                pass

    return {
        'success': True,
        'target': target,
        'checker': checker,
        'target_running': target_running,
        'summary': summary,
        'timestamp': datetime.now().isoformat()
    }


def save_cron_job(job):
    """Save or update a cron job in jobs.json."""
    if not job or not job.get('name'):
        return {'success': False, 'error': 'Job name required'}

    jobs_data = load_jobs()
    jobs = jobs_data.get('jobs', [])

    # Check if job already exists
    existing_idx = next((i for i, j in enumerate(jobs) if j['name'] == job['name']), None)

    if existing_idx is not None:
        # Update existing job
        jobs[existing_idx] = job
    else:
        # Add new job
        jobs.append(job)

    # Save back to file
    jobs_data['jobs'] = jobs
    try:
        with open(JOBS_FILE, 'w') as f:
            json.dump(jobs_data, f, indent=2)
        return {'success': True, 'job': job['name'], 'action': 'updated' if existing_idx else 'created'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def delete_cron_job(name):
    """Delete a cron job by name."""
    if not name:
        return {'success': False, 'error': 'Job name required'}

    jobs_data = load_jobs()
    jobs = jobs_data.get('jobs', [])

    original_len = len(jobs)
    jobs = [j for j in jobs if j['name'] != name]

    if len(jobs) == original_len:
        return {'success': False, 'error': f'Job not found: {name}'}

    jobs_data['jobs'] = jobs
    try:
        with open(JOBS_FILE, 'w') as f:
            json.dump(jobs_data, f, indent=2)
        return {'success': True, 'deleted': name}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def start_claude_session(bot_name, repo_path=''):
    """Start a Claude session with dangerous permissions for a bot."""
    session_name = f"claude-{bot_name}"

    # Default repo paths for each bot
    default_repos = {
        'assistant': str(BRIDGE_DIR.parent),  # openclaw vault
        'bitcoinml': str(Path.home() / 'bitcoinml'),
        'energyscout': str(Path.home() / 'energyscout'),
        'realestate': str(Path.home() / 'realestate'),
        'analytics': str(BRIDGE_DIR.parent),
    }

    # Use provided repo or default
    work_dir = repo_path if repo_path else default_repos.get(bot_name, str(BRIDGE_DIR.parent))

    try:
        # Check if session already exists
        check = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True
        )

        if check.returncode == 0:
            return {
                'success': True,
                'message': f'Session {session_name} already running',
                'session': session_name,
                'already_running': True
            }

        # Create new tmux session with claude --dangerously-skip-permissions
        cmd = f'cd "{work_dir}" && claude --dangerously-skip-permissions'
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "bash", "-c", cmd],
            capture_output=True
        )

        return {
            'success': True,
            'session': session_name,
            'repo': work_dir,
            'message': f'Started Claude for {bot_name} in {work_dir}'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def launch_npx_kanban():
    """Launch npx kanban in a tmux session."""
    vault_dir = BRIDGE_DIR.parent
    session_name = "npx-kanban"

    try:
        # Check if session exists
        check = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True
        )

        if check.returncode == 0:
            return {'success': True, 'message': 'npx kanban already running', 'port': 3000}

        # Create new tmux session with npx kanban
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "bash", "-c", f"cd {vault_dir} && npx kanban"],
            capture_output=True
        )

        return {
            'success': True,
            'session': session_name,
            'port': 3000
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def monitor_outboxes():
    """Background thread to monitor outboxes for task completion."""
    while True:
        try:
            tasks_data = load_tasks()
            tasks = tasks_data.get('tasks', [])

            for task in tasks:
                if task.get('status') == 'executing':
                    agent = task.get('agent', 'assistant')
                    outbox_content = read_outbox(agent)

                    # Check if task was completed or blocked
                    if 'DONE' in outbox_content or 'completed' in outbox_content.lower():
                        task['status'] = 'done'
                        task['notes'] = 'Auto-completed based on outbox'
                        task['updated'] = datetime.now().isoformat()
                    elif 'BLOCKED' in outbox_content or 'need' in outbox_content.lower():
                        task['status'] = 'blocked'
                        task['notes'] = 'Needs human input - check outbox'
                        task['updated'] = datetime.now().isoformat()

            save_tasks(tasks)
        except Exception as e:
            print(f"Monitor error: {e}")

        time.sleep(30)  # Check every 30 seconds


def get_routing_stats():
    """Get task routing statistics."""
    if not ROUTER_AVAILABLE or not ROUTER:
        return {
            'available': False,
            'reason': 'Router not available',
            'total_tasks': 0,
            'local_tasks': 0,
            'openrouter_tasks': 0,
            'cloud_tasks': 0
        }

    stats = ROUTER.get_routing_stats()
    stats['available'] = True
    stats['providers'] = ROUTER.get_available_providers()
    stats['models'] = ROUTER.list_models()[:15]
    stats['timestamp'] = datetime.now().isoformat()

    return stats


def check_routing(task_text):
    """Check routing decision for a task without executing."""
    if not task_text:
        return {'error': 'No task text provided'}

    if not ROUTER_AVAILABLE or not ROUTER:
        return {
            'available': False,
            'would_route_to': 'claude',
            'provider': 'claude',
            'reason': 'Router not available'
        }

    routing = ROUTER.should_use_local(task_text)

    return {
        'available': True,
        'would_route_to': routing.provider,
        'provider': routing.provider,
        'model': routing.model,
        'reason': routing.reason,
        'task_type': routing.task_type,
        'complexity': routing.complexity
    }


# Cline column -> OpenClaw status mapping
CLINE_COLUMN_TO_STATUS = {
    'backlog': 'todo',
    'in_progress': 'progress',
    'review': 'blocked',
    'trash': 'done',
}

# Agent name mapping (display name -> code)
AGENT_DISPLAY_TO_CODE = {
    'bitcoin ml': 'bml',
    'bitcoinml': 'bml',
    'energyscout': 'ene',
    'real estate': 'rea',
    'realestate': 'rea',
    'analytics': 'ana',
    'assistant': 'ass',
}


def sync_from_cline(data):
    """Sync a task/card from Cline kanban.

    Expected data:
    - card_id: Cline card ID
    - column: Cline column (backlog, in_progress, review, trash)
    - prompt: Task prompt/description
    - action: 'create', 'update', 'move', 'delete'
    """
    card_id = data.get('card_id')
    column = data.get('column', 'backlog')
    prompt = data.get('prompt', '')
    action = data.get('action', 'update')

    if not card_id:
        return {'success': False, 'error': 'card_id is required'}

    tasks_data = load_tasks()
    tasks_list = tasks_data.get('tasks', [])

    # Find existing task
    existing_task = next((t for t in tasks_list if t['id'] == card_id), None)

    if action == 'delete':
        if existing_task:
            tasks_list = [t for t in tasks_list if t['id'] != card_id]
            save_tasks(tasks_list)
            return {'success': True, 'action': 'deleted', 'task_id': card_id}
        return {'success': False, 'error': 'Task not found'}

    # Parse agent from prompt if present [AgentName] prefix
    agent = 'ass'
    text = prompt
    if prompt.startswith('['):
        end = prompt.find(']')
        if end > 0:
            agent_str = prompt[1:end].lower()
            agent = AGENT_DISPLAY_TO_CODE.get(agent_str, 'ass')
            text = prompt[end+1:].strip()

    # Map column to status
    status = CLINE_COLUMN_TO_STATUS.get(column, 'todo')

    if existing_task:
        # Update existing task
        old_status = existing_task.get('status', 'todo')
        existing_task['status'] = status
        existing_task['text'] = text if text else existing_task.get('text', '')
        existing_task['updated'] = datetime.now().isoformat()

        # Add work log if status changed
        if old_status != status:
            if 'workLog' not in existing_task:
                existing_task['workLog'] = []
            existing_task['workLog'].append({
                'timestamp': datetime.now().strftime('%m/%d/%Y, %I:%M:%S %p'),
                'content': f'Status changed to {status} via Cline sync',
                'type': 'move'
            })

        save_tasks(tasks_list)
        return {'success': True, 'action': 'updated', 'task_id': card_id, 'status': status}

    else:
        # Create new task
        new_task = {
            'id': card_id,
            'text': text or 'Untitled task from Cline',
            'agent': agent,
            'quadrant': 'q2',
            'status': status,
            'scheduled': False,
            'created': datetime.now().isoformat(),
            'source': 'cline',
        }
        tasks_list.append(new_task)
        save_tasks(tasks_list)
        return {'success': True, 'action': 'created', 'task_id': card_id, 'status': status}


def link_file_to_task(data):
    """Link a file or folder to a task.

    Expected data:
    - task_id: Task ID
    - path: File or folder path
    - type: 'file' or 'folder' (auto-detected if not provided)
    """
    task_id = data.get('task_id')
    file_path = data.get('path')

    if not task_id or not file_path:
        return {'success': False, 'error': 'task_id and path are required'}

    tasks_data = load_tasks()
    tasks_list = tasks_data.get('tasks', [])

    task = next((t for t in tasks_list if t['id'] == task_id), None)
    if not task:
        return {'success': False, 'error': f'Task {task_id} not found'}

    # Normalize and validate path
    path_obj = Path(file_path).expanduser().resolve()
    if not path_obj.exists():
        return {'success': False, 'error': f'Path does not exist: {file_path}'}

    file_type = data.get('type', 'folder' if path_obj.is_dir() else 'file')

    # Initialize linkedFiles if not present
    if 'linkedFiles' not in task:
        task['linkedFiles'] = []

    # Check if already linked
    if any(lf.get('path') == str(path_obj) for lf in task['linkedFiles']):
        return {'success': True, 'message': 'File already linked', 'task_id': task_id}

    # Add link
    task['linkedFiles'].append({
        'path': str(path_obj),
        'type': file_type,
        'linkedAt': datetime.now().isoformat()
    })

    save_tasks(tasks_list)
    save_task_to_obsidian(task)

    return {
        'success': True,
        'task_id': task_id,
        'linked': str(path_obj),
        'type': file_type
    }


def main():
    port = 8765
    # Bind to 0.0.0.0 to allow network access
    server = HTTPServer(('0.0.0.0', port), ExecutorHandler)

    # Start outbox monitor in background
    monitor_thread = threading.Thread(target=monitor_outboxes, daemon=True)
    monitor_thread.start()

    print(f"=" * 50)
    print(f"Task Executor Server")
    print(f"=" * 50)
    print(f"Running on http://localhost:{port}")

    # Show routing status
    if ROUTER_AVAILABLE:
        models = ROUTER.list_models()[:5] if ROUTER else []
        print(f"Routing: ENABLED (Ollama OK)")
        print(f"  Models: {', '.join(models) if models else 'checking...'}")
    else:
        print(f"Routing: DISABLED (Ollama unavailable)")
        print(f"  All tasks will route to Claude")

    print(f"\nEndpoints:")
    print(f"  GET  /jobs         - List cron jobs")
    print(f"  GET  /tasks        - Get task state")
    print(f"  GET  /status       - Check bot status")
    print(f"  GET  /outbox?bot=X - Read outbox")
    print(f"  GET  /routing-stats - Get routing statistics")
    print(f"  GET  /routing-check?task=X - Preview routing decision")
    print(f"  POST /execute      - Execute task (auto-routes)")
    print(f"  POST /run-job      - Run cron job")
    print(f"  POST /update-task  - Update status")
    print(f"  POST /save-tasks   - Save all tasks")
    print(f"=" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()

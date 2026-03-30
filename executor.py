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
            bots = ['assistant', 'bitcoinml', 'energyscout', 'realestate']
            status = {}
            for bot in bots:
                status[bot] = {
                    'tmux': check_tmux(bot),
                    'inbox': (BOTS_DIR / bot / 'inbox.md').exists(),
                    'outbox': read_outbox(bot)
                }
            self._send_json({'bots': status, 'timestamp': datetime.now().isoformat()})

        elif path == '/outbox':
            # Get recent outbox messages
            params = parse_qs(parsed.query)
            bot = params.get('bot', ['assistant'])[0]
            content = read_outbox(bot)
            self._send_json({'bot': bot, 'content': content})

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

            result = execute_task(task_id, task_text, agent)
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


def check_tmux(bot_name):
    """Check if bot's tmux session is running."""
    session_name = f"claude-{bot_name}"
    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True
    )
    return result.returncode == 0


def read_outbox(bot_name):
    """Read bot's outbox."""
    outbox = BOTS_DIR / bot_name / 'outbox.md'
    if outbox.exists():
        content = outbox.read_text()
        # Get last 500 chars
        return content[-500:] if len(content) > 500 else content
    return ''


def execute_task(task_id, task_text, agent):
    """Execute a task by writing to bot's inbox."""
    inbox = BOTS_DIR / agent / 'inbox.md'

    if not inbox.parent.exists():
        inbox.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create execution prompt
    prompt = f"""
---
**[{timestamp}]** From: Dashboard Executor (Task: {task_id})

## Task to Execute
{task_text}

## Instructions
1. Execute this task autonomously
2. When complete, write results to outbox
3. If blocked or need human input, clearly state what's needed
4. Mark as DONE if successful, BLOCKED if you need help

Begin execution now.
"""

    try:
        existing = inbox.read_text() if inbox.exists() else ""
        inbox.write_text(existing + prompt)

        # Log execution
        log_execution(task_id, agent, 'started')

        return {
            'success': True,
            'task_id': task_id,
            'agent': agent,
            'status': 'executing',
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


def main():
    port = 8765
    server = HTTPServer(('localhost', port), ExecutorHandler)

    # Start outbox monitor in background
    monitor_thread = threading.Thread(target=monitor_outboxes, daemon=True)
    monitor_thread.start()

    print(f"=" * 50)
    print(f"Task Executor Server")
    print(f"=" * 50)
    print(f"Running on http://localhost:{port}")
    print(f"Endpoints:")
    print(f"  GET  /jobs       - List cron jobs")
    print(f"  GET  /tasks      - Get task state")
    print(f"  GET  /status     - Check bot status")
    print(f"  GET  /outbox?bot=X - Read outbox")
    print(f"  POST /execute    - Execute a task")
    print(f"  POST /run-job    - Run cron job")
    print(f"  POST /update-task - Update status")
    print(f"  POST /save-tasks - Save all tasks")
    print(f"=" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()

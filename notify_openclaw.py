#!/usr/bin/env python3
"""
Notify OpenClaw of Cline events.

Can be called from Cline hooks to push immediate updates to OpenClaw.

Usage:
    python notify_openclaw.py --event task_moved --task-id abc123 --column in_progress
    python notify_openclaw.py --event task_created --task-id xyz789 --prompt "New task"
"""

import argparse
import json
import urllib.request
import urllib.error
import sys

OPENCLAW_API = "http://localhost:8765"


def notify_openclaw(event: str, task_id: str, column: str = None, prompt: str = None):
    """Send notification to OpenClaw API."""
    try:
        data = {
            'card_id': task_id,
            'column': column or 'backlog',
            'prompt': prompt or '',
            'action': 'update' if event == 'task_moved' else 'create',
        }

        req = urllib.request.Request(
            f"{OPENCLAW_API}/sync-from-cline",
            data=json.dumps(data).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode())
            print(f"OpenClaw notified: {result}")
            return True

    except urllib.error.URLError as e:
        print(f"OpenClaw not reachable: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Notification failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description='Notify OpenClaw of Cline events')
    parser.add_argument('--event', required=True, help='Event type: task_moved, task_created, task_deleted')
    parser.add_argument('--task-id', required=True, help='Task/card ID')
    parser.add_argument('--column', help='Target column')
    parser.add_argument('--prompt', help='Task prompt text')
    args = parser.parse_args()

    success = notify_openclaw(args.event, args.task_id, args.column, args.prompt)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

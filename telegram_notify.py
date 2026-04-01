#!/usr/bin/env python3
"""
Telegram Notifications for Kanban Task Completion.

Sends notifications to Telegram when tasks are completed locally
by Hermes/Ollama, so the user knows without checking the dashboard.

Usage:
    from telegram_notify import notify_task_complete
    notify_task_complete(task_id, prompt, result, provider, latency_ms)
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional


# Telegram outbox - messages here get sent to Telegram
OUTBOX_PATH = Path.home() / "Vaults/openclaw/bridge/outbox.md"

# Results directory for linking
RESULTS_DIR = Path(__file__).parent / "results"


def notify_task_complete(
    task_id: str,
    prompt: str,
    result: str,
    provider: str,
    model: str,
    latency_ms: int,
    success: bool = True
):
    """
    Send a Telegram notification when a task completes locally.

    Args:
        task_id: The task ID
        prompt: Original task prompt
        result: The execution result
        provider: hermes/ollama/openrouter
        model: Model used
        latency_ms: Execution time in milliseconds
        success: Whether execution succeeded
    """
    # Format latency nicely
    if latency_ms >= 60000:
        latency_str = f"{latency_ms / 60000:.1f}min"
    elif latency_ms >= 1000:
        latency_str = f"{latency_ms / 1000:.1f}s"
    else:
        latency_str = f"{latency_ms}ms"

    # Provider emoji
    provider_emoji = {
        "hermes": "🔧",
        "ollama": "🏠",
        "openrouter": "☁️"
    }.get(provider, "✓")

    # Truncate result for preview (keep it readable)
    result_preview = result[:500] if result else "(no output)"
    if len(result) > 500:
        result_preview += "..."

    # Format the notification
    if success:
        message = f"""
{provider_emoji} **Task Completed Locally**

**Task:** {prompt[:100]}{'...' if len(prompt) > 100 else ''}

**Model:** {model} ({latency_str})

**Result:**
{result_preview}

---
*Processed by Hermes/OpenClaw auto-routing*
"""
    else:
        message = f"""
❌ **Local Task Failed**

**Task:** {prompt[:100]}{'...' if len(prompt) > 100 else ''}

**Model:** {model}
**Error:** {result_preview}

*Task will be escalated to Claude*
"""

    # Write to outbox
    _write_to_outbox(message.strip())

    return True


def notify_daily_digest(
    completed_count: int,
    pending_count: int,
    hermes_count: int,
    ollama_count: int,
    openrouter_count: int,
    claude_count: int,
    top_completions: list = None
):
    """
    Send a daily digest of task routing stats.

    Args:
        completed_count: Tasks completed locally today
        pending_count: Tasks still pending
        hermes_count: Tasks handled by Hermes
        ollama_count: Tasks handled by Ollama
        openrouter_count: Tasks handled by OpenRouter
        claude_count: Tasks passed to Claude
        top_completions: List of recently completed task summaries
    """
    local_total = hermes_count + ollama_count + openrouter_count
    total = local_total + claude_count
    local_pct = (local_total / total * 100) if total > 0 else 0

    message = f"""
📊 **Daily Task Routing Summary**

**Completed locally:** {completed_count} tasks
**Pending:** {pending_count} tasks

**Routing breakdown:**
🔧 Hermes: {hermes_count}
🏠 Ollama: {ollama_count}
☁️ OpenRouter: {openrouter_count}
🤖 Claude: {claude_count}

**Local processing:** {local_pct:.0f}% of tasks
"""

    if top_completions:
        message += "\n**Recent completions:**\n"
        for task in top_completions[:3]:
            message += f"• {task}\n"

    message += "\n---\n*Hermes/OpenClaw Auto-Routing Active*"

    _write_to_outbox(message.strip())

    return True


def notify_error(error_message: str, context: str = ""):
    """Send an error notification."""
    message = f"""
⚠️ **OpenClaw Error**

{error_message}

{f'Context: {context}' if context else ''}

---
*Check logs: /tmp/prefilter-exec.log*
"""
    _write_to_outbox(message.strip())


def _write_to_outbox(message: str):
    """Write a message to the Telegram outbox."""
    try:
        # Ensure outbox exists
        OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Write message (overwrites - telegram_monitor reads and clears)
        with open(OUTBOX_PATH, 'w') as f:
            f.write(message)

        print(f"[Telegram] Notification sent ({len(message)} chars)")

    except Exception as e:
        print(f"[Telegram] Failed to send notification: {e}")


if __name__ == "__main__":
    # Test notification
    print("Sending test notification...")
    notify_task_complete(
        task_id="test-123",
        prompt="Test task: What is 2+2?",
        result="2 + 2 equals 4.",
        provider="ollama",
        model="qwen2.5:7b",
        latency_ms=1500,
        success=True
    )
    print(f"Check {OUTBOX_PATH}")
